-- =============================================================================
-- macros/get_current_ph_timestamp.sql
-- =============================================================================
-- Returns the current timestamp in Philippine Time (UTC+8).
-- Used in mart models for refreshed_at audit columns.
--
-- Usage in SQL:
--   {{ get_current_ph_timestamp() }}
-- =============================================================================

{% macro get_current_ph_timestamp() %}
    (now() at time zone 'Asia/Manila')
{% endmacro %}
