-- =============================================================================
-- macros/assert_column_is_positive.sql
-- =============================================================================
-- Custom test: asserts that all non-null values in a column are > 0.
-- Usage in schema.yml:
--   tests:
--     - assert_column_is_positive
-- =============================================================================

{% test assert_column_is_positive(model, column_name) %}

select {{ column_name }}
from {{ model }}
where {{ column_name }} is not null
  and {{ column_name }} <= 0

{% endtest %}