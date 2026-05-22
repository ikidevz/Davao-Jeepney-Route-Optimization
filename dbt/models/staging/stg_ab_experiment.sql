-- =============================================================================
-- models/staging/stg_ab_experiment.sql
-- Davao Jeepney Route Optimization — Silver Layer
-- =============================================================================
-- Grain      : One row per passenger per test week in the A/B experiment
-- Source     : raw.stg_ab_experiment (source table)
-- Materialise: view
-- Depends on : stg_passenger_survey (FK — passenger_id)
-- Notes      : Only Cluster 3 (Underserved Riders) passengers are included.
--              Statistical outputs live in marts.mart_ab_test_results.
-- =============================================================================

{{
  config(
    materialized = 'view',
    schema       = 'staging',
    tags = ["silver", "staging", "fact"]
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
    created_at,

    null::timestamptz                               as updated_at,

    -- experiment_phase: derived from test_week — not a raw column.
    case
        when test_week <= 4 then 'ramp_up'
        else 'main'
    end                                             as experiment_phase,

    -- is_treatment: derived from "group" — not a raw column.
    ("group" = 'treatment')                         as is_treatment,

    null::numeric                                   as p_value,
    null::boolean                                   as is_significant,
    null::numeric                                   as effect_size,
    null::numeric                                   as confidence_interval_low,
    null::numeric                                   as confidence_interval_high

from {{ source('raw', 'stg_ab_experiment') }}