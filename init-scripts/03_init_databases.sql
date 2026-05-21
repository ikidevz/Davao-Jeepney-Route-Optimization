-- =============================================================================
-- 03_init_databases.sql
-- Davao Jeepney Route Optimization — Data Lakehouse
-- PURPOSE : Create airflow_db and apply database-level grants
-- RUN AS  : postgres superuser
-- ORDER   : Run AFTER 02_users.sql
--
-- NOTE: jeepney_dw is created by Docker Compose via POSTGRES_DB.
--       Only airflow_db is created here.
-- =============================================================================

-- Create airflow_db if it doesn't exist yet
SELECT 'CREATE DATABASE airflow_db OWNER jeepney_user_admin'
  WHERE NOT EXISTS (
    SELECT FROM pg_database WHERE datname = 'airflow_db'
  )\gexec

-- svc_pipeline needs full access to both databases (runs Airflow + dbt)
GRANT ALL PRIVILEGES ON DATABASE airflow_db TO svc_pipeline;
GRANT ALL PRIVILEGES ON DATABASE jeepney_dw  TO svc_pipeline;

-- Configure airflow_db
\c airflow_db

COMMENT ON DATABASE airflow_db IS
  'Airflow metadata DB. Stores DAG runs, task instances, connections, variables. '
  'Managed entirely by Airflow — do not modify directly. Used by: svc_pipeline.';

GRANT ALL ON SCHEMA public TO svc_pipeline;

-- Return to jeepney_dw for remaining scripts
\c jeepney_dw

-- =============================================================================
-- END OF 03_init_databases.sql
-- =============================================================================