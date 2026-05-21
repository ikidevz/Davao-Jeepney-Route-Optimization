-- =============================================================================
-- models/staging/stg_operators.sql
-- Davao Jeepney Route Optimization — Silver Layer
-- =============================================================================
-- Grain      : One row per jeepney franchise holder or cooperative
-- Source     : staging.stg_operators
-- Materialise: view
-- Depends on : none
-- =============================================================================

{{
  config(
    materialized = 'view',
    schema       = 'staging',
    tags = ["silver", "staging", "dimension"]
  )
}}

select
    operator_id,
    operator_name,
    contact_number,
    franchise_type,
    num_units,
    base_district,
    is_compliant_puv,
    created_at,
    updated_at
 
from {{ source('raw', 'stg_operators') }}
