-- =============================================================================
-- models/staging/stg_passenger_survey.sql
-- Davao Jeepney Route Optimization — Silver Layer
-- =============================================================================
-- Grain      : One row per commuter survey respondent (5,000 rows)
-- Source     : staging.stg_passenger_survey
-- Materialise: view
-- Depends on : stg_routes (FK — primary_route_used)
-- Notes      : cluster_id and cluster_label are NULL at ingestion time.
--              They are written back to the SOURCE table by science/clustering.py
--              after K-Means runs. This view reads the current state — including
--              populated cluster columns once the science pipeline has run.
-- =============================================================================

{{
  config(
    materialized = 'view',
    schema       = 'staging',
    tags = ["silver", "staging", "fact"]
  )
}}

select
    passenger_id,
    survey_date,
    origin_barangay,
    origin_district,
    destination_type,
    trip_purpose,
    primary_route_used,
    trips_per_week,
    avg_fare_paid_php,
    transfers_required,
    wait_time_min,
    travel_time_min,
    satisfaction_score,
    income_bracket,
    prefers_aircon,

    -- Cluster columns — NULL until science/clustering.py writes labels
    cluster_id,
    cluster_label,

    -- Derived: A/B test eligibility flag mirrors the mart constraint
    case
        when cluster_id = 3 then true
        else false
    end                              as is_ab_test_eligible,

    -- Derived: underserved proxy rule (belt + suspenders before clustering runs)
    case
        when transfers_required >= 2
         and wait_time_min      >= 25
         and satisfaction_score <= 2
        then true
        else false
    end                              as is_likely_underserved,

    created_at,
    updated_at

from {{ source('raw', 'stg_passenger_survey') }}
