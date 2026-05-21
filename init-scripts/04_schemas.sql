-- =============================================================================
-- 04_schemas.sql
-- Davao Jeepney Route Optimization — Data Lakehouse
-- PURPOSE : Create schemas, assign ownership, and set all permissions
-- RUN AS  : postgres superuser
-- ORDER   : Run AFTER 03_init_databases.sql
--
-- All grants live here — nowhere else. This is the single source of truth
-- for who can do what on each schema.
--
-- Access matrix:
--   Schema   │ jeepney_admin (svc_pipeline) │ jeepney_writer (svc_fastapi) │ jeepney_reader (svc_bi)
--   ─────────┼──────────────────────────────┼──────────────────────────────┼─────────────────────────
--   staging  │ ALL                          │ INSERT on tables             │ SELECT (staging only for cross-schema joins)
--   marts    │ ALL                          │ —                            │ SELECT
-- =============================================================================

-- Guard: must be connected to jeepney_dw
DO $$ BEGIN
  IF current_database() <> 'jeepney_dw' THEN
    RAISE EXCEPTION 'Wrong database: % — expected jeepney_dw.', current_database();
  END IF;
END $$;

COMMENT ON DATABASE jeepney_dw IS
  'Davao Jeepney Route Optimization — Lightweight Data Lakehouse. '
  'Schemas: staging (Silver), marts (Gold). '
  'Bronze layer (raw Parquet) lives in MinIO: s3://raw/jeepney/. '
  'FastAPI writes Bronze. dbt builds Silver and Gold. '
  'Run init scripts 01–07 in order to set up. Do not run DDL directly.';


-- =============================================================================
-- SCHEMAS
-- Both owned by svc_pipeline so dbt (which runs as svc_pipeline) can
-- CREATE/DROP/ALTER tables freely without needing superuser.
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS staging AUTHORIZATION svc_pipeline;

COMMENT ON SCHEMA staging IS
  'Silver layer. Cleaned and typed data loaded from MinIO Parquet via ingest_to_postgres.py. '
  'Tables: stg_routes, stg_stops, stg_operators, stg_vehicles, stg_trips, '
  'stg_passenger_survey, stg_ab_experiment. Owner: svc_pipeline.';

CREATE SCHEMA IF NOT EXISTS marts AUTHORIZATION svc_pipeline;

COMMENT ON SCHEMA marts IS
  'Gold layer. Aggregated BI-ready tables built entirely by dbt. '
  'Tables: mart_route_summary, mart_district_ridership, '
  'mart_commuter_clusters, mart_ab_test_results. Owner: svc_pipeline.';


-- =============================================================================
-- SCHEMA-LEVEL GRANTS
-- USAGE lets a role see inside the schema and reference its objects.
-- Without USAGE, table-level grants are useless.
-- =============================================================================

GRANT ALL   ON SCHEMA staging TO jeepney_admin;
GRANT USAGE ON SCHEMA staging TO jeepney_writer;
GRANT USAGE ON SCHEMA staging TO jeepney_reader;  -- needed for cross-schema joins from marts

GRANT ALL   ON SCHEMA marts   TO jeepney_admin;
GRANT USAGE ON SCHEMA marts   TO jeepney_reader;


-- =============================================================================
-- DEFAULT PRIVILEGES
-- Applied to tables and sequences created in the future by svc_pipeline
-- (i.e. every dbt run). This is what makes grants survive dbt table rebuilds —
-- dbt drops and recreates tables, so without default privileges, permissions
-- would reset to nothing after every run.
-- =============================================================================

-- staging — future tables
ALTER DEFAULT PRIVILEGES FOR ROLE svc_pipeline IN SCHEMA staging
  GRANT ALL    ON TABLES    TO jeepney_admin;
ALTER DEFAULT PRIVILEGES FOR ROLE svc_pipeline IN SCHEMA staging
  GRANT INSERT ON TABLES    TO jeepney_writer;
ALTER DEFAULT PRIVILEGES FOR ROLE svc_pipeline IN SCHEMA staging
  GRANT SELECT ON TABLES    TO jeepney_reader;

-- staging — future sequences
ALTER DEFAULT PRIVILEGES FOR ROLE svc_pipeline IN SCHEMA staging
  GRANT ALL              ON SEQUENCES TO jeepney_admin;
ALTER DEFAULT PRIVILEGES FOR ROLE svc_pipeline IN SCHEMA staging
  GRANT USAGE, SELECT    ON SEQUENCES TO jeepney_writer;

-- marts — future tables
ALTER DEFAULT PRIVILEGES FOR ROLE svc_pipeline IN SCHEMA marts
  GRANT ALL    ON TABLES    TO jeepney_admin;
ALTER DEFAULT PRIVILEGES FOR ROLE svc_pipeline IN SCHEMA marts
  GRANT SELECT ON TABLES    TO jeepney_reader;

-- marts — future sequences
ALTER DEFAULT PRIVILEGES FOR ROLE svc_pipeline IN SCHEMA marts
  GRANT ALL    ON SEQUENCES TO jeepney_admin;

-- =============================================================================
-- END OF 04_schemas.sql
-- =============================================================================

-- =============================================================================
-- INTERMEDIATE SCHEMA
-- Pre-Gold aggregations built by dbt (e.g. int_passenger_features).
-- Used by dag_03_dbt_transform before clustering runs.
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS intermediate AUTHORIZATION svc_pipeline;

COMMENT ON SCHEMA intermediate IS
  'Pre-Gold layer. Intermediate dbt models (e.g. int_passenger_features). '
  'Built before marts — feeds science/clustering.py. Owner: svc_pipeline.';

GRANT ALL   ON SCHEMA intermediate TO jeepney_admin;
GRANT USAGE ON SCHEMA intermediate TO jeepney_reader;

ALTER DEFAULT PRIVILEGES FOR ROLE svc_pipeline IN SCHEMA intermediate
  GRANT ALL    ON TABLES    TO jeepney_admin;
ALTER DEFAULT PRIVILEGES FOR ROLE svc_pipeline IN SCHEMA intermediate
  GRANT SELECT ON TABLES    TO jeepney_reader;

-- =============================================================================
-- STAGING_VIEWS SCHEMA
-- dbt staging models (views) land here — separate from the staging source
-- tables to avoid name collisions. dbt would otherwise try to swap a view
-- named stg_routes over the existing stg_routes TABLE, causing deadlocks.
--
-- Access: same as staging — writer can INSERT (for any future use),
--         reader can SELECT (for cross-schema joins from marts).
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS staging_views AUTHORIZATION svc_pipeline;

COMMENT ON SCHEMA staging_views IS
  'dbt-managed Silver views. Mirrors staging source tables as clean SELECT views. '
  'Kept separate from staging to prevent dbt view-swap deadlocks on source tables. '
  'Owner: svc_pipeline.';

GRANT ALL   ON SCHEMA staging_views TO jeepney_admin;
GRANT USAGE ON SCHEMA staging_views TO jeepney_reader;
GRANT USAGE ON SCHEMA staging_views TO jeepney_writer;

ALTER DEFAULT PRIVILEGES FOR ROLE svc_pipeline IN SCHEMA staging_views
  GRANT ALL    ON TABLES TO jeepney_admin;
ALTER DEFAULT PRIVILEGES FOR ROLE svc_pipeline IN SCHEMA staging_views
  GRANT SELECT ON TABLES TO jeepney_reader;