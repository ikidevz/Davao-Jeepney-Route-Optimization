-- =============================================================================
-- models/marts/mart_district_ridership.sql
-- Davao Jeepney Route Optimization — Gold Layer
-- =============================================================================
-- Grain      : One row per district per day
--              (~4,015 rows: 11 districts × 365 days)
-- Depends on : int_daily_ridership, stg_stops, stg_passenger_survey
-- Materialise: table (full replace on each dbt run)
-- Serves     : Superset Dashboard 2 — District & Commuter Ridership
-- Notes      : avg_wait_time_min and avg_satisfaction are NULL for districts
--              with no survey respondents on that date.
--              pct_with_shelter is static (stop infrastructure doesn't change daily)
--              but is joined per district for convenience.
-- =============================================================================

{{
  config(
    materialized = 'table',
    schema       = 'marts',
    tags         = ['gold', 'marts', 'dashboard_2'],
    post_hook    = "comment on table {{ this }} is 'Gold: daily ridership and service quality by district. Grain: one row per district per day. Built by dbt. Refreshed: ' || now()::text"
  )
}}

with daily_ridership as (

    select * from {{ ref('int_daily_ridership') }}

),

stops as (

    select * from {{ ref('stg_stops') }}

),

survey as (

    select * from {{ ref('stg_passenger_survey') }}

),

-- ── Stop infrastructure per district ────────────────────────────────────────
-- Static: shelter coverage doesn't change daily, so we compute once
district_stops as (

    select
        district,
        count(stop_id)                                              as total_stops,
        count(stop_id) filter (where has_shelter = true)           as stops_with_shelter,
        round(
            count(stop_id) filter (where has_shelter = true)::numeric
            / nullif(count(stop_id), 0),
            3
        )                                                           as pct_with_shelter

    from stops
    group by district

),

-- ── Survey aggregates per district ──────────────────────────────────────────
-- Not date-partitioned: survey is a point-in-time snapshot.
-- avg_wait_time_min and avg_satisfaction are broadcast to all dates for that district.
district_survey as (

    select
        origin_district                                             as district,
        round(avg(wait_time_min)::numeric, 2)                      as avg_wait_time_min,
        round(avg(satisfaction_score)::numeric, 2)                 as avg_satisfaction

    from survey
    -- No cluster_id filter: wait_time_min and satisfaction_score exist at load time.
    -- These survey fields are populated during ingestion — not dependent on clustering.
    -- NULL avg_satisfaction only occurs for districts with zero survey respondents.
    group by origin_district

),

-- ── Trip-level boardings rolled up to district × day ────────────────────────
-- stg_trips doesn't have district directly — we route through int_daily_ridership
-- which carries district_covered from stg_routes.
district_daily as (

    select
        district_covered                                            as district,
        trip_date,
        is_rainy_day,

        -- Aggregate across all routes serving this district on this day
        sum(total_trips)                                            as total_trips_serving,
        count(distinct route_id)                                    as active_routes,
        sum(total_passengers)                                       as total_boardings

    from daily_ridership
    group by
        district_covered,
        trip_date,
        is_rainy_day

),

-- ── Peak and weekend boardings require trip-level data ──────────────────────
-- Re-aggregate stg_trips at district level for finer time splits.
district_time_splits as (

    select
        r.district_covered                                          as district,
        t.trip_date,

        sum(t.passengers_boarded)
            filter (where t.is_peak    = true)                      as peak_boardings,

        sum(t.passengers_boarded)
            filter (where t.is_weekend = true)                      as weekend_boardings

    from {{ ref('stg_trips') }}     as t
    inner join {{ ref('stg_routes') }} as r
        on t.route_id = r.route_id
    group by
        r.district_covered,
        t.trip_date

)

-- ── Final join ───────────────────────────────────────────────────────────────
select
    dd.district,
    dd.trip_date,

    -- Volume
    dd.total_boardings,
    dd.total_trips_serving,
    dd.active_routes,

    -- Service quality (from survey — may be NULL)
    ds.avg_wait_time_min,
    ds.avg_satisfaction,

    -- Infrastructure
    dst.pct_with_shelter,

    -- Time splits
    coalesce(dts.peak_boardings,    0)                              as peak_boardings,
    coalesce(dts.weekend_boardings, 0)                              as weekend_boardings,

    -- Weather context
    dd.is_rainy_day,

    -- Audit
    now()                                                           as refreshed_at

from district_daily             as dd
left join district_stops        as dst
    on dd.district = dst.district
left join district_survey       as ds
    on dd.district = ds.district
left join district_time_splits  as dts
    on dd.district = dts.district
    and dd.trip_date = dts.trip_date

order by
    dd.trip_date,
    dd.district
