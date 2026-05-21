-- =============================================================================
-- 02_users.sql
-- Davao Jeepney Route Optimization — Data Lakehouse
-- PURPOSE : Create the three service login users and assign roles
-- RUN AS  : postgres superuser
-- ORDER   : Run AFTER 01_roles.sql
--
-- Users
--   svc_pipeline → jeepney_admin  — dbt, Airflow, all pipeline scripts
--   svc_fastapi  → jeepney_writer — FastAPI ingestion (INSERT on staging only)
--   svc_bi       → jeepney_reader — Superset + Streamlit (SELECT on marts only)
--
-- NOTE: Passwords must match .env. In production use a secrets manager.
-- =============================================================================

-- svc_pipeline
DO $$ BEGIN
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

-- svc_fastapi
DO $$ BEGIN
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

-- svc_bi
DO $$ BEGIN
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