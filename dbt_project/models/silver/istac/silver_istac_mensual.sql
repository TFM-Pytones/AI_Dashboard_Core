{{ config(
    materialized='table',
    tags=['silver', 'istac', 'mensual']
) }}

WITH viajeros_entrados AS (
    SELECT 
        "GEOGRAPHICAL" AS municipio,
        "GEOGRAPHICAL_CODE" AS municipio_cod,
        CAST(SUBSTRING(TRIM("TIME_CODE"::text) FROM 1 FOR 4) AS INTEGER) AS anio,
        CAST(SUBSTRING(TRIM("TIME_CODE"::text) FROM 6 FOR 2) AS INTEGER) AS mes,
        "TIME_CODE"::text AS periodo_codigo,
        "TIME" AS periodo_texto,
        CAST(NULLIF(REPLACE(TRIM("OBS_VALUE"::text), ',', '.'), '.') AS NUMERIC) AS viajeros_entrados
    FROM {{ source('bronze', 'istac_mun_viajeros_entrados') }}
    WHERE "MEASURE_CODE" = 'ABSOLUTE' 
      AND "TIME_CODE"::text LIKE '____-__'
      AND CAST(SUBSTRING(TRIM("TIME_CODE"::text) FROM 1 FOR 4) AS INTEGER) >= 2022
),
pernoctaciones AS (
    SELECT 
        "GEOGRAPHICAL_CODE" AS municipio_cod,
        "TIME_CODE"::text AS periodo_codigo,
        CAST(NULLIF(REPLACE(TRIM("OBS_VALUE"::text), ',', '.'), '.') AS NUMERIC) AS pernoctaciones
    FROM {{ source('bronze', 'istac_mun_pernoctaciones') }}
    WHERE "MEASURE_CODE" = 'ABSOLUTE' AND "TIME_CODE"::text LIKE '____-__'
),
plazas_ofertadas AS (
    SELECT 
        "GEOGRAPHICAL_CODE" AS municipio_cod,
        "TIME_CODE"::text AS periodo_codigo,
        CAST(NULLIF(REPLACE(TRIM("OBS_VALUE"::text), ',', '.'), '.') AS NUMERIC) AS plazas_ofertadas
    FROM {{ source('bronze', 'istac_mun_plazas_ofertadas') }}
    WHERE "MEASURE_CODE" = 'ABSOLUTE' AND "TIME_CODE"::text LIKE '____-__'
),
alojamientos_abiertos AS (
    SELECT 
        "GEOGRAPHICAL_CODE" AS municipio_cod,
        "TIME_CODE"::text AS periodo_codigo,
        CAST(NULLIF(REPLACE(TRIM("OBS_VALUE"::text), ',', '.'), '.') AS NUMERIC) AS alojamientos_abiertos
    FROM {{ source('bronze', 'istac_mun_alojamientos_abiertos') }}
    WHERE "MEASURE_CODE" = 'ABSOLUTE' AND "TIME_CODE"::text LIKE '____-__'
),
tasa_ocupacion_plazas AS (
    SELECT 
        "GEOGRAPHICAL_CODE" AS municipio_cod,
        "TIME_CODE"::text AS periodo_codigo,
        CAST(NULLIF(REPLACE(TRIM("OBS_VALUE"::text), ',', '.'), '.') AS NUMERIC) AS tasa_ocupacion_plazas
    FROM {{ source('bronze', 'istac_mun_tasa_ocupacion_plazas') }}
    WHERE "MEASURE_CODE" = 'ABSOLUTE' AND "TIME_CODE"::text LIKE '____-__'
),
paro_registrado AS (
    SELECT 
        "GEOGRAPHICAL_CODE" AS municipio_cod,
        "TIME_CODE"::text AS periodo_codigo,
        CAST(NULLIF(REPLACE(TRIM("OBS_VALUE"::text), ',', '.'), '.') AS NUMERIC) AS paro_registrado
    FROM {{ source('bronze', 'istac_mun_paro_registrado') }}
    WHERE "MEASURE_CODE" = 'ABSOLUTE' AND "TIME_CODE"::text LIKE '____-__'
)

SELECT
    ve.municipio,
    ve.municipio_cod,
    ve.anio,
    ve.mes,
    ve.periodo_codigo,
    ve.periodo_texto,
    pe.pernoctaciones,
    ve.viajeros_entrados,
    po.plazas_ofertadas,
    aa.alojamientos_abiertos,
    "to".tasa_ocupacion_plazas,
    pr.paro_registrado
FROM viajeros_entrados ve
LEFT JOIN pernoctaciones pe ON ve.municipio_cod = pe.municipio_cod AND ve.periodo_codigo = pe.periodo_codigo
LEFT JOIN plazas_ofertadas po ON ve.municipio_cod = po.municipio_cod AND ve.periodo_codigo = po.periodo_codigo
LEFT JOIN alojamientos_abiertos aa ON ve.municipio_cod = aa.municipio_cod AND ve.periodo_codigo = aa.periodo_codigo
LEFT JOIN tasa_ocupacion_plazas "to" ON ve.municipio_cod = "to".municipio_cod AND ve.periodo_codigo = "to".periodo_codigo
LEFT JOIN paro_registrado pr ON ve.municipio_cod = pr.municipio_cod AND ve.periodo_codigo = pr.periodo_codigo
ORDER BY ve.municipio ASC, ve.anio ASC, ve.mes ASC
