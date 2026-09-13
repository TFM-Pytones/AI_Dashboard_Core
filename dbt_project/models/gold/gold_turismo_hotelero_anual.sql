{{ config(
    materialized='table',
    tags=['gold', 'turismo', 'hoteles', 'eoh', 'demografia', 'series_temporales'],
    indexes=[
      {'columns': ['cod_municipio']},
      {'columns': ['anio']},
      {'columns': ['polo_turistico']}
    ]
) }}

/*
  Modelo Gold: gold_turismo_hotelero_anual
  Serie histórica anual y sobrecarga demográfica (PTE) en los 6 municipios turísticos oficiales de Tenerife.
  Unifica (0% nulos, 0% ceros ficticios):
  - Población empadronada y Población Turística Equivalente (PTE) del ISTAC.
  - Ratio de presión demográfica flotante (% PTE sobre población residente).
  - Totales anuales de viajeros entrados y pernoctaciones hoteleras acumuladas.
  - Tasa media de ocupación de plazas hoteleras y estancia media anual.
  - Crecimientos interanuales (YoY).
*/

WITH eoh_anual AS (
    SELECT 
        municipio_cod,
        anio,
        COUNT(mes) AS n_meses,
        SUM(viajeros_entrados) AS viajeros_entrados_total,
        SUM(pernoctaciones) AS pernoctaciones_total,
        ROUND(AVG(plazas_ofertadas)::numeric, 0) AS plazas_ofertadas_hotel_media,
        ROUND(AVG(tasa_ocupacion_plazas)::numeric, 1) AS ocupacion_media_plazas,
        ROUND((SUM(pernoctaciones) / NULLIF(SUM(viajeros_entrados), 0))::numeric, 2) AS estancia_media_hotel_dias
    FROM {{ ref('silver_istac_mensual') }}
    WHERE municipio_cod IN ('38001', '38006', '38017', '38028', '38038', '38040')
      AND anio <= 2025
    GROUP BY municipio_cod, anio
),

anual_base AS (
    SELECT 
        m.cod_municipio,
        m.nombre_municipio AS municipio,
        CASE 
            WHEN m.cod_municipio IN ('38001', '38006', '38017', '38040') THEN 'Polo Sur'
            WHEN m.cod_municipio = '38028' THEN 'Polo Norte'
            WHEN m.cod_municipio = '38038' THEN 'Polo Metropolitano'
            ELSE 'Otros'
        END AS polo_turistico,
        ea.anio,
        ea.n_meses,
        a.poblacion_total AS poblacion,
        a.pob_turistica_equiv,
        ROUND(((a.pob_turistica_equiv / NULLIF(a.poblacion_total, 0)) * 100)::numeric, 2) AS pct_pob_turistica_equiv_sobre_pob,
        ea.viajeros_entrados_total,
        ea.pernoctaciones_total,
        ea.plazas_ofertadas_hotel_media,
        ea.ocupacion_media_plazas,
        ea.estancia_media_hotel_dias
    FROM eoh_anual ea
    JOIN {{ ref('silver_limites_municipales') }} m ON ea.municipio_cod = m.cod_municipio
    JOIN {{ ref('silver_istac_anual') }} a ON ea.municipio_cod = a.municipio_cod AND ea.anio = a.anio
)

SELECT 
    b.cod_municipio,
    b.municipio,
    b.polo_turistico,
    b.anio,
    b.n_meses,
    
    -- Demografía y Carga Turística (PTE)
    b.poblacion,
    b.pob_turistica_equiv,
    b.pct_pob_turistica_equiv_sobre_pob,
    
    -- Actividad Hotelera Acumulada
    b.viajeros_entrados_total,
    COALESCE(ROUND(((b.viajeros_entrados_total - LAG(b.viajeros_entrados_total) OVER (PARTITION BY b.cod_municipio ORDER BY b.anio)) / 
           NULLIF(LAG(b.viajeros_entrados_total) OVER (PARTITION BY b.cod_municipio ORDER BY b.anio), 0) * 100)::numeric, 1), 0) AS crec_viajeros_yoy_pct,
           
    b.pernoctaciones_total,
    COALESCE(ROUND(((b.pernoctaciones_total - LAG(b.pernoctaciones_total) OVER (PARTITION BY b.cod_municipio ORDER BY b.anio)) / 
           NULLIF(LAG(b.pernoctaciones_total) OVER (PARTITION BY b.cod_municipio ORDER BY b.anio), 0) * 100)::numeric, 1), 0) AS crec_pernoctaciones_yoy_pct,
           
    b.plazas_ofertadas_hotel_media,
    b.ocupacion_media_plazas,
    b.estancia_media_hotel_dias

FROM anual_base b
ORDER BY b.cod_municipio, b.anio DESC
