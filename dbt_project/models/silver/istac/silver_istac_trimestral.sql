{{ config(
    materialized='table',
    tags=['silver', 'istac', 'trimestral', 'empleo']
) }}

/*
  Modelo Silver: silver_istac_trimestral
  Consolida los indicadores trimestrales de empleo y afiliación a la Seguridad Social
  para los 31 municipios de Tenerife (2022 a 2026).
  Fuente: ISTAC (C00067A - Municipios en Cifras)
*/

WITH base_total AS (
    SELECT 
        "GEOGRAPHICAL" AS municipio,
        "GEOGRAPHICAL_CODE" AS municipio_cod,
        CAST(SUBSTRING(TRIM("TIME_CODE"::text) FROM 1 FOR 4) AS INTEGER) AS anio,
        CAST(SUBSTRING(TRIM("TIME_CODE"::text) FROM 7 FOR 1) AS INTEGER) AS trimestre,
        "TIME_CODE"::text AS periodo_codigo,
        "TIME" AS periodo_texto,
        CAST(NULLIF(REPLACE(TRIM("OBS_VALUE"::text), ',', '.'), '.') AS NUMERIC) AS empleo_total
    FROM {{ source('bronze', 'bronze_istac_mun_empleo_total') }}
    WHERE "MEASURE_CODE" = 'ABSOLUTE' 
      AND "TIME_CODE"::text LIKE '____-Q_'
      AND CAST(SUBSTRING(TRIM("TIME_CODE"::text) FROM 1 FOR 4) AS INTEGER) >= 2021
),

asalariados AS (
    SELECT 
        "GEOGRAPHICAL_CODE" AS municipio_cod,
        "TIME_CODE"::text AS periodo_codigo,
        CAST(NULLIF(REPLACE(TRIM("OBS_VALUE"::text), ',', '.'), '.') AS NUMERIC) AS empleo_asalariados
    FROM {{ source('bronze', 'bronze_istac_mun_empleo_asalariados') }}
    WHERE "MEASURE_CODE" = 'ABSOLUTE' 
      AND "TIME_CODE"::text LIKE '____-Q_'
      AND CAST(SUBSTRING(TRIM("TIME_CODE"::text) FROM 1 FOR 4) AS INTEGER) >= 2021
),

autonomos AS (
    SELECT 
        "GEOGRAPHICAL_CODE" AS municipio_cod,
        "TIME_CODE"::text AS periodo_codigo,
        CAST(NULLIF(REPLACE(TRIM("OBS_VALUE"::text), ',', '.'), '.') AS NUMERIC) AS empleo_autonomos
    FROM {{ source('bronze', 'bronze_istac_mun_empleo_autonomos') }}
    WHERE "MEASURE_CODE" = 'ABSOLUTE' 
      AND "TIME_CODE"::text LIKE '____-Q_'
      AND CAST(SUBSTRING(TRIM("TIME_CODE"::text) FROM 1 FOR 4) AS INTEGER) >= 2021
),

hosteleria AS (
    SELECT 
        "GEOGRAPHICAL_CODE" AS municipio_cod,
        "TIME_CODE"::text AS periodo_codigo,
        CAST(NULLIF(REPLACE(TRIM("OBS_VALUE"::text), ',', '.'), '.') AS NUMERIC) AS empleo_hosteleria
    FROM {{ source('bronze', 'bronze_istac_mun_empleo_hosteleria') }}
    WHERE "MEASURE_CODE" = 'ABSOLUTE' 
      AND "TIME_CODE"::text LIKE '____-Q_'
      AND CAST(SUBSTRING(TRIM("TIME_CODE"::text) FROM 1 FOR 4) AS INTEGER) >= 2021
),

servicios AS (
    SELECT 
        "GEOGRAPHICAL_CODE" AS municipio_cod,
        "TIME_CODE"::text AS periodo_codigo,
        CAST(NULLIF(REPLACE(TRIM("OBS_VALUE"::text), ',', '.'), '.') AS NUMERIC) AS empleo_servicios
    FROM {{ source('bronze', 'bronze_istac_mun_empleo_servicios') }}
    WHERE "MEASURE_CODE" = 'ABSOLUTE' 
      AND "TIME_CODE"::text LIKE '____-Q_'
      AND CAST(SUBSTRING(TRIM("TIME_CODE"::text) FROM 1 FOR 4) AS INTEGER) >= 2021
),

comercio AS (
    SELECT 
        "GEOGRAPHICAL_CODE" AS municipio_cod,
        "TIME_CODE"::text AS periodo_codigo,
        CAST(NULLIF(REPLACE(TRIM("OBS_VALUE"::text), ',', '.'), '.') AS NUMERIC) AS empleo_comercio
    FROM {{ source('bronze', 'bronze_istac_mun_empleo_comercio') }}
    WHERE "MEASURE_CODE" = 'ABSOLUTE' 
      AND "TIME_CODE"::text LIKE '____-Q_'
      AND CAST(SUBSTRING(TRIM("TIME_CODE"::text) FROM 1 FOR 4) AS INTEGER) >= 2021
),

construccion AS (
    SELECT 
        "GEOGRAPHICAL_CODE" AS municipio_cod,
        "TIME_CODE"::text AS periodo_codigo,
        CAST(NULLIF(REPLACE(TRIM("OBS_VALUE"::text), ',', '.'), '.') AS NUMERIC) AS empleo_construccion
    FROM {{ source('bronze', 'bronze_istac_mun_empleo_construccion') }}
    WHERE "MEASURE_CODE" = 'ABSOLUTE' 
      AND "TIME_CODE"::text LIKE '____-Q_'
      AND CAST(SUBSTRING(TRIM("TIME_CODE"::text) FROM 1 FOR 4) AS INTEGER) >= 2021
),

industria AS (
    SELECT 
        "GEOGRAPHICAL_CODE" AS municipio_cod,
        "TIME_CODE"::text AS periodo_codigo,
        CAST(NULLIF(REPLACE(TRIM("OBS_VALUE"::text), ',', '.'), '.') AS NUMERIC) AS empleo_industria
    FROM {{ source('bronze', 'bronze_istac_mun_empleo_industria') }}
    WHERE "MEASURE_CODE" = 'ABSOLUTE' 
      AND "TIME_CODE"::text LIKE '____-Q_'
      AND CAST(SUBSTRING(TRIM("TIME_CODE"::text) FROM 1 FOR 4) AS INTEGER) >= 2021
),

agricultura AS (
    SELECT 
        "GEOGRAPHICAL_CODE" AS municipio_cod,
        "TIME_CODE"::text AS periodo_codigo,
        CAST(NULLIF(REPLACE(TRIM("OBS_VALUE"::text), ',', '.'), '.') AS NUMERIC) AS empleo_agricultura
    FROM {{ source('bronze', 'bronze_istac_mun_empleo_agricultura') }}
    WHERE "MEASURE_CODE" = 'ABSOLUTE' 
      AND "TIME_CODE"::text LIKE '____-Q_'
      AND CAST(SUBSTRING(TRIM("TIME_CODE"::text) FROM 1 FOR 4) AS INTEGER) >= 2021
)

SELECT
    bt.municipio,
    bt.municipio_cod,
    bt.anio,
    bt.trimestre,
    bt.periodo_codigo,
    bt.periodo_texto,
    bt.empleo_total,
    asa.empleo_asalariados,
    aut.empleo_autonomos,
    hos.empleo_hosteleria,
    ser.empleo_servicios,
    com.empleo_comercio,
    con.empleo_construccion,
    ind.empleo_industria,
    agr.empleo_agricultura
FROM base_total bt
LEFT JOIN asalariados asa ON bt.municipio_cod = asa.municipio_cod AND bt.periodo_codigo = asa.periodo_codigo
LEFT JOIN autonomos aut ON bt.municipio_cod = aut.municipio_cod AND bt.periodo_codigo = aut.periodo_codigo
LEFT JOIN hosteleria hos ON bt.municipio_cod = hos.municipio_cod AND bt.periodo_codigo = hos.periodo_codigo
LEFT JOIN servicios ser ON bt.municipio_cod = ser.municipio_cod AND bt.periodo_codigo = ser.periodo_codigo
LEFT JOIN comercio com ON bt.municipio_cod = com.municipio_cod AND bt.periodo_codigo = com.periodo_codigo
LEFT JOIN construccion con ON bt.municipio_cod = con.municipio_cod AND bt.periodo_codigo = con.periodo_codigo
LEFT JOIN industria ind ON bt.municipio_cod = ind.municipio_cod AND bt.periodo_codigo = ind.periodo_codigo
LEFT JOIN agricultura agr ON bt.municipio_cod = agr.municipio_cod AND bt.periodo_codigo = agr.periodo_codigo
ORDER BY bt.municipio ASC, bt.anio ASC, bt.trimestre ASC
