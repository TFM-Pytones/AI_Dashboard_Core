{{ config(
    materialized='table',
    tags=['silver', 'espacial', 'osm']
) }}

WITH source_data AS (
    SELECT *
    FROM {{ source('bronze', 'osm_pois_tenerife') }}
)

SELECT
    osm_id,
    "type" AS poi_type,
    "group" AS poi_group,
    "name" AS poi_name,
    lon AS longitud,
    lat AS latitud
FROM source_data
WHERE lon IS NOT NULL AND lat IS NOT NULL
