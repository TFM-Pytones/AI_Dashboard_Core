{{ config(
    materialized='table',
    indexes=[
      {'columns': ['h3_index', 'year', 'quarter'], 'unique': True}
    ]
) }}

WITH satelite AS (
    SELECT 
        h3_index,
        year,
        quarter,
        ndvi_mean,
        ndbi_mean
    FROM {{ source('bronze', 'satelite_stats') }}
)

SELECT
    h3_index,
    year,
    quarter,
    -- Identificador temporal único para facilitar joins temporales futuros
    year || '_' || quarter AS time_period,
    
    -- Mantenemos los nulos matemáticos (NaN) tal cual, ya que sustituirlos por 0 
    -- falsearía los modelos de Machine Learning (0 de NDVI es suelo desnudo, no agua).
    ndvi_mean,
    ndbi_mean,
    
    -- Basado en los descubrimientos del EDA (Exploratory Data Analysis):
    -- Etiquetamos los trimestres de invierno donde el ángulo del sol
    -- genera sombras masivas que alteran el NDVI y NDBI artificialmente.
    CASE 
        WHEN quarter IN ('Q1', 'Q4') THEN TRUE 
        ELSE FALSE 
    END AS is_winter_shadow_season
FROM satelite
WHERE h3_index IS NOT NULL
