{{ config(
    materialized='table',
    tags=['silver', 'istac', 'anual']
) }}

WITH poblacion_total AS (
    SELECT 
        "GEOGRAPHICAL" AS municipio,
        "GEOGRAPHICAL_CODE" AS municipio_cod,
        CAST(SUBSTRING(TRIM("TIME_CODE"::text) FROM 1 FOR 4) AS INTEGER) AS anio,
        CAST(NULLIF(REPLACE(TRIM("OBS_VALUE"::text), ',', '.'), '.') AS NUMERIC) AS poblacion_total
    FROM {{ source('bronze', 'bronze_istac_mun_poblacion_total') }}
    WHERE "MEASURE_CODE" = 'ABSOLUTE' 
      AND LENGTH(TRIM("TIME_CODE"::text)) = 4
      AND CAST(TRIM("TIME_CODE"::text) AS INTEGER) >= 2022
),
poblacion_15_64 AS (
    SELECT 
        "GEOGRAPHICAL_CODE" AS municipio_cod,
        CAST(SUBSTRING(TRIM("TIME_CODE"::text) FROM 1 FOR 4) AS INTEGER) AS anio,
        CAST(NULLIF(REPLACE(TRIM("OBS_VALUE"::text), ',', '.'), '.') AS NUMERIC) AS poblacion_15_64
    FROM {{ source('bronze', 'bronze_istac_mun_poblacion_15_64') }}
    WHERE "MEASURE_CODE" = 'ABSOLUTE'
      AND LENGTH(TRIM("TIME_CODE"::text)) = 4
      AND CAST(TRIM("TIME_CODE"::text) AS INTEGER) >= 2022
),
poblacion_65_mas AS (
    SELECT 
        "GEOGRAPHICAL_CODE" AS municipio_cod,
        CAST(SUBSTRING(TRIM("TIME_CODE"::text) FROM 1 FOR 4) AS INTEGER) AS anio,
        CAST(NULLIF(REPLACE(TRIM("OBS_VALUE"::text), ',', '.'), '.') AS NUMERIC) AS poblacion_65_mas
    FROM {{ source('bronze', 'bronze_istac_mun_poblacion_65_mas') }}
    WHERE "MEASURE_CODE" = 'ABSOLUTE'
      AND LENGTH(TRIM("TIME_CODE"::text)) = 4
      AND CAST(TRIM("TIME_CODE"::text) AS INTEGER) >= 2022
),
edad_media AS (
    SELECT 
        "GEOGRAPHICAL_CODE" AS municipio_cod,
        CAST(SUBSTRING(TRIM("TIME_CODE"::text) FROM 1 FOR 4) AS INTEGER) AS anio,
        CAST(NULLIF(REPLACE(TRIM("OBS_VALUE"::text), ',', '.'), '.') AS NUMERIC) AS edad_media
    FROM {{ source('bronze', 'bronze_istac_mun_edad_media') }}
    WHERE "MEASURE_CODE" = 'ABSOLUTE'
      AND LENGTH(TRIM("TIME_CODE"::text)) = 4
      AND CAST(TRIM("TIME_CODE"::text) AS INTEGER) >= 2022
)

SELECT
    pt.municipio,
    pt.municipio_cod,
    pt.anio,
    pt.poblacion_total,
    p15.poblacion_15_64,
    p65.poblacion_65_mas,
    em.edad_media
FROM poblacion_total pt
LEFT JOIN poblacion_15_64 p15 ON pt.municipio_cod = p15.municipio_cod AND pt.anio = p15.anio
LEFT JOIN poblacion_65_mas p65 ON pt.municipio_cod = p65.municipio_cod AND pt.anio = p65.anio
LEFT JOIN edad_media em ON pt.municipio_cod = em.municipio_cod AND pt.anio = em.anio
ORDER BY pt.municipio ASC, pt.anio ASC