{{ config(
    materialized='table',
    tags=['silver', 'movilidad', 'gtfs'],
    indexes=[
      {'columns': ['geometry'], 'type': 'gist'},
      {'columns': ['shape_id'], 'unique': True}
    ]
) }}

WITH shapes AS (
    SELECT
        shape_id,
        route_short_name,
        route_long_name,
        operador,
        geometry::geometry AS geometry
    FROM {{ source('bronze', 'bronze_gtfs_rutas') }}
    WHERE shape_id IS NOT NULL
),

viajes AS (
    SELECT
        shape_id,
        COUNT(DISTINCT trip_id) AS total_expediciones
    FROM {{ source('bronze', 'bronze_gtfs_viajes') }}
    GROUP BY shape_id
)

SELECT
    s.shape_id,
    s.route_short_name,
    s.route_long_name,
    s.operador,
    v.total_expediciones,
    s.geometry
FROM shapes s
LEFT JOIN viajes v ON s.shape_id = v.shape_id
