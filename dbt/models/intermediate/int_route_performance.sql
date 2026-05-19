-- =============================================================================
-- models/intermediate/int_route_performance.sql
-- Davao Jeepney Route Optimization — Intermediate Layer
-- =============================================================================
-- Grain      : One row per route per day (enriched with vehicle + operator data)
-- Depends on : stg_trips, stg_routes, stg_vehicles, stg_operators
-- Materialise: ephemeral
-- Used by    : mart_route_summary
-- Fix note   : total_fuel_cost_php pre-aggregates to vehicle×day grain first
--              (avg_fuel_cost_daily_php is a per-vehicle daily cost, NOT per trip).
--              Summing it across trip rows would multiply by trip count incorrectly.
-- =============================================================================

{{
  config(
    materialized = 'ephemeral',
    tags         = ['intermediate']
  )
}}

with trips as (

    select * from {{ ref('stg_trips') }}

),

routes as (

    select * from {{ ref('stg_routes') }}

),

vehicles as (

    select * from {{ ref('stg_vehicles') }}

),

operators as (

    select * from {{ ref('stg_operators') }}

),

-- ── Per-vehicle daily fuel cost ──────────────────────────────────────────────
-- Collapse to vehicle × route × day grain before joining to trips.
-- This prevents multiplying avg_fuel_cost_daily_php by trip count.
vehicle_daily_cost as (

    select
        t.vehicle_id,
        t.route_id,
        t.trip_date,
        v.avg_fuel_cost_daily_php

    from trips      as t
    inner join vehicles as v
        on t.vehicle_id = v.vehicle_id
    group by
        t.vehicle_id,
        t.route_id,
        t.trip_date,
        v.avg_fuel_cost_daily_php

),

-- ── Route × day fuel cost total ──────────────────────────────────────────────
route_fuel_cost as (

    select
        route_id,
        trip_date,
        sum(avg_fuel_cost_daily_php)    as total_fuel_cost_php

    from vehicle_daily_cost
    group by
        route_id,
        trip_date

),

-- ── Enrich each trip with vehicle and operator attributes ────────────────────
trip_enriched as (

    select
        t.trip_id,
        t.route_id,
        t.vehicle_id,
        t.trip_date,
        t.time_period,
        t.day_of_week,
        t.passengers_boarded,
        t.revenue_php,
        t.travel_time_min,
        t.scheduled_time_min,
        t.delay_min,
        t.is_on_time,
        t.is_rainy_day,
        t.load_factor,
        t.is_peak,
        t.is_weekend,
        t.is_overcrowded,

        -- Vehicle attributes
        v.vehicle_type,
        v.capacity              as vehicle_capacity,
        v.fuel_type,
        v.year_manufactured,
        v.vehicle_age_years,
        v.is_active             as vehicle_is_active,

        -- Operator attributes
        o.operator_id,
        o.franchise_type,
        o.is_compliant_puv

    from trips             as t
    left join vehicles     as v
        on t.vehicle_id = v.vehicle_id
    left join operators    as o
        on v.operator_id = o.operator_id

),

-- ── Aggregate to route × day grain ──────────────────────────────────────────
route_daily as (

    select
        route_id,
        trip_date,
        is_rainy_day,

        -- Trip volume
        count(trip_id)                                              as total_trips,
        sum(passengers_boarded)                                     as total_passengers,
        round(avg(passengers_boarded)::numeric, 2)                  as avg_passengers_per_trip,

        -- Revenue
        sum(revenue_php)                                            as total_revenue_php,

        -- Service quality
        round(avg(load_factor)::numeric, 3)                         as avg_load_factor,
        round(avg(travel_time_min)::numeric, 2)                     as avg_travel_time_min,
        round(avg(delay_min)::numeric, 2)                           as avg_delay_min,

        -- On-time
        count(trip_id) filter (where is_on_time = true)             as on_time_trips,
        round(
            count(trip_id) filter (where is_on_time = true)::numeric
            / nullif(count(trip_id), 0),
            3
        )                                                           as on_time_rate,

        -- Peak split
        count(trip_id) filter (where is_peak  = true)               as peak_trips,
        count(trip_id) filter (where is_peak  = false)              as off_peak_trips,

        -- Overcrowding incidence
        count(trip_id) filter (where is_overcrowded = true)         as overcrowded_trips,

        -- Vehicle fleet composition (distinct units on this route this day)
        count(distinct vehicle_id)                                  as distinct_vehicles,
        count(distinct vehicle_id)
            filter (where vehicle_type = 'modernized_PUV')          as modern_vehicles,
        round(avg(vehicle_capacity)::numeric, 1)                    as avg_vehicle_capacity,
        round(avg(vehicle_age_years)::numeric, 1)                   as avg_fleet_age_years,

        -- Fuel type mix
        count(distinct vehicle_id)
            filter (where fuel_type = 'electric')                   as electric_vehicles,

        -- Operator compliance rate
        round(
            count(distinct operator_id)
                filter (where is_compliant_puv = true)::numeric
            / nullif(count(distinct operator_id), 0),
            3
        )                                                           as pct_compliant_operators

    from trip_enriched
    group by
        route_id,
        trip_date,
        is_rainy_day

)

-- ── Final: join route dimension + correct fuel cost ──────────────────────────
select
    rd.route_id,
    r.route_name,
    r.district_covered,
    r.route_length_km,
    r.base_fare_php,
    r.peak_frequency_min,
    r.off_peak_frequency_min,
    rd.trip_date,
    rd.is_rainy_day,
    rd.total_trips,
    rd.total_passengers,
    rd.avg_passengers_per_trip,
    rd.total_revenue_php,

    round(
        rd.total_revenue_php / nullif(r.route_length_km, 0),
        2
    )                                                               as revenue_per_km_php,

    rd.avg_load_factor,
    rd.avg_travel_time_min,
    rd.avg_delay_min,
    rd.on_time_trips,
    rd.on_time_rate,
    rd.peak_trips,
    rd.off_peak_trips,
    rd.overcrowded_trips,
    rd.distinct_vehicles,
    rd.modern_vehicles,
    rd.avg_vehicle_capacity,
    rd.avg_fleet_age_years,
    rd.electric_vehicles,
    rd.pct_compliant_operators,

    -- Correct fuel cost: one cost entry per vehicle per day, not per trip
    coalesce(rfc.total_fuel_cost_php, 0)                            as total_fuel_cost_php

from route_daily          as rd
inner join routes         as r
    on rd.route_id = r.route_id
left join route_fuel_cost as rfc
    on rd.route_id   = rfc.route_id
    and rd.trip_date = rfc.trip_date
