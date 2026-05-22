-- =============================================================================
-- models/marts/mart_commuter_clusters.sql
-- Davao Jeepney Route Optimization — Gold Layer
-- =============================================================================
-- Grain      : One row per passenger (5,000 rows)
-- Depends on : int_passenger_features
-- Materialise: table (full replace on each dbt mart run)
-- Serves     : Superset Dashboard 2 + Streamlit cluster explorer page
-- IMPORTANT  : This model will produce 0 rows until science/clustering.py
--              has written cluster_id and cluster_label back to
--              staging.stg_passenger_survey. Run dag_04_science first,
--              then dag_05_marts_refresh.
-- Clusters   :
--   0 = Student Commuters  (high freq, low fare, school destination)
--   1 = Market Workers     (AM peak, Toril/Calinan → Bankerohan)
--   2 = CBD Workers        (daily, higher fare, Poblacion/Lanang destination)
--   3 = Underserved Riders (2+ transfers, long wait, low satisfaction) ← A/B target
--   4 = Occasional Riders  (low freq, mall/hospital trips)
-- =============================================================================

{{
  config(
    materialized = 'table',
    schema       = 'marts',
    tags = ["gold", "marts", "dashboard_2", "ml_output"],
    post_hook    = "comment on table {{ this }} is 'Gold: 5,000 passengers with K-Means cluster assignments. Populated after clustering.py runs. Built by dbt.'"
  )
}}

with features as (
    select * 
    from {{ ref('int_passenger_features') }}
    where cluster_id is not null
)

select
    -- ── Identity ────────────────────────────────────────────────────────────
    passenger_id,
    origin_barangay,
    origin_district,

    -- ── Commuter profile ─────────────────────────────────────────────────────
    destination_type,
    trip_purpose,
    primary_route_used,
    income_bracket,
    prefers_aircon,

    -- ── Core clustering features ─────────────────────────────────────────────
    trips_per_week,
    avg_fare_paid_php,
    transfers_required,
    wait_time_min,
    travel_time_min,
    satisfaction_score,

    -- ── Cluster assignment ───────────────────────────────────────────────────
    cluster_id,
    cluster_label,

    -- ── A/B test eligibility ─────────────────────────────────────────────────
    case
        when cluster_id = 3 then true
        else false
    end                                     as is_ab_test_eligible,

    -- ── Underserved severity score ────────────────────────────────────────────
    case
        when cluster_id = 3 then
            round(
                (transfers_required::numeric * 0.35)
                + (wait_time_min::numeric     * 0.01)
                + ((6 - satisfaction_score)   * 0.30)
                + (travel_time_min::numeric   * 0.005),
                4
            )
        else null
    end                                     as underserved_severity_score,

    -- ── Route context ────────────────────────────────────────────────────────
    primary_route_name,
    primary_route_district,
    route_length_km,

    -- ── Audit ────────────────────────────────────────────────────────────────
    now()                                   as refreshed_at

from features
order by cluster_id, passenger_id