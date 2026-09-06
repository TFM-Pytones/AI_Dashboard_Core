{#
    Override del macro por defecto de dbt.

    Por defecto, dbt concatena target_schema + "_" + custom_schema (p.ej.
    "silver_gold") cuando un modelo define `+schema:`. Aqui queremos que un
    modelo con `+schema: gold` (ver dbt_project.yml) aterrice literalmente en
    el esquema `gold`, igual que los modelos de `silver` (sin +schema propio)
    aterrizan en el esquema por defecto del target (`silver`, ver profiles.yml).
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
