{{ config(
    materialized='table',
    tags=['gold', 'municipio', 'istac', 'empleo', 'series_temporales'],
    indexes=[
      {'columns': ['cod_municipio']},
      {'columns': ['periodo']},
      {'columns': ['anio', 'trimestre']}
    ]
) }}

/*
  Modelo Gold: gold_municipio_empleo
  Serie temporal trimestral completa de afiliación a la Seguridad Social (2022 a 2026).
  Métricas 100% continuas (0% NULLs) optimizadas para LLM y dashboards:
  - Cifras absolutas por régimen (Total, Asalariados, Autónomos).
  - Ratios estructurales de régimen (% autónomos, % asalariados).
  - Variaciones interanuales (YoY) respecto al mismo trimestre del año anterior (LAG 4 con línea base 2021).
  Nota: La desagregación sectorial por CNAE (hostelería, servicios, etc.) se concentra como foto fija estructural en gold_municipio_master.
*/

WITH base AS (
    SELECT 
        m.cod_municipio,
        m.nombre_municipio AS municipio,
        t.periodo_codigo AS periodo,
        t.periodo_texto,
        t.anio,
        t.trimestre,
        t.empleo_total,
        t.empleo_asalariados,
        t.empleo_autonomos
    FROM {{ ref('silver_limites_municipales') }} m
    JOIN {{ ref('silver_istac_trimestral') }} t ON m.cod_municipio = t.municipio_cod
),

calculado AS (
    SELECT 
        b.cod_municipio,
        b.municipio,
        b.periodo,
        b.periodo_texto,
        b.anio,
        b.trimestre,
        
        -- Cifras absolutas de afiliación
        b.empleo_total,
        b.empleo_asalariados,
        b.empleo_autonomos,
        
        -- Ratios de régimen (%)
        ROUND(((b.empleo_autonomos / NULLIF(b.empleo_total, 0)) * 100)::numeric, 2)   AS pct_autonomos,
        ROUND(((b.empleo_asalariados / NULLIF(b.empleo_total, 0)) * 100)::numeric, 2) AS pct_asalariados,
        
        -- Variaciones interanuales (mismo trimestre del año anterior, LAG 4)
        ROUND(((b.empleo_total - LAG(b.empleo_total, 4) OVER (PARTITION BY b.cod_municipio ORDER BY b.anio, b.trimestre)) / 
               NULLIF(LAG(b.empleo_total, 4) OVER (PARTITION BY b.cod_municipio ORDER BY b.anio, b.trimestre), 0) * 100)::numeric, 1) AS crec_empleo_total_yoy_pct,
               
        ROUND(((b.empleo_autonomos - LAG(b.empleo_autonomos, 4) OVER (PARTITION BY b.cod_municipio ORDER BY b.anio, b.trimestre)) / 
               NULLIF(LAG(b.empleo_autonomos, 4) OVER (PARTITION BY b.cod_municipio ORDER BY b.anio, b.trimestre), 0) * 100)::numeric, 1) AS crec_empleo_autonomos_yoy_pct

    FROM base b
)

SELECT * 
FROM calculado
WHERE anio >= 2022
ORDER BY cod_municipio, anio DESC, trimestre DESC
