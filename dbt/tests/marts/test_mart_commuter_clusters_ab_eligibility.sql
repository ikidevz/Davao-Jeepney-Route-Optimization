-- =============================================================================
-- tests/marts/test_mart_commuter_clusters_ab_eligibility.sql
-- =============================================================================
-- Business rule: is_ab_test_eligible = TRUE  ↔ cluster_id = 3
--                is_ab_test_eligible = FALSE ↔ cluster_id ≠ 3
-- Mirrors the DB constraint chk_mcc_ab_eligible_logic from 06_tables_marts.sql.
-- =============================================================================

select
    passenger_id,
    cluster_id,
    is_ab_test_eligible
from {{ ref('mart_commuter_clusters') }}
where
    (is_ab_test_eligible = true  and cluster_id <> 3)
    or
    (is_ab_test_eligible = false and cluster_id  = 3)
