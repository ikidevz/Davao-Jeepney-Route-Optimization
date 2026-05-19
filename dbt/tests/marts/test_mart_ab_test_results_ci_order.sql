-- =============================================================================
-- tests/marts/test_mart_ab_test_results_ci_order.sql
-- =============================================================================
-- Business rule: confidence_interval_low must be <= confidence_interval_high.
-- Applies only to rows where statistical results have been populated
-- (i.e., science/ab_testing.py has run). Rows with NULLs are skipped.
-- =============================================================================

select
    experiment_record_id,
    confidence_interval_low,
    confidence_interval_high
from {{ ref('mart_ab_test_results') }}
where
    confidence_interval_low  is not null
    and confidence_interval_high is not null
    and confidence_interval_low > confidence_interval_high
