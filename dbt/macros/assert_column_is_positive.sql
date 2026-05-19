-- =============================================================================
-- macros/assert_column_is_positive.sql
-- =============================================================================
-- Generic test: asserts that a numeric column contains only non-negative values.
-- Usage in schema.yml:
--   tests:
--     - jeepney_dw.assert_column_is_positive
-- =============================================================================

{% test assert_column_is_positive(model, column_name) %}

select
    {{ column_name }}
from {{ model }}
where {{ column_name }} < 0

{% endtest %}
