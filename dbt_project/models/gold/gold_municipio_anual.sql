{{ config(
    materialized='table',
    tags=['gold', 'municipio', 'istac', 'series_temporales'],
    indexes=[
      {'columns': ['cod_municipio']},
      {'columns': ['anio']}
    ]
) }}

/*
  Modelo Gold: gold_municipio_anual
  Serie anual consolidada por municipio (2022 a 2026).
  Métricas anuales limpias (0% NULLs artificiales) optimizadas para LLM:
  - Años 2022 a 2025: Años cerrados completos (12 meses, padrón oficial del ISTAC).
  - Año 2026 (YTD): Año en curso parcial (meses disponibles hasta agosto), con referencia censal de 2025.
  - Mercado laboral: Empleo total medio, empleo autónomo medio, paro medio y sus variaciones interanuales (YoY).
  - Turismo: Vivienda vacacional e indicadores hoteleros acumulados y medios.
  - Demografía y presión turística equivalente sobre la población residente.
*/

WITH mensual_agregado AS (
    SELECT 
        municipio_cod,
        anio,
        COUNT(mes) AS n_meses,
        ROUND(AVG(paro_registrado)::numeric, 0) AS paro_medio,
        ROUND(AVG(plazas_vv)::numeric, 0) AS plazas_vv_media,
        ROUND(AVG(tasa_ocupacion_vv)::numeric, 1) AS tasa_ocupacion_vv_media,
        ROUND(AVG(estancia_media_vv)::numeric, 2) AS estancia_media_vv,
        ROUND(SUM(ingresos_vv)::numeric, 2) AS ingresos_vv_acumulados,
        ROUND(AVG(ingresos_vv)::numeric, 2) AS ingresos_vv_media_mensual
    FROM {{ ref('silver_istac_mensual') }}
    GROUP BY municipio_cod, anio
),

trimestral_agregado AS (
    SELECT 
        municipio_cod,
        anio,
        ROUND(AVG(empleo_total)::numeric, 0) AS empleo_total_medio,
        ROUND(AVG(empleo_autonomos)::numeric, 0) AS empleo_autonomos_medio
    FROM {{ ref('silver_istac_trimestral') }}
    GROUP BY municipio_cod, anio
),

anual_base AS (
    SELECT 
        m.cod_municipio,
        m.nombre_municipio AS municipio,
        men.anio,
        men.n_meses,
        (men.anio < 2026) AS es_anio_completo,
        
        -- Población: padrón oficial del año o fallback al último disponible (2025)
        COALESCE(
            a.poblacion_total, 
            (SELECT poblacion_total FROM {{ ref('silver_istac_anual') }} WHERE municipio_cod = m.cod_municipio AND anio = 2025)
        ) AS poblacion,
        
        COALESCE(men.paro_medio, 0) AS paro_medio,
        COALESCE(tri.empleo_total_medio, 0) AS empleo_total_medio,
        COALESCE(tri.empleo_autonomos_medio, 0) AS empleo_autonomos_medio,
        COALESCE(men.plazas_vv_media, 0) AS plazas_vv_media,
        COALESCE(men.tasa_ocupacion_vv_media, 0) AS tasa_ocupacion_vv_media,
        COALESCE(men.estancia_media_vv, 0) AS estancia_media_vv,
        COALESCE(men.ingresos_vv_acumulados, 0) AS ingresos_vv_acumulados,
        COALESCE(men.ingresos_vv_media_mensual, 0) AS ingresos_vv_media_mensual
    FROM {{ ref('silver_limites_municipales') }} m
    JOIN mensual_agregado men ON m.cod_municipio = men.municipio_cod
    LEFT JOIN {{ ref('silver_istac_anual') }} a ON m.cod_municipio = a.municipio_cod AND men.anio = a.anio
    LEFT JOIN trimestral_agregado tri ON m.cod_municipio = tri.municipio_cod AND men.anio = tri.anio
)

SELECT 
    b.cod_municipio,
    b.municipio,
    b.anio,
    b.n_meses,
    b.es_anio_completo,
    b.poblacion,
    
    -- Paro y variación anual
    b.paro_medio,
    COALESCE(ROUND(((b.paro_medio - LAG(b.paro_medio) OVER (PARTITION BY b.cod_municipio ORDER BY b.anio)) / 
           NULLIF(LAG(b.paro_medio) OVER (PARTITION BY b.cod_municipio ORDER BY b.anio), 0) * 100)::numeric, 1), 0) AS var_paro_yoy_pct,
           
    -- Empleo total y variación anual
    b.empleo_total_medio,
    COALESCE(ROUND(((b.empleo_total_medio - LAG(b.empleo_total_medio) OVER (PARTITION BY b.cod_municipio ORDER BY b.anio)) / 
           NULLIF(LAG(b.empleo_total_medio) OVER (PARTITION BY b.cod_municipio ORDER BY b.anio), 0) * 100)::numeric, 1), 0) AS crec_empleo_total_yoy_pct,

    -- Empleo autónomo y variación anual
    b.empleo_autonomos_medio,
    COALESCE(ROUND(((b.empleo_autonomos_medio - LAG(b.empleo_autonomos_medio) OVER (PARTITION BY b.cod_municipio ORDER BY b.anio)) / 
           NULLIF(LAG(b.empleo_autonomos_medio) OVER (PARTITION BY b.cod_municipio ORDER BY b.anio), 0) * 100)::numeric, 1), 0) AS crec_empleo_autonomos_yoy_pct,
           
    -- Plazas VV y variación anual
    b.plazas_vv_media,
    COALESCE(ROUND(((b.plazas_vv_media - LAG(b.plazas_vv_media) OVER (PARTITION BY b.cod_municipio ORDER BY b.anio)) / 
           NULLIF(LAG(b.plazas_vv_media) OVER (PARTITION BY b.cod_municipio ORDER BY b.anio), 0) * 100)::numeric, 1), 0) AS crec_plazas_vv_yoy_pct,
           
    -- Ingresos VV (media mensual homogénea) y variación anual
    b.ingresos_vv_media_mensual,
    COALESCE(ROUND(((b.ingresos_vv_media_mensual - LAG(b.ingresos_vv_media_mensual) OVER (PARTITION BY b.cod_municipio ORDER BY b.anio)) / 
           NULLIF(LAG(b.ingresos_vv_media_mensual) OVER (PARTITION BY b.cod_municipio ORDER BY b.anio), 0) * 100)::numeric, 1), 0) AS crec_ingresos_mensual_yoy_pct,
           
    b.ingresos_vv_acumulados,
    b.tasa_ocupacion_vv_media,
    b.estancia_media_vv

FROM anual_base b
ORDER BY b.cod_municipio, b.anio DESC
