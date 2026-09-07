{{ config(materialized='table', tags=['silver', 'espacial', 'turismo']) }}

/*
  Modelo Silver: silver_zonas_turisticas
  Polígonos de zonas turísticas de Tenerife con área calculada.
  Columnas reales en bronze: GEOCODE, ETIQUETA, LONGITUD, LATITUD, geometry
*/

WITH source_zonas AS (
    SELECT
        "GEOCODE"   AS id_zona,
        "ETIQUETA"  AS nombre_zona,
        ROUND(CAST(ST_Area(geometry::geography) / 1000000.0 AS NUMERIC), 4) AS area_km2,
        ST_Transform(ST_SetSRID(geometry, COALESCE(NULLIF(ST_SRID(geometry), 0), 4326)), 4326) AS geometry
    FROM {{ source('bronze', 'bronze_zonas_turisticas') }}
    WHERE geometry IS NOT NULL
      AND "GEOCODE" != 'ES709B90'
)

SELECT
    z.id_zona,
    z.nombre_zona,
    m.cod_municipio,
    m.nombre_municipio AS municipio,
    z.area_km2,
    z.geometry
FROM source_zonas z
LEFT JOIN {{ ref('silver_limites_municipales') }} m
  ON ST_Intersects(z.geometry, m.geometry)
  AND ST_Area(ST_Intersection(z.geometry, m.geometry)) = 
      (SELECT MAX(ST_Area(ST_Intersection(z.geometry, m2.geometry)))
       FROM {{ ref('silver_limites_municipales') }} m2
       WHERE ST_Intersects(z.geometry, m2.geometry))
