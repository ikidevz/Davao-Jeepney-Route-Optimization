-- =============================================================================
-- models/marts/mart_route_summary.sql
-- Davao Jeepney Route Optimization — Gold Layer
-- =============================================================================
-- Grain      : One row per route per day (~4,380 rows: 12 routes × 365 days)
-- Depends on : int_route_performance
-- Materialise: table (full replace on each dbt run)
-- Serves     : Superset Dashboard 1 — Route Performance Overview
-- KPIs       :
--   - Daily ridership by route
--   - Average load factor
--   - Revenue per kilometre
--   - On-time performance rate (LTFRB target ≥ 80%)
--   - Peak vs off-peak ridership ratio
--   - Rainy day impact on delay and ridership
-- =============================================================================

{{
  config(
    materialized = 'table',
    schema       = 'marts',
    tags = ["gold", "marts", "dashboard_1"],
    post_hook    = "comment on table {{ this }} is 'Gold: daily route performance KPIs. Grain: one row per route per day. Built by dbt. Refreshed: ' || now()::text"
  )
}}

with route_perf as (

    select * from {{ ref('int_route_performance') }}

)

select
    -- ── Identity ────────────────────────────────────────────────────────────
    route_id,
    route_name,
    district_covered,
    trip_date,

    -- ── Volume ──────────────────────────────────────────────────────────────
    total_trips,
    total_passengers,
    avg_passengers_per_trip,

    -- ── Revenue ─────────────────────────────────────────────────────────────
    total_revenue_php,
    revenue_per_km_php,

    -- ── Service quality ─────────────────────────────────────────────────────
    avg_load_factor,
    avg_travel_time_min,
    avg_delay_min,

    -- ── On-time performance ─────────────────────────────────────────────────
    on_time_trips,
    on_time_rate,

    -- LTFRB compliance flag: route meets 80% on-time target
    case
        when on_time_rate >= 0.80 then true
        else false
    end                                                     as meets_ltfrb_target,

    -- ── Peak split ──────────────────────────────────────────────────────────
    peak_trips,
    off_peak_trips,

    -- Peak ratio (peak trips as share of total)
    round(
        peak_trips::numeric / nullif(total_trips, 0),
        3
    )                                                       as peak_trip_ratio,

    -- ── Weather ─────────────────────────────────────────────────────────────
    is_rainy_day,

    -- ── Fleet context ───────────────────────────────────────────────────────
    distinct_vehicles,
    modern_vehicles,
    avg_vehicle_capacity,
    avg_fleet_age_years,
    electric_vehicles,
    pct_compliant_operators,
    overcrowded_trips,

    -- ── Audit ───────────────────────────────────────────────────────────────
    now()                                                   as refreshed_at

from route_perf
order by
    trip_date,
    route_id
