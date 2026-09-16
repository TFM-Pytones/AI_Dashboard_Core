{{ config(
    materialized='table',
    tags=['silver', 'clima'],
    indexes=[
      {'columns': ['geometry'], 'type': 'gist'},
      {'columns': ['id_estacion'], 'unique': True}
    ]
) }}

/*
  Modelo Silver: silver_estaciones_agrocabildo
  Columnas reales en bronze: estacion_id, estacion_nombre, municipio_nombre,
                              latitud, longitud, altitud, fecha_instalacion
  Nota: bronze_clima_horario_agrocabildo no existe en BD aún → se omite el join de sensores.
*/

SELECT
    e.estacion_id       AS id_estacion,
    e.estacion_nombre   AS nombre_estacion,
    e.municipio_nombre  AS municipio,
    e.altitud           AS altitud_m,
    e.latitud,
    e.longitud,
    e.fecha_instalacion,
    ST_SetSRID(ST_MakePoint(e.longitud::float8, e.latitud::float8), 4326) AS geometry
FROM {{ source('bronze', 'bronze_estaciones_agrocabildo') }} e
WHERE e.estacion_id IS NOT NULL
  AND e.latitud  IS NOT NULL
  AND e.longitud IS NOT NULL
  AND e.fecha_instalacion::timestamp <= '2022-01-01'::timestamp
