{{ config(materialized='table', tags=['silver', 'movilidad', 'gtfs']) }}

/*
  Modelo Silver: silver_gtfs_paradas
  Limpieza de paradas de autobús TITSA/TITF de Tenerife.
  Descarta paradas sin coordenadas válidas.
  La asignación a zona turística se hace en Gold con ST_Within.
*/

SELECT
    stop_id,
    stop_name,
    CAST(stop_lat AS NUMERIC) AS latitud,
    CAST(stop_lon AS NUMERIC) AS longitud,
    location_type,
    parent_station,
    zone_id
FROM {{ source('bronze', 'gtfs_paradas') }}
WHERE stop_id IS NOT NULL
  AND stop_lat IS NOT NULL
  AND stop_lon IS NOT NULL
  AND TRIM(stop_lat::text) NOT IN ('', 'None', 'NULL')
  AND TRIM(stop_lon::text) NOT IN ('', 'None', 'NULL')
