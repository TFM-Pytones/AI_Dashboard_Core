{{ config(
    materialized='table',
    tags=['silver', 'istac', 'estatico']
) }}

WITH source_data AS (
    SELECT *
    FROM {{ source('bronze', 'istac_municipios') }}
    WHERE "MEASURE_CODE" = 'ABSOLUTE'
      AND _indicador = 'superficie_km2'
)

SELECT
    "GEOGRAPHICAL" AS municipio,
    "GEOGRAPHICAL_CODE" AS municipio_cod,
    MAX(CAST(NULLIF(REPLACE(TRIM("OBS_VALUE"::text), ',', '.'), '.') AS NUMERIC)) AS superficie_km2

FROM source_data
GROUP BY "GEOGRAPHICAL", "GEOGRAPHICAL_CODE"
ORDER BY municipio ASC
