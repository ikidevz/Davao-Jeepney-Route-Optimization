"""
export_to_parquet.py
--------------------
Export final ML outputs from PostgreSQL mart tables to Parquet files
so that Streamlit and DuckDB can query them without hitting Postgres.

Exports:
  - passenger_features.parquet      (already written by feature_engineering.py)
  - cluster_assignments.parquet     (already written by clustering.py)
  - ab_test_statistics.parquet      (already written by ab_testing.py)
  - elbow_scores.parquet            (already written by clustering.py)
  - silhouette_scores.parquet       (already written by clustering.py)

This script additionally exports fresh copies from the mart tables for
Streamlit to consume as its primary data source.

Run order: AFTER ab_testing.py, BEFORE streamlit reload / DAG completion
"""

import json
import os
import logging
import pandas as pd
import psycopg2
import pyarrow as pa
import pyarrow.parquet as pq
from datetime import datetime, timezone

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
log = logging.getLogger("export_to_parquet")

DB_CONFIG = {
    "host":     os.getenv("DB_HOST", "localhost"),
    "port":     int(os.getenv("DB_PORT", 5432)),
    "dbname":   os.getenv("DB_NAME", "jeepney_dw"),
    "user":     os.getenv("DB_USER", "admin"),
    "password": os.getenv("DB_PASS", "password123"),
}

PARQUET_DIR = os.path.join(os.path.dirname(__file__), "parquet")
os.makedirs(PARQUET_DIR, exist_ok=True)


def get_connection():
    return psycopg2.connect(**DB_CONFIG)


def export_table(conn, query: str, filename: str, label: str) -> None:
    path = os.path.join(PARQUET_DIR, filename)
    log.info("Exporting %s → %s …", label, filename)
    df = pd.read_sql(query, conn)
    table = pa.Table.from_pandas(df, preserve_index=False)
    pq.write_table(table, path)
    log.info("  → %d rows  |  %.1f KB", len(df), os.path.getsize(path) / 1024)


EXPORTS: list[dict] = [
    {
        "filename": "mart_commuter_clusters.parquet",
        "label":    "mart_commuter_clusters",
        "query":    """
            SELECT
                passenger_id,
                origin_barangay,
                origin_district,
                destination_type,
                trip_purpose,
                trips_per_week,
                avg_fare_paid_php,
                transfers_required,
                wait_time_min,
                travel_time_min,
                satisfaction_score,
                income_bracket,
                prefers_aircon,
                cluster_id,
                cluster_label,
                is_ab_test_eligible,
                refreshed_at
            FROM marts.mart_commuter_clusters
            ORDER BY cluster_id, passenger_id
        """,
    },
    {
        "filename": "mart_ab_test_results.parquet",
        "label":    "mart_ab_test_results",
        "query":    """
            SELECT
                experiment_record_id,
                experiment_id,
                passenger_id,
                cluster_label,
                "group",
                route_variant,
                test_week,
                simulated_travel_time_min,
                simulated_fare_php,
                transfers_needed,
                satisfaction_score,
                would_use_again,
                p_value,
                is_significant,
                effect_size,
                confidence_interval_low,
                confidence_interval_high,
                refreshed_at
            FROM marts.mart_ab_test_results
            ORDER BY passenger_id, test_week
        """,
    },
    {
        "filename": "mart_route_summary_recent.parquet",
        "label":    "mart_route_summary (last 30 days)",
        "query":    """
            SELECT *
            FROM marts.mart_route_summary
            WHERE trip_date >= CURRENT_DATE - INTERVAL '30 days'
            ORDER BY trip_date DESC, route_id
        """,
    },
    {
        "filename": "mart_district_ridership_recent.parquet",
        "label":    "mart_district_ridership (last 30 days)",
        "query":    """
            SELECT *
            FROM marts.mart_district_ridership
            WHERE trip_date >= CURRENT_DATE - INTERVAL '30 days'
            ORDER BY trip_date DESC, district
        """,
    },
]


def verify_existing_parquets() -> None:
    """Log status of all expected Parquet files."""
    expected = [
        "passenger_features.parquet",
        "cluster_assignments.parquet",
        "ab_test_statistics.parquet",
        "elbow_scores.parquet",
        "silhouette_scores.parquet",
        "mart_commuter_clusters.parquet",
        "mart_ab_test_results.parquet",
        "mart_route_summary_recent.parquet",
        "mart_district_ridership_recent.parquet",
    ]
    log.info("--- Parquet file inventory ---")
    for fname in expected:
        path = os.path.join(PARQUET_DIR, fname)
        if os.path.exists(path):
            size_kb = os.path.getsize(path) / 1024
            df = pd.read_parquet(path)
            log.info("  ✓ %-45s  %6.1f KB  %d rows", fname, size_kb, len(df))
        else:
            log.warning("  ✗ %-45s  MISSING", fname)


def write_export_manifest() -> None:
    """Write a small JSON manifest so Streamlit knows when data was last refreshed."""
    manifest = {
        "exported_at": datetime.now(tz=timezone.utc).isoformat(),
        "files": sorted(f for f in os.listdir(PARQUET_DIR) if f.endswith(".parquet")),
    }
    manifest_path = os.path.join(PARQUET_DIR, "manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    log.info("Export manifest written → %s", manifest_path)


def main():
    log.info("=== Export to Parquet START ===")

    conn = get_connection()
    try:
        for exp in EXPORTS:
            export_table(conn, exp["query"], exp["filename"], exp["label"])
    finally:
        conn.close()

    verify_existing_parquets()
    write_export_manifest()

    log.info("=== Export to Parquet COMPLETE ===")
    log.info("All Parquet files written to: %s", PARQUET_DIR)
    log.info("Streamlit app will auto-load from science/parquet/ on next request.")


if __name__ == "__main__":
    main()
