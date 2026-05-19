-- =============================================================================
-- 02_users.sql
-- Davao Jeepney Route Optimization — Data Lakehouse
-- PURPOSE : Create application login users and assign them to roles
-- RUN AS  : postgres superuser
-- ORDER   : Run AFTER 01_roles.sql
-- SAFE    : All CREATE USER statements are idempotent via IF NOT EXISTS check
-- NOTE    : Passwords here must match what is defined in .env
--           In production, override via environment variables and use
--           pg_hba.conf + secrets manager — never commit real passwords.
-- =============================================================================


-- svc_pipeline — dbt, Airflow scheduler/worker, all pipeline scripts
-- Password matches SVC_PIPELINE_PASSWORD in .env
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'svc_pipeline') THEN
    CREATE USER svc_pipeline
      WITH PASSWORD 'pipeline_pass_123'
      CONNECTION LIMIT 20
      VALID UNTIL 'infinity';
    RAISE NOTICE 'User svc_pipeline created.';
  ELSE
    ALTER USER svc_pipeline WITH PASSWORD 'pipeline_pass_123';
    RAISE NOTICE 'User svc_pipeline already exists — password synced.';
  END IF;
END $$;

GRANT jeepney_admin TO svc_pipeline;

-- svc_fastapi — FastAPI Bronze ingestion service (INSERT only on staging)
-- Password matches SVC_FASTAPI_PASSWORD in .env
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'svc_fastapi') THEN
    CREATE USER svc_fastapi
      WITH PASSWORD 'fastapi_pass_123'
      CONNECTION LIMIT 10
      VALID UNTIL 'infinity';
    RAISE NOTICE 'User svc_fastapi created.';
  ELSE
    ALTER USER svc_fastapi WITH PASSWORD 'fastapi_pass_123';
    RAISE NOTICE 'User svc_fastapi already exists — password synced.';
  END IF;
END $$;

GRANT jeepney_writer TO svc_fastapi;


-- svc_bi — Apache Superset and Streamlit (SELECT only on marts)
-- Password matches SVC_BI_PASSWORD in .env
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'svc_bi') THEN
    CREATE USER svc_bi
      WITH PASSWORD 'bi_pass_123'
      CONNECTION LIMIT 20
      VALID UNTIL 'infinity';
    RAISE NOTICE 'User svc_bi created.';
  ELSE
    ALTER USER svc_bi WITH PASSWORD 'bi_pass_123';
    RAISE NOTICE 'User svc_bi already exists — password synced.';
  END IF;
END $$;

GRANT jeepney_reader TO svc_bi;

-- =============================================================================
-- END OF 02_users.sql
-- =============================================================================