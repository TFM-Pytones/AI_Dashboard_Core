{{ config(
    materialized='table',
    tags=['silver', 'istac']
) }}

WITH source_data AS (
    SELECT *
    FROM {{ source('bronze', 'istac_municipios') }}
    WHERE "MEASURE_CODE" = 'ABSOLUTE'
)

SELECT
    "GEOGRAPHICAL" AS municipio,
    "GEOGRAPHICAL_CODE" AS municipio_cod,
    "TIME" AS periodo_original,
    CAST(SUBSTRING(TRIM("TIME") FROM 1 FOR 4) AS INTEGER) AS anio,
    CASE
        WHEN "TIME" ILIKE '%Enero%' THEN 1
        WHEN "TIME" ILIKE '%Febrero%' THEN 2
        WHEN "TIME" ILIKE '%Marzo%' THEN 3
        WHEN "TIME" ILIKE '%Abril%' THEN 4
        WHEN "TIME" ILIKE '%Mayo%' THEN 5
        WHEN "TIME" ILIKE '%Junio%' THEN 6
        WHEN "TIME" ILIKE '%Julio%' THEN 7
        WHEN "TIME" ILIKE '%Agosto%' THEN 8
        WHEN "TIME" ILIKE '%Septiembre%' THEN 9
        WHEN "TIME" ILIKE '%Octubre%' THEN 10
        WHEN "TIME" ILIKE '%Noviembre%' THEN 11
        WHEN "TIME" ILIKE '%Diciembre%' THEN 12
        ELSE NULL
    END AS mes,
    
    -- Variables Demográficas
    MAX(CASE WHEN _indicador = 'poblacion_total' THEN CAST(NULLIF(REPLACE(TRIM("OBS_VALUE"), ',', '.'), '.') AS NUMERIC) END) AS poblacion_total,
    MAX(CASE WHEN _indicador = 'poblacion_15_64' THEN CAST(NULLIF(REPLACE(TRIM("OBS_VALUE"), ',', '.'), '.') AS NUMERIC) END) AS poblacion_15_64,
    MAX(CASE WHEN _indicador = 'poblacion_65_mas' THEN CAST(NULLIF(REPLACE(TRIM("OBS_VALUE"), ',', '.'), '.') AS NUMERIC) END) AS poblacion_65_mas,
    MAX(CASE WHEN _indicador = 'edad_media' THEN CAST(NULLIF(REPLACE(TRIM("OBS_VALUE"), ',', '.'), '.') AS NUMERIC) END) AS edad_media,
    MAX(CASE WHEN _indicador = 'saldo_migratorio' THEN CAST(NULLIF(REPLACE(TRIM("OBS_VALUE"), ',', '.'), '.') AS NUMERIC) END) AS saldo_migratorio,
    
    -- Variables Económicas y de Empleo
    MAX(CASE WHEN _indicador = 'paro_registrado' THEN CAST(NULLIF(REPLACE(TRIM("OBS_VALUE"), ',', '.'), '.') AS NUMERIC) END) AS paro_registrado,
    MAX(CASE WHEN _indicador = 'empresas_ss' THEN CAST(NULLIF(REPLACE(TRIM("OBS_VALUE"), ',', '.'), '.') AS NUMERIC) END) AS empresas_ss,
    MAX(CASE WHEN _indicador = 'empleo_servicios' THEN CAST(NULLIF(REPLACE(TRIM("OBS_VALUE"), ',', '.'), '.') AS NUMERIC) END) AS empleo_servicios,
    MAX(CASE WHEN _indicador = 'empleo_hosteleria' THEN CAST(NULLIF(REPLACE(TRIM("OBS_VALUE"), ',', '.'), '.') AS NUMERIC) END) AS empleo_hosteleria,
    
    -- Variables Geográficas y de Presión Turística
    MAX(CASE WHEN _indicador = 'superficie_km2' THEN CAST(NULLIF(REPLACE(TRIM("OBS_VALUE"), ',', '.'), '.') AS NUMERIC) END) AS superficie_km2,
    MAX(CASE WHEN _indicador = 'pob_turistica_equiv' THEN CAST(NULLIF(REPLACE(TRIM("OBS_VALUE"), ',', '.'), '.') AS NUMERIC) END) AS pob_turistica_equiv,
    
    -- Variables de Oferta y Demanda Turística
    MAX(CASE WHEN _indicador = 'alojamientos_abiertos' THEN CAST(NULLIF(REPLACE(TRIM("OBS_VALUE"), ',', '.'), '.') AS NUMERIC) END) AS alojamientos_abiertos,
    MAX(CASE WHEN _indicador = 'plazas_ofertadas' THEN CAST(NULLIF(REPLACE(TRIM("OBS_VALUE"), ',', '.'), '.') AS NUMERIC) END) AS plazas_ofertadas,
    MAX(CASE WHEN _indicador = 'viajeros_entrados' THEN CAST(NULLIF(REPLACE(TRIM("OBS_VALUE"), ',', '.'), '.') AS NUMERIC) END) AS viajeros_entrados,
    MAX(CASE WHEN _indicador = 'pernoctaciones' THEN CAST(NULLIF(REPLACE(TRIM("OBS_VALUE"), ',', '.'), '.') AS NUMERIC) END) AS pernoctaciones,
    MAX(CASE WHEN _indicador = 'tasa_ocupacion_plazas' THEN CAST(NULLIF(REPLACE(TRIM("OBS_VALUE"), ',', '.'), '.') AS NUMERIC) END) AS tasa_ocupacion_plazas

FROM source_data
GROUP BY "GEOGRAPHICAL", "GEOGRAPHICAL_CODE", "TIME"
ORDER BY municipio ASC, anio ASC, mes ASC NULLS FIRST
