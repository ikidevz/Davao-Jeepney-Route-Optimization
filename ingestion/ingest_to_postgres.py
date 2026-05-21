"""
ingest_to_postgres.py
---------------------
Bronze → Silver ingestion.

Reads Parquet files from MinIO (raw/jeepney/{entity}/date=YYYY-MM-DD/{entity}_*.parquet),
Supports multiple chunk files per partition (produced by chunked FastAPI POST ingestion).
loads them into PostgreSQL staging tables with type casting, null checks,
and row-count logging per entity.

Run order: AFTER producers POST to FastAPI, BEFORE dbt run.
"""

import io
import os
import logging
from datetime import date

import boto3
import pandas as pd
import psycopg2
import psycopg2.extras
import pyarrow as pa
import pyarrow.parquet as pq

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
log = logging.getLogger("ingest_to_postgres")

# ---------------------------------------------------------------------------
# Config from environment
# ---------------------------------------------------------------------------
DB_CONFIG = {
    "host":     os.getenv("POSTGRES_HOST", "postgres"),
    "port":     int(os.getenv("POSTGRES_PORT", 5432)),
    "dbname":   os.getenv("POSTGRES_DB",   "jeepney_dw"),
    "user":     os.getenv("SVC_PIPELINE_USER",     "svc_pipeline"),
    "password": os.getenv("SVC_PIPELINE_PASSWORD", "pipeline_pass_123"),
}

MINIO_CONFIG = {
    "endpoint_url":          f"http://{os.getenv('MINIO_ENDPOINT', 'minio:9000')}",
    "aws_access_key_id":     os.getenv("MINIO_ACCESS_KEY"),
    "aws_secret_access_key": os.getenv("MINIO_SECRET_KEY"),
}
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "raw")
MINIO_PREFIX = "jeepney"

TODAY = date.today().isoformat()

# ---------------------------------------------------------------------------
# Entity → staging table mapping
# MinIO path:  raw/jeepney/{entity}/date={date}/{entity}.parquet
# ---------------------------------------------------------------------------
ENTITY_TABLE_MAP = {
    "routes":        "staging.stg_routes",       # no FK deps
    "operators":     "staging.stg_operators",    # no FK deps
    "stops":         "staging.stg_stops",        # FK → routes
    "vehicles":      "staging.stg_vehicles",     # FK → routes, operators
    "trips":         "staging.stg_trips",        # FK → routes, vehicles
    "passengers":    "staging.stg_passenger_survey",  # FK → routes
    "ab_experiment": "staging.stg_ab_experiment",     # FK → passengers ← MUST be last
}

# ---------------------------------------------------------------------------
# Column casting rules per entity (applied after reading Parquet)
# ---------------------------------------------------------------------------
BOOL_COLS = {
    "routes":        ["is_active"],
    "stops":         ["has_shelter"],
    "vehicles":      ["is_active"],
    "operators":     ["is_compliant_puv"],
    "trips":         ["is_on_time", "is_rainy_day"],
    "passengers":    ["prefers_aircon"],
    "ab_experiment": ["would_use_again"],
}

DATE_COLS = {
    "trips":      ["trip_date"],
    "passengers": ["survey_date"],
    "ab_experiment": [],
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def get_s3_client():
    return boto3.client("s3", **MINIO_CONFIG)


def get_pg_connection():
    return psycopg2.connect(**DB_CONFIG)


def list_parquet_keys(s3, entity: str) -> list[str]:
    """List all Parquet objects under raw/jeepney/{entity}/"""
    prefix = f"{MINIO_PREFIX}/{entity}/"
    paginator = s3.get_paginator("list_objects_v2")
    keys = []
    for page in paginator.paginate(Bucket=MINIO_BUCKET, Prefix=prefix):
        for obj in page.get("Contents", []):
            if obj["Key"].endswith(".parquet"):
                keys.append(obj["Key"])
    return keys


def read_parquet_from_minio(s3, key: str) -> pd.DataFrame:
    """Download a Parquet object from MinIO and return as DataFrame."""
    response = s3.get_object(Bucket=MINIO_BUCKET, Key=key)
    buf = io.BytesIO(response["Body"].read())
    return pq.read_table(buf).to_pandas()


def cast_columns(df: pd.DataFrame, entity: str) -> pd.DataFrame:
    """Apply type casts specific to each entity."""
    df = df.copy()

    # Boolean columns
    for col in BOOL_COLS.get(entity, []):
        if col in df.columns:
            df[col] = df[col].astype(bool)

    # Date columns
    for col in DATE_COLS.get(entity, []):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col]).dt.date

    for col in df.columns:
        dtype = df[col].dtype
        is_string_col = (
            dtype == object
            or isinstance(dtype, pd.StringDtype)
            or (
                hasattr(pd, 'ArrowDtype')
                and isinstance(dtype, pd.ArrowDtype)
                and pa.types.is_string(dtype.pyarrow_dtype)
            )
        )
        if not is_string_col:
            continue
        try:
            df[col] = df[col].str.strip().replace("", None)
        except AttributeError:
            log.warning(
                "cast_columns: skipping strip on '%s' (dtype=%s) — "
                ".str accessor not available",
                col, dtype,
            )

    return df


def validate_dataframe(df: pd.DataFrame, entity: str) -> None:
    """Basic data quality checks — log warnings, don't raise."""
    if df.empty:
        log.warning("[%s] DataFrame is empty after reading Parquet!", entity)
        return

    null_pct = df.isnull().mean() * 100
    high_null = null_pct[null_pct > 20]
    if not high_null.empty:
        log.warning(
            "[%s] High null rate columns: %s",
            entity,
            high_null.to_dict(),
        )

    if entity == "passengers" and "satisfaction_score" in df.columns:
        out_of_range = df[~df["satisfaction_score"].between(1, 5)]
        if not out_of_range.empty:
            log.warning(
                "[%s] %d rows with satisfaction_score outside 1–5",
                entity, len(out_of_range),
            )

    if entity == "trips" and "load_factor" in df.columns:
        out_of_range = df[~df["load_factor"].between(0, 1.5)]
        if not out_of_range.empty:
            log.warning(
                "[%s] %d rows with load_factor outside 0–1.5",
                entity, len(out_of_range),
            )


def drop_fk_orphans(df: pd.DataFrame, fk_col: str, parent_table: str,
                    parent_pk: str, conn) -> pd.DataFrame:
    """
    Remove rows whose FK value is not present in the parent table.

    This guards against ForeignKeyViolation when the parent entity was
    ingested in a prior pipeline run (e.g. incremental re-runs where
    ab_experiment references a passenger_id that was never loaded).

    Returns the filtered DataFrame and logs how many rows were dropped.
    """
    if df.empty:
        return df

    fk_values = tuple(df[fk_col].dropna().unique().tolist())
    if not fk_values:
        return df

    with conn.cursor() as cur:
        cur.execute(
            f"SELECT {parent_pk} FROM {parent_table} "
            f"WHERE {parent_pk} = ANY(%s)",
            (list(fk_values),),
        )
        present = {row[0] for row in cur.fetchall()}

    orphans = df[~df[fk_col].isin(present)]
    if not orphans.empty:
        missing_ids = sorted(orphans[fk_col].unique().tolist())
        log.warning(
            "drop_fk_orphans: dropping %d rows — %d unique %s value(s) not "
            "found in %s.%s: %s%s",
            len(orphans),
            len(missing_ids),
            fk_col,
            parent_table,
            parent_pk,
            missing_ids[:10],
            " …" if len(missing_ids) > 10 else "",
        )
        df = df[df[fk_col].isin(present)].copy()

    return df


def upsert_to_postgres(df: pd.DataFrame, table: str, pk_col: str, conn) -> int:
    """
    UPSERT rows into a staging table using INSERT ... ON CONFLICT DO NOTHING.
    Returns number of rows inserted.
    """
    if df.empty:
        return 0

    cols = list(df.columns)
    col_str = ", ".join(f'"{c}"' for c in cols)
    val_str = ", ".join(["%s"] * len(cols))

    sql = (
        f'INSERT INTO {table} ({col_str}) VALUES ({val_str}) '
        f'ON CONFLICT ({pk_col}) DO NOTHING'
    )

    # Convert NaN/NaT to None so psycopg2 writes NULL, not a string "nan"
    # This is critical for nullable columns like cluster_id, cluster_label in passengers
    rows = [
        tuple(None if (v != v) else v for v in row)  # NaN != NaN is True
        for row in df.itertuples(index=False, name=None)
    ]

    with conn.cursor() as cur:
        psycopg2.extras.execute_batch(cur, sql, rows, page_size=1000)
    conn.commit()
    return len(rows)


# ---------------------------------------------------------------------------
# Per-entity primary key
# ---------------------------------------------------------------------------
ENTITY_PK = {
    "routes":        "route_id",
    "stops":         "stop_id",
    "operators":     "operator_id",
    "vehicles":      "vehicle_id",
    "trips":         "trip_id",
    "passengers":    "passenger_id",
    "ab_experiment": "experiment_record_id",
}


# ---------------------------------------------------------------------------
# Main ingestion loop
# ---------------------------------------------------------------------------
def ingest_entity(entity: str, table: str, s3, conn) -> int:
    log.info("--- Ingesting %s → %s ---", entity, table)

    keys = list_parquet_keys(s3, entity)
    if not keys:
        log.warning("No Parquet files found for entity '%s' in MinIO.", entity)
        return 0

    log.info("Found %d Parquet file(s) for '%s'", len(keys), entity)

    frames = []
    for key in keys:
        log.info("  Reading s3://%s/%s", MINIO_BUCKET, key)
        df = read_parquet_from_minio(s3, key)
        frames.append(df)

    combined = pd.concat(frames, ignore_index=True).drop_duplicates()
    log.info("  Combined: %d rows before cast", len(combined))

    combined = cast_columns(combined, entity)
    validate_dataframe(combined, entity)

    pk = ENTITY_PK[entity]

    # Guard: drop ab_experiment rows whose passenger_id has no matching row
    # in stg_passenger_survey to prevent FK violations on upsert.
    if entity == "ab_experiment":
        before = len(combined)
        combined = drop_fk_orphans(
            combined,
            fk_col="passenger_id",
            parent_table="staging.stg_passenger_survey",
            parent_pk="passenger_id",
            conn=conn,
        )
        dropped = before - len(combined)
        if dropped:
            log.warning(
                "  [%s] Dropped %d orphan row(s) missing from stg_passenger_survey",
                entity, dropped,
            )

    inserted = upsert_to_postgres(combined, table, pk, conn)
    log.info("  Upserted: %d rows into %s", inserted, table)

    return inserted


def main():
    log.info("=== Ingestion Pipeline START ===")
    log.info("Source: MinIO s3://%s/%s/", MINIO_BUCKET, MINIO_PREFIX)
    log.info("Target: PostgreSQL %s@%s/%s",
             DB_CONFIG["user"], DB_CONFIG["host"], DB_CONFIG["dbname"])

    s3 = get_s3_client()

    phase1 = {k: v for k, v in ENTITY_TABLE_MAP.items() if k !=
              "ab_experiment"}
    phase2 = {k: v for k, v in ENTITY_TABLE_MAP.items() if k ==
              "ab_experiment"}

    totals = {}
    try:
        conn = get_pg_connection()
        try:
            for entity, table in phase1.items():
                n = ingest_entity(entity, table, s3, conn)
                totals[entity] = n
        finally:
            conn.close()

        conn = get_pg_connection()
        try:
            for entity, table in phase2.items():
                n = ingest_entity(entity, table, s3, conn)
                totals[entity] = n
        finally:
            conn.close()
    except Exception:
        log.exception("Ingestion pipeline encountered a fatal error.")

    log.info("=== Ingestion Summary ===")
    for entity, n in totals.items():
        log.info("  %-20s  %d rows", entity, n)
    log.info("=== Ingestion Pipeline COMPLETE ===")
    log.info("Next step: dbt run --select staging intermediate")


if __name__ == "__main__":
    main()
