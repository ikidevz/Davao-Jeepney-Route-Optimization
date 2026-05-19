-- =============================================================================
-- macros/encode_income_bracket.sql
-- =============================================================================
-- Encodes income_bracket categorical string as an ordinal integer.
-- low=1, middle=2, high=3. NULL for any unexpected value.
-- Used consistently across int_passenger_features and any future feature models.
--
-- Usage:
--   {{ encode_income_bracket('income_bracket') }}
-- =============================================================================

{% macro encode_income_bracket(column_name) %}
    case {{ column_name }}
        when 'low'    then 1
        when 'middle' then 2
        when 'high'   then 3
        else null
    end
{% endmacro %}
