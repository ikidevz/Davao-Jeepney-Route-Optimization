-- =============================================================================
-- analyses/cluster_profile_summary.sql
-- Davao Jeepney Route Optimization
-- =============================================================================
-- Purpose  : Aggregate commuter cluster profiles — average feature values
--            per cluster. Used to validate K-Means output and populate the
--            Streamlit cluster explorer profile cards.
-- Run after: science/clustering.py has written cluster labels to staging,
--            and dbt mart models have been refreshed.
-- =============================================================================

select
    cluster_id,
    cluster_label,

    count(passenger_id)                             as passenger_count,
    round(
        count(passenger_id)::numeric
        / sum(count(passenger_id)) over (),
        3
    )                                               as pct_of_total,

    -- Core feature averages
    round(avg(trips_per_week), 2)                  as avg_trips_per_week,
    round(avg(avg_fare_paid_php), 2)               as avg_fare_paid_php,
    round(avg(transfers_required), 2)              as avg_transfers,
    round(avg(wait_time_min), 1)                   as avg_wait_min,
    round(avg(travel_time_min), 1)                 as avg_travel_min,
    round(avg(satisfaction_score), 2)              as avg_satisfaction,

    -- Demographics
    round(
        count(passenger_id) filter (where income_bracket = 'low')::numeric
        / count(passenger_id), 3
    )                                               as pct_low_income,
    round(
        count(passenger_id) filter (where prefers_aircon = true)::numeric
        / count(passenger_id), 3
    )                                               as pct_prefers_aircon,

    -- A/B eligibility
    count(passenger_id) filter (
        where is_ab_test_eligible = true
    )                                               as ab_eligible_count,

    -- Underserved severity (Cluster 3 only)
    round(avg(underserved_severity_score), 4)       as avg_severity_score

from {{ ref('mart_commuter_clusters') }}
group by
    cluster_id,
    cluster_label
order by
    cluster_id
