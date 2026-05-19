-- =============================================================================
-- models/staging/stg_ab_experiment.sql
-- Davao Jeepney Route Optimization — Silver Layer
-- =============================================================================
-- Grain      : One row per passenger per test week (~8,000 rows)
-- Source     : staging.stg_ab_experiment
-- Materialise: view
-- Depends on : stg_passenger_survey (FK — passenger_id)
-- Notes      :
--   Only Cluster 3 (Underserved Riders) passengers appear here (enforced by DB
--   constraint chk_ab_cluster_only_3).
--
--   Statistical columns (p_value, is_significant, effect_size,
--   confidence_interval_low, confidence_interval_high) are NOT in the source
--   table schema defined in 05_tables_staging.sql.
--   science/ab_testing.py adds them via ALTER TABLE + UPDATE after running the
--   statistical tests. Once added, this view automatically exposes them to
--   mart_ab_test_results on the next dbt run.
--
--   Until ab_testing.py runs, these columns do not exist on the source table.
--   The CASE/COALESCE fallback below uses a safe NULL default so dbt compiles
--   even before the columns exist. If your dbt adapter raises "column not found",
--   uncomment the fallback block and re-run after ab_testing.py has executed.
-- =============================================================================

{{
  config(
    materialized = 'view',
    schema       = 'staging',
    tags         = ['silver', 'staging', 'fact']
  )
}}

select
    experiment_record_id,
    experiment_id,
    passenger_id,
    cluster_id,
    "group",
    route_variant,
    test_week,
    simulated_travel_time_min,
    simulated_fare_php,
    transfers_needed,
    satisfaction_score,
    would_use_again,

    -- Convenience flag to simplify downstream aggregations
    case
        when "group" = 'treatment' then true
        else false
    end                             as is_treatment,

    -- Experiment phase split (weeks 1-4 = early, 5-8 = late)
    case
        when test_week <= 4 then 'early'
        else 'late'
    end                             as experiment_phase,

    -- ── Statistical output columns ─────────────────────────────────────────
    -- Written by science/ab_testing.py via ALTER TABLE + UPDATE.
    -- These columns are added to stg_ab_experiment AFTER ab_testing.py runs.
    -- Before that, reference them as NULL to avoid compile errors.
    -- Switch the active block after ab_testing.py has run:

    -- BEFORE ab_testing.py (default — safe NULL placeholders):
    null::numeric(8,6)              as p_value,
    null::boolean                   as is_significant,
    null::numeric(6,4)              as effect_size,
    null::numeric(6,4)              as confidence_interval_low,
    null::numeric(6,4)              as confidence_interval_high,

    -- AFTER ab_testing.py (uncomment these, comment the NULLs above):
    -- p_value,
    -- is_significant,
    -- effect_size,
    -- confidence_interval_low,
    -- confidence_interval_high,

    created_at,
    updated_at

from {{ source('staging', 'stg_ab_experiment') }}
