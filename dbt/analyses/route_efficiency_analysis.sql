-- =============================================================================
-- analyses/route_efficiency_analysis.sql
-- Davao Jeepney Route Optimization
-- =============================================================================
-- Purpose  : Ad-hoc analysis of route efficiency for the data team.
--            NOT part of the dbt DAG — run manually via `dbt compile` + psql.
-- Scope    : Compares all routes on key efficiency KPIs over the full year.
-- Audience : Data analysts preparing Superset chart customisations.
-- =============================================================================

-- Route efficiency leaderboard (full year)
select
    route_id,
    route_name,
    district_covered,

    -- Volume
    sum(total_trips)                                            as annual_trips,
    sum(total_passengers)                                       as annual_passengers,

    -- Revenue
    sum(total_revenue_php)                                      as annual_revenue_php,
    round(avg(revenue_per_km_php), 2)                          as avg_revenue_per_km,

    -- Service quality
    round(avg(avg_load_factor), 3)                             as avg_load_factor,
    round(avg(avg_delay_min), 2)                               as avg_delay_min,
    round(avg(on_time_rate), 3)                                as avg_on_time_rate,

    -- LTFRB compliance
    round(
        sum(case when meets_ltfrb_target then 1 else 0 end)::numeric
        / count(*),
        3
    )                                                          as pct_days_meeting_ltfrb,

    -- Rainy day impact
    round(
        avg(avg_delay_min) filter (where is_rainy_day = true), 2
    )                                                          as avg_delay_rainy_days,
    round(
        avg(avg_delay_min) filter (where is_rainy_day = false), 2
    )                                                          as avg_delay_dry_days,

    -- Fleet stats
    round(avg(distinct_vehicles), 1)                           as avg_daily_vehicles,
    round(avg(avg_fleet_age_years), 1)                         as avg_fleet_age,
    round(avg(pct_compliant_operators), 3)                     as avg_operator_compliance

from {{ ref('mart_route_summary') }}
group by
    route_id,
    route_name,
    district_covered
order by
    avg_on_time_rate desc,
    avg_revenue_per_km desc
