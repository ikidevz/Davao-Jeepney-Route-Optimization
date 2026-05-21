-- =============================================================================
-- models/intermediate/int_daily_ridership.sql
-- Davao Jeepney Route Optimization — Intermediate Layer
-- =============================================================================
-- Grain      : One row per route per day
-- Depends on : stg_trips, stg_routes
-- Materialise: ephemeral (inlined as CTE in mart models)
-- Used by    : mart_route_summary, mart_district_ridership
-- =============================================================================

{{
  config(
    materialized = 'ephemeral',
    tags = ["intermediate"]
  )
}}

with trips as (
    select * from {{ ref('stg_trips') }}
),

routes as (
    select * from {{ ref('stg_routes') }}
),

daily_agg as (

    select
        t.route_id,
        t.trip_date,
        t.is_rainy_day,

        -- Volume counts
        count(t.trip_id)                                        as total_trips,
        sum(t.passengers_boarded)                               as total_passengers,
        round(avg(t.passengers_boarded), 2)                     as avg_passengers_per_trip,

        -- Revenue
        sum(t.revenue_php)                                      as total_revenue_php,

        -- Performance
        round(avg(t.load_factor)::numeric, 3)                   as avg_load_factor,
        round(avg(t.travel_time_min)::numeric, 2)               as avg_travel_time_min,
        round(avg(t.delay_min)::numeric, 2)                     as avg_delay_min,

        -- On-time rate
        count(t.trip_id) filter (where t.is_on_time = true)     as on_time_trips,
        round(
            count(t.trip_id) filter (where t.is_on_time = true)::numeric
            / nullif(count(t.trip_id), 0),
            3
        )                                                        as on_time_rate,

        -- Peak vs off-peak split
        count(t.trip_id) filter (where t.is_peak   = true)      as peak_trips,
        count(t.trip_id) filter (where t.is_peak   = false)     as off_peak_trips

    from trips as t
    group by
        t.route_id,
        t.trip_date,
        t.is_rainy_day

)

select
    d.route_id,
    r.route_name,
    r.district_covered,
    r.route_length_km,
    d.trip_date,
    d.is_rainy_day,
    d.total_trips,
    d.total_passengers,
    d.avg_passengers_per_trip,
    d.total_revenue_php,

    -- Revenue efficiency KPI
    round(d.total_revenue_php / nullif(r.route_length_km, 0),2) as revenue_per_km_php,

    d.avg_load_factor,
    d.avg_travel_time_min,
    d.avg_delay_min,
    d.on_time_trips,
    d.on_time_rate,
    d.peak_trips,
    d.off_peak_trips

from daily_agg as d
inner join routes as r
    on d.route_id = r.route_id