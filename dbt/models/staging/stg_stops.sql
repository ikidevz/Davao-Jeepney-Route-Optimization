-- =============================================================================
-- models/staging/stg_stops.sql
-- Davao Jeepney Route Optimization — Silver Layer
-- =============================================================================
-- Grain      : One row per jeepney stop (~180 rows — static dimension)
-- Source     : staging.stg_stops
-- Materialise: view
-- Depends on : none (route enrichment deferred to intermediate/mart layer)
-- =============================================================================

{{
  config(
    materialized = 'view',
    schema       = 'staging',
    tags = ["silver", "staging", "dimension"]
  )
}}

select
    stop_id,
    stop_name,
    barangay,
    district,
    latitude,
    longitude,
    stop_type,
    has_shelter,
    avg_daily_boardings,
    route_id,
    created_at,
    updated_at

from {{ source('raw', 'stg_stops') }}
