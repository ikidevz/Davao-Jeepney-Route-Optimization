-- =============================================================================
-- 05_schemas.sql
-- Davao Jeepney Route Optimization — Data Lakehouse
-- PURPOSE : Create schemas, assign ownership, apply grants and default privileges
-- =============================================================================


-- -----------------------------------------------------------------------------
-- STAGING SCHEMA — Silver Layer
-- Receives cleaned, typed data from MinIO Parquet via ingest_to_postgres.py
-- Writer: svc_fastapi (INSERT) via ingestion script
-- Owner:  svc_pipeline (CREATE/DROP for dbt)
-- -----------------------------------------------------------------------------

CREATE SCHEMA IF NOT EXISTS staging AUTHORIZATION svc_pipeline;

COMMENT ON SCHEMA staging IS
  'Silver layer. '
  'Source: MinIO Bronze Parquet (s3://raw/jeepney/*) via ingest_to_postgres.py. '
  'Contains one table per entity: routes, stops, operators, vehicles, trips, '
  'passengers, ab_experiment. No business logic — clean and typed only. '
  'Owner: svc_pipeline. Writer: svc_fastapi. Readers: svc_pipeline only.';


-- -----------------------------------------------------------------------------
-- MARTS SCHEMA — Gold Layer
-- Aggregated, BI-ready tables built by dbt
-- Reader: svc_bi (SELECT) for Superset and Streamlit
-- Owner:  svc_pipeline (CREATE/DROP for dbt)
-- -----------------------------------------------------------------------------

CREATE SCHEMA IF NOT EXISTS marts AUTHORIZATION svc_pipeline;

COMMENT ON SCHEMA marts IS
  'Gold layer. Built entirely by dbt models. '
  'mart_commuter_clusters and mart_ab_test_results are populated AFTER '
  'science/clustering.py and science/ab_testing.py write results to staging. '
  'Owner: svc_pipeline. Reader: svc_bi (Superset, Streamlit). '
  'No direct writes by application services.';


-- -----------------------------------------------------------------------------
-- SCHEMA-LEVEL GRANTS
-- -----------------------------------------------------------------------------

-- staging: writer needs USAGE to INSERT; admin needs full control
GRANT USAGE ON SCHEMA staging TO jeepney_writer;
GRANT ALL   ON SCHEMA staging TO jeepney_admin;

-- marts: reader needs USAGE to SELECT; admin needs full control
GRANT USAGE ON SCHEMA marts   TO jeepney_reader;
GRANT ALL   ON SCHEMA marts   TO jeepney_admin;

-- svc_bi also needs USAGE on staging for any cross-schema references
GRANT USAGE ON SCHEMA staging TO jeepney_reader;


-- -----------------------------------------------------------------------------
-- DEFAULT PRIVILEGES — applied to ALL FUTURE tables in each schema
-- This is the fix for the dbt re-grant problem: dbt drops and recreates tables
-- on each run. Without default privileges, permissions reset after every run.
-- Setting them here means every new table inherits the correct grants automatically.
-- -----------------------------------------------------------------------------

-- Tables in staging
ALTER DEFAULT PRIVILEGES FOR ROLE svc_pipeline IN SCHEMA staging
  GRANT INSERT ON TABLES TO jeepney_writer;

ALTER DEFAULT PRIVILEGES FOR ROLE svc_pipeline IN SCHEMA staging
  GRANT ALL ON TABLES TO jeepney_admin;

ALTER DEFAULT PRIVILEGES FOR ROLE svc_pipeline IN SCHEMA staging
  GRANT SELECT ON TABLES TO jeepney_reader; 

-- Tables in marts
ALTER DEFAULT PRIVILEGES FOR ROLE svc_pipeline IN SCHEMA marts
  GRANT SELECT ON TABLES TO jeepney_reader;

ALTER DEFAULT PRIVILEGES FOR ROLE svc_pipeline IN SCHEMA marts
  GRANT ALL ON TABLES TO jeepney_admin;

ALTER DEFAULT PRIVILEGES FOR ROLE svc_pipeline IN SCHEMA staging
  GRANT USAGE, SELECT ON SEQUENCES TO jeepney_writer;

ALTER DEFAULT PRIVILEGES FOR ROLE svc_pipeline IN SCHEMA staging
  GRANT ALL ON SEQUENCES TO jeepney_admin;

ALTER DEFAULT PRIVILEGES FOR ROLE svc_pipeline IN SCHEMA marts
  GRANT ALL ON SEQUENCES TO jeepney_admin;


-- =============================================================================
-- END OF 05_schemas.sql
-- =============================================================================