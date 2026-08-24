{{ config(
    materialized='view'
) }}

WITH raw_booking AS (
    SELECT 
        establishment_id,
        name,
        url,
        address,
        latitude,
        longitude,
        establishment_type
    FROM {{ source('bronze', 'booking_establishments') }}
),

lookup AS (
    SELECT
        establishment_id,
        latitud_geocoded,
        longitud_geocoded
    FROM {{ source('bronze', 'booking_geocoding_lookup') }}
),

enriched AS (
    SELECT 
        r.establishment_id,
        r.name,
        r.url,
        r.address,
        r.establishment_type,
        
        -- Prioridad: 
        -- 1. Coordenadas del geocodificador avanzado (lookup)
        -- 2. Si no hay (NULL), intentar castear la original de Booking
        COALESCE(
            TRY_CAST(l.latitud_geocoded AS FLOAT),
            TRY_CAST(REPLACE(r.latitude, ',', '.') AS FLOAT)
        ) AS latitud,
        
        COALESCE(
            TRY_CAST(l.longitud_geocoded AS FLOAT),
            TRY_CAST(REPLACE(r.longitude, ',', '.') AS FLOAT)
        ) AS longitud
        
    FROM raw_booking r
    LEFT JOIN lookup l ON r.establishment_id = l.establishment_id
)

SELECT *
FROM enriched
-- Opcional: Filtrar por bounding box de Tenerife para quitar basura que caiga fuera de la isla
WHERE latitud BETWEEN 27.9 AND 28.7
  AND longitud BETWEEN -17.0 AND -16.0
