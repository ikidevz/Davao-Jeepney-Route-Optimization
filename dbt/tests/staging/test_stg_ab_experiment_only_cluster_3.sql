-- =============================================================================
-- tests/staging/test_stg_ab_experiment_only_cluster_3.sql
-- =============================================================================
-- Business rule: Only Cluster 3 (Underserved Riders) passengers participate
-- in the A/B experiment. Any other cluster_id is a seeding or ingestion error.
-- =============================================================================

select
    experiment_record_id,
    passenger_id,
    cluster_id
from {{ ref('stg_ab_experiment') }}
where cluster_id <> 3
