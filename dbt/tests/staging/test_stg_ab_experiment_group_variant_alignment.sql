-- =============================================================================
-- tests/staging/test_stg_ab_experiment_group_variant_alignment.sql
-- =============================================================================
-- Business rule: control group  → always A_existing_route
--                treatment group → always B_express_direct
-- Any mismatch is a data integrity failure (enforced by DB constraint but
-- tested here at the dbt layer too for full observability).
-- =============================================================================

select
    experiment_record_id,
    "group",
    route_variant
from {{ ref('stg_ab_experiment') }}
where
    ("group" = 'control'   and route_variant <> 'A_existing_route')
    or
    ("group" = 'treatment' and route_variant <> 'B_express_direct')
