{{ config(
    materialized='table',
    tags=['silver', 'alojamiento', 'extrahoteleros']
) }}

WITH source_data AS (
    SELECT *
    FROM {{ source('bronze', 'registro_extrahoteleros') }}
),
lookup AS (
    SELECT *
    FROM {{ source('bronze', 'registro_geocoding_lookup') }}
)

SELECT
    s.establecimiento_id AS id,
    s.establecimiento_nombre_comercial AS nombre,
    s.direccion_municipio_nombre AS municipio,
    s.direccion_isla_nombre AS isla,
    s.establecimiento_clasificacion AS categoria,
    s.establecimiento_modalidad AS modalidad,
    TRY_CAST(REPLACE(CAST(s.plazas AS VARCHAR), ',', '.') AS NUMERIC) AS plazas,
    TRY_CAST(REPLACE(CAST(s.unidades_explotacion AS VARCHAR), ',', '.') AS NUMERIC) AS unidades_alojativas,
    CASE 
        WHEN COALESCE(l.longitud_geocoded, TRY_CAST(REPLACE(CAST(s.longitud AS VARCHAR), ',', '.') AS NUMERIC)) = 0 THEN NULL
        WHEN COALESCE(l.longitud_geocoded, TRY_CAST(REPLACE(CAST(s.longitud AS VARCHAR), ',', '.') AS NUMERIC)) NOT BETWEEN -16.95 AND -16.09 THEN NULL
        ELSE COALESCE(l.longitud_geocoded, TRY_CAST(REPLACE(CAST(s.longitud AS VARCHAR), ',', '.') AS NUMERIC))
    END AS longitud,
    CASE 
        WHEN COALESCE(l.latitud_geocoded, TRY_CAST(REPLACE(CAST(s.latitud AS VARCHAR), ',', '.') AS NUMERIC)) = 0 THEN NULL
        WHEN COALESCE(l.latitud_geocoded, TRY_CAST(REPLACE(CAST(s.latitud AS VARCHAR), ',', '.') AS NUMERIC)) NOT BETWEEN 27.97 AND 28.59 THEN NULL
        ELSE COALESCE(l.latitud_geocoded, TRY_CAST(REPLACE(CAST(s.latitud AS VARCHAR), ',', '.') AS NUMERIC))
    END AS latitud
FROM source_data s
LEFT JOIN lookup l ON CAST(s.establecimiento_id AS VARCHAR) = CAST(l.establecimiento_id AS VARCHAR)
WHERE s.direccion_isla_nombre ILIKE '%Tenerife%'
