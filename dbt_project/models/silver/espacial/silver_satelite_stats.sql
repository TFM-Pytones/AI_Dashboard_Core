{{ config(
    materialized='table',
    indexes=[
      {'columns': ['h3_index', 'year', 'quarter'], 'unique': True}
    ]
) }}

WITH satelite AS (
    SELECT 
        s.h3_index,
        s.year,
        s.quarter,
        s.ndvi_mean,
        s.ndbi_mean,
        s.viirs_mean
    FROM {{ source('bronze', 'bronze_satelite_stats') }} s
    WHERE s.year >= 2022
      AND EXISTS (
          SELECT 1 
          FROM {{ ref('silver_h3_grid') }} g 
          WHERE g.h3_index = s.h3_index
      )
)

SELECT
    h3_index,
    year,
    quarter,
    -- Identificador temporal único para facilitar joins temporales
    year || '_' || quarter AS time_period,
    
    -- Mantenemos los nulos matemáticos (NaN) tal cual, ya que sustituirlos por 0 falsearía los modelos de Machine Learning (0 de NDVI es suelo desnudo, no agua).
    ndvi_mean,
    ndbi_mean,
    viirs_mean,
    
    -- Basado en los descubrimientos del EDA (Exploratory Data Analysis): Etiquetamos los trimestres de invierno donde el ángulo del sol genera sombras masivas que alteran el NDVI y NDBI artificialmente.
    CASE 
        WHEN quarter IN ('Q1', 'Q4') THEN TRUE 
        ELSE FALSE 
    END AS is_winter_shadow_season
FROM satelite
WHERE h3_index IS NOT NULL
