{{ config(
    materialized='table',
    tags=['silver', 'espacial', 'osm'],
    indexes=[
      {'columns': ['geometry'], 'type': 'gist'},
      {'columns': ['poi_type']}
    ]
) }}

/*
  Modelo Silver: silver_osm_pois
  Columnas reales en bronze: geometry, osm_id, type, group, name
  La geometría ya viene en formato PostGIS desde la ingesta vectorial.
*/

WITH source_data AS (
    SELECT *
    FROM {{ source('bronze', 'bronze_osm_pois') }}
)

SELECT
    osm_id,
    "type"  AS poi_type,
    "group" AS poi_group,
    "name"  AS poi_name,
    -- Extraer lat/lon de la geometría que ya viene en bronze
    ST_Y(geometry::geometry) AS latitud,
    ST_X(geometry::geometry) AS longitud,
    geometry::geometry AS geometry
FROM source_data
WHERE geometry IS NOT NULL
