{{ config(
    materialized='table',
    tags=['silver', 'alojamiento'],
    indexes=[
      {'columns': ['geometry'], 'type': 'gist'},
      {'columns': ['municipio']}
    ]
) }}

WITH source_hoteles AS (
    SELECT 
        establecimiento_id, establecimiento_nombre_comercial, direccion_municipio_nombre, 
        direccion_isla_nombre, plazas, unidades_explotacion, longitud, latitud,
        establecimiento_clasificacion AS categoria,
        establecimiento_modalidad AS modalidad,
        'hotel' AS tipo_alojamiento
    FROM {{ source('bronze', 'registro_hoteles') }}
    WHERE direccion_isla_nombre ILIKE '%Tenerife%'
),
source_extrahoteleros AS (
    SELECT 
        establecimiento_id, establecimiento_nombre_comercial, direccion_municipio_nombre, 
        direccion_isla_nombre, plazas, unidades_explotacion, longitud, latitud,
        establecimiento_clasificacion AS categoria,
        establecimiento_modalidad AS modalidad,
        'extrahotelero' AS tipo_alojamiento
    FROM {{ source('bronze', 'registro_extrahoteleros') }}
    WHERE direccion_isla_nombre ILIKE '%Tenerife%'
),
source_vv AS (
    SELECT 
        establecimiento_id, establecimiento_nombre_comercial, direccion_municipio_nombre, 
        direccion_isla_nombre, plazas, 
        CAST('1' AS VARCHAR) AS unidades_explotacion, 
        longitud, latitud,
        establecimiento_clasificacion AS categoria,
        establecimiento_modalidad AS modalidad,
        'vivienda_vacacional' AS tipo_alojamiento
    FROM {{ source('bronze', 'registro_viviendas_vacacionales') }}
    WHERE direccion_isla_nombre ILIKE '%Tenerife%'
),
source_data AS (
    SELECT * FROM source_hoteles
    UNION ALL
    SELECT * FROM source_extrahoteleros
    UNION ALL
    SELECT * FROM source_vv
),
lookup AS (
    SELECT *
    FROM {{ source('bronze', 'registro_geocoding_lookup') }}
),
cleaned_coords AS (
    SELECT
        s.establecimiento_id AS id,
        s.establecimiento_nombre_comercial AS nombre,
        s.tipo_alojamiento,
        s.direccion_municipio_nombre AS municipio,
        s.direccion_isla_nombre AS isla,
        CASE 
            WHEN s.categoria = '_U' THEN NULL
            WHEN UPPER(s.categoria) ILIKE '%CINCO ESTRELLAS GRAN LUJO%' THEN '5 Estrellas Gran Lujo'
            WHEN UPPER(s.categoria) ILIKE '%CINCO ESTRELLAS%' OR UPPER(s.categoria) ILIKE '%5 ESTRELLA%' THEN '5 Estrellas'
            WHEN UPPER(s.categoria) ILIKE '%CUATRO ESTRELLAS%' OR UPPER(s.categoria) ILIKE '%4 ESTRELLA%' THEN '4 Estrellas'
            WHEN UPPER(s.categoria) ILIKE '%TRES ESTRELLAS%' OR UPPER(s.categoria) ILIKE '%3 ESTRELLA%' THEN '3 Estrellas'
            WHEN UPPER(s.categoria) ILIKE '%DOS ESTRELLAS%' OR UPPER(s.categoria) ILIKE '%2 ESTRELLA%' THEN '2 Estrellas'
            WHEN UPPER(s.categoria) ILIKE '%UNA ESTRELLA%' OR UPPER(s.categoria) ILIKE '%1 ESTRELLA%' THEN '1 Estrella'
            WHEN UPPER(s.categoria) ILIKE '%CATEGOR%A%NICA%' THEN 'Categoría Única'
            WHEN UPPER(s.categoria) ILIKE '%1 PALMERA%' OR UPPER(s.categoria) ILIKE '%UNA PALMERA%' THEN '1 Palmera'
            WHEN UPPER(s.categoria) ILIKE '%2 PALMERA%' OR UPPER(s.categoria) ILIKE '%DOS PALMERA%' THEN '2 Palmeras'
            WHEN UPPER(s.categoria) ILIKE '%3 PALMERA%' OR UPPER(s.categoria) ILIKE '%TRES PALMERA%' THEN '3 Palmeras'
            WHEN UPPER(s.categoria) ILIKE '%1 LLAVE%' OR UPPER(s.categoria) ILIKE '%UNA LLAVE%' THEN '1 Llave'
            WHEN UPPER(s.categoria) ILIKE '%2 LLAVE%' OR UPPER(s.categoria) ILIKE '%DOS LLAVE%' THEN '2 Llaves'
            WHEN UPPER(s.categoria) ILIKE '%3 LLAVE%' OR UPPER(s.categoria) ILIKE '%TRES LLAVE%' THEN '3 Llaves'
            WHEN UPPER(s.categoria) ILIKE '%4 LLAVE%' OR UPPER(s.categoria) ILIKE '%CUATRO LLAVE%' THEN '4 Llaves'
            ELSE s.categoria
        END AS categoria,
        CASE WHEN s.modalidad = '_U' THEN NULL ELSE s.modalidad END AS modalidad,
        CAST(NULLIF(TRIM(REPLACE(CAST(s.plazas AS VARCHAR), ',', '.')), '') AS NUMERIC) AS plazas,
        CAST(NULLIF(TRIM(REPLACE(CAST(s.unidades_explotacion AS VARCHAR), ',', '.')), '') AS NUMERIC) AS unidades_alojativas,
        
        -- Prioridad: 1) Geocodificador (lookup) 2) Coordenada original limpia
        COALESCE(
            CAST(l.longitud_geocoded AS NUMERIC),
            CAST(NULLIF(TRIM(REPLACE(CAST(s.longitud AS VARCHAR), ',', '.')), '') AS NUMERIC)
        ) AS longitud,
        
        COALESCE(
            CAST(l.latitud_geocoded AS NUMERIC),
            CAST(NULLIF(TRIM(REPLACE(CAST(s.latitud AS VARCHAR), ',', '.')), '') AS NUMERIC)
        ) AS latitud
    FROM source_data s
    LEFT JOIN lookup l ON CAST(s.establecimiento_id AS VARCHAR) = CAST(l.establecimiento_id AS VARCHAR)
)

SELECT
    id,
    nombre,
    tipo_alojamiento,
    municipio,
    isla,
    categoria,
    modalidad,
    plazas,
    unidades_alojativas,
    -- Limpiamos coordenadas que sean nulas, 0 o estén fuera del bounding box de Tenerife
    CASE 
        WHEN longitud IS NULL OR longitud = 0 OR longitud NOT BETWEEN -16.95 AND -16.09 THEN NULL
        ELSE longitud
    END AS longitud,
    CASE 
        WHEN latitud IS NULL OR latitud = 0 OR latitud NOT BETWEEN 27.97 AND 28.59 THEN NULL
        ELSE latitud
    END AS latitud,
    -- Generamos la geometría solo si las coordenadas finales son válidas
    CASE
        WHEN longitud IS NOT NULL AND longitud != 0 AND longitud BETWEEN -16.95 AND -16.09 
         AND latitud IS NOT NULL AND latitud != 0 AND latitud BETWEEN 27.97 AND 28.59
        THEN ST_SetSRID(ST_MakePoint(longitud, latitud), 4326)
        ELSE NULL
    END AS geometry
FROM cleaned_coords
