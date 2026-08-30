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
  - La tabla bronze.tripadvisor_ubicaciones contiene el JSON crudo en la columna `location`.
  - La validación geográfica principal ya se hizo en el script de ingesta (Python/GeoPandas)
    por razones de cuota de la API, por lo que aquí asumimos que están en Tenerife.
*/

WITH source_data AS (
    SELECT
        location::jsonb AS location,
        categoria_busqueda,
        municipio_busqueda
    FROM {{ source('bronze', 'tripadvisor_ubicaciones') }}
),
raw_data AS (
    SELECT
        location->>'id' AS location_id,
        COALESCE(
            jsonb_path_query_first(location->'names', '$[*] ? (@.language == "es").value') #>> '{}',
            jsonb_path_query_first(location->'names', '$[*] ? (@.primary == true).value') #>> '{}',
            location->'names'->0->>'value'
        ) AS nombre,
        categoria_busqueda AS categoria,
        municipio_busqueda AS municipio,
        location->'addresses'->0->>'formatted' AS direccion,
        (location->'traveler_ratings'->'overall'->>'rating')::numeric AS rating,
        (location->'traveler_ratings'->'overall'->>'count')::integer AS num_resenas,
        location->>'price_level' AS nivel_precio,
        (location->'coordinates'->>'latitude')::numeric AS latitud,
        (location->'coordinates'->>'longitude')::numeric AS longitud
    FROM source_data
)

SELECT
    location_id,
    nombre,
    categoria,
    municipio,
    direccion,
    rating,
    num_resenas,
    nivel_precio,
    latitud,
    longitud,
    ST_SetSRID(ST_MakePoint(longitud, latitud), 4326) AS geometry
FROM raw_data
WHERE location_id IS NOT NULL
  AND latitud IS NOT NULL
  AND longitud IS NOT NULL
