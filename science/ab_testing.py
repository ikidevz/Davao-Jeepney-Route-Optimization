"""
ab_testing.py
-------------
Run the A/B experiment analysis on the Matina → SM Lanang express route trial.

Steps:
  1. Pull Cluster 3 (Underserved Riders) experiment records from staging.stg_ab_experiment
  2. Verify 50/50 control/treatment split
  3. Simulate Treatment B outcome adjustments (if not already in the raw data)
  4. Run two-sample t-test on satisfaction_score and simulated_travel_time_min
  5. Run chi-square test on would_use_again
  6. Compute Cohen's d effect size + 95% confidence intervals
  7. Write per-passenger-per-week results (with stats) to marts.mart_ab_test_results

Run order: AFTER clustering.py, BEFORE export_to_parquet.py
"""

import os
import logging
import numpy as np
import pandas as pd
import psycopg2
import psycopg2.extras
import pyarrow as pa
import pyarrow.parquet as pq
from scipy import stats

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
log = logging.getLogger("ab_testing")

DB_CONFIG = {
    "host":     os.getenv("DB_HOST", "localhost"),
    "port":     int(os.getenv("DB_PORT", 5432)),
    "dbname":   os.getenv("DB_NAME", "jeepney_dw"),
    "user":     os.getenv("DB_USER", "admin"),
    "password": os.getenv("DB_PASS", "password123"),
}

PARQUET_DIR = os.path.join(os.path.dirname(__file__), "parquet")
os.makedirs(PARQUET_DIR, exist_ok=True)

ALPHA = 0.05
UNDERSERVED_CLUSTER_ID = 3


def get_connection():
    return psycopg2.connect(**DB_CONFIG)


# ---------------------------------------------------------------------------
# Load experiment data
# ---------------------------------------------------------------------------
def load_experiment_data(conn) -> pd.DataFrame:
    query = """
        SELECT
            e.experiment_record_id,
            e.experiment_id,
            e.passenger_id,
            e.cluster_id,
            e."group",
            e.route_variant,
            e.test_week,
            e.simulated_travel_time_min,
            e.simulated_fare_php,
            e.transfers_needed,
            e.satisfaction_score,
            e.would_use_again,
            e.experiment_phase,
            e.is_treatment,

            -- Pull what is safely available
            c.cluster_label,
            c.origin_district,
            c.income_bracket

            -- Note: underserved_severity_score is only in the mart layer
            -- We will let dbt calculate it later

        FROM staging.stg_ab_experiment e
        LEFT JOIN intermediate.int_passenger_features c
            ON e.passenger_id = c.passenger_id
        WHERE e.cluster_id = %(cluster_id)s
        ORDER BY e.passenger_id, e.test_week
    """
    log.info("Loading A/B experiment data for Cluster %d (Underserved Riders) …",
             UNDERSERVED_CLUSTER_ID)

    df = pd.read_sql(query, conn, params={
                     "cluster_id": UNDERSERVED_CLUSTER_ID})

    log.info("  → %d experiment records loaded", len(df))
    if not df.empty:
        log.info("Available columns: %s", list(df.columns))

    return df


# ---------------------------------------------------------------------------
# Validate split
# ---------------------------------------------------------------------------
def validate_split(df: pd.DataFrame) -> None:
    counts = df.drop_duplicates("passenger_id")["group"].value_counts()
    log.info("Passenger split — Control: %d  Treatment: %d",
             counts.get("control", 0), counts.get("treatment", 0))
    total = counts.sum()
    for grp, cnt in counts.items():
        pct = 100 * cnt / total
        if not (40 <= pct <= 60):
            log.warning(
                "Split imbalance detected for group '%s': %.1f%%", grp, pct)


# ---------------------------------------------------------------------------
# Statistical tests
# ---------------------------------------------------------------------------
def cohens_d(group_a: np.ndarray, group_b: np.ndarray) -> float:
    """Compute Cohen's d effect size."""
    pooled_std = np.sqrt(
        (group_a.std(ddof=1) ** 2 + group_b.std(ddof=1) ** 2) / 2)
    if pooled_std == 0:
        return 0.0
    return float((group_b.mean() - group_a.mean()) / pooled_std)


def run_ttest(control: np.ndarray, treatment: np.ndarray, metric_name: str) -> dict:
    t_stat, p_value = stats.ttest_ind(
        control, treatment, equal_var=False)  # Welch's t-test
    d = cohens_d(control, treatment)

    # 95% CI on the difference of means
    diff = treatment.mean() - control.mean()
    se = np.sqrt(control.var(ddof=1) / len(control) +
                 treatment.var(ddof=1) / len(treatment))
    ci_low = diff - 1.96 * se
    ci_high = diff + 1.96 * se

    result = {
        "metric":             metric_name,
        "control_mean":       round(float(control.mean()),   4),
        "treatment_mean":     round(float(treatment.mean()), 4),
        "mean_diff":          round(float(diff),   4),
        "t_statistic":        round(float(t_stat),  6),
        "p_value":            round(float(p_value), 6),
        "is_significant":     bool(p_value < ALPHA),
        "effect_size":        round(float(d),       4),
        "ci_low_95":          round(float(ci_low),  4),
        "ci_high_95":         round(float(ci_high), 4),
        "n_control":          int(len(control)),
        "n_treatment":        int(len(treatment)),
    }

    log.info(
        "[%s] p=%.4f  d=%.3f  control_mean=%.3f  treatment_mean=%.3f  significant=%s",
        metric_name, p_value, d,
        result["control_mean"], result["treatment_mean"],
        result["is_significant"],
    )
    return result


def run_chi_square(control: pd.Series, treatment: pd.Series, metric_name: str) -> dict:
    values = pd.concat(
        [control.reset_index(drop=True), treatment.reset_index(drop=True)],
        ignore_index=True,
    ).astype(int)
    groups = pd.Series(
        ["control"] * len(control) + ["treatment"] * len(treatment),
        name="group",
    )
    ct = pd.crosstab(values, groups)
    chi2, p_value, dof, _ = stats.chi2_contingency(ct)

    result = {
        "metric":         metric_name,
        "chi2_statistic": round(float(chi2),    6),
        "p_value":        round(float(p_value), 6),
        "dof":            int(dof),
        "is_significant": bool(p_value < ALPHA),
        "control_pct_yes":    round(float(control.mean()),   4),
        "treatment_pct_yes":  round(float(treatment.mean()), 4),
        "n_control":   int(len(control)),
        "n_treatment": int(len(treatment)),
    }

    log.info(
        "[%s] chi2=%.4f  p=%.4f  ctrl_pct_yes=%.2f  trt_pct_yes=%.2f  significant=%s",
        metric_name, chi2, p_value,
        result["control_pct_yes"], result["treatment_pct_yes"],
        result["is_significant"],
    )
    return result


# ---------------------------------------------------------------------------
# Run all tests
# ---------------------------------------------------------------------------
def run_all_tests(df: pd.DataFrame) -> list[dict]:
    ctrl = df[df["group"] == "control"]
    trt = df[df["group"] == "treatment"]

    log.info("Running statistical tests …")

    results = []

    # 1. Satisfaction score (t-test)
    results.append(
        run_ttest(
            ctrl["satisfaction_score"].values.astype(float),
            trt["satisfaction_score"].values.astype(float),
            "satisfaction_score",
        )
    )

    # 2. Travel time (t-test)
    results.append(
        run_ttest(
            ctrl["simulated_travel_time_min"].values.astype(float),
            trt["simulated_travel_time_min"].values.astype(float),
            "simulated_travel_time_min",
        )
    )

    # 3. Would use again (chi-square)
    results.append(
        run_chi_square(
            ctrl["would_use_again"].astype(int),
            trt["would_use_again"].astype(int),
            "would_use_again",
        )
    )

    return results


# ---------------------------------------------------------------------------
# Save ab_test_statistics Parquet
# ---------------------------------------------------------------------------
def save_statistics_parquet(results: list[dict]) -> None:
    df = pd.DataFrame(results)
    path = os.path.join(PARQUET_DIR, "ab_test_statistics.parquet")
    pq.write_table(pa.Table.from_pandas(df, preserve_index=False), path)
    log.info("Saved ab_test_statistics.parquet")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    log.info("=== A/B Testing Pipeline START ===")
    log.info(
        "Hypothesis: Matina → SM Lanang express reduces travel time and improves satisfaction")
    log.info(
        "α = %.2f  |  Primary metric: satisfaction_score  |  Secondary: would_use_again", ALPHA)

    conn = get_connection()
    try:
        df = load_experiment_data(conn)

        if df.empty:
            log.error("No experiment records found. Aborting.")
            return

        validate_split(df)

        results = run_all_tests(df)

        save_statistics_parquet(results)

        # Summary
        sat_result = next(
            (r for r in results if r["metric"] == "satisfaction_score"), {})
        if sat_result.get("is_significant"):
            log.info(
                "✓ RESULT: Treatment B (express route) shows a STATISTICALLY SIGNIFICANT "
                "improvement in satisfaction (p=%.4f, d=%.3f). Recommend route adoption.",
                sat_result["p_value"], sat_result["effect_size"],
            )
        else:
            log.info(
                "✗ RESULT: No significant improvement detected at α=%.2f (p=%.4f). "
                "Consider extending trial or adjusting route design.",
                ALPHA, sat_result.get("p_value", float("nan")),
            )

    finally:
        conn.close()

    log.info("=== A/B Testing Pipeline COMPLETE ===")
    log.info("Next step: python science/export_to_parquet.py")


if __name__ == "__main__":
    main()
