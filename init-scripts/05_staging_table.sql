-- =============================================================================
-- 05_tables_staging.sql
-- Davao Jeepney Route Optimization — Data Lakehouse
-- PURPOSE : Create all Silver (source) tables in the raw schema
-- NOTE    : dbt views land in staging schema — kept separate to avoid name collision
-- RUN AS  : postgres superuser (tables will be owned by svc_pipeline
--           because svc_pipeline owns the staging schema)
-- ORDER   : Run AFTER 04_schemas.sql
-- =============================================================================

-- Guard: must be connected to jeepney_dw
DO $$ BEGIN
  IF current_database() <> 'jeepney_dw' THEN
    RAISE EXCEPTION 'Wrong database: % — expected jeepney_dw.', current_database();
  END IF;
END $$;


-- =============================================================================
-- 1. raw.stg_routes
-- Grain  : One row per jeepney route
-- Source : MinIO s3://raw/jeepney/routes/
-- Volume : 12 rows (static dimension)
-- =============================================================================

CREATE TABLE IF NOT EXISTS raw.stg_routes (
  route_id                VARCHAR(10)   NOT NULL,
  route_name              VARCHAR(100)  NOT NULL,
  origin                  VARCHAR(100)  NOT NULL,
  destination             VARCHAR(100)  NOT NULL,
  district_covered        VARCHAR(50)   NOT NULL,
  route_length_km         NUMERIC(5,2)  NOT NULL,
  num_stops               INTEGER       NOT NULL,
  base_fare_php           NUMERIC(5,2)  NOT NULL  DEFAULT 13.00,
  peak_frequency_min      INTEGER       NOT NULL,
  off_peak_frequency_min  INTEGER       NOT NULL,
  is_active               BOOLEAN       NOT NULL  DEFAULT TRUE,
  created_at              TIMESTAMP     NOT NULL  DEFAULT NOW(),
  updated_at              TIMESTAMP     NOT NULL  DEFAULT NOW(),

  CONSTRAINT pk_stg_routes
    PRIMARY KEY (route_id),
  CONSTRAINT chk_routes_fare
    CHECK (base_fare_php >= 13.00),
  CONSTRAINT chk_routes_length
    CHECK (route_length_km > 0),
  CONSTRAINT chk_routes_stops
    CHECK (num_stops > 0),
  CONSTRAINT chk_routes_peak_freq
    CHECK (peak_frequency_min > 0),
  CONSTRAINT chk_routes_offpeak_freq
    CHECK (off_peak_frequency_min > 0),
  CONSTRAINT chk_routes_offpeak_gte_peak
    CHECK (off_peak_frequency_min >= peak_frequency_min)
);

COMMENT ON TABLE  raw.stg_routes IS
  'Silver: 12 Davao jeepney routes. Grain: one row per route. Static dimension.';
COMMENT ON COLUMN raw.stg_routes.route_id IS
  'PK. Format: R01–R12. Matches LTFRB route code convention.';
COMMENT ON COLUMN raw.stg_routes.base_fare_php IS
  'Minimum fare per LTFRB 2026 ruling — ₱13.00 for first 4 km.';
COMMENT ON COLUMN raw.stg_routes.peak_frequency_min IS
  'Headway in minutes between trips during AM/PM peak hours.';
COMMENT ON COLUMN raw.stg_routes.off_peak_frequency_min IS
  'Headway in minutes during midday and off-peak periods. Always >= peak.';
COMMENT ON COLUMN raw.stg_routes.is_active IS
  'FALSE if route is suspended or rerouted under PUV Modernization Program.';


-- =============================================================================
-- 2. raw.stg_operators
-- Grain  : One row per franchise holder or cooperative
-- Source : MinIO s3://raw/jeepney/operators/
-- Volume : ~30–50 rows (static dimension)
-- =============================================================================

CREATE TABLE IF NOT EXISTS raw.stg_operators (
  operator_id         VARCHAR(10)   NOT NULL,
  operator_name       VARCHAR(150)  NOT NULL,
  contact_number      VARCHAR(20),
  franchise_type      VARCHAR(30)   NOT NULL,
  num_units           INTEGER       NOT NULL,
  base_district       VARCHAR(50)   NOT NULL,
  is_compliant_puv    BOOLEAN       NOT NULL  DEFAULT FALSE,
  created_at          TIMESTAMP     NOT NULL  DEFAULT NOW(),
  updated_at          TIMESTAMP     NOT NULL  DEFAULT NOW(),

  CONSTRAINT pk_stg_operators
    PRIMARY KEY (operator_id),
  CONSTRAINT chk_operators_units
    CHECK (num_units >= 1),
  CONSTRAINT chk_operators_franchise
    CHECK (franchise_type IN ('individual', 'cooperative', 'corporation'))
);

COMMENT ON TABLE  raw.stg_operators IS
  'Silver: jeepney franchise holders and cooperatives. Grain: one row per operator.';
COMMENT ON COLUMN raw.stg_operators.franchise_type IS
  'individual = solo driver-operator, cooperative = group, corporation = company-owned.';
COMMENT ON COLUMN raw.stg_operators.is_compliant_puv IS
  'TRUE if operator has complied with LTFRB PUV Modernization Program requirements.';


-- =============================================================================
-- 3. raw.stg_stops
-- Grain  : One row per jeepney stop
-- Source : MinIO s3://raw/jeepney/stops/
-- Volume : ~180 rows (static dimension, anchored on real Davao landmarks)
-- =============================================================================

CREATE TABLE IF NOT EXISTS raw.stg_stops (
  stop_id              VARCHAR(10)   NOT NULL,
  stop_name            VARCHAR(150)  NOT NULL,
  barangay             VARCHAR(100)  NOT NULL,
  district             VARCHAR(50)   NOT NULL,
  latitude             NUMERIC(9,6)  NOT NULL,
  longitude            NUMERIC(9,6)  NOT NULL,
  stop_type            VARCHAR(30)   NOT NULL,
  has_shelter          BOOLEAN       NOT NULL  DEFAULT FALSE,
  avg_daily_boardings  INTEGER       NOT NULL  DEFAULT 0,
  route_id             VARCHAR(10)   NOT NULL,
  created_at           TIMESTAMP     NOT NULL  DEFAULT NOW(),
  updated_at           TIMESTAMP     NOT NULL  DEFAULT NOW(),

  CONSTRAINT pk_stg_stops
    PRIMARY KEY (stop_id),
  CONSTRAINT fk_stops_route
    FOREIGN KEY (route_id) REFERENCES raw.stg_routes (route_id),
  CONSTRAINT chk_stops_lat
    CHECK (latitude  BETWEEN 6.8 AND 7.5),
  CONSTRAINT chk_stops_lon
    CHECK (longitude BETWEEN 125.0 AND 126.0),
  CONSTRAINT chk_stops_boardings
    CHECK (avg_daily_boardings >= 0),
  CONSTRAINT chk_stops_type
    CHECK (stop_type IN ('terminal', 'market', 'school', 'hospital', 'mall', 'residential'))
);

COMMENT ON TABLE  raw.stg_stops IS
  'Silver: ~180 stops anchored on real Davao City landmarks. Grain: one row per stop.';
COMMENT ON COLUMN raw.stg_stops.latitude IS
  'GPS latitude. Valid range: Davao City geographic bounds (6.8–7.5).';
COMMENT ON COLUMN raw.stg_stops.has_shelter IS
  'TRUE if stop has a waiting shed. Approx 70% of urban stops = TRUE.';


-- =============================================================================
-- 4. raw.stg_vehicles
-- Grain  : One row per jeepney unit
-- Source : MinIO s3://raw/jeepney/vehicles/
-- Volume : 120 rows (static dimension)
-- =============================================================================

CREATE TABLE IF NOT EXISTS raw.stg_vehicles (
  vehicle_id               VARCHAR(10)  NOT NULL,
  plate_number             VARCHAR(15)  NOT NULL,
  vehicle_type             VARCHAR(30)  NOT NULL,
  capacity                 INTEGER      NOT NULL,
  fuel_type                VARCHAR(20)  NOT NULL,
  year_manufactured        INTEGER      NOT NULL,
  route_assigned           VARCHAR(10)  NOT NULL,
  operator_id              VARCHAR(10)  NOT NULL,
  avg_fuel_cost_daily_php  NUMERIC(7,2) NOT NULL,
  is_active                BOOLEAN      NOT NULL  DEFAULT TRUE,
  created_at               TIMESTAMP    NOT NULL  DEFAULT NOW(),
  updated_at               TIMESTAMP    NOT NULL  DEFAULT NOW(),

  CONSTRAINT pk_stg_vehicles
    PRIMARY KEY (vehicle_id),
  CONSTRAINT uq_vehicles_plate
    UNIQUE (plate_number),
  CONSTRAINT fk_vehicles_route
    FOREIGN KEY (route_assigned) REFERENCES raw.stg_routes    (route_id),
  CONSTRAINT fk_vehicles_operator
    FOREIGN KEY (operator_id)    REFERENCES raw.stg_operators (operator_id),
  CONSTRAINT chk_vehicles_capacity
    CHECK (capacity BETWEEN 10 AND 30),
  CONSTRAINT chk_vehicles_year
    CHECK (year_manufactured BETWEEN 2000 AND 2025),
  CONSTRAINT chk_vehicles_fuel_cost
    CHECK (avg_fuel_cost_daily_php > 0),
  CONSTRAINT chk_vehicles_type
    CHECK (vehicle_type IN ('traditional', 'modernized_PUV')),
  CONSTRAINT chk_vehicles_fuel
    CHECK (fuel_type IN ('diesel', 'euro4_diesel', 'electric'))
);

COMMENT ON TABLE  raw.stg_vehicles IS
  'Silver: 120 jeepney units across 12 routes. Grain: one row per vehicle.';
COMMENT ON COLUMN raw.stg_vehicles.plate_number IS
  'Synthetic PH plate format (e.g. DBX-1234). Enforced unique.';
COMMENT ON COLUMN raw.stg_vehicles.capacity IS
  '16 seats for traditional units, 23 for modernized PUV (LTFRB standard).';
COMMENT ON COLUMN raw.stg_vehicles.avg_fuel_cost_daily_php IS
  'Based on Davao City diesel price ~₱65/L as of 2026. Higher for longer routes.';


-- =============================================================================
-- 5. raw.stg_trips
-- Grain  : One row per trip run (one vehicle, one direction, one day)
-- Source : MinIO s3://raw/jeepney/trips/
-- Volume : ~500,000 rows (365 days × 12 routes × ~114 avg trips/day)
-- =============================================================================

CREATE TABLE IF NOT EXISTS raw.stg_trips (
  trip_id              VARCHAR(20)   NOT NULL,
  route_id             VARCHAR(10)   NOT NULL,
  vehicle_id           VARCHAR(10)   NOT NULL,
  trip_date            DATE          NOT NULL,
  departure_time       TIME          NOT NULL,
  arrival_time         TIME          NOT NULL,
  time_period          VARCHAR(20)   NOT NULL,
  day_of_week          VARCHAR(10)   NOT NULL,
  passengers_boarded   INTEGER       NOT NULL,
  revenue_php          NUMERIC(8,2)  NOT NULL,
  travel_time_min      INTEGER       NOT NULL,
  scheduled_time_min   INTEGER       NOT NULL,
  delay_min            INTEGER       NOT NULL  DEFAULT 0,
  is_on_time           BOOLEAN       NOT NULL,
  is_rainy_day         BOOLEAN       NOT NULL  DEFAULT FALSE,
  load_factor          NUMERIC(4,3)  NOT NULL,
  created_at           TIMESTAMP     NOT NULL  DEFAULT NOW(),
  updated_at           TIMESTAMP     NOT NULL  DEFAULT NOW(),

  CONSTRAINT pk_stg_trips
    PRIMARY KEY (trip_id),
  CONSTRAINT fk_trips_route
    FOREIGN KEY (route_id)   REFERENCES raw.stg_routes   (route_id),
  CONSTRAINT fk_trips_vehicle
    FOREIGN KEY (vehicle_id) REFERENCES raw.stg_vehicles (vehicle_id),
  CONSTRAINT chk_trips_passengers
    CHECK (passengers_boarded >= 0),
  CONSTRAINT chk_trips_revenue
    CHECK (revenue_php >= 0),
  CONSTRAINT chk_trips_load_factor
    CHECK (load_factor BETWEEN 0.000 AND 1.500),
  CONSTRAINT chk_trips_travel_time
    CHECK (travel_time_min > 0),
  CONSTRAINT chk_trips_scheduled_time
    CHECK (scheduled_time_min > 0),
  CONSTRAINT chk_trips_delay
    CHECK (delay_min >= 0),
  CONSTRAINT chk_trips_time_period
    CHECK (time_period IN ('AM_peak', 'midday', 'PM_peak', 'off_peak')),
  CONSTRAINT chk_trips_day_of_week
    CHECK (day_of_week IN (
      'Monday', 'Tuesday', 'Wednesday', 'Thursday',
      'Friday', 'Saturday', 'Sunday')),
  CONSTRAINT chk_trips_on_time_logic
    CHECK (
      (is_on_time = TRUE  AND delay_min <= 5) OR
      (is_on_time = FALSE AND delay_min >  5)
    )
);

COMMENT ON TABLE  raw.stg_trips IS
  'Silver: ~500K trip records over 1 year. Grain: one trip run per vehicle per day.';
COMMENT ON COLUMN raw.stg_trips.load_factor IS
  'passengers_boarded / vehicle capacity. Above 1.0 = overcrowded (allowed up to 1.5).';
COMMENT ON COLUMN raw.stg_trips.is_on_time IS
  'TRUE when delay_min <= 5. Enforced by chk_trips_on_time_logic constraint.';
COMMENT ON COLUMN raw.stg_trips.time_period IS
  'AM_peak = 6–9am, midday = 9am–5pm, PM_peak = 5–8pm, off_peak = other hours.';


-- =============================================================================
-- 6. raw.stg_passenger_survey
-- Grain  : One row per survey respondent
-- Source : MinIO s3://raw/jeepney/passengers/
-- Volume : 5,000 rows
-- NOTE   : cluster_id and cluster_label are NULL at load time.
--          science/clustering.py writes them after K-Means runs.
-- =============================================================================

CREATE TABLE IF NOT EXISTS raw.stg_passenger_survey (
  passenger_id        VARCHAR(15)   NOT NULL,
  survey_date         DATE          NOT NULL,
  origin_barangay     VARCHAR(100)  NOT NULL,
  origin_district     VARCHAR(50)   NOT NULL,
  destination_type    VARCHAR(30)   NOT NULL,
  trip_purpose        VARCHAR(30)   NOT NULL,
  primary_route_used  VARCHAR(10)   NOT NULL,
  trips_per_week      INTEGER       NOT NULL,
  avg_fare_paid_php   NUMERIC(6,2)  NOT NULL,
  transfers_required  INTEGER       NOT NULL,
  wait_time_min       INTEGER       NOT NULL,
  travel_time_min     INTEGER       NOT NULL,
  satisfaction_score  INTEGER       NOT NULL,
  income_bracket      VARCHAR(10)   NOT NULL,
  prefers_aircon      BOOLEAN       NOT NULL  DEFAULT FALSE,
  cluster_id          INTEGER,                -- NULL until clustering.py runs
  cluster_label       VARCHAR(50),            -- NULL until clustering.py runs
  created_at          TIMESTAMP     NOT NULL  DEFAULT NOW(),
  updated_at          TIMESTAMP     NOT NULL  DEFAULT NOW(),

  CONSTRAINT pk_stg_passenger_survey
    PRIMARY KEY (passenger_id),
  CONSTRAINT fk_survey_route
    FOREIGN KEY (primary_route_used) REFERENCES raw.stg_routes (route_id),
  CONSTRAINT chk_survey_satisfaction
    CHECK (satisfaction_score BETWEEN 1 AND 5),
  CONSTRAINT chk_survey_trips_per_week
    CHECK (trips_per_week BETWEEN 0 AND 14),
  CONSTRAINT chk_survey_transfers
    CHECK (transfers_required BETWEEN 0 AND 3),
  CONSTRAINT chk_survey_wait_time
    CHECK (wait_time_min >= 0),
  CONSTRAINT chk_survey_fare
    CHECK (avg_fare_paid_php > 0),
  CONSTRAINT chk_survey_cluster_id
    CHECK (cluster_id BETWEEN 0 AND 4 OR cluster_id IS NULL),
  CONSTRAINT chk_survey_destination_type
    CHECK (destination_type IN ('work', 'school', 'market', 'hospital', 'mall')),
  CONSTRAINT chk_survey_trip_purpose
    CHECK (trip_purpose IN ('daily_commute', 'occasional', 'weekend_only')),
  CONSTRAINT chk_survey_income
    CHECK (income_bracket IN ('low', 'middle', 'high'))
);

COMMENT ON TABLE  raw.stg_passenger_survey IS
  'Silver: 5,000 commuter survey records. Grain: one row per respondent.';
COMMENT ON COLUMN raw.stg_passenger_survey.cluster_id IS
  'NULL at load time. Written by science/clustering.py after K-Means. Values: 0–4.';
COMMENT ON COLUMN raw.stg_passenger_survey.cluster_label IS
  'NULL at load time. Human-readable label written by clustering.py. '
  'Examples: Underserved Riders, Student Commuters.';
COMMENT ON COLUMN raw.stg_passenger_survey.satisfaction_score IS
  '1=very poor, 2=poor, 3=fair, 4=good, 5=excellent.';


-- =============================================================================
-- 7. raw.stg_ab_experiment
-- Grain  : One row per passenger per test week
-- Source : MinIO s3://raw/jeepney/ab_experiment/
-- Volume : ~8,000 rows (1,000 Cluster 3 passengers × 8 weeks)
-- NOTE   : Only Cluster 3 (Underserved Riders) passengers are included.
--          Statistical outputs live in marts.mart_ab_test_results — not here.
-- =============================================================================

CREATE TABLE IF NOT EXISTS raw.stg_ab_experiment (
  experiment_record_id       VARCHAR(20)   NOT NULL,
  experiment_id              VARCHAR(10)   NOT NULL  DEFAULT 'EXP-001',
  passenger_id               VARCHAR(15)   NOT NULL,
  cluster_id                 INTEGER       NOT NULL,
  "group"                    VARCHAR(15)   NOT NULL,  -- reserved word — must stay quoted
  route_variant              VARCHAR(30)   NOT NULL,
  test_week                  INTEGER       NOT NULL,
  simulated_travel_time_min  INTEGER       NOT NULL,
  simulated_fare_php         NUMERIC(6,2)  NOT NULL,
  transfers_needed           INTEGER       NOT NULL,
  satisfaction_score         INTEGER       NOT NULL,
  would_use_again            BOOLEAN       NOT NULL,
  created_at                 TIMESTAMP     NOT NULL  DEFAULT NOW(),
  updated_at                 TIMESTAMP     NOT NULL  DEFAULT NOW(),

  CONSTRAINT pk_stg_ab_experiment
    PRIMARY KEY (experiment_record_id),
  CONSTRAINT fk_ab_passenger
    FOREIGN KEY (passenger_id) REFERENCES raw.stg_passenger_survey (passenger_id),
  CONSTRAINT chk_ab_cluster_only_3
    CHECK (cluster_id = 3),
  CONSTRAINT chk_ab_group
    CHECK ("group" IN ('control', 'treatment')),
  CONSTRAINT chk_ab_variant
    CHECK (route_variant IN ('A_existing_route', 'B_express_direct')),
  CONSTRAINT chk_ab_week
    CHECK (test_week BETWEEN 1 AND 8),
  CONSTRAINT chk_ab_satisfaction
    CHECK (satisfaction_score BETWEEN 1 AND 5),
  CONSTRAINT chk_ab_travel_time
    CHECK (simulated_travel_time_min > 0),
  CONSTRAINT chk_ab_fare
    CHECK (simulated_fare_php > 0),
  CONSTRAINT chk_ab_transfers
    CHECK (transfers_needed BETWEEN 0 AND 3),
  CONSTRAINT chk_ab_group_variant_match
    CHECK (
      ("group" = 'control'   AND route_variant = 'A_existing_route') OR
      ("group" = 'treatment' AND route_variant = 'B_express_direct')
    )
);

COMMENT ON TABLE  raw.stg_ab_experiment IS
  'Silver: A/B experiment records for Cluster 3 (Underserved Riders) only. '
  'Grain: one row per passenger per week. ~8,000 rows.';
COMMENT ON COLUMN raw.stg_ab_experiment."group" IS
  'Quoted — GROUP is a PostgreSQL reserved word. Values: control | treatment.';
COMMENT ON COLUMN raw.stg_ab_experiment.cluster_id IS
  'Always 3 (Underserved Riders). Enforced by chk_ab_cluster_only_3.';
COMMENT ON COLUMN raw.stg_ab_experiment.route_variant IS
  'A_existing_route = control (1–2 transfers, ~55 min avg). '
  'B_express_direct = treatment (0 transfers, ~35 min avg).';

-- =============================================================================
-- END OF 05_tables_staging.sql
-- =============================================================================

-- =============================================================================
-- OWNERSHIP TRANSFER
-- dbt runs as svc_pipeline and needs to be the table owner to DROP/CREATE
-- on each run. Tables were created by the superuser above, so we transfer
-- ownership explicitly here.
-- =============================================================================

ALTER TABLE raw.stg_routes           OWNER TO svc_pipeline;
ALTER TABLE raw.stg_operators        OWNER TO svc_pipeline;
ALTER TABLE raw.stg_stops            OWNER TO svc_pipeline;
ALTER TABLE raw.stg_vehicles         OWNER TO svc_pipeline;
ALTER TABLE raw.stg_trips            OWNER TO svc_pipeline;
ALTER TABLE raw.stg_passenger_survey OWNER TO svc_pipeline;
ALTER TABLE raw.stg_ab_experiment    OWNER TO svc_pipeline;