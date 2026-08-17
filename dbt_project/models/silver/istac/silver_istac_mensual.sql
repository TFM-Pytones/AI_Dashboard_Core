{{ config(
    materialized='table',
    tags=['silver', 'istac', 'mensual']
) }}

WITH source_data AS (
    SELECT *
    FROM {{ source('bronze', 'istac_municipios') }}
    WHERE "MEASURE_CODE" = 'ABSOLUTE'
      AND "TIME_CODE"::text LIKE '____-__'
)

SELECT
    "GEOGRAPHICAL" AS municipio,
    "GEOGRAPHICAL_CODE" AS municipio_cod,
    CAST(SUBSTRING(TRIM("TIME_CODE"::text) FROM 1 FOR 4) AS INTEGER) AS anio,
    CAST(SUBSTRING(TRIM("TIME_CODE"::text) FROM 6 FOR 2) AS INTEGER) AS mes,
    "TIME_CODE"::text AS periodo_codigo,
    "TIME" AS periodo_texto,
    
    -- Variables Mensuales
    MAX(CASE WHEN _indicador = 'pernoctaciones' THEN CAST(NULLIF(REPLACE(TRIM("OBS_VALUE"::text), ',', '.'), '.') AS NUMERIC) END) AS pernoctaciones,
    MAX(CASE WHEN _indicador = 'viajeros_entrados' THEN CAST(NULLIF(REPLACE(TRIM("OBS_VALUE"::text), ',', '.'), '.') AS NUMERIC) END) AS viajeros_entrados,
    MAX(CASE WHEN _indicador = 'plazas_ofertadas' THEN CAST(NULLIF(REPLACE(TRIM("OBS_VALUE"::text), ',', '.'), '.') AS NUMERIC) END) AS plazas_ofertadas,
    MAX(CASE WHEN _indicador = 'alojamientos_abiertos' THEN CAST(NULLIF(REPLACE(TRIM("OBS_VALUE"::text), ',', '.'), '.') AS NUMERIC) END) AS alojamientos_abiertos,
    MAX(CASE WHEN _indicador = 'tasa_ocupacion_plazas' THEN CAST(NULLIF(REPLACE(TRIM("OBS_VALUE"::text), ',', '.'), '.') AS NUMERIC) END) AS tasa_ocupacion_plazas,
    MAX(CASE WHEN _indicador = 'paro_registrado' THEN CAST(NULLIF(REPLACE(TRIM("OBS_VALUE"::text), ',', '.'), '.') AS NUMERIC) END) AS paro_registrado,
    MAX(CASE WHEN _indicador = 'empresas_ss' THEN CAST(NULLIF(REPLACE(TRIM("OBS_VALUE"::text), ',', '.'), '.') AS NUMERIC) END) AS empresas_ss

FROM source_data
GROUP BY "GEOGRAPHICAL", "GEOGRAPHICAL_CODE", "TIME_CODE", "TIME"
ORDER BY municipio ASC, anio ASC, mes ASC
