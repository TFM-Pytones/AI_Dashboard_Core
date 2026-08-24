{{ config(
    materialized='table',
    tags=['silver', 'istac', 'anual']
) }}

WITH source_data AS (
    SELECT *
    FROM {{ source('bronze', 'istac_municipios') }}
    WHERE "MEASURE_CODE" = 'ABSOLUTE'
      AND _indicador IN (
          'poblacion_total', 'poblacion_15_64', 'poblacion_65_mas', 
          'edad_media', 'saldo_migratorio', 'pob_turistica_equiv'
      )
)

SELECT
    "GEOGRAPHICAL" AS municipio,
    "GEOGRAPHICAL_CODE" AS municipio_cod,
    CAST(SUBSTRING(TRIM("TIME_CODE"::text) FROM 1 FOR 4) AS INTEGER) AS anio,
    
    -- Variables Anuales
    MAX(CASE WHEN _indicador = 'poblacion_total' THEN CAST(NULLIF(REPLACE(TRIM("OBS_VALUE"::text), ',', '.'), '.') AS NUMERIC) END) AS poblacion_total,
    MAX(CASE WHEN _indicador = 'poblacion_15_64' THEN CAST(NULLIF(REPLACE(TRIM("OBS_VALUE"::text), ',', '.'), '.') AS NUMERIC) END) AS poblacion_15_64,
    MAX(CASE WHEN _indicador = 'poblacion_65_mas' THEN CAST(NULLIF(REPLACE(TRIM("OBS_VALUE"::text), ',', '.'), '.') AS NUMERIC) END) AS poblacion_65_mas,
    MAX(CASE WHEN _indicador = 'edad_media' THEN CAST(NULLIF(REPLACE(TRIM("OBS_VALUE"::text), ',', '.'), '.') AS NUMERIC) END) AS edad_media,
    MAX(CASE WHEN _indicador = 'saldo_migratorio' THEN CAST(NULLIF(REPLACE(TRIM("OBS_VALUE"::text), ',', '.'), '.') AS NUMERIC) END) AS saldo_migratorio,
    MAX(CASE WHEN _indicador = 'pob_turistica_equiv' THEN CAST(NULLIF(REPLACE(TRIM("OBS_VALUE"::text), ',', '.'), '.') AS NUMERIC) END) AS pob_turistica_equiv

FROM source_data
GROUP BY "GEOGRAPHICAL", "GEOGRAPHICAL_CODE", CAST(SUBSTRING(TRIM("TIME_CODE"::text) FROM 1 FOR 4) AS INTEGER)
ORDER BY municipio ASC, anio ASC
