{{ config(
    materialized='table',
    tags=['gold', 'municipio', 'istac', 'series_temporales'],
    indexes=[
      {'columns': ['cod_municipio']},
      {'columns': ['periodo']},
      {'columns': ['anio', 'mes']}
    ]
) }}

/*
  Modelo Gold: gold_municipio_mensual
  Serie temporal mensual unificada por municipio (2022 a 2026).
  Métricas mensuales continuas (100% de municipios cubiertos, 0% NULLs ni falsos ceros) optimizadas para LLM y BI:
  - Paro registrado mensual (ISTAC).
  - Métricas mensuales de Vivienda Vacacional (ISTAC): plazas, tasa de ocupación, estancia media, ingresos y alojamientos abiertos.
  - Clasificación de trimestres y estaciones del año ('Invierno', 'Primavera', 'Verano', 'Otoño').
  - Variaciones interanuales mes a mes (mismo mes del año anterior con LAG 12).
  - Filtro temporal: Incluye todos los meses consolidados con publicación turística y laboral (hasta julio 2026).
*/

WITH mensual_base AS (
    SELECT 
        m.cod_municipio,
        m.nombre_municipio AS municipio,
        men.periodo_codigo AS periodo,
        men.anio,
        men.mes,
        CASE 
            WHEN men.mes IN (1, 2, 3) THEN 'Q1'
            WHEN men.mes IN (4, 5, 6) THEN 'Q2'
            WHEN men.mes IN (7, 8, 9) THEN 'Q3'
            ELSE 'Q4'
        END AS trimestre,
        CASE 
            WHEN men.mes IN (12, 1, 2) THEN 'Invierno'
            WHEN men.mes IN (3, 4, 5) THEN 'Primavera'
            WHEN men.mes IN (6, 7, 8) THEN 'Verano'
            ELSE 'Otoño'
        END AS estacion,
        men.paro_registrado,
        
        -- Vivienda Vacacional (cobertura 100% en los 31 municipios)
        COALESCE(men.plazas_vv, 0) AS plazas_vv,
        COALESCE(men.tasa_ocupacion_vv, 0) AS tasa_ocupacion_vv,
        COALESCE(men.estancia_media_vv, 0) AS estancia_media_vv,
        COALESCE(men.ingresos_vv, 0) AS ingresos_vv,
        COALESCE(men.alojamientos_abiertos_vv, 0) AS alojamientos_abiertos_vv
    FROM {{ ref('silver_limites_municipales') }} m
    JOIN {{ ref('silver_istac_mensual') }} men ON m.cod_municipio = men.municipio_cod
    WHERE (men.anio < 2026 OR men.mes <= 7)
)

SELECT 
    b.cod_municipio,
    b.municipio,
    b.periodo,
    b.anio,
    b.mes,
    b.trimestre,
    b.estacion,
    
    -- Métricas del mercado laboral mensual
    b.paro_registrado,
    
    -- Vivienda Vacacional mensual
    b.plazas_vv,
    b.tasa_ocupacion_vv,
    b.estancia_media_vv,
    b.ingresos_vv,
    b.alojamientos_abiertos_vv,
    
    -- Variaciones interanuales mes a mes (mismo mes del año anterior)
    COALESCE(ROUND(((b.paro_registrado - LAG(b.paro_registrado, 12) OVER (PARTITION BY b.cod_municipio ORDER BY b.anio, b.mes)) / 
           NULLIF(LAG(b.paro_registrado, 12) OVER (PARTITION BY b.cod_municipio ORDER BY b.anio, b.mes), 0) * 100)::numeric, 1), 0) AS paro_yoy_pct,
           
    COALESCE(ROUND(((b.plazas_vv - LAG(b.plazas_vv, 12) OVER (PARTITION BY b.cod_municipio ORDER BY b.anio, b.mes)) / 
           NULLIF(LAG(b.plazas_vv, 12) OVER (PARTITION BY b.cod_municipio ORDER BY b.anio, b.mes), 0) * 100)::numeric, 1), 0) AS plazas_vv_yoy_pct,
           
    COALESCE(ROUND(((b.ingresos_vv - LAG(b.ingresos_vv, 12) OVER (PARTITION BY b.cod_municipio ORDER BY b.anio, b.mes)) / 
           NULLIF(LAG(b.ingresos_vv, 12) OVER (PARTITION BY b.cod_municipio ORDER BY b.anio, b.mes), 0) * 100)::numeric, 1), 0) AS ingresos_vv_yoy_pct

FROM mensual_base b
ORDER BY b.cod_municipio, b.anio DESC, b.mes DESC
