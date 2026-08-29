{{ config(
    materialized='table',
    tags=['silver', 'espacial', 'tripadvisor'],
    indexes=[
      {'columns': ['geometry'], 'type': 'gist'},
      {'columns': ['categoria']}
    ]
) }}

/*
  Modelo Silver: silver_tripadvisor_ubicaciones
  Establecimientos de TripAdvisor georreferenciados.
  - 691 ubicaciones (restaurantes, atracciones, hoteles, etc.)
  - La columna geometry ya viene de bronze con geometría PostGIS válida.
  - Clave de join con silver_tripadvisor_resenas: location_id
*/

SELECT
    location_id,
    nombre,
    categoria,
    municipio_busqueda AS municipio,
    direccion,
    rating,
    CAST(num_resenas AS INTEGER) AS num_resenas,
    nivel_precio,
    latitud,
    longitud,
    ST_Transform(ST_SetSRID(geometry, COALESCE(NULLIF(ST_SRID(geometry), 0), 4326)), 4326) AS geometry
FROM {{ source('bronze', 'tripadvisor_ubicaciones') }}
WHERE location_id IS NOT NULL
  AND geometry IS NOT NULL
