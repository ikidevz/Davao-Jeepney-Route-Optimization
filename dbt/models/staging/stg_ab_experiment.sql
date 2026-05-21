-- =============================================================================
-- models/staging/stg_ab_experiment.sql
-- Davao Jeepney Route Optimization — Silver Layer
-- =============================================================================
-- Grain      : One row per passenger per test week in the A/B experiment
-- Source     : staging.stg_ab_experiment (source table)
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
    updated_at

from {{ source('staging', 'stg_ab_experiment') }}