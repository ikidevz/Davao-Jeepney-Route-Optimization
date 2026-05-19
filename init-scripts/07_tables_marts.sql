-- =============================================================================
-- 07_tables_marts.sql
-- Davao Jeepney Route Optimization — Data Lakehouse
-- PURPOSE : Create all Gold layer tables in the marts schema
-- RUN AS  : svc_pipeline (jeepney_admin role)
-- ORDER   : Run AFTER 06_tables_staging.sql
-- NOTE    : All mart tables are built (populated) by dbt at runtime.
--           mart_commuter_clusters and mart_ab_test_results are created here
--           as empty shells — dbt populates them AFTER science/ scripts run.
--           Do NOT insert into these tables manually.
-- =============================================================================


-- =============================================================================
-- 1. marts.mart_route_summary
-- Grain      : One row per route per day
-- Built by   : dbt/models/marts/mart_route_summary.sql
-- Source     : stg_trips JOIN stg_routes JOIN stg_vehicles
-- Volume     : ~4,380 rows (12 routes × 365 days)
-- Serves     : Superset Dashboard 1 — Route Performance Overview
-- =============================================================================

CREATE TABLE IF NOT EXISTS marts.mart_route_summary (
  route_id                VARCHAR(10)     NOT NULL,
  route_name              VARCHAR(100)    NOT NULL,
  district_covered        VARCHAR(50)     NOT NULL,
  trip_date               DATE            NOT NULL,
  total_trips             INTEGER         NOT NULL  DEFAULT 0,
  total_passengers        INTEGER         NOT NULL  DEFAULT 0,
  avg_passengers_per_trip NUMERIC(5,2)    NOT NULL  DEFAULT 0,
  total_revenue_php       NUMERIC(10,2)   NOT NULL  DEFAULT 0,
  revenue_per_km_php      NUMERIC(7,2)    NOT NULL  DEFAULT 0,
  avg_load_factor         NUMERIC(4,3)    NOT NULL  DEFAULT 0,
  avg_travel_time_min     NUMERIC(5,2)    NOT NULL  DEFAULT 0,
  avg_delay_min           NUMERIC(5,2)    NOT NULL  DEFAULT 0,
  on_time_trips           INTEGER         NOT NULL  DEFAULT 0,
  on_time_rate            NUMERIC(4,3)    NOT NULL  DEFAULT 0,
  peak_trips              INTEGER         NOT NULL  DEFAULT 0,
  off_peak_trips          INTEGER         NOT NULL  DEFAULT 0,
  is_rainy_day            BOOLEAN         NOT NULL  DEFAULT FALSE,
  refreshed_at            TIMESTAMP       NOT NULL  DEFAULT NOW(),

  CONSTRAINT pk_mart_route_summary
    PRIMARY KEY (route_id, trip_date),
  CONSTRAINT chk_mart_rs_trips
    CHECK (total_trips >= 0),
  CONSTRAINT chk_mart_rs_passengers
    CHECK (total_passengers >= 0),
  CONSTRAINT chk_mart_rs_revenue
    CHECK (total_revenue_php >= 0),
  CONSTRAINT chk_mart_rs_load_factor
    CHECK (avg_load_factor BETWEEN 0 AND 1.500),
  CONSTRAINT chk_mart_rs_on_time_rate
    CHECK (on_time_rate BETWEEN 0 AND 1),
  CONSTRAINT chk_mart_rs_on_time_count
    CHECK (on_time_trips <= total_trips)
);

COMMENT ON TABLE  marts.mart_route_summary IS
  'Gold: daily route performance KPIs. Grain: one row per route per day. Built by dbt.';
COMMENT ON COLUMN marts.mart_route_summary.on_time_rate IS
  'on_time_trips / total_trips. LTFRB target >= 0.80 (80%).';
COMMENT ON COLUMN marts.mart_route_summary.avg_load_factor IS
  'avg(passengers / capacity). Above 1.0 = overcrowded. Allowed up to 1.5.';
COMMENT ON COLUMN marts.mart_route_summary.revenue_per_km_php IS
  'total_revenue_php / route_length_km. Key profitability metric per route.';
COMMENT ON COLUMN marts.mart_route_summary.refreshed_at IS
  'Timestamp of last dbt run that populated or updated this row.';


-- =============================================================================
-- 2. marts.mart_district_ridership
-- Grain      : One row per district per day
-- Built by   : dbt/models/marts/mart_district_ridership.sql
-- Source     : stg_trips JOIN stg_stops JOIN stg_routes JOIN stg_passenger_survey
-- Volume     : ~4,015 rows (11 districts × 365 days)
-- Serves     : Superset Dashboard 2 — District & Commuter Ridership
-- =============================================================================

CREATE TABLE IF NOT EXISTS marts.mart_district_ridership (
  district                VARCHAR(50)     NOT NULL,
  trip_date               DATE            NOT NULL,
  total_boardings         INTEGER         NOT NULL  DEFAULT 0,
  total_trips_serving     INTEGER         NOT NULL  DEFAULT 0,
  active_routes           INTEGER         NOT NULL  DEFAULT 0,
  avg_wait_time_min       NUMERIC(5,2),             -- NULL if no survey data for district
  avg_satisfaction        NUMERIC(3,2),             -- NULL if no survey data for district
  pct_with_shelter        NUMERIC(4,3)    NOT NULL  DEFAULT 0,
  peak_boardings          INTEGER         NOT NULL  DEFAULT 0,
  weekend_boardings       INTEGER         NOT NULL  DEFAULT 0,
  refreshed_at            TIMESTAMP       NOT NULL  DEFAULT NOW(),

  CONSTRAINT pk_mart_district_ridership
    PRIMARY KEY (district, trip_date),
  CONSTRAINT chk_mart_dr_boardings
    CHECK (total_boardings >= 0),
  CONSTRAINT chk_mart_dr_shelter
    CHECK (pct_with_shelter BETWEEN 0 AND 1),
  CONSTRAINT chk_mart_dr_satisfaction
    CHECK (avg_satisfaction BETWEEN 1 AND 5 OR avg_satisfaction IS NULL),
  CONSTRAINT chk_mart_dr_peak_lte_total
    CHECK (peak_boardings <= total_boardings),
  CONSTRAINT chk_mart_dr_weekend_lte_total
    CHECK (weekend_boardings <= total_boardings)
);

COMMENT ON TABLE  marts.mart_district_ridership IS
  'Gold: daily ridership and service quality by district. '
  'Grain: one row per district per day. 11 Davao districts total. Built by dbt.';
COMMENT ON COLUMN marts.mart_district_ridership.avg_wait_time_min IS
  'Derived from stg_passenger_survey. NULL for districts with no survey respondents.';
COMMENT ON COLUMN marts.mart_district_ridership.avg_satisfaction IS
  'Derived from stg_passenger_survey. NULL for districts with no survey respondents.';
COMMENT ON COLUMN marts.mart_district_ridership.pct_with_shelter IS
  'Proportion of stops in this district that have a waiting shed (0.0–1.0).';


-- =============================================================================
-- 3. marts.mart_commuter_clusters
-- Grain      : One row per passenger with cluster assignment
-- Built by   : dbt/models/marts/mart_commuter_clusters.sql
-- Source     : stg_passenger_survey (after cluster_id populated by clustering.py)
-- Volume     : 5,000 rows
-- Serves     : Superset Dashboard 2 + Streamlit cluster explorer page
-- IMPORTANT  : Created as empty shell here.
--              Populated ONLY after science/clustering.py writes cluster_id
--              and cluster_label back to stg_passenger_survey.
-- =============================================================================

CREATE TABLE IF NOT EXISTS marts.mart_commuter_clusters (
  passenger_id            VARCHAR(15)     NOT NULL,
  origin_barangay         VARCHAR(100)    NOT NULL,
  origin_district         VARCHAR(50)     NOT NULL,
  destination_type        VARCHAR(30)     NOT NULL,
  trip_purpose            VARCHAR(30)     NOT NULL,
  trips_per_week          INTEGER         NOT NULL,
  avg_fare_paid_php       NUMERIC(6,2)    NOT NULL,
  transfers_required      INTEGER         NOT NULL,
  wait_time_min           INTEGER         NOT NULL,
  travel_time_min         INTEGER         NOT NULL,
  satisfaction_score      INTEGER         NOT NULL,
  income_bracket          VARCHAR(10)     NOT NULL,
  prefers_aircon          BOOLEAN         NOT NULL,
  cluster_id              INTEGER         NOT NULL,
  cluster_label           VARCHAR(50)     NOT NULL,
  is_ab_test_eligible     BOOLEAN         NOT NULL  DEFAULT FALSE,
  refreshed_at            TIMESTAMP       NOT NULL  DEFAULT NOW(),

  CONSTRAINT pk_mart_commuter_clusters
    PRIMARY KEY (passenger_id),
  CONSTRAINT chk_mcc_cluster_id
    CHECK (cluster_id BETWEEN 0 AND 4),
  CONSTRAINT chk_mcc_satisfaction
    CHECK (satisfaction_score BETWEEN 1 AND 5),
  CONSTRAINT chk_mcc_transfers
    CHECK (transfers_required BETWEEN 0 AND 3),
  CONSTRAINT chk_mcc_ab_eligible_logic
    CHECK (
      (is_ab_test_eligible = TRUE  AND cluster_id = 3) OR
      (is_ab_test_eligible = FALSE AND cluster_id <> 3)
    )
);

COMMENT ON TABLE  marts.mart_commuter_clusters IS
  'Gold: 5,000 passengers with K-Means cluster assignments. '
  'Grain: one row per passenger. Empty until science/clustering.py + dbt marts run. '
  'Built by dbt.';
COMMENT ON COLUMN marts.mart_commuter_clusters.cluster_id IS
  '0=Student Commuters, 1=Market Workers, 2=CBD Workers, '
  '3=Underserved Riders (A/B target), 4=Occasional Riders.';
COMMENT ON COLUMN marts.mart_commuter_clusters.is_ab_test_eligible IS
  'TRUE only for cluster_id = 3 (Underserved Riders). '
  'Enforced by chk_mcc_ab_eligible_logic constraint.';
COMMENT ON COLUMN marts.mart_commuter_clusters.cluster_label IS
  'Human-readable cluster name written by clustering.py. '
  'Matches cluster_id: 3 = Underserved Riders.';


-- =============================================================================
-- 4. marts.mart_ab_test_results
-- Grain      : One row per passenger per test week
-- Built by   : dbt/models/marts/mart_ab_test_results.sql
-- Source     : stg_ab_experiment JOIN mart_commuter_clusters
--              + statistical columns from science/ab_testing.py
-- Volume     : ~8,000 rows (1,000 Cluster 3 passengers × 8 weeks)
-- Serves     : Superset Dashboard 3 + Streamlit A/B test results page
-- IMPORTANT  : p_value, is_significant, effect_size, CI columns are NULL here
--              until science/ab_testing.py runs and writes them to postgres.
--              dbt then builds this mart after ab_testing.py completes.
-- =============================================================================

CREATE TABLE IF NOT EXISTS marts.mart_ab_test_results (
  experiment_record_id        VARCHAR(20)   NOT NULL,
  experiment_id               VARCHAR(10)   NOT NULL  DEFAULT 'EXP-001',
  passenger_id                VARCHAR(15)   NOT NULL,
  cluster_label               VARCHAR(50)   NOT NULL  DEFAULT 'Underserved Riders',
  "group"                     VARCHAR(15)   NOT NULL,  -- reserved word — must stay quoted
  route_variant               VARCHAR(30)   NOT NULL,
  test_week                   INTEGER       NOT NULL,
  simulated_travel_time_min   INTEGER       NOT NULL,
  simulated_fare_php          NUMERIC(6,2)  NOT NULL,
  transfers_needed            INTEGER       NOT NULL,
  satisfaction_score          INTEGER       NOT NULL,
  would_use_again             BOOLEAN       NOT NULL,
  p_value                     NUMERIC(8,6),            -- NULL until ab_testing.py runs
  is_significant              BOOLEAN,                 -- NULL until ab_testing.py runs
  effect_size                 NUMERIC(6,4),            -- Cohen d — NULL until ab_testing.py
  confidence_interval_low     NUMERIC(6,4),            -- 95% CI lower bound
  confidence_interval_high    NUMERIC(6,4),            -- 95% CI upper bound
  refreshed_at                TIMESTAMP     NOT NULL  DEFAULT NOW(),

  CONSTRAINT pk_mart_ab_test_results
    PRIMARY KEY (experiment_record_id),
  CONSTRAINT chk_ab_res_group
    CHECK ("group" IN ('control', 'treatment')),
  CONSTRAINT chk_ab_res_variant
    CHECK (route_variant IN ('A_existing_route', 'B_express_direct')),
  CONSTRAINT chk_ab_res_week
    CHECK (test_week BETWEEN 1 AND 8),
  CONSTRAINT chk_ab_res_satisfaction
    CHECK (satisfaction_score BETWEEN 1 AND 5),
  CONSTRAINT chk_ab_res_p_value
    CHECK (p_value BETWEEN 0 AND 1 OR p_value IS NULL),
  CONSTRAINT chk_ab_res_ci_order
    CHECK (
      confidence_interval_low <= confidence_interval_high
      OR confidence_interval_low IS NULL
    )
);

COMMENT ON TABLE  marts.mart_ab_test_results IS
  'Gold: A/B test results for Cluster 3 (Underserved Riders). '
  'Statistical columns (p_value, effect_size, CI) populated after science/ab_testing.py. '
  'Grain: one row per passenger per week. ~8,000 rows. Built by dbt.';
COMMENT ON COLUMN marts.mart_ab_test_results."group" IS
  'Quoted — GROUP is a PostgreSQL reserved word. Values: control | treatment.';
COMMENT ON COLUMN marts.mart_ab_test_results.p_value IS
  'Two-sample t-test p-value on satisfaction_score. Significant if < 0.05. '
  'NULL until science/ab_testing.py runs.';
COMMENT ON COLUMN marts.mart_ab_test_results.effect_size IS
  'Cohen d — standardized mean difference between treatment and control. '
  'NULL until science/ab_testing.py runs.';
COMMENT ON COLUMN marts.mart_ab_test_results.confidence_interval_low IS
  '95% confidence interval lower bound on satisfaction score difference.';
COMMENT ON COLUMN marts.mart_ab_test_results.confidence_interval_high IS
  '95% confidence interval upper bound on satisfaction score difference.';


-- =============================================================================
-- END OF 07_tables_marts.sql
-- =============================================================================
