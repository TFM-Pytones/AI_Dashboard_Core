{{ config(materialized='table', tags=['silver', 'movilidad', 'gtfs']) }}

/*
  Modelo Silver: silver_gtfs_rutas
  Limpieza de rutas de transporte público de Tenerife.
*/

SELECT
    route_id,
    agency_id,
    route_short_name,
    route_long_name,
    route_type,
    CASE route_type
        WHEN 3 THEN 'Bus'
        WHEN 2 THEN 'Tren'
        WHEN 0 THEN 'Tram'
        ELSE 'Otro'
    END AS tipo_transporte
FROM {{ source('bronze', 'gtfs_rutas') }}
WHERE route_id IS NOT NULL
