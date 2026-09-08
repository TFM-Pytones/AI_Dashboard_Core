{{ config(
    materialized='table',
    tags=['silver', 'movilidad', 'gtfs'],
    indexes=[
      {'columns': ['geometry'], 'type': 'gist'},
      {'columns': ['stop_id'], 'unique': True}
    ]
) }}

WITH paradas_geom AS (
    SELECT
        stop_id,
        stop_name,
        operador,
        modo,
        geometry::geometry AS geometry
    FROM {{ source('bronze', 'bronze_gtfs_paradas') }}
    WHERE stop_id IS NOT NULL
),

lineas_por_parada AS (
    -- Agrupamos primero por parada y línea para tener la cuenta de expediciones
    SELECT
        h.stop_id,
        r.route_short_name,
        COUNT(h.trip_id) AS total_paradas_diarias
    FROM {{ source('bronze', 'bronze_gtfs_horarios') }} h
    JOIN {{ source('bronze', 'bronze_gtfs_viajes') }} v ON h.trip_id = v.trip_id
    JOIN {{ source('bronze', 'bronze_gtfs_rutas_atributos') }} r ON v.route_id = r.route_id
    GROUP BY h.stop_id, r.route_short_name
),

paradas_agregadas AS (
    -- Concatenamos las líneas y sumamos las expediciones totales
    SELECT
        stop_id,
        STRING_AGG(route_short_name, ', ' ORDER BY route_short_name) AS lineas_disponibles,
        SUM(total_paradas_diarias) AS total_expediciones_parada
    FROM lineas_por_parada
    GROUP BY stop_id
)

SELECT
    p.stop_id,
    p.stop_name,
    p.operador,
    p.modo,
    a.lineas_disponibles,
    COALESCE(a.total_expediciones_parada, 0) AS total_expediciones_parada,
    p.geometry
FROM paradas_geom p
LEFT JOIN paradas_agregadas a ON p.stop_id::TEXT = a.stop_id::TEXT
