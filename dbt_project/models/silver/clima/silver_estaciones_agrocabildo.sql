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
  Limpieza de metadatos de estaciones meteorológicas.
  Descarta estaciones sin coordenadas (no georeferenciables).
  La columna geometry permite cruzar estaciones con malla H3
  para calcular el índice de confort climático por hexágono.
*/

SELECT
    id_estacion,
    nombre_estacion,
    municipio,
    altitud_m,
    latitud,
    longitud,
    fecha_instalacion,
    activa,
    -- Columna geometry PostGIS para cruce con malla H3 (confort climático por hexágono)
    ST_SetSRID(ST_MakePoint(longitud, latitud), 4326) AS geometry
FROM {{ source('bronze', 'estaciones_agrocabildo') }}
WHERE id_estacion IS NOT NULL
  AND latitud IS NOT NULL
  AND longitud IS NOT NULL
