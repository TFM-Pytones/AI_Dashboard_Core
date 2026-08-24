{{ config(materialized='table', tags=['silver', 'clima']) }}

/*
  Modelo Silver: silver_estaciones_agrocabildo
  Limpieza de metadatos de estaciones meteorológicas.
  Descarta estaciones sin coordenadas (no georeferenciables).
*/

SELECT
    id_estacion,
    nombre_estacion,
    municipio,
    altitud_m,
    latitud,
    longitud,
    fecha_instalacion,
    activa
FROM {{ source('bronze', 'estaciones_agrocabildo') }}
WHERE id_estacion IS NOT NULL
  AND latitud IS NOT NULL
  AND longitud IS NOT NULL
