{{ config(
    materialized='table',
    indexes=[
      {'columns': ['h3_index'], 'unique': True},
      {'columns': ['geometry'], 'type': 'gist'}
    ]
) }}

WITH grid AS (
    SELECT
        h3_index,
        resolution,
        geometry,
        -- Area real en km2 (::geography para que ST_Area no de grados^2,
        -- ya que bronze.h3_grid esta en SRID 4326)
        ROUND((ST_Area(geometry::geography) / 1000000)::numeric, 6) AS area_km2,
        -- Centroide en lon/lat (geometry ya esta en 4326, no hace falta transformar)
        ST_X(ST_Centroid(geometry)) AS centroide_lon,
        ST_Y(ST_Centroid(geometry)) AS centroide_lat
    FROM {{ source('bronze', 'h3_grid') }}
),

mdt AS (
    SELECT 
        h3_index,
        -- Elevación
        elevation_mean,
        elevation_min,
        elevation_max,
        -- Pendiente (Slope)
        slope_mean,
        slope_min,
        slope_max,
        -- Orientación (Aspect)
        aspect_mean,
        -- Hillshade (útil para visualización en Dashboard)
        hillshade_mean
    FROM {{ source('bronze', 'mdt_stats') }}
),

enp_intersection AS (
    -- JOIN espacial para saber si el hexágono toca o está dentro de un parque natural
    SELECT DISTINCT
        g.h3_index,
        TRUE AS is_protected_area
    FROM grid g
    JOIN {{ source('bronze', 'espacios_naturales') }} e
      ON ST_Intersects(g.geometry, e.geometry)
)

SELECT
    g.h3_index,
    g.resolution,
    g.geometry,
    g.area_km2,
    g.centroide_lon,
    g.centroide_lat,
    -- Elevación (rellenar con 0 si el hexágono cae en el mar)
    COALESCE(m.elevation_mean, 0.0) AS elevation_mean,
    COALESCE(m.elevation_min,  0.0) AS elevation_min,
    COALESCE(m.elevation_max,  0.0) AS elevation_max,
    -- Pendiente en grados
    COALESCE(m.slope_mean, 0.0) AS slope_mean,
    COALESCE(m.slope_min,  0.0) AS slope_min,
    COALESCE(m.slope_max,  0.0) AS slope_max,
    -- Orientación en grados (Norte=0°)
    COALESCE(m.aspect_mean, 0.0) AS aspect_mean,
    -- Hillshade para visualización
    COALESCE(m.hillshade_mean, 0.0) AS hillshade_mean,
    -- Área protegida (ENP)
    COALESCE(e.is_protected_area, FALSE) AS is_protected_area
FROM grid g
LEFT JOIN mdt m ON g.h3_index = m.h3_index
LEFT JOIN enp_intersection e ON g.h3_index = e.h3_index

