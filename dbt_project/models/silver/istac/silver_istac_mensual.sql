{{ config(
    materialized='table',
    tags=['silver', 'istac', 'mensual']
) }}

/*
  Modelo Silver: silver_istac_mensual
  Consolida los indicadores mensuales del ISTAC (2022 a 2026):
  - Paro registrado municipal.
  - Métricas de Vivienda Vacacional (plazas, tasa de ocupación, estancia media, ingresos, alojamientos).
  - Métricas de Alojamientos Turísticos / EOH (pernoctaciones, plazas ofertadas, tasa de ocupación por plazas, viajeros entrados).
*/

WITH paro_registrado AS (
    SELECT 
        "GEOGRAPHICAL" AS municipio,
        "GEOGRAPHICAL_CODE" AS municipio_cod,
        CAST(SUBSTRING(TRIM("TIME_CODE"::text) FROM 1 FOR 4) AS INTEGER) AS anio,
        CAST(SUBSTRING(TRIM("TIME_CODE"::text) FROM 6 FOR 2) AS INTEGER) AS mes,
        "TIME_CODE"::text AS periodo_codigo,
        "TIME" AS periodo_texto,
        CAST(NULLIF(REPLACE(TRIM("OBS_VALUE"::text), ',', '.'), '.') AS NUMERIC) AS paro_registrado
    FROM {{ source('bronze', 'bronze_istac_mun_paro_registrado') }}
    WHERE "MEASURE_CODE" = 'ABSOLUTE' 
      AND "TIME_CODE"::text LIKE '____-__'
      AND CAST(SUBSTRING(TRIM("TIME_CODE"::text) FROM 1 FOR 4) AS INTEGER) >= 2022
),

estancia_media_vv AS (
    SELECT 
        "GEOGRAPHICAL_CODE" AS municipio_cod,
        "TIME_CODE"::text AS periodo_codigo,
        CAST(NULLIF(REPLACE(TRIM("OBS_VALUE"::text), ',', '.'), '.') AS NUMERIC) AS estancia_media_vv
    FROM {{ source('bronze', 'bronze_istac_mun_estancia_media_vv') }}
    WHERE "MEASURE_CODE" = 'ABSOLUTE' 
      AND "TIME_CODE"::text LIKE '____-__'
      AND CAST(SUBSTRING(TRIM("TIME_CODE"::text) FROM 1 FOR 4) AS INTEGER) >= 2022
),

ingresos_vv AS (
    SELECT 
        "GEOGRAPHICAL_CODE" AS municipio_cod,
        "TIME_CODE"::text AS periodo_codigo,
        CAST(NULLIF(REPLACE(TRIM("OBS_VALUE"::text), ',', '.'), '.') AS NUMERIC) AS ingresos_vv
    FROM {{ source('bronze', 'bronze_istac_mun_ingresos_vv') }}
    WHERE "MEASURE_CODE" = 'ABSOLUTE' 
      AND "TIME_CODE"::text LIKE '____-__'
      AND CAST(SUBSTRING(TRIM("TIME_CODE"::text) FROM 1 FOR 4) AS INTEGER) >= 2022
),

plazas_vv AS (
    SELECT 
        "GEOGRAPHICAL_CODE" AS municipio_cod,
        "TIME_CODE"::text AS periodo_codigo,
        CAST(NULLIF(REPLACE(TRIM("OBS_VALUE"::text), ',', '.'), '.') AS NUMERIC) AS plazas_vv
    FROM {{ source('bronze', 'bronze_istac_mun_plazas_vv') }}
    WHERE "MEASURE_CODE" = 'ABSOLUTE' 
      AND "TIME_CODE"::text LIKE '____-__'
      AND CAST(SUBSTRING(TRIM("TIME_CODE"::text) FROM 1 FOR 4) AS INTEGER) >= 2022
),

tasa_ocupacion_vv AS (
    SELECT 
        "GEOGRAPHICAL_CODE" AS municipio_cod,
        "TIME_CODE"::text AS periodo_codigo,
        CAST(NULLIF(REPLACE(TRIM("OBS_VALUE"::text), ',', '.'), '.') AS NUMERIC) AS tasa_ocupacion_vv
    FROM {{ source('bronze', 'bronze_istac_mun_tasa_ocupacion_vv') }}
    WHERE "MEASURE_CODE" = 'ABSOLUTE' 
      AND "TIME_CODE"::text LIKE '____-__'
      AND CAST(SUBSTRING(TRIM("TIME_CODE"::text) FROM 1 FOR 4) AS INTEGER) >= 2022
),

alojamientos_abiertos_vv AS (
    SELECT 
        "GEOGRAPHICAL_CODE" AS municipio_cod,
        "TIME_CODE"::text AS periodo_codigo,
        CAST(NULLIF(REPLACE(TRIM("OBS_VALUE"::text), ',', '.'), '.') AS NUMERIC) AS alojamientos_abiertos_vv
    FROM {{ source('bronze', 'bronze_istac_mun_alojamientos_abiertos_vv') }}
    WHERE "MEASURE_CODE" = 'ABSOLUTE' 
      AND "TIME_CODE"::text LIKE '____-__'
      AND CAST(SUBSTRING(TRIM("TIME_CODE"::text) FROM 1 FOR 4) AS INTEGER) >= 2022
),

pernoctaciones AS (
    SELECT 
        "GEOGRAPHICAL_CODE" AS municipio_cod,
        "TIME_CODE"::text AS periodo_codigo,
        CAST(NULLIF(REPLACE(TRIM("OBS_VALUE"::text), ',', '.'), '.') AS NUMERIC) AS pernoctaciones
    FROM {{ source('bronze', 'bronze_istac_mun_pernoctaciones') }}
    WHERE "MEASURE_CODE" = 'ABSOLUTE' 
      AND "TIME_CODE"::text LIKE '____-__'
      AND CAST(SUBSTRING(TRIM("TIME_CODE"::text) FROM 1 FOR 4) AS INTEGER) >= 2022
),

plazas_ofertadas AS (
    SELECT 
        "GEOGRAPHICAL_CODE" AS municipio_cod,
        "TIME_CODE"::text AS periodo_codigo,
        CAST(NULLIF(REPLACE(TRIM("OBS_VALUE"::text), ',', '.'), '.') AS NUMERIC) AS plazas_ofertadas
    FROM {{ source('bronze', 'bronze_istac_mun_plazas_ofertadas') }}
    WHERE "MEASURE_CODE" = 'ABSOLUTE' 
      AND "TIME_CODE"::text LIKE '____-__'
      AND CAST(SUBSTRING(TRIM("TIME_CODE"::text) FROM 1 FOR 4) AS INTEGER) >= 2022
),

tasa_ocupacion_plazas AS (
    SELECT 
        "GEOGRAPHICAL_CODE" AS municipio_cod,
        "TIME_CODE"::text AS periodo_codigo,
        CAST(NULLIF(REPLACE(TRIM("OBS_VALUE"::text), ',', '.'), '.') AS NUMERIC) AS tasa_ocupacion_plazas
    FROM {{ source('bronze', 'bronze_istac_mun_tasa_ocupacion_plazas') }}
    WHERE "MEASURE_CODE" = 'ABSOLUTE' 
      AND "TIME_CODE"::text LIKE '____-__'
      AND CAST(SUBSTRING(TRIM("TIME_CODE"::text) FROM 1 FOR 4) AS INTEGER) >= 2022
),

viajeros_entrados AS (
    SELECT 
        "GEOGRAPHICAL_CODE" AS municipio_cod,
        "TIME_CODE"::text AS periodo_codigo,
        CAST(NULLIF(REPLACE(TRIM("OBS_VALUE"::text), ',', '.'), '.') AS NUMERIC) AS viajeros_entrados
    FROM {{ source('bronze', 'bronze_istac_mun_viajeros_entrados') }}
    WHERE "MEASURE_CODE" = 'ABSOLUTE' 
      AND "TIME_CODE"::text LIKE '____-__'
      AND CAST(SUBSTRING(TRIM("TIME_CODE"::text) FROM 1 FOR 4) AS INTEGER) >= 2022
)

SELECT
    pr.municipio,
    pr.municipio_cod,
    pr.anio,
    pr.mes,
    pr.periodo_codigo,
    pr.periodo_texto,
    pr.paro_registrado,
    
    -- Vivienda Vacacional (ISTAC)
    em.estancia_media_vv,
    ing.ingresos_vv,
    pl.plazas_vv,
    to_vv.tasa_ocupacion_vv,
    aloj.alojamientos_abiertos_vv,
    
    -- Alojamientos Turísticos / EOH (ISTAC)
    pern.pernoctaciones,
    po.plazas_ofertadas,
    topz.tasa_ocupacion_plazas,
    ve.viajeros_entrados

FROM paro_registrado pr
LEFT JOIN estancia_media_vv em ON pr.municipio_cod = em.municipio_cod AND pr.periodo_codigo = em.periodo_codigo
LEFT JOIN ingresos_vv ing ON pr.municipio_cod = ing.municipio_cod AND pr.periodo_codigo = ing.periodo_codigo
LEFT JOIN plazas_vv pl ON pr.municipio_cod = pl.municipio_cod AND pr.periodo_codigo = pl.periodo_codigo
LEFT JOIN tasa_ocupacion_vv to_vv ON pr.municipio_cod = to_vv.municipio_cod AND pr.periodo_codigo = to_vv.periodo_codigo
LEFT JOIN alojamientos_abiertos_vv aloj ON pr.municipio_cod = aloj.municipio_cod AND pr.periodo_codigo = aloj.periodo_codigo
LEFT JOIN pernoctaciones pern ON pr.municipio_cod = pern.municipio_cod AND pr.periodo_codigo = pern.periodo_codigo
LEFT JOIN plazas_ofertadas po ON pr.municipio_cod = po.municipio_cod AND pr.periodo_codigo = po.periodo_codigo
LEFT JOIN tasa_ocupacion_plazas topz ON pr.municipio_cod = topz.municipio_cod AND pr.periodo_codigo = topz.periodo_codigo
LEFT JOIN viajeros_entrados ve ON pr.municipio_cod = ve.municipio_cod AND pr.periodo_codigo = ve.periodo_codigo
ORDER BY pr.municipio ASC, pr.anio ASC, pr.mes ASC
