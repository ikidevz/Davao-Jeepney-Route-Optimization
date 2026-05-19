-- =============================================================================
-- tests/staging/test_stg_trips_load_factor_range.sql
-- =============================================================================
-- Business rule: load_factor must be between 0.0 and 1.5 (inclusive).
-- Values above 1.5 indicate a data generation bug — max overcrowding allowed
-- in this simulation is 1.5 (50% over capacity).
-- =============================================================================

select
    trip_id,
    load_factor,
    passengers_boarded,
    vehicle_id
from {{ ref('stg_trips') }}
where
    load_factor < 0
    or load_factor > 1.5
