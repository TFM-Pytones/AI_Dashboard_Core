{{ config(
    materialized='table',
    indexes=[
      {'columns': ['h3_index'], 'unique': True},
      {'columns': ['geometry'], 'type': 'gist'}
    ]
) }}

WITH grid AS (
    SELECT 
        g.h3_index,
        g.resolution,
        g.geometry
    FROM {{ source('bronze', 'bronze_h3_grid') }} g
    WHERE EXISTS (
        SELECT 1
        FROM {{ ref('silver_limites_municipales') }} lm
        WHERE ST_Intersects(g.geometry, lm.geometry)
    )
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
    FROM {{ source('bronze', 'bronze_mdt_stats') }}
),

enp_intersection AS (
    -- JOIN espacial para saber si el hexágono toca o está dentro de un parque natural
    SELECT DISTINCT
        g.h3_index,
        TRUE AS is_protected_area
    FROM grid g
    JOIN {{ source('bronze', 'bronze_espacios_naturales') }} e
      ON ST_Intersects(g.geometry, e.geometry)
)

, poi_centroids AS (
    -- Mejora de MAUP: Centroide ponderado por actividad humana
    -- Calcula el centro de masa de todos los POIs que caen dentro del hexágono.
    SELECT
        g.h3_index,
        ST_Centroid(ST_Collect(p.geometry)) AS poi_centroid
    FROM grid g
    JOIN {{ ref('silver_osm_pois') }} p
      ON ST_Intersects(g.geometry, p.geometry)
    WHERE p.geometry IS NOT NULL
    GROUP BY g.h3_index
)

SELECT
    g.h3_index,
    g.resolution,
    g.geometry,
    -- Coordenadas: Si hay POIs usamos su centro de masa, si no, el centroide geométrico
    ST_X(COALESCE(pc.poi_centroid, ST_Centroid(g.geometry))) AS centroide_lon,
    ST_Y(COALESCE(pc.poi_centroid, ST_Centroid(g.geometry))) AS centroide_lat,
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
LEFT JOIN poi_centroids pc ON g.h3_index = pc.h3_index
