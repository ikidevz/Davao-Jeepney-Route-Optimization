-- =============================================================================
-- models/staging/stg_vehicles.sql
-- Davao Jeepney Route Optimization — Silver Layer
-- =============================================================================
-- Grain      : One row per jeepney unit (120 rows — static dimension)
-- Source     : staging.stg_vehicles
-- Materialise: view
-- Depends on : stg_routes, stg_operators (FKs)
-- =============================================================================

{{
  config(
    materialized = 'view',
    schema       = 'staging',
    tags         = ['silver', 'staging', 'dimension']
  )
}}

select
    v.vehicle_id,
    v.plate_number,
    v.vehicle_type,
    v.capacity,
    v.fuel_type,
    v.year_manufactured,
    v.route_assigned,
    v.operator_id,
    v.avg_fuel_cost_daily_php,
    v.is_active,
    -- Computed convenience column
    date_part('year', current_date) - v.year_manufactured  as vehicle_age_years,
    v.created_at,
    v.updated_at

from {{ source('staging', 'stg_vehicles') }} as v

-- NOTE: No active-only filter here. Staging exposes all vehicles so FK tests
-- on stg_trips (vehicle_id) never fail for retired units.
-- Use is_active column to filter in intermediate/mart models as needed.
