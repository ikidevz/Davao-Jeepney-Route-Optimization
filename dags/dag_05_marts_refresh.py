"""
dag_05_marts_refresh.py
------------------------
DAG 5 — Gold Layer Mart Refresh
Schedule: Triggered after dag_04_science
"""

from __future__ import annotations
import os
from datetime import datetime, timezone

from airflow import DAG
from airflow.providers.standard.operators.bash import BashOperator

DEFAULT_ARGS = {
    "owner":            "jeepney-pipeline",
    "depends_on_past":  False,
    "email_on_failure": False,
    "email_on_retry":   False,
}

DBT_DIR = "/opt/airflow/dbt"
DBT_CMD = f"cd {DBT_DIR} && dbt --no-partial-parse"
PROFILES_ARG = f"--profiles-dir {DBT_DIR}"

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

SCIENCE_DIR = "/opt/airflow/science"
_CONFIRM_SCIENCE = """python - <<'PYEOF'
import psycopg2, os
from pathlib import Path

conn = psycopg2.connect(
    host='postgres', dbname='jeepney_dw',
    user=os.environ['SVC_PIPELINE_USER'],
    password=os.environ['SVC_PIPELINE_PASSWORD'],
)
cur = conn.cursor()

# Check cluster labels written by clustering.py
cur.execute('SELECT COUNT(*) FROM raw.stg_passenger_survey WHERE cluster_id IS NOT NULL')
n = cur.fetchone()[0]
print(f'Passengers with cluster labels: {n:,}')
assert n > 0, 'clustering.py has not written labels yet -- dag_04 may not have completed'

conn.close()

# ab_testing.py writes stats directly to marts.mart_ab_test_results (no ALTER TABLE).
# That mart table does not exist yet at this point (dag_05 builds it below).
# The only pre-dag_05 evidence ab_testing.py ran is its parquet output.
ab_stat = Path('/opt/airflow/science/parquet/ab_test_statistics.parquet')
assert ab_stat.exists(), 'ab_test_statistics.parquet not found -- ab_testing.py has not run yet'

import pyarrow.parquet as pq
t = pq.read_table(str(ab_stat))
print(f'ab_test_statistics.parquet: {t.num_rows} test results found')
assert t.num_rows >= 3, f'Expected at least 3 stat results, got {t.num_rows}'

print('Science outputs confirmed ready.')
PYEOF
"""

_VALIDATE_MART_COUNTS = """\
python - <<'PYEOF'
import psycopg2, os
conn = psycopg2.connect(
    host='postgres', dbname='jeepney_dw',
    user=os.environ['SVC_PIPELINE_USER'],
    password=os.environ['SVC_PIPELINE_PASSWORD'],
)
cur = conn.cursor()
marts = ['mart_route_summary', 'mart_district_ridership',
         'mart_commuter_clusters', 'mart_ab_test_results']
for m in marts:
    cur.execute(f'SELECT COUNT(*) FROM marts.{m}')
    print(f'{m}: {cur.fetchone()[0]:,} rows')
conn.close()
PYEOF
"""

_VALIDATE_CLUSTER_MART = """\
python - <<'PYEOF'
import psycopg2, os
conn = psycopg2.connect(
    host='postgres', dbname='jeepney_dw',
    user=os.environ['SVC_PIPELINE_USER'],
    password=os.environ['SVC_PIPELINE_PASSWORD'],
)
cur = conn.cursor()
cur.execute(
    'SELECT cluster_label, COUNT(*) FROM marts.mart_commuter_clusters'
    ' GROUP BY cluster_label ORDER BY cluster_label'
)
rows = cur.fetchall()
for r in rows:
    print(f'  {r[0]}: {r[1]:,} passengers')
null_check = [r for r in rows if r[0] is None]
assert not null_check, 'NULL cluster labels found in mart_commuter_clusters!'
conn.close()
PYEOF
"""

_VALIDATE_AB_MART = """\
python - <<'PYEOF'
import psycopg2, os
conn = psycopg2.connect(
    host='postgres', dbname='jeepney_dw',
    user=os.environ['SVC_PIPELINE_USER'],
    password=os.environ['SVC_PIPELINE_PASSWORD'],
)
cur = conn.cursor()
cur.execute('SELECT COUNT(*) FROM marts.mart_ab_test_results WHERE p_value IS NULL')
null_count = cur.fetchone()[0]
print(f'mart_ab_test_results rows with NULL p_value: {null_count}')
assert null_count == 0, 'NULL p_values found — ab_testing.py may not have run'
cur.execute(
    'SELECT is_significant, COUNT(*) FROM marts.mart_ab_test_results'
    ' GROUP BY is_significant'
)
for r in cur.fetchall():
    print(f'  is_significant={r[0]}: {r[1]:,} rows')
conn.close()
PYEOF
"""


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
        task_id="confirm_science_outputs_ready",
        bash_command=_CONFIRM_SCIENCE,
        env=DBT_ENV,
    )

    dbt_run_marts = BashOperator(
        task_id="dbt_run_marts",
        bash_command=f"{DBT_CMD} run --select marts {PROFILES_ARG}",
        env=DBT_ENV,
    )

    # Mart tables now exist — safe to export them to Parquet.
    # Moved out of dag_04: export_to_parquet.py reads from
    # marts.mart_commuter_clusters + marts.mart_ab_test_results,
    # which don't exist until dbt_run_marts completes above.
    run_export_mart_parquets = BashOperator(
        task_id="run_export_mart_parquets",
        bash_command=f"python {SCIENCE_DIR}/export_to_parquet.py --marts-only",
        env=DBT_ENV,
    )

    dbt_test_marts = BashOperator(
        task_id="dbt_test_marts",
        bash_command=f"{DBT_CMD} test --select marts {PROFILES_ARG}",
        env=DBT_ENV,
    )

    validate_mart_counts = BashOperator(
        task_id="validate_mart_row_counts",
        bash_command=_VALIDATE_MART_COUNTS,
        env=DBT_ENV,
    )

    validate_cluster_mart = BashOperator(
        task_id="validate_cluster_labels_in_mart",
        bash_command=_VALIDATE_CLUSTER_MART,
        env=DBT_ENV,
    )

    validate_ab_mart = BashOperator(
        task_id="validate_ab_pvalues_in_mart",
        bash_command=_VALIDATE_AB_MART,
        env=DBT_ENV,
    )

    pipeline_complete = BashOperator(
        task_id="pipeline_complete_notification",
        bash_command=(
            "echo '=== DAVAO JEEPNEY PIPELINE COMPLETE ==='\n"
            "echo 'All 5 DAGs completed successfully.'\n"
            "echo 'Services ready:'\n"
            "echo '  Superset:  http://localhost:8088'\n"
            "echo '  Streamlit: http://localhost:8501'\n"
            "echo '  Airflow:   http://localhost:8080'\n"
            "echo '  MinIO:     http://localhost:9001'\n"
        ),
    )

    (
        wait_for_science
        >> dbt_run_marts
        >> run_export_mart_parquets
        >> dbt_test_marts
        >> validate_mart_counts
        >> validate_cluster_mart
        >> validate_ab_mart
        >> pipeline_complete
    )
