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
    FROM {{ source('bronze', 'istac_mun_poblacion_total') }}
    WHERE "MEASURE_CODE" = 'ABSOLUTE' 
      AND CAST(SUBSTRING(TRIM("TIME_CODE"::text) FROM 1 FOR 4) AS INTEGER) >= 2022
),
poblacion_15_64 AS (
    SELECT 
        "GEOGRAPHICAL_CODE" AS municipio_cod,
        CAST(SUBSTRING(TRIM("TIME_CODE"::text) FROM 1 FOR 4) AS INTEGER) AS anio,
        CAST(NULLIF(REPLACE(TRIM("OBS_VALUE"::text), ',', '.'), '.') AS NUMERIC) AS poblacion_15_64
    FROM {{ source('bronze', 'istac_mun_poblacion_15_64') }}
    WHERE "MEASURE_CODE" = 'ABSOLUTE'
),
poblacion_65_mas AS (
    SELECT 
        "GEOGRAPHICAL_CODE" AS municipio_cod,
        CAST(SUBSTRING(TRIM("TIME_CODE"::text) FROM 1 FOR 4) AS INTEGER) AS anio,
        CAST(NULLIF(REPLACE(TRIM("OBS_VALUE"::text), ',', '.'), '.') AS NUMERIC) AS poblacion_65_mas
    FROM {{ source('bronze', 'istac_mun_poblacion_65_mas') }}
    WHERE "MEASURE_CODE" = 'ABSOLUTE'
),
edad_media AS (
    SELECT 
        "GEOGRAPHICAL_CODE" AS municipio_cod,
        CAST(SUBSTRING(TRIM("TIME_CODE"::text) FROM 1 FOR 4) AS INTEGER) AS anio,
        CAST(NULLIF(REPLACE(TRIM("OBS_VALUE"::text), ',', '.'), '.') AS NUMERIC) AS edad_media
    FROM {{ source('bronze', 'istac_mun_edad_media') }}
    WHERE "MEASURE_CODE" = 'ABSOLUTE'
),
pob_turistica_equiv AS (
    SELECT 
        "GEOGRAPHICAL_CODE" AS municipio_cod,
        CAST(SUBSTRING(TRIM("TIME_CODE"::text) FROM 1 FOR 4) AS INTEGER) AS anio,
        CAST(NULLIF(REPLACE(TRIM("OBS_VALUE"::text), ',', '.'), '.') AS NUMERIC) AS pob_turistica_equiv
    FROM {{ source('bronze', 'istac_mun_pob_turistica_equiv') }}
    WHERE "MEASURE_CODE" = 'ABSOLUTE'
)

SELECT
    pt.municipio,
    pt.municipio_cod,
    pt.anio,
    pt.poblacion_total,
    p15.poblacion_15_64,
    p65.poblacion_65_mas,
    em.edad_media,
    pte.pob_turistica_equiv
FROM poblacion_total pt
LEFT JOIN poblacion_15_64 p15 ON pt.municipio_cod = p15.municipio_cod AND pt.anio = p15.anio
LEFT JOIN poblacion_65_mas p65 ON pt.municipio_cod = p65.municipio_cod AND pt.anio = p65.anio
LEFT JOIN edad_media em ON pt.municipio_cod = em.municipio_cod AND pt.anio = em.anio
LEFT JOIN pob_turistica_equiv pte ON pt.municipio_cod = pte.municipio_cod AND pt.anio = pte.anio
ORDER BY pt.municipio ASC, pt.anio ASC
