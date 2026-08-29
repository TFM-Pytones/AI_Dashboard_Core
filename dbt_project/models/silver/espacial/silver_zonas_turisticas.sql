{{ config(materialized='table', tags=['silver', 'espacial', 'turismo']) }}

/*
  Modelo Silver: silver_zonas_turisticas
  Polígonos de zonas turísticas de Tenerife con área calculada.
*/

SELECT
    id_zona,
    nombre_zona,
    municipio,
    cod_municipio,
    tipo_zona,
    ROUND(CAST(ST_Area(geometry::geography) / 1000000.0 AS NUMERIC), 4) AS area_km2,
    ST_Transform(ST_SetSRID(geometry, COALESCE(NULLIF(ST_SRID(geometry), 0), 4326)), 4326) AS geometry
FROM {{ source('bronze', 'zonas_turisticas') }}
WHERE geometry IS NOT NULL
