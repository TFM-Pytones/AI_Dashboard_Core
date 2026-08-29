{{ config(
    materialized='table',
    tags=['silver', 'istac', 'vivienda_vacacional']
) }}

WITH plazas AS (
    SELECT "GEOGRAPHICAL" AS municipio, "TIME_CODE" AS periodo, CAST(NULLIF(REPLACE(TRIM("OBS_VALUE"::text), ',', '.'), '.') AS NUMERIC) AS plazas_vv
    FROM {{ source('bronze', 'istac_mun_plazas_vv') }}
),
tasa AS (
    SELECT "GEOGRAPHICAL" AS municipio, "TIME_CODE" AS periodo, CAST(NULLIF(REPLACE(TRIM("OBS_VALUE"::text), ',', '.'), '.') AS NUMERIC) AS tasa_ocupacion_vv
    FROM {{ source('bronze', 'istac_mun_tasa_ocupacion_vv') }}
),
estancia AS (
    SELECT "GEOGRAPHICAL" AS municipio, "TIME_CODE" AS periodo, CAST(NULLIF(REPLACE(TRIM("OBS_VALUE"::text), ',', '.'), '.') AS NUMERIC) AS estancia_media_vv
    FROM {{ source('bronze', 'istac_mun_estancia_media_vv') }}
),
ingresos AS (
    SELECT "GEOGRAPHICAL" AS municipio, "TIME_CODE" AS periodo, CAST(NULLIF(REPLACE(TRIM("OBS_VALUE"::text), ',', '.'), '.') AS NUMERIC) AS ingresos_vv
    FROM {{ source('bronze', 'istac_mun_ingresos_vv') }}
),
alojamientos AS (
    SELECT "GEOGRAPHICAL" AS municipio, "TIME_CODE" AS periodo, CAST(NULLIF(REPLACE(TRIM("OBS_VALUE"::text), ',', '.'), '.') AS NUMERIC) AS alojamientos_abiertos_vv
    FROM {{ source('bronze', 'istac_mun_alojamientos_abiertos_vv') }}
)

SELECT
    p.municipio,
    p.periodo,
    CAST(SUBSTRING(TRIM(p.periodo) FROM 1 FOR 4) AS INTEGER) AS anio,
    CAST(SUBSTRING(TRIM(p.periodo) FROM 6 FOR 2) AS INTEGER) AS mes,
    p.plazas_vv,
    t.tasa_ocupacion_vv,
    e.estancia_media_vv,
    i.ingresos_vv,
    a.alojamientos_abiertos_vv
FROM plazas p
LEFT JOIN tasa t ON p.municipio = t.municipio AND p.periodo = t.periodo
LEFT JOIN estancia e ON p.municipio = e.municipio AND p.periodo = e.periodo
LEFT JOIN ingresos i ON p.municipio = i.municipio AND p.periodo = i.periodo
LEFT JOIN alojamientos a ON p.municipio = a.municipio AND p.periodo = a.periodo
WHERE CAST(SUBSTRING(TRIM(p.periodo) FROM 1 FOR 4) AS INTEGER) >= 2022
ORDER BY p.municipio ASC, p.periodo DESC
