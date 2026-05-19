-- =============================================================================
-- tests/marts/test_mart_district_ridership_peak_lte_total.sql
-- =============================================================================
-- Business rule: peak_boardings can never exceed total_boardings for a district
-- on a given day. Also checks weekend_boardings <= total_boardings.
-- =============================================================================

select
    district,
    trip_date,
    peak_boardings,
    weekend_boardings,
    total_boardings
from {{ ref('mart_district_ridership') }}
where
    peak_boardings    > total_boardings
    or
    weekend_boardings > total_boardings
