{{ config(
    materialized='table',
    indexes=[
      {'columns': ['h3_index'], 'unique': True},
      {'columns': ['geometry'], 'type': 'gist'}
    ]
) }}

/*
  Modelo Silver: silver_h3_grid
  -------------------------------------------------------------
  Transformación, depuración y filtrado de la malla espacial H3 Res 8:
  - Capa Bronze (bronze.bronze_h3_grid): 2.746 celdas generadas con
    buffer de amortiguación costera de 0.01° (~1,1 km).
  - Filtro 1 (Límites Municipales): Descarta 163 celdas 100% marinas en aguas
    abiertas sin intersección con los 31 municipios de Tenerife (2.583 celdas).
  - Filtro 2 (Integridad Biofísica y Topográfica): Descarta 4 celdas residuales
    costeras/roques marinos que carecen de elevación válida (cota <= 0 o NoData en MDT)
    o de cobertura satelital biofísica (NDVI nulo en Sentinel-2), consolidando
    exactamente 2.579 celdas terrestres 100% completas y libres de nulos.
  - Centroides geométricos canónicos puros (ST_Centroid de H3) sin distorsiones espaciales.
  - Enriquecimiento: relieve MDT25 (GRAFCAN) y figuras protegidas (ENP).
*/

WITH grid_municipal AS (
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
    WHERE elevation_mean IS NOT NULL 
      AND elevation_mean > 0
),

satelite_valid AS (
    -- Asegura que el hexágono tiene lecturas válidas de vegetación / teledetección
    SELECT DISTINCT h3_index
    FROM {{ source('bronze', 'bronze_satelite_stats') }}
    WHERE ndvi_mean IS NOT NULL
),

enp_intersection AS (
    -- JOIN espacial para saber si el hexágono toca o está dentro de un parque natural
    SELECT DISTINCT
        g.h3_index,
        TRUE AS is_protected_area
    FROM grid_municipal g
    JOIN {{ source('bronze', 'bronze_espacios_naturales') }} e
      ON ST_Intersects(g.geometry, e.geometry)
)

SELECT
    g.h3_index,
    g.resolution,
    g.geometry,
    -- Centroide geométrico canónico de la celda H3
    ST_X(ST_Centroid(g.geometry)) AS centroide_lon,
    ST_Y(ST_Centroid(g.geometry)) AS centroide_lat,
    -- Elevación
    m.elevation_mean,
    m.elevation_min,
    m.elevation_max,
    -- Pendiente en grados
    m.slope_mean,
    m.slope_min,
    m.slope_max,
    -- Orientación en grados (Norte=0°)
    m.aspect_mean,
    -- Hillshade para visualización
    m.hillshade_mean,
    -- Área protegida (ENP)
    COALESCE(e.is_protected_area, FALSE) AS is_protected_area
FROM grid_municipal g
INNER JOIN mdt m ON g.h3_index = m.h3_index
INNER JOIN satelite_valid s ON g.h3_index = s.h3_index
LEFT JOIN enp_intersection e ON g.h3_index = e.h3_index

