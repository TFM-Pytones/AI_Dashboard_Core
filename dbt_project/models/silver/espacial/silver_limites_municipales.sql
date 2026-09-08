{{ config(materialized='table', tags=['silver', 'espacial']) }}

/*
  Modelo Silver: silver_limites_municipales
  Geometrías limpias de los 31 municipios de Tenerife.
  Calcula área en km² y centroide para joins rápidos en Gold.
  Requiere PostGIS activado en el esquema.
*/

SELECT
    "COD_MUNI" AS cod_municipio,
    "NOMBRE" AS nombre_municipio,
    -- Sumamos las áreas de todos los fragmentos del municipio
    SUM(ROUND(CAST(ST_Area(geometry::geography) / 1000000.0 AS NUMERIC), 2)) AS area_km2,
    -- Centroide del polígono unificado
    ST_X(ST_Centroid(ST_Union(geometry))) AS centroide_lon,
    ST_Y(ST_Centroid(ST_Union(geometry))) AS centroide_lat,
    ST_Transform(ST_SetSRID(ST_Union(geometry), COALESCE(NULLIF(ST_SRID(MAX(geometry)), 0), 4326)), 4326) AS geometry
FROM {{ source('bronze', 'bronze_limites_municipales') }}
WHERE "COD_MUNI" IS NOT NULL
  AND geometry IS NOT NULL
  AND ROUND(CAST(ST_Area(geometry::geography) / 1000000.0 AS NUMERIC), 2) > 0
GROUP BY "COD_MUNI", "NOMBRE"
