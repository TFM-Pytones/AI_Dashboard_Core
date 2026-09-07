{{ config(
    materialized='table',
    tags=['silver', 'istac', 'trimestral']
) }}

WITH empleo_hosteleria AS (
    SELECT 
        "GEOGRAPHICAL" AS municipio,
        "GEOGRAPHICAL_CODE" AS municipio_cod,
        CAST(SUBSTRING(TRIM("TIME_CODE"::text) FROM 1 FOR 4) AS INTEGER) AS anio,
        CAST(SUBSTRING(TRIM("TIME_CODE"::text) FROM 7 FOR 1) AS INTEGER) AS trimestre,
        "TIME_CODE"::text AS periodo_codigo,
        "TIME" AS periodo_texto,
        CAST(NULLIF(REPLACE(TRIM("OBS_VALUE"::text), ',', '.'), '.') AS NUMERIC) AS empleo_hosteleria
    FROM {{ source('bronze', 'bronze_istac_mun_empleo_hosteleria') }}
    WHERE "MEASURE_CODE" = 'ABSOLUTE' 
      AND "TIME_CODE"::text LIKE '____-Q_'
      AND CAST(SUBSTRING(TRIM("TIME_CODE"::text) FROM 1 FOR 4) AS INTEGER) >= 2022
)

SELECT
    eh.municipio,
    eh.municipio_cod,
    eh.anio,
    eh.trimestre,
    eh.periodo_codigo,
    eh.periodo_texto,
    eh.empleo_hosteleria
FROM empleo_hosteleria eh
ORDER BY eh.municipio ASC, eh.anio ASC, eh.trimestre ASC
