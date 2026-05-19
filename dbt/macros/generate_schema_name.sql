-- =============================================================================
-- macros/generate_schema_name.sql
-- =============================================================================
-- Overrides dbt's default schema naming behaviour.
-- By default dbt appends the target schema prefix to custom schema names,
-- producing e.g. "staging_staging" or "dev_marts". This macro disables
-- that behaviour so models land in "staging" and "marts" exactly as specified
-- in dbt_project.yml, matching the schemas created by 04_schemas.sql.
--
-- Reference: https://docs.getdbt.com/docs/build/custom-schemas
-- =============================================================================

{% macro generate_schema_name(custom_schema_name, node) -%}

    {%- set default_schema = target.schema -%}

    {%- if custom_schema_name is none -%}
        {{ default_schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}

{%- endmacro %}
