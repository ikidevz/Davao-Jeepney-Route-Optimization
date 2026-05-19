-- =============================================================================
-- 04_database.sql
-- Davao Jeepney Route Optimization — Data Lakehouse
-- PURPOSE : Apply database-level metadata and governance comment to jeepney_dw
-- RUN AS  : postgres superuser
-- ORDER   : Run AFTER 03_init_databases.sql
-- NOTE    : The database itself (jeepney_dw) is created by Docker Compose via
--           the POSTGRES_DB environment variable — we do NOT run CREATE DATABASE
--           here to avoid transaction block conflicts. This file only applies
--           the governance comment and confirms we are on the right database.
-- =============================================================================

DO $$
BEGIN
  IF current_database() <> 'jeepney_dw' THEN
    RAISE EXCEPTION
      'Wrong database: connected to % — expected jeepney_dw. Aborting.',
      current_database();
  END IF;
  RAISE NOTICE 'Connected to correct database: jeepney_dw.';
END $$;


COMMENT ON DATABASE jeepney_dw IS
  'Davao Jeepney Route Optimization — Lightweight Data Lakehouse. '
  'Owner: Data Engineering Team. '
  'Schemas: staging (Silver — cleaned/typed), marts (Gold — aggregated/BI-ready). '
  'Bronze layer (raw Parquet) lives in MinIO: s3://raw/jeepney/. '
  'FastAPI ingestion service writes Bronze. dbt builds Silver and Gold. '
  'Do not run DDL directly — use init scripts in order (01 through 08).';

-- =============================================================================
-- END OF 04_database.sql
-- =============================================================================
