-- =============================================================================
-- 01_roles.sql
-- Davao Jeepney Route Optimization — Data Lakehouse
-- PURPOSE : Create PostgreSQL roles (cluster-level — no schema dependency)
-- RUN AS  : postgres superuser
-- ORDER   : Run FIRST. Roles are cluster-wide, not database-scoped.
-- SAFE    : All CREATE ROLE statements are idempotent via IF NOT EXISTS check
-- =============================================================================

DO $$
BEGIN

  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'jeepney_admin') THEN
    CREATE ROLE jeepney_admin  NOLOGIN;
    RAISE NOTICE 'Role jeepney_admin created.';
  ELSE
    RAISE NOTICE 'Role jeepney_admin already exists — skipped.';
  END IF;

  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'jeepney_writer') THEN
    CREATE ROLE jeepney_writer NOLOGIN;
    RAISE NOTICE 'Role jeepney_writer created.';
  ELSE
    RAISE NOTICE 'Role jeepney_writer already exists — skipped.';
  END IF;

  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'jeepney_reader') THEN
    CREATE ROLE jeepney_reader NOLOGIN;
    RAISE NOTICE 'Role jeepney_reader created.';
  ELSE
    RAISE NOTICE 'Role jeepney_reader already exists — skipped.';
  END IF;

END $$;

-- =============================================================================
-- END OF 01_roles.sql
-- =============================================================================
