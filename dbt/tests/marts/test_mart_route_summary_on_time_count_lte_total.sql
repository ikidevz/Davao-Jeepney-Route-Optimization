-- =============================================================================
-- tests/marts/test_mart_route_summary_on_time_count_lte_total.sql
-- =============================================================================
-- Business rule: on_time_trips can never exceed total_trips for a route on a day.
-- Ensures the aggregation logic in int_route_performance is correct.
-- =============================================================================

select
    route_id,
    trip_date,
    on_time_trips,
    total_trips
from {{ ref('mart_route_summary') }}
where on_time_trips > total_trips
