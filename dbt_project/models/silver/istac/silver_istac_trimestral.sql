{{ config(
    materialized='table',
    tags=['silver', 'istac', 'trimestral']
) }}

WITH source_data AS (
    SELECT *
    FROM {{ source('bronze', 'istac_municipios') }}
    WHERE "MEASURE_CODE" = 'ABSOLUTE'
      AND "TIME_CODE"::text LIKE '____-Q_'
)

SELECT
    "GEOGRAPHICAL" AS municipio,
    "GEOGRAPHICAL_CODE" AS municipio_cod,
    CAST(SUBSTRING(TRIM("TIME_CODE"::text) FROM 1 FOR 4) AS INTEGER) AS anio,
    CAST(SUBSTRING(TRIM("TIME_CODE"::text) FROM 7 FOR 1) AS INTEGER) AS trimestre,
    "TIME_CODE"::text AS periodo_codigo,
    "TIME" AS periodo_texto,
    
    -- Variables Trimestrales
    MAX(CASE WHEN _indicador = 'empleo_hosteleria' THEN CAST(NULLIF(REPLACE(TRIM("OBS_VALUE"::text), ',', '.'), '.') AS NUMERIC) END) AS empleo_hosteleria,
    MAX(CASE WHEN _indicador = 'empleo_servicios' THEN CAST(NULLIF(REPLACE(TRIM("OBS_VALUE"::text), ',', '.'), '.') AS NUMERIC) END) AS empleo_servicios

FROM source_data
GROUP BY "GEOGRAPHICAL", "GEOGRAPHICAL_CODE", "TIME_CODE", "TIME"
ORDER BY municipio ASC, anio ASC, trimestre ASC
