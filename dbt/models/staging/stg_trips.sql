-- =============================================================================
-- models/staging/stg_trips.sql
-- Davao Jeepney Route Optimization — Silver Layer
-- =============================================================================
-- Grain      : One trip run per vehicle per direction per day (~500K rows)
-- Source     : staging.stg_trips
-- Materialise: view
-- Depends on : stg_routes, stg_vehicles (FKs)
-- Notes      : This is the highest-volume table in the lakehouse.
--              Indexes on (route_id, trip_date) and (trip_date) are defined
--              in 07_indexes_grants_audit.sql.
-- =============================================================================

{{
  config(
    materialized = 'view',
    schema       = 'staging',
    tags = ["silver", "staging", "fact"]
  )
}}

select
    trip_id,
    route_id,
    vehicle_id,
    trip_date,
    departure_time,
    arrival_time,
    time_period,
    day_of_week,
    passengers_boarded,
    revenue_php,
    travel_time_min,
    scheduled_time_min,
    delay_min,
    is_on_time,
    is_rainy_day,
    load_factor,

    -- Derived convenience flags used in multiple downstream models
    case
        when time_period in ('AM_peak', 'PM_peak') then true
        else false
    end                                                        as is_peak,

    case
        when day_of_week in ('Saturday', 'Sunday') then true
        else false
    end                                                        as is_weekend,

    -- Overcrowding flag (load factor > 1.0 but within 1.5 tolerance)
    case
        when load_factor > 1.0 then true
        else false
    end                                                        as is_overcrowded,

    created_at

from {{ source('raw', 'stg_trips') }}
