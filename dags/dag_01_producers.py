"""
dag_01_producers.py
--------------------
DAG 1 — Synthetic Data Production
Schedule: Daily at 06:00 PHT (UTC+8 = 22:00 UTC previous day)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from airflow import DAG
from airflow.providers.standard.operators.bash import BashOperator
from airflow.providers.standard.operators.trigger_dagrun import TriggerDagRunOperator

# ---------------------------------------------------------------------------
# Default args
# ---------------------------------------------------------------------------
DEFAULT_ARGS = {
    "owner":            "jeepney-pipeline",
    "depends_on_past":  False,
    "email_on_failure": False,
    "email_on_retry":   False
}


with DAG(
    dag_id="dag_01_producers",
    description="Synthetic data production — POST to FastAPI → Parquet in MinIO",
    default_args=DEFAULT_ARGS,
    schedule="0 22 * * *",
    start_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
    catchup=False,
    max_active_runs=1,
    tags=["jeepney", "producers", "bronze"],
) as dag:

    # Health-check FastAPI before producing
    check_fastapi = BashOperator(
        task_id="check_fastapi_health",
        bash_command=(
            "for i in $(seq 1 10); do "
            "  curl -sf http://fastapi:8000/health && exit 0; "
            "  echo 'FastAPI not ready, retrying in 10s...'; sleep 10; "
            "done; "
            "echo 'FastAPI health check failed after 10 attempts'; exit 1"
        ),
    )

    run_all_producers = BashOperator(
        task_id="run_all_producers",
        bash_command="python /opt/airflow/producers/produce_all.py",
        env={
            "FASTAPI_URL":      "http://fastapi:8000",
            "PYTHONUNBUFFERED": "1",
        },
    )

    verify_minio = BashOperator(
        task_id="verify_minio_parquet",
        bash_command=(
            "python -c \""
            "import boto3, os; "
            "s3 = boto3.client("
            "  's3',"
            "  endpoint_url='http://minio:9000',"
            "  aws_access_key_id=os.environ['MINIO_ACCESS_KEY'],"
            "  aws_secret_access_key=os.environ['MINIO_SECRET_KEY']"
            "); "
            "result = s3.list_objects_v2(Bucket=os.environ['MINIO_BUCKET'], Prefix='jeepney/'); "
            "objs = result.get('Contents', []); "
            "print(f'MinIO: {len(objs)} objects found in raw/jeepney/'); "
            "assert len(objs) > 0, 'No Parquet files found in MinIO!'"
            "\""
        ),
    )

    trigger_ingestion = TriggerDagRunOperator(
        task_id="trigger_dag_02_ingestion",
        trigger_dag_id="dag_02_ingestion",
        wait_for_completion=False,
        reset_dag_run=True,
    )

    check_fastapi >> run_all_producers >> verify_minio >> trigger_ingestion
