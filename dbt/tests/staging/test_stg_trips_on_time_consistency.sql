-- =============================================================================
-- tests/staging/test_stg_trips_on_time_consistency.sql
-- =============================================================================
-- Business rule: is_on_time = TRUE  ↔ delay_min <= 5
--                is_on_time = FALSE ↔ delay_min >  5
-- Any row that violates this constraint is a data quality failure.
-- =============================================================================

select
    trip_id,
    is_on_time,
    delay_min
from {{ ref('stg_trips') }}
where
    (is_on_time = true  and delay_min > 5)
    or
    (is_on_time = false and delay_min <= 5)
