{{ config(
    materialized='table',
    tags=['silver', 'movilidad', 'gtfs'],
    indexes=[
      {'columns': ['geometry'], 'type': 'gist'},
      {'columns': ['stop_id'], 'unique': True}
    ]
) }}

/*
  Modelo Silver: silver_gtfs_paradas
  Limpieza de paradas de autobús TITSA/TITF de Tenerife.
  Descarta paradas sin coordenadas válidas.
  La columna geometry se genera aquí en Silver para permitir:
    - Cruce con malla H3 (ST_Contains) en Gold
    - Cálculo de isócronas con pgRouting en Gold
*/

SELECT
    stop_id,
    stop_name,
    CAST(stop_lat AS NUMERIC) AS latitud,
    CAST(stop_lon AS NUMERIC) AS longitud,
    location_type,
    parent_station,
    zone_id,
    -- Columna geometry PostGIS para cruces espaciales con H3 y cálculo de isócronas con pgRouting
    ST_SetSRID(ST_MakePoint(
        CAST(stop_lon AS NUMERIC),
        CAST(stop_lat AS NUMERIC)
    ), 4326) AS geometry
FROM {{ source('bronze', 'gtfs_paradas') }}
WHERE stop_id IS NOT NULL
  AND stop_lat IS NOT NULL
  AND stop_lon IS NOT NULL
  AND TRIM(stop_lat::text) NOT IN ('', 'None', 'NULL')
  AND TRIM(stop_lon::text) NOT IN ('', 'None', 'NULL')
