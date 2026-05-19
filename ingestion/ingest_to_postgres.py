"""
ingest_to_postgres.py
---------------------
Bronze → Silver ingestion.

Reads Parquet files from MinIO (raw/jeepney/{entity}/date=YYYY-MM-DD/{entity}.parquet),
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
    "host":     os.getenv("DB_HOST",  "localhost"),
    "port":     int(os.getenv("DB_PORT", 5432)),
    "dbname":   os.getenv("DB_NAME",  "jeepney_dw"),
    "user":     os.getenv("DB_USER",  "admin"),
    "password": os.getenv("DB_PASS",  "password123"),
}

MINIO_CONFIG = {
    "endpoint_url":          f"http://{os.getenv('MINIO_ENDPOINT', 'localhost:9000')}",
    "aws_access_key_id":     os.getenv("MINIO_ACCESS_KEY", "admin"),
    "aws_secret_access_key": os.getenv("MINIO_SECRET_KEY", "password123"),
}
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "raw")
MINIO_PREFIX = "jeepney"

TODAY = date.today().isoformat()

# ---------------------------------------------------------------------------
# Entity → staging table mapping
# MinIO path:  raw/jeepney/{entity}/date={date}/{entity}.parquet
# ---------------------------------------------------------------------------
ENTITY_TABLE_MAP = {
    "routes":       "staging.stg_routes",
    "stops":        "staging.stg_stops",
    "operators":    "staging.stg_operators",
    "vehicles":     "staging.stg_vehicles",
    "trips":        "staging.stg_trips",
    "passengers":   "staging.stg_passenger_survey",
    "ab_experiment": "staging.stg_ab_experiment",
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

    # Null handling — strip whitespace from string cols
    str_cols = df.select_dtypes(include="object").columns
    for col in str_cols:
        df[col] = df[col].str.strip().replace("", None)

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

    rows = [tuple(row) for row in df.itertuples(index=False, name=None)]

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
    inserted = upsert_to_postgres(combined, table, pk, conn)
    log.info("  Upserted: %d rows into %s", inserted, table)

    return inserted


def main():
    log.info("=== Ingestion Pipeline START ===")
    log.info("Source: MinIO s3://%s/%s/", MINIO_BUCKET, MINIO_PREFIX)
    log.info("Target: PostgreSQL %s@%s/%s",
             DB_CONFIG["user"], DB_CONFIG["host"], DB_CONFIG["dbname"])

    s3 = get_s3_client()
    conn = get_pg_connection()

    totals = {}
    try:
        for entity, table in ENTITY_TABLE_MAP.items():
            n = ingest_entity(entity, table, s3, conn)
            totals[entity] = n
    finally:
        conn.close()

    log.info("=== Ingestion Summary ===")
    for entity, n in totals.items():
        log.info("  %-20s  %d rows", entity, n)
    log.info("=== Ingestion Pipeline COMPLETE ===")
    log.info("Next step: dbt run --select staging intermediate")


if __name__ == "__main__":
    main()
