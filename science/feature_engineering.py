"""
feature_engineering.py
-----------------------
Pull passenger features from the intermediate dbt model (int_passenger_features),
standardize the feature matrix, and persist it as a Parquet file for clustering.

Run order: AFTER dbt staging + intermediate models, BEFORE clustering.py
"""

import os
import logging
import numpy as np
import pandas as pd
import psycopg2
import joblib
from sklearn.preprocessing import StandardScaler
import pyarrow as pa
import pyarrow.parquet as pq

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
log = logging.getLogger("feature_engineering")

SCALER_PATH = os.path.join(os.path.dirname(
    __file__), "models", "scaler.joblib")

# ---------------------------------------------------------------------------
# DB connection
# ---------------------------------------------------------------------------
DB_CONFIG = {
    "host":     os.getenv("DB_HOST", "localhost"),
    "port":     int(os.getenv("DB_PORT", 5432)),
    "dbname":   os.getenv("DB_NAME", "jeepney_dw"),
    "user":     os.getenv("DB_USER", "admin"),
    "password": os.getenv("DB_PASS", "password123"),
}

PARQUET_DIR = os.path.join(os.path.dirname(__file__), "parquet")
os.makedirs(PARQUET_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# Feature columns used for clustering
# ---------------------------------------------------------------------------
FEATURE_COLS = [
    "trips_per_week",
    "avg_fare_paid_php",
    "transfers_required",
    "wait_time_min",
    "travel_time_min",
    "satisfaction_score",
    "income_bracket_encoded",
]

INCOME_MAP = {"low": 0, "middle": 1, "high": 2}


def get_connection():
    return psycopg2.connect(**DB_CONFIG)


def load_passenger_features(conn) -> pd.DataFrame:
    """Pull the intermediate passenger feature table from PostgreSQL."""
    query = """
        SELECT
            passenger_id,
            origin_barangay,
            origin_district,
            destination_type,
            trip_purpose,
            primary_route_used,
            trips_per_week,
            avg_fare_paid_php,
            transfers_required,
            wait_time_min,
            travel_time_min,
            satisfaction_score,
            income_bracket,
            prefers_aircon
        FROM intermediate.int_passenger_features
        ORDER BY passenger_id
    """
    log.info("Pulling int_passenger_features from PostgreSQL …")
    df = pd.read_sql(query, conn)
    log.info("  → %d passenger records loaded", len(df))
    return df


def encode_features(df: pd.DataFrame) -> pd.DataFrame:
    """Encode categoricals and derive any extra features."""
    df = df.copy()

    # Encode income bracket as ordinal integer (low=0, middle=1, high=2)
    df["income_bracket_encoded"] = (
        df["income_bracket"].str.lower().map(INCOME_MAP).fillna(1).astype(int)
    )

    return df


def build_feature_matrix(
    df: pd.DataFrame,
) -> tuple[pd.DataFrame, np.ndarray, StandardScaler]:
    """Return (meta_df, scaled_matrix, fitted_scaler)."""
    df = encode_features(df)

    meta_cols = [
        "passenger_id", "origin_barangay", "origin_district",
        "destination_type", "trip_purpose", "primary_route_used",
        "income_bracket", "prefers_aircon",
    ] + FEATURE_COLS

    meta = df[meta_cols].copy()

    raw_matrix = df[FEATURE_COLS].values.astype(float)

    # Check for nulls
    null_counts = pd.isnull(raw_matrix).sum(axis=0)
    if null_counts.any():
        log.warning(
            "Nulls detected in feature columns — filling with column median")
        for i, col in enumerate(FEATURE_COLS):
            if null_counts[i] > 0:
                median_val = np.nanmedian(raw_matrix[:, i])
                raw_matrix[np.isnan(raw_matrix[:, i]), i] = median_val

    scaler = StandardScaler()
    scaled = scaler.fit_transform(raw_matrix)

    log.info("Feature matrix shape: %s", scaled.shape)
    log.info(
        "Feature means (raw): %s",
        {col: round(float(raw_matrix[:, i].mean()), 3)
         for i, col in enumerate(FEATURE_COLS)},
    )

    return meta, scaled, scaler


def save_passenger_features_parquet(meta: pd.DataFrame, scaled: np.ndarray) -> None:
    """Write the feature matrix (raw + scaled columns) to Parquet."""
    out_df = meta.copy()
    for i, col in enumerate(FEATURE_COLS):
        out_df[f"{col}_scaled"] = scaled[:, i]

    out_path = os.path.join(PARQUET_DIR, "passenger_features.parquet")
    table = pa.Table.from_pandas(out_df, preserve_index=False)
    pq.write_table(table, out_path)
    log.info("Saved → %s  (%d rows)", out_path, len(out_df))


def save_scaler(scaler: StandardScaler) -> None:
    os.makedirs(os.path.dirname(SCALER_PATH), exist_ok=True)
    joblib.dump(scaler, SCALER_PATH)
    log.info("StandardScaler saved → %s", SCALER_PATH)


def main():
    log.info("=== Feature Engineering Pipeline START ===")

    conn = get_connection()
    try:
        df = load_passenger_features(conn)

        if df.empty:
            log.error("No data returned from int_passenger_features. Aborting.")
            return

        meta, scaled, scaler = build_feature_matrix(df)
        save_passenger_features_parquet(meta, scaled)
        save_scaler(scaler)

        log.info("=== Feature Engineering Pipeline COMPLETE ===")
        log.info("Output: science/parquet/passenger_features.parquet")
        log.info("Next step: python science/clustering.py")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
