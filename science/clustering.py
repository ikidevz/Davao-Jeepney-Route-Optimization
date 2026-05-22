"""
clustering.py
-------------
Load passenger features, run K-Means (primary) + DBSCAN (validation),
determine optimal K via Elbow + Silhouette, assign cluster labels,
and write results back to PostgreSQL (staging.stg_passenger_survey).

Run order: AFTER feature_engineering.py, BEFORE ab_testing.py
"""

import os
import logging
import joblib
import numpy as np
import pandas as pd
import psycopg2
import psycopg2.extras
import pyarrow as pa
import pyarrow.parquet as pq
from sklearn.cluster import KMeans, DBSCAN
from sklearn.metrics import silhouette_score

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
log = logging.getLogger("clustering")

DB_CONFIG = {
    "host":     os.getenv("DB_HOST", "localhost"),
    "port":     int(os.getenv("DB_PORT", 5432)),
    "dbname":   os.getenv("DB_NAME", "jeepney_dw"),
    "user":     os.getenv("DB_USER", "admin"),
    "password": os.getenv("DB_PASS", "password123"),
}

PARQUET_DIR = os.path.join(os.path.dirname(__file__), "parquet")
MODEL_DIR = os.path.join(os.path.dirname(__file__), "models")
os.makedirs(PARQUET_DIR, exist_ok=True)
os.makedirs(MODEL_DIR,   exist_ok=True)

FEATURE_COLS = [
    "trips_per_week",
    "avg_fare_paid_php",
    "transfers_required",
    "wait_time_min",
    "travel_time_min",
    "satisfaction_score",
    "income_bracket_encoded",
]

# Cluster labels in expected order (0-indexed)
CLUSTER_LABELS = {
    0: "Student Commuters",
    1: "Market Workers",
    2: "CBD Workers",
    3: "Underserved Riders",
    4: "Occasional Riders",
}

K_RANGE = range(2, 11)
OPTIMAL_K = 5   # override after elbow/silhouette analysis; can also be auto-selected
RANDOM_STATE = 42


def get_connection():
    return psycopg2.connect(**DB_CONFIG)


# ---------------------------------------------------------------------------
# Load features from Parquet
# ---------------------------------------------------------------------------
def load_features() -> tuple[pd.DataFrame, np.ndarray]:
    path = os.path.join(PARQUET_DIR, "passenger_features.parquet")
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Feature Parquet not found at {path}. "
            "Run feature_engineering.py first."
        )
    df = pd.read_parquet(path)
    log.info("Loaded feature Parquet: %d rows", len(df))

    scaled_cols = [f"{c}_scaled" for c in FEATURE_COLS]
    X = df[scaled_cols].values.astype(float)
    return df, X


# ---------------------------------------------------------------------------
# Elbow + Silhouette diagnostics
# ---------------------------------------------------------------------------
def run_diagnostics(X: np.ndarray) -> tuple[pd.DataFrame, pd.DataFrame]:
    log.info("Running Elbow + Silhouette diagnostics for K=%d..%d …",
             K_RANGE.start, K_RANGE.stop - 1)
    elbow_rows = []
    silhouette_rows = []

    for k in K_RANGE:
        km = KMeans(n_clusters=k, random_state=RANDOM_STATE, n_init=10)
        labels = km.fit_predict(X)
        wss = float(km.inertia_)
        sil = float(silhouette_score(X, labels, sample_size=min(
            2000, len(X)), random_state=RANDOM_STATE))
        elbow_rows.append({"k": k, "wss": wss})
        silhouette_rows.append({"k": k, "silhouette_score": sil})
        log.info("  K=%d  WSS=%.2f  Silhouette=%.4f", k, wss, sil)

    elbow_df = pd.DataFrame(elbow_rows)
    silhouette_df = pd.DataFrame(silhouette_rows)

    # Auto-select K: highest silhouette score
    best_k = int(
        silhouette_df.loc[silhouette_df["silhouette_score"].idxmax(), "k"])
    log.info(
        "Auto-selected K (max silhouette) = %d. Blueprint target = %d.", best_k, OPTIMAL_K)

    return elbow_df, silhouette_df


def save_diagnostic_parquets(elbow_df: pd.DataFrame, silhouette_df: pd.DataFrame) -> None:
    pq.write_table(pa.Table.from_pandas(elbow_df, preserve_index=False),
                   os.path.join(PARQUET_DIR, "elbow_scores.parquet"))
    pq.write_table(pa.Table.from_pandas(silhouette_df, preserve_index=False),
                   os.path.join(PARQUET_DIR, "silhouette_scores.parquet"))
    log.info("Saved elbow_scores.parquet and silhouette_scores.parquet")


# ---------------------------------------------------------------------------
# Remap cluster IDs to match expected semantic labels
# ---------------------------------------------------------------------------
def remap_clusters(df: pd.DataFrame, raw_labels: np.ndarray) -> np.ndarray:
    """
    K-Means assigns cluster IDs arbitrarily. We remap them to the expected
    semantic order by matching cluster centroids to known prototypes.

    Expected profiles (rough Z-score direction):
      0 Student Commuters  — high trips, low fare, moderate satisfaction
      1 Market Workers     — AM peak signal, moderate transfers
      2 CBD Workers        — high fare, high satisfaction, low transfers
      3 Underserved Riders — high transfers, long wait, low satisfaction
      4 Occasional Riders  — low trips, low transfers
    """
    scaled_cols = [f"{c}_scaled" for c in FEATURE_COLS]
    X = df[scaled_cols].values

    unique_raw = np.unique(raw_labels)
    centroids = np.array([X[raw_labels == k].mean(axis=0) for k in unique_raw])

    # Feature indices for remapping heuristics
    idx = {col: i for i, col in enumerate(FEATURE_COLS)}

    # Score each raw cluster against expected prototypes
    # (higher = better match for that semantic cluster)
    prototype_scores = []
    for raw_k, centroid in zip(unique_raw, centroids):
        scores = {
            # high freq, low fare
            0: centroid[idx["trips_per_week"]] - centroid[idx["avg_fare_paid_php"]],
            # transfers + wait
            1: centroid[idx["transfers_required"]] + centroid[idx["wait_time_min"]],
            # high fare, high sat
            2: centroid[idx["avg_fare_paid_php"]] + centroid[idx["satisfaction_score"]],
            # low sat, high transfers
            3: -centroid[idx["satisfaction_score"]] + centroid[idx["transfers_required"]],
            # low freq, few transfers
            4: -centroid[idx["trips_per_week"]] - centroid[idx["transfers_required"]],
        }
        prototype_scores.append((raw_k, scores))

    # Greedy assignment: assign raw cluster to the semantic cluster it scores highest on
    assignment = {}
    taken = set()
    scores_lookup = dict(prototype_scores)

    for semantic_k in [3, 2, 0, 4, 1]:
        best_raw = max(
            (raw_k for raw_k, _ in prototype_scores if raw_k not in taken),
            key=lambda rk, sk=semantic_k: scores_lookup[rk][sk],
            default=None,
        )
        if best_raw is not None:
            assignment[best_raw] = semantic_k
            taken.add(best_raw)

    # Any remaining unmapped clusters
    for raw_k, _ in prototype_scores:
        if raw_k not in assignment:
            remaining = [s for s in range(
                OPTIMAL_K) if s not in assignment.values()]
            assignment[raw_k] = remaining[0] if remaining else raw_k

    log.info("Cluster remapping: raw → semantic %s", assignment)
    return np.array([assignment.get(lbl, lbl) for lbl in raw_labels])


# ---------------------------------------------------------------------------
# Fit final K-Means model
# ---------------------------------------------------------------------------
def fit_kmeans(X: np.ndarray) -> tuple[KMeans, np.ndarray]:
    log.info("Fitting final K-Means with K=%d …", OPTIMAL_K)
    km = KMeans(n_clusters=OPTIMAL_K, random_state=RANDOM_STATE,
                n_init=20, max_iter=500)
    raw_labels = km.fit_predict(X)
    inertia = km.inertia_
    log.info("Final model inertia: %.2f", inertia)
    return km, raw_labels


def run_dbscan_validation(X: np.ndarray) -> pd.Series:
    """Run DBSCAN for noise/outlier detection as a validation step."""
    log.info("Running DBSCAN validation …")
    db = DBSCAN(eps=1.2, min_samples=15)
    db_labels = db.fit_predict(X)
    n_noise = int((db_labels == -1).sum())
    n_clusters = len(set(db_labels)) - (1 if -1 in db_labels else 0)
    log.info("DBSCAN: %d clusters found, %d noise points (%.1f%%)",
             n_clusters, n_noise, 100 * n_noise / len(X))
    return pd.Series(db_labels, name="dbscan_label")


# ---------------------------------------------------------------------------
# Write cluster assignments to Parquet
# ---------------------------------------------------------------------------
def save_cluster_parquet(df: pd.DataFrame, labels: np.ndarray) -> None:
    out = pd.DataFrame({
        "passenger_id":  df["passenger_id"].values,
        "cluster_id":    labels,
        "cluster_label": [CLUSTER_LABELS.get(lbl, f"Cluster {lbl}") for lbl in labels],
    })
    path = os.path.join(PARQUET_DIR, "cluster_assignments.parquet")
    pq.write_table(pa.Table.from_pandas(out, preserve_index=False), path)
    log.info("Saved cluster_assignments.parquet  (%d rows)", len(out))

    # Summary
    counts = out["cluster_label"].value_counts()
    log.info("Cluster distribution:\n%s", counts.to_string())


# ---------------------------------------------------------------------------
# Write cluster labels back to PostgreSQL staging table
# ---------------------------------------------------------------------------
def update_postgres_cluster_labels(df: pd.DataFrame, labels: np.ndarray, conn) -> None:
    log.info("Writing cluster labels to staging.stg_passenger_survey …")
    # Reset index so positional i aligns with labels array positions
    df_reset = df.reset_index(drop=True)
    updates = [
        (
            int(labels[i]),
            CLUSTER_LABELS.get(int(labels[i]), f"Cluster {labels[i]}"),
            df_reset.at[i, "passenger_id"],
        )
        for i in range(len(labels))
    ]
    update_sql = """
        UPDATE raw.stg_passenger_survey
        SET cluster_id    = %s,
            cluster_label = %s
        WHERE passenger_id = %s
    """
    with conn.cursor() as cur:
        psycopg2.extras.execute_batch(cur, update_sql, updates, page_size=500)
    conn.commit()
    log.info("Updated %d rows in stg_passenger_survey", len(updates))


# ---------------------------------------------------------------------------
# Save model artefact
# ---------------------------------------------------------------------------
def save_model(km: KMeans) -> None:
    path = os.path.join(MODEL_DIR, "kmeans_model.joblib")
    joblib.dump(km, path)
    log.info("K-Means model saved → %s", path)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    log.info("=== Clustering Pipeline START ===")

    df, X = load_features()

    elbow_df, silhouette_df = run_diagnostics(X)
    save_diagnostic_parquets(elbow_df, silhouette_df)

    km, raw_labels = fit_kmeans(X)
    final_labels = remap_clusters(df, raw_labels)

    run_dbscan_validation(X)

    save_cluster_parquet(df, final_labels)
    save_model(km)

    conn = get_connection()
    try:
        update_postgres_cluster_labels(df, final_labels, conn)
    finally:
        conn.close()

    log.info("=== Clustering Pipeline COMPLETE ===")
    log.info("Next step: python science/ab_testing.py")


if __name__ == "__main__":
    main()
