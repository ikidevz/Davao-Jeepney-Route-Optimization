-- =============================================================================
-- 03_init_databases.sql
-- Davao Jeepney Route Optimization — Data Lakehouse
-- PURPOSE : Create airflow_db, apply DB-level grants, grant public schema access
-- RUN AS  : postgres superuser
-- ORDER   : Run AFTER 02_users.sql (svc_pipeline must exist before GRANT)
-- NOTE    : jeepney_dw is created by Docker Compose via POSTGRES_DB env var.
--           Only airflow_db is created here — it is not managed by Compose.
--           DB-level grants for both databases live here (not in 02_users.sql)
--           because airflow_db does not exist until this script runs.
-- =============================================================================

SELECT 'CREATE DATABASE airflow_db OWNER jeepney_user_admin'
  WHERE NOT EXISTS (
    SELECT FROM pg_database WHERE datname = 'airflow_db'
  )\gexec

GRANT ALL PRIVILEGES ON DATABASE airflow_db TO svc_pipeline;
GRANT ALL PRIVILEGES ON DATABASE jeepney_dw  TO svc_pipeline;

\c airflow_db

COMMENT ON DATABASE airflow_db IS
  'Airflow metadata database. Stores DAG runs, task instances, connections, '
  'variables, and logs. Managed by Airflow — do not modify directly. '
  'Owner: postgres (superuser). Used by: svc_pipeline (Airflow scheduler/worker).';

GRANT ALL ON SCHEMA public TO svc_pipeline;

\c jeepney_dw

-- =============================================================================
-- END OF 03_init_databases.sql
-- =============================================================================