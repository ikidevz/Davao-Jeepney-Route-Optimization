-- =============================================================================
-- 07_indexes_grants_audit.sql
-- Davao Jeepney Route Optimization — Data Lakehouse
-- PURPOSE : Create indexes, flush table-level grants, create audit table
-- RUN AS  : postgres superuser
-- ORDER   : Run LAST — after 06_tables_marts.sql
--
-- Why the explicit GRANT ON ALL TABLES here?
--   Default privileges in 04_schemas.sql cover tables created AFTER that
--   script runs. These explicit grants cover the tables we just created in
--   05 and 06, which were created by the superuser and may have been missed
--   by default privileges. Running both is safe — GRANT is idempotent.
-- =============================================================================

-- Guard: must be connected to jeepney_dw
DO $$ BEGIN
  IF current_database() <> 'jeepney_dw' THEN
    RAISE EXCEPTION 'Wrong database: % — expected jeepney_dw.', current_database();
  END IF;
END $$;


-- =============================================================================
-- SECTION 1 — INDEXES
-- Naming: idx_{schema_abbrev}_{table_abbrev}_{columns}
-- =============================================================================

-- -----------------------------------------------------------------------------
-- staging.stg_trips — highest volume (~500K rows)
-- -----------------------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_stg_trips_route_date
  ON staging.stg_trips (route_id, trip_date);
COMMENT ON INDEX staging.idx_stg_trips_route_date IS
  'Supports dbt mart_route_summary aggregation and Superset route+date filters.';

CREATE INDEX IF NOT EXISTS idx_stg_trips_vehicle_date
  ON staging.stg_trips (vehicle_id, trip_date);
COMMENT ON INDEX staging.idx_stg_trips_vehicle_date IS
  'Supports vehicle utilization queries.';

CREATE INDEX IF NOT EXISTS idx_stg_trips_date
  ON staging.stg_trips (trip_date);
COMMENT ON INDEX staging.idx_stg_trips_date IS
  'Supports date range filters in Superset dashboards.';

CREATE INDEX IF NOT EXISTS idx_stg_trips_time_period
  ON staging.stg_trips (time_period);
COMMENT ON INDEX staging.idx_stg_trips_time_period IS
  'Supports peak vs off-peak breakdowns in Superset heatmaps.';

CREATE INDEX IF NOT EXISTS idx_stg_trips_rainy
  ON staging.stg_trips (is_rainy_day, trip_date);
COMMENT ON INDEX staging.idx_stg_trips_rainy IS
  'Supports rain impact analysis charts in Dashboard 1.';

-- -----------------------------------------------------------------------------
-- staging.stg_passenger_survey — clustering reads and district filters
-- -----------------------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_stg_survey_district
  ON staging.stg_passenger_survey (origin_district);
COMMENT ON INDEX staging.idx_stg_survey_district IS
  'Supports district-level aggregation in mart_district_ridership.';

CREATE INDEX IF NOT EXISTS idx_stg_survey_cluster
  ON staging.stg_passenger_survey (cluster_id);
COMMENT ON INDEX staging.idx_stg_survey_cluster IS
  'Supports fast lookup of cluster members after clustering.py writes labels.';

CREATE INDEX IF NOT EXISTS idx_stg_survey_satisfaction
  ON staging.stg_passenger_survey (satisfaction_score, cluster_id);
COMMENT ON INDEX staging.idx_stg_survey_satisfaction IS
  'Supports identifying worst-served cluster (lowest avg satisfaction).';

-- -----------------------------------------------------------------------------
-- staging.stg_ab_experiment
-- -----------------------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_stg_ab_group_week
  ON staging.stg_ab_experiment ("group", test_week);
COMMENT ON INDEX staging.idx_stg_ab_group_week IS
  'Supports weekly control vs treatment breakdowns in ab_testing.py.';

CREATE INDEX IF NOT EXISTS idx_stg_ab_passenger
  ON staging.stg_ab_experiment (passenger_id);
COMMENT ON INDEX staging.idx_stg_ab_passenger IS
  'Supports FK join to stg_passenger_survey in dbt mart_ab_test_results.';

-- -----------------------------------------------------------------------------
-- marts.mart_route_summary — primary Superset Dashboard 1 table
-- -----------------------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_mart_rs_date
  ON marts.mart_route_summary (trip_date);
COMMENT ON INDEX marts.idx_mart_rs_date IS
  'Supports date range filters in Dashboard 1.';

CREATE INDEX IF NOT EXISTS idx_mart_rs_district
  ON marts.mart_route_summary (district_covered);
COMMENT ON INDEX marts.idx_mart_rs_district IS
  'Supports district filter in Dashboard 1 filter box.';

CREATE INDEX IF NOT EXISTS idx_mart_rs_rainy
  ON marts.mart_route_summary (is_rainy_day, trip_date);
COMMENT ON INDEX marts.idx_mart_rs_rainy IS
  'Supports rainy day toggle filter in Dashboard 1.';

-- -----------------------------------------------------------------------------
-- marts.mart_district_ridership — primary Superset Dashboard 2 table
-- -----------------------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_mart_dr_date
  ON marts.mart_district_ridership (trip_date);
COMMENT ON INDEX marts.idx_mart_dr_date IS
  'Supports date range filters in Dashboard 2.';

CREATE INDEX IF NOT EXISTS idx_mart_dr_district
  ON marts.mart_district_ridership (district);
COMMENT ON INDEX marts.idx_mart_dr_district IS
  'Supports district selector filter in Dashboard 2.';

-- -----------------------------------------------------------------------------
-- marts.mart_commuter_clusters
-- -----------------------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_mart_mcc_cluster
  ON marts.mart_commuter_clusters (cluster_id, cluster_label);
COMMENT ON INDEX marts.idx_mart_mcc_cluster IS
  'Supports cluster profile table and distribution chart in Dashboard 2.';

CREATE INDEX IF NOT EXISTS idx_mart_mcc_district
  ON marts.mart_commuter_clusters (origin_district, cluster_id);
COMMENT ON INDEX marts.idx_mart_mcc_district IS
  'Supports district vs cluster cross-tab in Streamlit cluster explorer.';

CREATE INDEX IF NOT EXISTS idx_mart_mcc_ab_eligible
  ON marts.mart_commuter_clusters (is_ab_test_eligible)
  WHERE is_ab_test_eligible = TRUE;
COMMENT ON INDEX marts.idx_mart_mcc_ab_eligible IS
  'Partial index — fast lookup of Cluster 3 (A/B test target) passengers only.';

-- -----------------------------------------------------------------------------
-- marts.mart_ab_test_results
-- -----------------------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_mart_ab_group_week
  ON marts.mart_ab_test_results ("group", test_week);
COMMENT ON INDEX marts.idx_mart_ab_group_week IS
  'Supports weekly satisfaction trend line chart in Dashboard 3.';

CREATE INDEX IF NOT EXISTS idx_mart_ab_significant
  ON marts.mart_ab_test_results (is_significant)
  WHERE is_significant IS NOT NULL;
COMMENT ON INDEX marts.idx_mart_ab_significant IS
  'Partial index — used after ab_testing.py populates statistical columns.';


-- =============================================================================
-- SECTION 2 — FLUSH TABLE-LEVEL GRANTS
-- Covers tables created in scripts 05 and 06 (created by superuser, so
-- the default privileges set in 04_schemas.sql may not have applied).
-- Safe to run repeatedly — GRANT is idempotent in PostgreSQL.
-- =============================================================================

-- staging
GRANT ALL    ON ALL TABLES    IN SCHEMA staging TO jeepney_admin;
GRANT INSERT ON ALL TABLES    IN SCHEMA staging TO jeepney_writer;
GRANT SELECT ON ALL TABLES    IN SCHEMA staging TO jeepney_reader;
GRANT ALL    ON ALL SEQUENCES IN SCHEMA staging TO jeepney_admin;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA staging TO jeepney_writer;

-- marts
GRANT ALL    ON ALL TABLES    IN SCHEMA marts   TO jeepney_admin;
GRANT SELECT ON ALL TABLES    IN SCHEMA marts   TO jeepney_reader;
GRANT ALL    ON ALL SEQUENCES IN SCHEMA marts   TO jeepney_admin;


-- =============================================================================
-- SECTION 3 — AUDIT TABLE
-- Tracks when each init script last ran. Internal only — not exposed to svc_bi.
-- Stored in staging schema with a _ prefix to signal it is a system table.
-- =============================================================================

CREATE TABLE IF NOT EXISTS staging._init_audit (
  script_name  VARCHAR(100)  NOT NULL,
  run_at       TIMESTAMP     NOT NULL  DEFAULT NOW(),
  run_by       VARCHAR(100)  NOT NULL  DEFAULT current_user,
  db_name      VARCHAR(100)  NOT NULL  DEFAULT current_database(),
  pg_version   VARCHAR(200)  NOT NULL  DEFAULT version(),
  notes        TEXT,

  CONSTRAINT pk_init_audit PRIMARY KEY (script_name, run_at)
);

COMMENT ON TABLE staging._init_audit IS
  'Tracks execution of each SQL init script. '
  'Prefix _ = internal/system table — not exposed to svc_bi or Superset.';
COMMENT ON COLUMN staging._init_audit.script_name IS
  'Filename of the init script (e.g. 01_roles.sql).';
COMMENT ON COLUMN staging._init_audit.run_by IS
  'PostgreSQL user who ran the script. Captured via current_user.';

-- Audit table is internal — remove the blanket staging SELECT granted above
REVOKE SELECT ON staging._init_audit FROM jeepney_reader;

-- Log that this final script ran successfully
INSERT INTO staging._init_audit (script_name, notes)
VALUES (
  '07_indexes_grants_audit.sql',
  'Final init script. All indexes, grants, and audit table created successfully.'
);


-- =============================================================================
-- VERIFICATION QUERY (uncomment to run after all scripts complete)
-- Expected: 7 staging tables + 4 mart tables = 11 user tables, plus _init_audit
-- =============================================================================

-- SELECT
--   table_schema  AS schema,
--   table_name,
--   obj_description(
--     (quote_ident(table_schema) || '.' || quote_ident(table_name))::regclass,
--     'pg_class'
--   ) AS comment
-- FROM information_schema.tables
-- WHERE table_schema IN ('staging', 'marts')
--   AND table_type = 'BASE TABLE'
-- ORDER BY table_schema, table_name;

-- =============================================================================
-- END OF 07_indexes_grants_audit.sql
-- =============================================================================