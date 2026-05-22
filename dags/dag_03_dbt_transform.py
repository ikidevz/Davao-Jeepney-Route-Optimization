"""
------------------------
DAG 3 — Silver → Gold Transformation (staging + intermediate only)
Schedule: Triggered after dag_02_ingestion
"""

from __future__ import annotations
import os
from datetime import datetime, timezone

from airflow import DAG
from airflow.providers.standard.operators.bash import BashOperator
from airflow.providers.standard.operators.trigger_dagrun import TriggerDagRunOperator

DEFAULT_ARGS = {
    "owner": "jeepney-pipeline",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
}

DBT_DIR = "/opt/airflow/dbt"
DBT_CMD = f"cd {DBT_DIR} && dbt --no-partial-parse"
PROFILES_ARG = f"--profiles-dir {DBT_DIR}"

DBT_ENV = {
    "DB_HOST": "postgres",
    "DB_PORT": "5432",
    "DB_NAME": "jeepney_dw",
    "DB_USER": os.environ.get("SVC_PIPELINE_USER", "svc_pipeline"),
    "DB_PASS": os.environ.get("SVC_PIPELINE_PASSWORD", ""),
    "PYTHONUNBUFFERED": "1",
    "SVC_PIPELINE_USER": os.environ.get("SVC_PIPELINE_USER", "svc_pipeline"),
    "SVC_PIPELINE_PASSWORD": os.environ.get("SVC_PIPELINE_PASSWORD", ""),
    "PATH": f"/home/airflow/.local/bin:{os.environ.get('PATH', '')}",
}

with DAG(
    dag_id="dag_03_dbt_transform",
    description="dbt staging + intermediate models (Silver → pre-Gold)",
    default_args=DEFAULT_ARGS,
    schedule=None,
    start_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
    catchup=False,
    max_active_runs=1,
    tags=["jeepney", "dbt", "transform"],
) as dag:

    # ── Step 0: install / refresh dbt packages ────────────────────────────────
    dbt_deps = BashOperator(
        task_id="dbt_deps",
        bash_command=f"{DBT_CMD} deps {PROFILES_ARG}",
        env=DBT_ENV,
    )

    # ── Step 1: compile-only pass ─────────────────────────────────────────────
    # Resolves all ref() and source() calls and validates Jinja syntax without
    # writing anything to the database. Fails fast on any config/syntax error.
    dbt_compile = BashOperator(
        task_id="dbt_compile",
        bash_command=f"{DBT_CMD} compile {PROFILES_ARG}",
        env=DBT_ENV,
    )

    # ── Step 2: Staging models ────────────────────────────────────────────────
    dbt_run_staging = BashOperator(
        task_id="dbt_run_staging",
        bash_command=f"{DBT_CMD} run --select staging {PROFILES_ARG}",
        env=DBT_ENV,
    )

    dbt_test_staging = BashOperator(
        task_id="dbt_test_staging",
        bash_command=f"{DBT_CMD} test --select staging {PROFILES_ARG}",
        env=DBT_ENV,
    )

    # ── Step 3: Intermediate models ───────────────────────────────────────────
    dbt_run_intermediate = BashOperator(
        task_id="dbt_run_intermediate",
        bash_command=f"{DBT_CMD} run --select intermediate {PROFILES_ARG}",
        env=DBT_ENV,
    )

    dbt_test_intermediate = BashOperator(
        task_id="dbt_test_intermediate",
        bash_command=f"{DBT_CMD} test --select intermediate {PROFILES_ARG}",
        env=DBT_ENV,
    )

    validate_int_passenger_features = BashOperator(
        task_id="validate_int_passenger_features",
        bash_command=(
            "python -c \""
            "import psycopg2, os; "
            "conn = psycopg2.connect("
            "  host='postgres', dbname='jeepney_dw',"
            "  user=os.environ['SVC_PIPELINE_USER'],"
            "  password=os.environ['SVC_PIPELINE_PASSWORD']"
            "); "
            "cur = conn.cursor(); "
            "cur.execute('SELECT COUNT(*) FROM staging.int_passenger_features'); "
            "n = cur.fetchone()[0]; "
            "print(f'int_passenger_features: {n:,} rows'); "
            "assert n > 0, 'int_passenger_features is empty — clustering will fail!'; "
            "conn.close()"
            "\""
        ),
        env=DBT_ENV,
    )

    trigger_science = TriggerDagRunOperator(
        task_id="trigger_dag_04_science",
        trigger_dag_id="dag_04_science",
        wait_for_completion=False,
        reset_dag_run=True,
    )

    # ── Task flow ─────────────────────────────────────────────────────────────
    (
        dbt_deps
        >> dbt_compile
        >> dbt_run_staging
        >> dbt_test_staging
        >> dbt_run_intermediate
        >> dbt_test_intermediate
        >> validate_int_passenger_features
        >> trigger_science
    )
