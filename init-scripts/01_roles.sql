-- =============================================================================
-- 01_roles.sql
-- Davao Jeepney Route Optimization — Data Lakehouse
-- PURPOSE : Create the three permission roles used by all service users
-- RUN AS  : postgres superuser (jeepney_user_admin via Docker init)
-- ORDER   : Run FIRST — everything else depends on these roles
-- =============================================================================

-- jeepney_admin  — full DDL + DML on staging + marts (dbt, Airflow, scripts)
-- jeepney_writer — INSERT on staging only (FastAPI ingestion)
-- jeepney_reader — SELECT on marts only  (Superset, Streamlit)

DO $$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'jeepney_admin') THEN
    CREATE ROLE jeepney_admin  NOLOGIN;
    RAISE NOTICE 'Role jeepney_admin created.';
  ELSE
    RAISE NOTICE 'Role jeepney_admin already exists — skipping.';
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'jeepney_writer') THEN
    CREATE ROLE jeepney_writer NOLOGIN;
    RAISE NOTICE 'Role jeepney_writer created.';
  ELSE
    RAISE NOTICE 'Role jeepney_writer already exists — skipping.';
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'jeepney_reader') THEN
    CREATE ROLE jeepney_reader NOLOGIN;
    RAISE NOTICE 'Role jeepney_reader created.';
  ELSE
    RAISE NOTICE 'Role jeepney_reader already exists — skipping.';
  END IF;
END $$;

-- =============================================================================
-- END OF 01_roles.sql
-- =============================================================================