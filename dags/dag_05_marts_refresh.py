"""
dag_05_marts_refresh.py
------------------------
DAG 5 — Gold Layer Mart Refresh
Schedule: Triggered after dag_04_science
"""

from __future__ import annotations
import os
from datetime import datetime, timedelta, timezone

from airflow import DAG
from airflow.providers.standard.operators.bash import BashOperator

DEFAULT_ARGS = {
    "owner":            "jeepney-pipeline",
    "depends_on_past":  False,
    "email_on_failure": False,
    "email_on_retry":   False,
}

DBT_DIR = "/opt/airflow/dbt"
DBT_CMD = f"cd {DBT_DIR} && dbt"
PROFILES_ARG = f"--profiles-dir {DBT_DIR}"
SCIENCE_DIR = "/opt/airflow/science"

DBT_ENV = {
    "DB_HOST":          "postgres",
    "DB_PORT":          "5432",
    "DB_NAME":          "jeepney_dw",
    "DB_USER":          os.environ.get("SVC_PIPELINE_USER", "svc_pipeline"),
    "DB_PASS":          os.environ.get("SVC_PIPELINE_PASSWORD", ""),
    "PYTHONUNBUFFERED": "1",
    "SVC_PIPELINE_USER":     os.environ.get("SVC_PIPELINE_USER", "svc_pipeline"),
    "SVC_PIPELINE_PASSWORD": os.environ.get("SVC_PIPELINE_PASSWORD", ""),
    "PATH": f"/home/airflow/.local/bin:{os.environ.get('PATH', '')}",
}

with DAG(
    dag_id="dag_05_marts_refresh",
    description="dbt mart models refresh (Gold layer) — final BI-ready tables",
    default_args=DEFAULT_ARGS,
    schedule=None,
    start_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
    catchup=False,
    max_active_runs=1,
    tags=["jeepney", "dbt", "marts", "gold"],
) as dag:

    wait_for_science = BashOperator(
        task_id="confirm_parquet_inputs_ready",
        bash_command=(
            "python -c \""
            "from pathlib import Path; "
            "required = ['/opt/airflow/science/parquet/passenger_features.parquet',"
            "  '/opt/airflow/science/parquet/cluster_assignments.parquet',"
            "  '/opt/airflow/science/parquet/ab_test_statistics.parquet']; "
            "missing = [f for f in required if not Path(f).exists()]; "
            "assert not missing, f'Science outputs missing: {missing}'; "
            "print('All science Parquet outputs confirmed ready.')"
            "\""
        ),
    )

    dbt_refresh_int_features = BashOperator(
        task_id="dbt_refresh_int_passenger_features",
        bash_command=f"{DBT_CMD} run --select int_passenger_features {PROFILES_ARG}",
        env=DBT_ENV,
    )

    dbt_run_marts = BashOperator(
        task_id="dbt_run_marts",
        bash_command=f"{DBT_CMD} run --select marts {PROFILES_ARG}",
        env=DBT_ENV,
    )

    dbt_test_marts = BashOperator(
        task_id="dbt_test_marts",
        bash_command=f"{DBT_CMD} test --select marts {PROFILES_ARG}",
        env=DBT_ENV,
    )

    validate_mart_counts = BashOperator(
        task_id="validate_mart_row_counts",
        bash_command=(
            "python -c \""
            "import psycopg2, os; "
            "conn = psycopg2.connect("
            "  host='postgres', dbname='jeepney_dw',"
            "  user=os.environ['SVC_PIPELINE_USER'],"
            "  password=os.environ['SVC_PIPELINE_PASSWORD']"
            "); "
            "cur = conn.cursor(); "
            "marts = ['mart_route_summary', 'mart_district_ridership', "
            "         'mart_commuter_clusters', 'mart_ab_test_results']; "
            "[cur.execute(f\\\"SELECT COUNT(*) FROM marts.{m}\\\") or "
            " print(f'{m}: {cur.fetchone()[0]:,} rows') for m in marts]; "
            "conn.close()"
            "\""
        ),
        env=DBT_ENV,
    )

    validate_cluster_mart = BashOperator(
        task_id="validate_cluster_labels_in_mart",
        bash_command=(
            "python -c \""
            "import psycopg2, os; "
            "conn = psycopg2.connect("
            "  host='postgres', dbname='jeepney_dw',"
            "  user=os.environ['SVC_PIPELINE_USER'],"
            "  password=os.environ['SVC_PIPELINE_PASSWORD']"
            "); "
            "cur = conn.cursor(); "
            "cur.execute(\\\"SELECT cluster_label, COUNT(*) FROM marts.mart_commuter_clusters "
            "  GROUP BY cluster_label ORDER BY cluster_label\\\"); "
            "rows = cur.fetchall(); "
            "[print(f'  {r[0]}: {r[1]:,} passengers') for r in rows]; "
            "null_check = [r for r in rows if r[0] is None]; "
            "assert not null_check, 'NULL cluster labels found in mart_commuter_clusters!'; "
            "conn.close()"
            "\""
        ),
        env=DBT_ENV,
    )

    validate_ab_mart = BashOperator(
        task_id="validate_ab_mart_contents",
        bash_command=(
            "python -c \""
            "import psycopg2, os; "
            "conn = psycopg2.connect("
            "  host='postgres', dbname='jeepney_dw',"
            "  user=os.environ['SVC_PIPELINE_USER'],"
            "  password=os.environ['SVC_PIPELINE_PASSWORD']"
            "); "
            "cur = conn.cursor(); "

            "cur.execute(\\\"SELECT COUNT(*) FROM marts.mart_ab_test_results\\\"); "
            "row_count = cur.fetchone()[0]; "
            "print(f'mart_ab_test_results total rows: {row_count:,}'); "
            "assert row_count > 0, 'mart_ab_test_results is empty!'; "

            "cur.execute(\\\"SELECT COUNT(DISTINCT passenger_id) "
            "FROM marts.mart_ab_test_results\\\"); "
            "passengers = cur.fetchone()[0]; "
            "print(f'Distinct passengers in A/B mart: {passengers:,}'); "

            "cur.execute(\\\"SELECT route_variant, COUNT(*) "
            "FROM marts.mart_ab_test_results "
            "GROUP BY route_variant ORDER BY route_variant\\\"); "
            "[print(f'  {r[0]}: {r[1]:,} rows') for r in cur.fetchall()]; "

            "conn.close()"
            "\""
        ),
        env=DBT_ENV,
    )

    run_export_parquet = BashOperator(
        task_id="run_export_to_parquet",
        bash_command=f"python {SCIENCE_DIR}/export_to_parquet.py",
        env=DBT_ENV,
    )

    pipeline_complete = BashOperator(
        task_id="pipeline_complete_notification",
        bash_command=(
            "echo '=== DAVAO JEEPNEY PIPELINE COMPLETE ==='; "
            "echo 'All 5 DAGs completed successfully.'; "
            "echo 'Services ready:'; "
            "echo '  Superset:  http://localhost:8088'; "
            "echo '  Streamlit: http://localhost:8501'; "
            "echo '  Airflow:   http://localhost:8080'; "
            "echo '  MinIO:     http://localhost:9001'; "
        ),
    )

    (
        wait_for_science
        >> dbt_refresh_int_features
        >> dbt_run_marts
        >> dbt_test_marts
        >> validate_mart_counts
        >> validate_cluster_mart
        >> validate_ab_mart
        >> run_export_parquet
        >> pipeline_complete
    )
