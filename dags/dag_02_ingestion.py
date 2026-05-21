"""
dag_02_ingestion.py
--------------------
DAG 2 — Bronze → Silver Ingestion
Schedule: Triggered by dag_01_producers (TriggerDagRunOperator)
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
    "email_on_retry":   False
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

            "POSTGRES_HOST":         os.getenv("POSTGRES_HOST",         "postgres"),
            "POSTGRES_PORT":         os.getenv("POSTGRES_PORT",         "5432"),
            "POSTGRES_DB":           os.getenv("POSTGRES_DB",           "jeepney_dw"),
            "SVC_PIPELINE_USER":     os.getenv("SVC_PIPELINE_USER",     "svc_pipeline"),
            "SVC_PIPELINE_PASSWORD": os.getenv("SVC_PIPELINE_PASSWORD", "pipeline_pass_123"),


            "MINIO_ENDPOINT":        os.getenv("MINIO_ENDPOINT",    "minio:9000"),
            "MINIO_ACCESS_KEY":      os.getenv("MINIO_ACCESS_KEY"),
            "MINIO_SECRET_KEY":      os.getenv("MINIO_SECRET_KEY"),
            "MINIO_BUCKET":          os.getenv("MINIO_BUCKET",      "raw"),

            "PYTHONUNBUFFERED": "1",
        },
    )

    # -------------------------------------------------------------------------
    # Task 2 — Validate row counts in every staging table
    # -------------------------------------------------------------------------
    validate_staging = BashOperator(
        task_id="validate_staging_row_counts",
        bash_command=(
            "python -c \""
            "import psycopg2, os; "
            "conn = psycopg2.connect("
            "  host=os.environ['POSTGRES_HOST'],"
            "  port=int(os.environ['POSTGRES_PORT']),"
            "  dbname=os.environ['POSTGRES_DB'],"
            "  user=os.environ['SVC_PIPELINE_USER'],"
            "  password=os.environ['SVC_PIPELINE_PASSWORD']"
            "); "
            "cur = conn.cursor(); "
            "tables = ['stg_routes','stg_stops','stg_vehicles','stg_operators',"
            "          'stg_trips','stg_passenger_survey','stg_ab_experiment']; "
            "[cur.execute(f\\\"SELECT COUNT(*) FROM raw.{t}\\\") or "
            " print(f'{t}: {cur.fetchone()[0]:,} rows') for t in tables]; "
            "conn.close()"
            "\""
        ),
        env={
            "POSTGRES_HOST":         os.getenv("POSTGRES_HOST",         "postgres"),
            "POSTGRES_PORT":         os.getenv("POSTGRES_PORT",         "5432"),
            "POSTGRES_DB":           os.getenv("POSTGRES_DB",           "jeepney_dw"),
            "SVC_PIPELINE_USER":     os.getenv("SVC_PIPELINE_USER",     "svc_pipeline"),
            "SVC_PIPELINE_PASSWORD": os.getenv("SVC_PIPELINE_PASSWORD", "pipeline_pass_123"),
        },
    )

    # -------------------------------------------------------------------------
    # Task 3 — Trigger dbt transform DAG
    # -------------------------------------------------------------------------
    trigger_dbt = TriggerDagRunOperator(
        task_id="trigger_dag_03_dbt_transform",
        trigger_dag_id="dag_03_dbt_transform",
        wait_for_completion=False,
        reset_dag_run=True,
    )

    run_ingestion >> validate_staging >> trigger_dbt
