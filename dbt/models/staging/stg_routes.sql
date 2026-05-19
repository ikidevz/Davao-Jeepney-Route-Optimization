-- =============================================================================
-- models/staging/stg_routes.sql
-- Davao Jeepney Route Optimization — Silver Layer
-- =============================================================================
-- Grain      : One row per jeepney route (12 rows — static dimension)
-- Source     : staging.stg_routes (loaded from MinIO Parquet by ingest_to_postgres.py)
-- Materialise: view
-- Depends on : none
-- =============================================================================

{{
  config(
    materialized = 'view',
    schema       = 'staging',
    tags         = ['silver', 'staging', 'dimension']
  )
}}

select
    route_id,
    route_name,
    origin,
    destination,
    district_covered,
    route_length_km,
    num_stops,
    base_fare_php,
    peak_frequency_min,
    off_peak_frequency_min,
    is_active,
    created_at,
    updated_at

from {{ source('staging', 'stg_routes') }}

-- NOTE: No active-only filter here. Staging models must expose ALL rows
-- so FK tests on stg_stops, stg_vehicles, and stg_trips pass for historical data.
-- Filter is_active in mart models or intermediate models where business logic applies.
