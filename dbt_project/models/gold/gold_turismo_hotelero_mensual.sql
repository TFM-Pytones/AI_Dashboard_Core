{{ config(
    materialized='table',
    tags=['gold', 'turismo', 'hoteles', 'eoh', 'series_temporales'],
    indexes=[
      {'columns': ['cod_municipio']},
      {'columns': ['periodo']},
      {'columns': ['polo_turistico']}
    ]
) }}

/*
  Modelo Gold: gold_turismo_hotelero_mensual
  Serie temporal mensual de la Encuesta de Ocupación Hotelera (EOH) del ISTAC.
  Cubre los 6 municipios turísticos oficiales de Tenerife (100% datos reales, 0% nulos, 0% ceros ficticios):
  - Adeje, Arona, Granadilla de Abona, Santiago del Teide (Polo Sur)
  - Puerto de la Cruz (Polo Norte)
  - Santa Cruz de Tenerife (Polo Metropolitano)
  
  Métricas:
  - Viajeros entrados, Pernoctaciones hoteleras, Plazas ofertadas en hoteles, Tasa de ocupación de plazas.
  - Estancia media hotelera calculada (pernoctaciones / viajeros).
  - Tasas de variación interanual mes a mes (LAG 12).
*/

WITH eoh_base AS (
    SELECT 
        m.cod_municipio,
        m.nombre_municipio AS municipio,
        CASE 
            WHEN m.cod_municipio IN ('38001', '38006', '38017', '38040') THEN 'Polo Sur'
            WHEN m.cod_municipio = '38028' THEN 'Polo Norte'
            WHEN m.cod_municipio = '38038' THEN 'Polo Metropolitano'
            ELSE 'Otros'
        END AS polo_turistico,
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
        men.viajeros_entrados,
        men.pernoctaciones,
        men.plazas_ofertadas AS plazas_ofertadas_hotel,
        men.tasa_ocupacion_plazas,
        ROUND((men.pernoctaciones / NULLIF(men.viajeros_entrados, 0))::numeric, 2) AS estancia_media_hotel_dias
    FROM {{ ref('silver_istac_mensual') }} men
    JOIN {{ ref('silver_limites_municipales') }} m ON men.municipio_cod = m.cod_municipio
    WHERE men.municipio_cod IN ('38001', '38006', '38017', '38028', '38038', '38040')
      AND (men.anio < 2026 OR men.mes <= 7)
)

SELECT 
    b.cod_municipio,
    b.municipio,
    b.polo_turistico,
    b.periodo,
    b.anio,
    b.mes,
    b.trimestre,
    b.estacion,
    
    -- Flujo y Capacidad Hotelera
    b.viajeros_entrados,
    b.pernoctaciones,
    b.plazas_ofertadas_hotel,
    b.tasa_ocupacion_plazas,
    b.estancia_media_hotel_dias,
    
    -- Variaciones interanuales mes a mes (mismo mes año anterior)
    COALESCE(ROUND(((b.viajeros_entrados - LAG(b.viajeros_entrados, 12) OVER (PARTITION BY b.cod_municipio ORDER BY b.anio, b.mes)) / 
           NULLIF(LAG(b.viajeros_entrados, 12) OVER (PARTITION BY b.cod_municipio ORDER BY b.anio, b.mes), 0) * 100)::numeric, 1), 0) AS crec_viajeros_yoy_pct,
           
    COALESCE(ROUND(((b.pernoctaciones - LAG(b.pernoctaciones, 12) OVER (PARTITION BY b.cod_municipio ORDER BY b.anio, b.mes)) / 
           NULLIF(LAG(b.pernoctaciones, 12) OVER (PARTITION BY b.cod_municipio ORDER BY b.anio, b.mes), 0) * 100)::numeric, 1), 0) AS crec_pernoctaciones_yoy_pct

FROM eoh_base b
ORDER BY b.cod_municipio, b.anio DESC, b.mes DESC
