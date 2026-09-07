{{ config(
    materialized='table',
    tags=['silver', 'booking'],
    indexes=[
      {'columns': ['geometry'], 'type': 'gist'},
      {'columns': ['establishment_id'], 'unique': True}
    ]
) }}

-- 1. Deduplicamos los establecimientos desde bronze para evitar repetidos (del de booking)
WITH raw_booking AS (
    SELECT DISTINCT ON (establishment_id) *
    FROM {{ source('bronze', 'bronze_booking_establishments') }}
    ORDER BY establishment_id
),

-- 2. Obtenemos las coordenadas corregidas por el geocodificador (del de alojamiento)
lookup AS (
    SELECT
        establishment_id,
        latitud_geocoded,
        longitud_geocoded
    FROM {{ source('bronze', 'bronze_booking_geocoding_lookup') }}
),

-- 3. Cruzamos y enriquecemos priorizando las coordenadas corregidas (del de alojamiento)
enriched AS (
    SELECT 
        r.establishment_id,
        r.name,
        r.url,
        r.address,
        r.establishment_type,
        
        -- Prioridad: 
        -- 1. Coordenadas del geocodificador avanzado (lookup)
        -- 2. Si no hay (NULL), intentar castear la original de Booking reemplazando coma por punto
        COALESCE(
            CAST(l.latitud_geocoded AS FLOAT),
            CAST(r.latitude AS FLOAT)
        ) AS latitud,
        
        COALESCE(
            CAST(l.longitud_geocoded AS FLOAT),
            CAST(r.longitude AS FLOAT)
        ) AS longitud
        
    FROM raw_booking r
    LEFT JOIN lookup l ON r.establishment_id = l.establishment_id
)

-- 4. Seleccionamos el resultado, añadimos geometry y filtramos por el Bounding Box de Tenerife
SELECT
    establishment_id,
    name,
    url,
    address,
    establishment_type,
    latitud,
    longitud,
    -- Columna geometry PostGIS para cruces espaciales con malla H3 (ST_Contains)
    ST_SetSRID(ST_MakePoint(longitud, latitud), 4326) AS geometry
FROM enriched
WHERE latitud BETWEEN 27.9 AND 28.7
  AND longitud BETWEEN -17.0 AND -16.0
