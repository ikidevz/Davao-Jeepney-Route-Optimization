"""
dag_02_ingestion.py
--------------------
DAG 2 — Bronze → Silver Ingestion
Schedule: Triggered by dag_01_producers (TriggerDagRunOperator)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from airflow import DAG
from airflow.providers.standard.operators.bash import BashOperator
from airflow.providers.standard.operators.trigger_dagrun import TriggerDagRunOperator

DEFAULT_ARGS = {
    "owner":            "jeepney-pipeline",
    "depends_on_past":  False,
    "email_on_failure": False,
    "email_on_retry":   False,
    "retries":          2,
    "retry_delay":      timedelta(minutes=5),
}

with DAG(
    dag_id="dag_02_ingestion",
    description="MinIO Parquet → PostgreSQL staging (Silver layer)",
    default_args=DEFAULT_ARGS,
    schedule=None,
    start_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
    catchup=False,
    max_active_runs=1,
    tags=["jeepney", "ingestion", "silver"],
) as dag:

    run_ingestion = BashOperator(
        task_id="run_ingest_to_postgres",
        bash_command="python /opt/airflow/ingestion/ingest_to_postgres.py",
        env={
            "DB_HOST":          "postgres",
            "DB_PORT":          "5432",
            "DB_NAME":          "jeepney_dw",
            "DB_USER":          "{{ conn.postgres_default.login | default(env['SVC_PIPELINE_USER']) }}",
            "DB_PASS":          "{{ conn.postgres_default.password | default(env['SVC_PIPELINE_PASSWORD']) }}",
            "MINIO_ENDPOINT":   "minio:9000",
            "MINIO_ACCESS_KEY": "{{ env['MINIO_ACCESS_KEY'] }}",
            "MINIO_SECRET_KEY": "{{ env['MINIO_SECRET_KEY'] }}",
            "MINIO_BUCKET":     "{{ env['MINIO_BUCKET'] }}",
            "PYTHONUNBUFFERED": "1",
        },
    )

    validate_staging = BashOperator(
        task_id="validate_staging_row_counts",
        bash_command=(
            "python -c \""
            "import psycopg2, os; "
            "conn = psycopg2.connect("
            "  host='postgres', dbname='jeepney_dw',"
            "  user=os.environ['SVC_PIPELINE_USER'],"
            "  password=os.environ['SVC_PIPELINE_PASSWORD']"
            "); "
            "cur = conn.cursor(); "
            "tables = ['stg_routes','stg_stops','stg_vehicles','stg_operators',"
            "          'stg_trips','stg_passenger_survey','stg_ab_experiment']; "
            "[cur.execute(f\\\"SELECT COUNT(*) FROM staging.{t}\\\") or "
            " print(f'{t}: {cur.fetchone()[0]:,} rows') for t in tables]; "
            "conn.close()"
            "\""
        ),
    )

    trigger_dbt = TriggerDagRunOperator(
        task_id="trigger_dag_03_dbt_transform",
        trigger_dag_id="dag_03_dbt_transform",
        wait_for_completion=False,
        reset_dag_run=True,
    )

    run_ingestion >> validate_staging >> trigger_dbt
