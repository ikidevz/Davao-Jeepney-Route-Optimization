-- =============================================================================
-- models/intermediate/int_passenger_features.sql
-- Davao Jeepney Route Optimization — Intermediate Layer
-- =============================================================================
-- Grain      : One row per survey respondent (5,000 rows)
-- Depends on : stg_passenger_survey, stg_routes
-- Materialise: ephemeral (default) — change to 'table' so science/clustering.py
--              can read it directly from PostgreSQL after dbt staging+intermediate run.
-- Used by    : mart_commuter_clusters
--              science/clustering.py (reads this as feature matrix for K-Means)
-- Notes      :
--   - Encodes income_bracket as a numeric ordinal for ML: low=1, middle=2, high=3
--   - Encodes destination_type and trip_purpose as integers for optional use
--   - Includes all 6 primary clustering features cited in BLUEPRINT section 7
--   - cluster_id and cluster_label pass through as-is (NULL before clustering runs)
-- =============================================================================

{{ config(
    materialized = 'table',
    schema       = 'staging',
    tags         = ["intermediate", "ml_feature_store"]
) }}

with survey as (

    select * from {{ ref('stg_passenger_survey') }}

),

routes as (
    select * from {{ ref('stg_routes') }}
),

encoded as (

    select
        s.passenger_id,
        s.survey_date,
        s.origin_barangay,
        s.origin_district,
        s.destination_type,
        s.trip_purpose,
        s.primary_route_used,
        s.trips_per_week,
        s.avg_fare_paid_php,
        s.transfers_required,
        s.wait_time_min,
        s.travel_time_min,
        s.satisfaction_score,
        s.income_bracket,
        s.prefers_aircon,
        s.cluster_id,
        s.cluster_label,
        s.is_ab_test_eligible,
        s.is_likely_underserved,

        -- ── Numeric encodings for clustering ──────────────────────────────
        case s.income_bracket
            when 'low'    then 1
            when 'middle' then 2
            when 'high'   then 3
            else null
        end                                         as income_bracket_encoded,

        case s.destination_type
            when 'work'     then 1
            when 'school'   then 2
            when 'market'   then 3
            when 'hospital' then 4
            when 'mall'     then 5
            else null
        end                                         as destination_type_encoded,

        case s.trip_purpose
            when 'daily_commute'  then 1
            when 'occasional'     then 2
            when 'weekend_only'   then 3
            else null
        end                                         as trip_purpose_encoded,

        case s.prefers_aircon
            when true  then 1
            when false then 0
        end                                         as prefers_aircon_int,

        -- ── Route context ─────────────────────────────────────────────────
        r.route_name                                as primary_route_name,
        r.district_covered                          as primary_route_district,
        r.base_fare_php                             as route_base_fare_php,
        r.route_length_km

    from survey     as s
    left join routes as r
        on s.primary_route_used = r.route_id

)

select
    passenger_id,
    survey_date,
    origin_barangay,
    origin_district,
    destination_type,
    trip_purpose,
    primary_route_used,
    income_bracket,
    prefers_aircon,

    -- ── Primary K-Means clustering features (6) ───────────────────────────
    trips_per_week,
    avg_fare_paid_php,
    transfers_required,
    wait_time_min,
    satisfaction_score,
    income_bracket_encoded,

    -- ── Encoded features for optional extended model ──────────────────────
    destination_type_encoded,
    trip_purpose_encoded,
    prefers_aircon_int,
    travel_time_min,

    -- ── Route enrichment ──────────────────────────────────────────────────
    primary_route_name,
    primary_route_district,
    route_base_fare_php,
    route_length_km,

    -- ── Cluster output columns (NULL until clustering.py runs) ────────────
    cluster_id,
    cluster_label,
    is_ab_test_eligible,
    is_likely_underserved

from encoded