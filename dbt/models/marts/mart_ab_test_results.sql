-- =============================================================================
-- models/marts/mart_ab_test_results.sql
-- Davao Jeepney Route Optimization — Gold Layer
-- =============================================================================
-- Grain      : One row per passenger per test week (~8,000 rows)
-- Depends on : stg_ab_experiment, mart_commuter_clusters
-- Materialise: table (full replace on each dbt mart run)
-- Serves     : Superset Dashboard 3 + Streamlit A/B test results page
--
-- Statistical columns lifecycle:
--   Phase 1 (pre ab_testing.py): p_value, is_significant, effect_size,
--             confidence_interval_low, confidence_interval_high → all NULL.
--             science/ab_testing.py writes these back to staging.stg_ab_experiment
--             via ALTER TABLE ... ADD COLUMN + UPDATE statements.
--   Phase 2 (post ab_testing.py): dbt mart refresh reads them from
--             stg_ab_experiment via stg_ab_experiment model.
--             This mart surfaces them fully populated.
--
-- IMPORTANT: Run dag_04_science (ab_testing.py) before dag_05_marts_refresh
--            for statistical columns to be non-NULL.
-- =============================================================================

{{
  config(
    materialized = 'table',
    schema       = 'marts',
    tags = ["gold", "marts", "dashboard_3", "ab_test"],
    post_hook    = "comment on table {{ this }} is 'Gold: A/B test results for Cluster 3. Stats filled by ab_testing.py.'"
  )
}}

with ab_exp as (
    select * from {{ ref('stg_ab_experiment') }}
),

-- Pull cluster info from intermediate layer instead (to break cycle)
clusters as (
    select 
        passenger_id,
        cluster_id,
        cluster_label,
        origin_district,
        income_bracket,
        underserved_severity_score
    from {{ ref('int_passenger_features') }}
    where cluster_id = 3
)

select
    ab.experiment_record_id,
    ab.experiment_id,
    ab.passenger_id,
    c.cluster_id,
    c.cluster_label,
    c.origin_district,
    c.income_bracket,

    ab."group",
    ab.route_variant,
    ab.test_week,
    ab.experiment_phase,
    ab.is_treatment,

    ab.simulated_travel_time_min,
    ab.simulated_fare_php,
    ab.transfers_needed,
    ab.satisfaction_score,
    ab.would_use_again,

    case 
        when ab.is_treatment = true 
        then 55 - ab.simulated_travel_time_min 
        else null 
    end as estimated_time_saving_min,

    case 
        when ab.is_treatment = true 
        then ab.simulated_fare_php - 26.00 
        else null 
    end as fare_delta_php,

    c.underserved_severity_score,

    -- Stats start NULL, filled later by ab_testing.py
    ab.p_value,
    ab.is_significant,
    ab.effect_size,
    ab.confidence_interval_low,
    ab.confidence_interval_high,

    now() as refreshed_at

from ab_exp as ab
inner join clusters as c 
    on ab.passenger_id = c.passenger_id

order by ab.test_week, ab."group", ab.passenger_id