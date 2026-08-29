{{ config(
    materialized='table',
    tags=['silver', 'espacial', 'osm'],
    indexes=[
      {'columns': ['geometry'], 'type': 'gist'},
      {'columns': ['poi_type']}
    ]
) }}

WITH source_data AS (
    SELECT *
    FROM {{ source('bronze', 'osm_pois') }}
)

SELECT
    osm_id,
    "type" AS poi_type,
    "group" AS poi_group,
    "name" AS poi_name,
    lon AS longitud,
    lat AS latitud,
    -- Columna geometry PostGIS para cruces espaciales con malla H3 (ST_Contains)
    ST_SetSRID(ST_MakePoint(lon, lat), 4326) AS geometry
FROM source_data
WHERE lon IS NOT NULL AND lat IS NOT NULL
