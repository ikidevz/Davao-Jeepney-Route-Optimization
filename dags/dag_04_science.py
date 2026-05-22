"""
dag_04_science.py
------------------
DAG 4 — Data Science Pipeline
Schedule: Triggered after dag_03_dbt_transform
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from airflow import DAG
from airflow.providers.standard.operators.bash import BashOperator
from airflow.providers.standard.operators.trigger_dagrun import TriggerDagRunOperator

DEFAULT_ARGS = {
    "owner":            "jeepney-pipeline",
    "depends_on_past":  False,
    "email_on_failure": False,
    "email_on_retry":   False,
}

SCIENCE_DIR = "/opt/airflow/science"
SCIENCE_ENV = {
    "DB_HOST":          "postgres",
    "DB_PORT":          "5432",
    "DB_NAME":          "jeepney_dw",
    "DB_USER":          os.environ.get("SVC_PIPELINE_USER", "svc_pipeline"),
    "DB_PASS":          os.environ.get("SVC_PIPELINE_PASSWORD", ""),
    "PYTHONUNBUFFERED": "1",
    "SVC_PIPELINE_USER":     os.environ.get("SVC_PIPELINE_USER", "svc_pipeline"),
    "SVC_PIPELINE_PASSWORD": os.environ.get("SVC_PIPELINE_PASSWORD", ""),

}

with DAG(
    dag_id="dag_04_science",
    description="ML pipeline: feature engineering → clustering → A/B testing → Parquet export",
    default_args=DEFAULT_ARGS,
    schedule=None,
    start_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
    catchup=False,
    max_active_runs=1,
    tags=["jeepney", "science", "ml", "clustering", "ab-test"],
) as dag:

    run_feature_engineering = BashOperator(
        task_id="run_feature_engineering",
        bash_command=f"python {SCIENCE_DIR}/feature_engineering.py",
        env=SCIENCE_ENV,
    )

    validate_feature_parquet = BashOperator(
        task_id="validate_feature_parquet",
        bash_command=(
            "python -c \""
            "import pyarrow.parquet as pq; "
            "t = pq.read_table('/opt/airflow/science/parquet/passenger_features.parquet'); "
            "print(f'passenger_features.parquet: {t.num_rows:,} rows, {t.num_columns} cols'); "
            "assert t.num_rows > 0, 'Feature parquet is empty!'"
            "\""
        ),
    )

    run_clustering = BashOperator(
        task_id="run_clustering",
        bash_command=f"python {SCIENCE_DIR}/clustering.py",
        env=SCIENCE_ENV,
    )

    validate_cluster_assignments = BashOperator(
        task_id="validate_cluster_assignments",
        bash_command=(
            "python -c \""
            "import pyarrow.parquet as pq, psycopg2, os; "
            "t = pq.read_table('/opt/airflow/science/parquet/cluster_assignments.parquet'); "
            "n_clusters = t.column('cluster_id').to_pylist(); "
            "distinct_k = len(set(n_clusters)); "
            "print(f'cluster_assignments.parquet: {t.num_rows:,} rows, {distinct_k} distinct clusters'); "
            "assert distinct_k >= 2, f'Too few clusters in parquet: {distinct_k} (minimum 2)'; "
            "conn = psycopg2.connect("
            "  host='postgres', dbname='jeepney_dw',"
            "  user=os.environ['SVC_PIPELINE_USER'],"
            "  password=os.environ['SVC_PIPELINE_PASSWORD']"
            "); "
            "cur = conn.cursor(); "
            "cur.execute(\\\"SELECT cluster_id, COUNT(*) FROM staging.stg_passenger_survey "
            "  WHERE cluster_id IS NOT NULL GROUP BY cluster_id ORDER BY cluster_id\\\"); "
            "rows = cur.fetchall(); "
            "[print(f'  Cluster {r[0]}: {r[1]:,} passengers') for r in rows]; "
            "assert len(rows) >= 2, f'Expected at least 2 clusters in staging, got {len(rows)}'; "
            "assert len(rows) == distinct_k, ("
            "  f'Cluster count mismatch: parquet has {distinct_k} clusters but '"
            "  f'staging has {len(rows)} — clustering.py may not have written back yet'"
            "); "
            "conn.close(); "
            "print(f'Cluster validation passed — {distinct_k} clusters confirmed.')"
            "\""
        ),
        env=SCIENCE_ENV,
    )

    run_ab_testing = BashOperator(
        task_id="run_ab_testing",
        bash_command=f"python {SCIENCE_DIR}/ab_testing.py",
        env=SCIENCE_ENV,
    )

    validate_ab_results = BashOperator(
        task_id="validate_ab_results",
        bash_command=(
            "python -c \""
            "import pyarrow.parquet as pq; "
            "t = pq.read_table('/opt/airflow/science/parquet/ab_test_statistics.parquet'); "
            "print(f'ab_test_statistics.parquet: {t.num_rows} test results'); "
            "assert t.num_rows >= 3, 'Expected at least 3 statistical tests'"
            "\""
        ),
    )

    validate_all_parquets = BashOperator(
        task_id="validate_all_parquets",
        bash_command=(
            "python -c \""
            "from pathlib import Path; "
            "parquet_dir = Path('/opt/airflow/science/parquet'); "
            "required = ['passenger_features.parquet', 'cluster_assignments.parquet', "
            "  'ab_test_statistics.parquet', 'elbow_scores.parquet', "
            "  'silhouette_scores.parquet']; "
            "missing = [f for f in required if not (parquet_dir / f).exists()]; "
            "[print(f'  OK: {f}') for f in required if (parquet_dir / f).exists()]; "
            "assert not missing, f'Missing Parquet files: {missing}'"
            "\""
        ),
    )

    trigger_marts = TriggerDagRunOperator(
        task_id="trigger_dag_05_marts_refresh",
        trigger_dag_id="dag_05_marts_refresh",
        wait_for_completion=False,
        reset_dag_run=True,
    )

    (
        run_feature_engineering
        >> validate_feature_parquet
        >> run_clustering
        >> validate_cluster_assignments
        >> run_ab_testing
        >> validate_ab_results
        >> validate_all_parquets
        >> trigger_marts
    )
