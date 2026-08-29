{{ config(materialized='table', tags=['silver', 'espacial']) }}

/*
  Modelo Silver: silver_limites_municipales
  Geometrías limpias de los 31 municipios de Tenerife.
  Calcula área en km² y centroide para joins rápidos en Gold.
  Requiere PostGIS activado en el esquema.
*/

SELECT
    cod_municipio,
    nombre_municipio,
    nombre_municipio_normalizado,
    -- Área en km² (geometry en EPSG:32628 → unidades en metros)
    ROUND(CAST(ST_Area(geometry::geography) / 1000000.0 AS NUMERIC), 2) AS area_km2,
    -- Centroide para joins de puntos sin PostGIS
    ST_X(ST_Centroid(geometry)) AS centroide_lon,
    ST_Y(ST_Centroid(geometry)) AS centroide_lat,
    ST_Transform(ST_SetSRID(geometry, COALESCE(NULLIF(ST_SRID(geometry), 0), 4326)), 4326) AS geometry
FROM {{ source('bronze', 'limites_municipales') }}
WHERE cod_municipio IS NOT NULL
  AND geometry IS NOT NULL
