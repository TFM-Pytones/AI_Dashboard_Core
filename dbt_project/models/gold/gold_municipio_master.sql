{{ config(
    materialized='table',
    tags=['gold', 'municipio', 'core'],
    indexes=[
      {'columns': ['cod_municipio'], 'unique': True},
      {'columns': ['geometry'], 'type': 'gist'}
    ]
) }}

/*
  Modelo Gold: gold_municipio_master
  Tabla maestra a nivel municipal (31 municipios de Tenerife).
  Unifica en una única fila por municipio (31 filas, 0% NULLs):
  - Geometría MultiPolygon oficial (SRID 4326) para renderizar mapas coropléticos.
  - Foto fija actual de oferta alojativa, plataformas, POIs, clima y satélite (gold_h3_master).
  - Radiografía estructural de empleo y especialización sectorial CNAE 2026 (hostelería, servicios, industria, etc.).
  - Demografía, paro y vivienda vacacional ISTAC actual.
  - Ratios de presión y capacidad de carga turística (plazas por 1.000 hab, densidad por km²).
  - Métricas de EVOLUCIÓN HISTÓRICA continua (2022 vs 2025/2026):
      * % Crecimiento de población
      * % Variación del paro registrado
      * % Crecimiento del empleo total
      * % Crecimiento del empleo autónomo
      * % Crecimiento de plazas de Vivienda Vacacional
      * % Crecimiento de ingresos de Vivienda Vacacional
      * Variación de actividad nocturna / satélite (VIIRS 2022 vs 2026)
*/

WITH muni_geo AS (
    SELECT
        cod_municipio,
        nombre_municipio AS municipio,
        area_km2,
        centroide_lon,
        centroide_lat,
        geometry
    FROM {{ ref('silver_limites_municipales') }}
),

h3_agg AS (
    SELECT 
        cod_municipio,
        COUNT(*) AS n_hexagonos,
        
        -- Alojamiento oficial
        COALESCE(SUM(n_establecimientos_registro), 0) AS n_establecimientos_registro,
        COALESCE(SUM(n_plazas_registro), 0) AS n_plazas_registro,
        COALESCE(SUM(n_hoteles), 0) AS n_hoteles,
        COALESCE(SUM(n_vv), 0) AS n_vv,
        COALESCE(SUM(n_extrahoteleros), 0) AS n_extrahoteleros,
        
        -- Plataformas
        COALESCE(SUM(n_establecimientos_booking), 0) AS n_establecimientos_booking,
        ROUND(AVG(rating_booking_medio)::numeric, 2) AS rating_booking_medio,
        COALESCE(SUM(n_reviews_booking), 0) AS n_reviews_booking,
        COALESCE(SUM(n_establecimientos_tripadvisor), 0) AS n_establecimientos_tripadvisor,
        ROUND(AVG(rating_tripadvisor_medio)::numeric, 2) AS rating_tripadvisor_medio,
        
        -- POIs y Servicios
        COALESCE(SUM(n_pois_total), 0) AS n_pois_total,
        COALESCE(SUM(n_restaurantes), 0) AS n_restaurantes,
        COALESCE(SUM(n_cultura), 0) AS n_cultura,
        COALESCE(SUM(n_naturaleza), 0) AS n_naturaleza,
        COALESCE(SUM(n_pois_institucionales), 0) AS n_pois_institucionales,
        COALESCE(SUM(n_paradas_bus), 0) AS n_paradas_bus,
        
        -- Territorio y Clima
        ROUND(AVG(altitud_media_m)::numeric, 1) AS altitud_media_m,
        ROUND(AVG(temp_media_anual)::numeric, 1) AS temp_media_anual,
        ROUND(AVG(lluvia_mm_anual)::numeric, 1) AS lluvia_mm_anual,
        ROUND(AVG(pct_area_enp)::numeric, 3) AS pct_area_enp_medio,
        BOOL_OR(es_zona_turistica_oficial) AS tiene_zona_turistica_oficial,

        -- Satélite Medio y Evolución (2022 vs 2026)
        ROUND(AVG(ndvi_medio)::numeric, 3) AS ndvi_medio,
        ROUND(AVG(ndvi_2022)::numeric, 3) AS ndvi_2022,
        ROUND(AVG(ndvi_2026)::numeric, 3) AS ndvi_2026,
        ROUND(AVG(ndbi_medio)::numeric, 3) AS ndbi_medio,
        ROUND(AVG(ndbi_2022)::numeric, 3) AS ndbi_2022,
        ROUND(AVG(ndbi_2026)::numeric, 3) AS ndbi_2026,
        ROUND(AVG(viirs_medio)::numeric, 3) AS viirs_medio,
        ROUND(AVG(viirs_2022)::numeric, 3) AS viirs_2022,
        ROUND(AVG(viirs_2026)::numeric, 3) AS viirs_2026
    FROM {{ ref('gold_h3_master') }}
    GROUP BY cod_municipio
),

istac_2022 AS (
    SELECT 
        m.municipio_cod,
        a.poblacion_total AS poblacion_2022,
        ROUND(AVG(m.paro_registrado)::numeric, 0) AS paro_2022,
        ROUND(AVG(t.empleo_total)::numeric, 0) AS empleo_total_2022,
        ROUND(AVG(t.empleo_autonomos)::numeric, 0) AS empleo_autonomos_2022,
        ROUND(AVG(m.plazas_vv)::numeric, 0) AS plazas_vv_2022,
        ROUND(SUM(m.ingresos_vv)::numeric, 2) AS ingresos_vv_2022
    FROM {{ ref('silver_istac_mensual') }} m
    LEFT JOIN {{ ref('silver_istac_anual') }} a ON m.municipio_cod = a.municipio_cod AND a.anio = 2022
    LEFT JOIN {{ ref('silver_istac_trimestral') }} t ON m.municipio_cod = t.municipio_cod AND t.anio = 2022
    WHERE m.anio = 2022
    GROUP BY m.municipio_cod, a.poblacion_total
),

istac_turismo_actual AS (
    SELECT 
        m.municipio_cod,
        a.poblacion_total AS poblacion_actual,
        ROUND(AVG(m.paro_registrado)::numeric, 0) AS paro_actual,
        ROUND(AVG(m.plazas_vv)::numeric, 0) AS plazas_vv_actual,
        ROUND(SUM(m.ingresos_vv)::numeric, 2) AS ingresos_vv_actual,
        ROUND(AVG(m.tasa_ocupacion_vv)::numeric, 2) AS tasa_ocupacion_vv_actual,
        ROUND(AVG(m.estancia_media_vv)::numeric, 2) AS estancia_media_vv_actual
    FROM {{ ref('silver_istac_mensual') }} m
    LEFT JOIN {{ ref('silver_istac_anual') }} a ON m.municipio_cod = a.municipio_cod AND a.anio = 2025
    WHERE m.anio = 2025
    GROUP BY m.municipio_cod, a.poblacion_total
),

empleo_2026 AS (
    SELECT 
        municipio_cod,
        ROUND(AVG(empleo_total)::numeric, 0) AS empleo_total_actual,
        ROUND(AVG(empleo_asalariados)::numeric, 0) AS empleo_asalariados_actual,
        ROUND(AVG(empleo_autonomos)::numeric, 0) AS empleo_autonomos_actual,
        ROUND(AVG(empleo_hosteleria)::numeric, 0) AS empleo_hosteleria_actual,
        ROUND(AVG(empleo_servicios)::numeric, 0) AS empleo_servicios_actual,
        ROUND(AVG(empleo_comercio)::numeric, 0) AS empleo_comercio_actual,
        ROUND(AVG(empleo_construccion)::numeric, 0) AS empleo_construccion_actual,
        ROUND(AVG(empleo_industria)::numeric, 0) AS empleo_industria_actual,
        ROUND(AVG(empleo_agricultura)::numeric, 0) AS empleo_agricultura_actual,
        ROUND(((AVG(empleo_hosteleria) / NULLIF(AVG(empleo_total), 0)) * 100)::numeric, 2) AS pct_dependencia_hosteleria,
        ROUND(((AVG(empleo_servicios) / NULLIF(AVG(empleo_total), 0)) * 100)::numeric, 2)   AS pct_terciarizacion,
        ROUND(((AVG(empleo_autonomos) / NULLIF(AVG(empleo_total), 0)) * 100)::numeric, 2)   AS pct_autonomos,
        ROUND(((AVG(empleo_asalariados) / NULLIF(AVG(empleo_total), 0)) * 100)::numeric, 2) AS pct_asalariados,
        ROUND(((AVG(empleo_comercio) / NULLIF(AVG(empleo_total), 0)) * 100)::numeric, 2)    AS pct_comercio,
        ROUND(((AVG(empleo_construccion) / NULLIF(AVG(empleo_total), 0)) * 100)::numeric, 2) AS pct_construccion,
        ROUND(((AVG(empleo_industria) / NULLIF(AVG(empleo_total), 0)) * 100)::numeric, 2)   AS pct_industria,
        ROUND(((AVG(empleo_agricultura) / NULLIF(AVG(empleo_total), 0)) * 100)::numeric, 2) AS pct_agricultura
    FROM {{ ref('silver_istac_trimestral') }}
    WHERE anio = 2026
    GROUP BY municipio_cod
)

SELECT
    -- 1. Identificación y Geografía
    m.cod_municipio,
    m.municipio,
    m.area_km2,
    m.centroide_lon,
    m.centroide_lat,
    
    -- 2. Demografía y Empleo (Foto fija actual 2025/2026)
    COALESCE(it.poblacion_actual, 0) AS poblacion_actual,
    COALESCE(it.paro_actual, 0) AS paro_actual,
    COALESCE(e.empleo_total_actual, 0) AS empleo_total_actual,
    COALESCE(e.empleo_asalariados_actual, 0) AS empleo_asalariados_actual,
    COALESCE(e.empleo_autonomos_actual, 0) AS empleo_autonomos_actual,
    COALESCE(e.empleo_hosteleria_actual, 0) AS empleo_hosteleria_actual,
    COALESCE(e.empleo_servicios_actual, 0) AS empleo_servicios_actual,
    COALESCE(e.empleo_comercio_actual, 0) AS empleo_comercio_actual,
    COALESCE(e.empleo_construccion_actual, 0) AS empleo_construccion_actual,
    COALESCE(e.empleo_industria_actual, 0) AS empleo_industria_actual,
    COALESCE(e.empleo_agricultura_actual, 0) AS empleo_agricultura_actual,
    
    -- Especialización y diversificación económica (%)
    COALESCE(e.pct_dependencia_hosteleria, 0) AS pct_dependencia_hosteleria,
    COALESCE(e.pct_terciarizacion, 0) AS pct_terciarizacion,
    COALESCE(e.pct_autonomos, 0) AS pct_autonomos,
    COALESCE(e.pct_asalariados, 0) AS pct_asalariados,
    COALESCE(e.pct_comercio, 0) AS pct_comercio,
    COALESCE(e.pct_construccion, 0) AS pct_construccion,
    COALESCE(e.pct_industria, 0) AS pct_industria,
    COALESCE(e.pct_agricultura, 0) AS pct_agricultura,
    
    -- 3. Métricas de Turismo y Vivienda Vacacional (ISTAC)
    COALESCE(it.plazas_vv_actual, 0) AS plazas_vv_actual,
    COALESCE(it.tasa_ocupacion_vv_actual, 0) AS tasa_ocupacion_vv_actual,
    COALESCE(it.estancia_media_vv_actual, 0) AS estancia_media_vv_actual,
    COALESCE(it.ingresos_vv_actual, 0) AS ingresos_vv_actual,
    
    -- 4. Oferta alojativa oficial agregada H3 (Cabildo / Registro General)
    COALESCE(h.n_hexagonos, 0) AS n_hexagonos,
    COALESCE(h.n_establecimientos_registro, 0) AS n_establecimientos_registro,
    COALESCE(h.n_plazas_registro, 0) AS n_plazas_registro,
    COALESCE(h.n_hoteles, 0) AS n_hoteles,
    COALESCE(h.n_vv, 0) AS n_vv,
    COALESCE(h.n_extrahoteleros, 0) AS n_extrahoteleros,
    
    -- 5. Ratios de Presión y Capacidad de Carga
    ROUND((COALESCE(h.n_plazas_registro, 0) / NULLIF(m.area_km2, 0))::numeric, 2) AS densidad_plazas_km2,
    ROUND(((COALESCE(h.n_plazas_registro, 0)::numeric / NULLIF(it.poblacion_actual, 0)) * 1000)::numeric, 1) AS plazas_por_1000_hab,
    
    -- 6. EVOLUCIÓN HISTÓRICA (2022 vs 2025/2026)
    COALESCE(i2.poblacion_2022, 0) AS poblacion_2022,
    COALESCE(ROUND(((it.poblacion_actual - i2.poblacion_2022) / NULLIF(i2.poblacion_2022, 0) * 100)::numeric, 1), 0) AS crec_poblacion_pct,
    
    COALESCE(i2.paro_2022, 0) AS paro_2022,
    COALESCE(ROUND(((it.paro_actual - i2.paro_2022) / NULLIF(i2.paro_2022, 0) * 100)::numeric, 1), 0) AS var_paro_pct,
    
    COALESCE(i2.empleo_total_2022, 0) AS empleo_total_2022,
    COALESCE(ROUND(((e.empleo_total_actual - i2.empleo_total_2022) / NULLIF(i2.empleo_total_2022, 0) * 100)::numeric, 1), 0) AS crec_empleo_total_pct,
    
    COALESCE(i2.empleo_autonomos_2022, 0) AS empleo_autonomos_2022,
    COALESCE(ROUND(((e.empleo_autonomos_actual - i2.empleo_autonomos_2022) / NULLIF(i2.empleo_autonomos_2022, 0) * 100)::numeric, 1), 0) AS crec_empleo_autonomos_pct,
    
    COALESCE(i2.plazas_vv_2022, 0) AS plazas_vv_2022,
    COALESCE(ROUND(((it.plazas_vv_actual - i2.plazas_vv_2022) / NULLIF(i2.plazas_vv_2022, 0) * 100)::numeric, 1), 0) AS crec_plazas_vv_pct,
    
    COALESCE(i2.ingresos_vv_2022, 0) AS ingresos_vv_2022,
    COALESCE(ROUND(((it.ingresos_vv_actual - i2.ingresos_vv_2022) / NULLIF(i2.ingresos_vv_2022, 0) * 100)::numeric, 1), 0) AS crec_ingresos_vv_pct,
    
    -- 7. Plataformas (Booking y TripAdvisor)
    COALESCE(h.n_establecimientos_booking, 0) AS n_establecimientos_booking,
    COALESCE(h.rating_booking_medio, 0) AS rating_booking_medio,
    COALESCE(h.n_reviews_booking, 0) AS n_reviews_booking,
    COALESCE(h.n_establecimientos_tripadvisor, 0) AS n_establecimientos_tripadvisor,
    COALESCE(h.rating_tripadvisor_medio, 0) AS rating_tripadvisor_medio,
    
    -- 8. POIs y Movilidad
    COALESCE(h.n_pois_total, 0) AS n_pois_total,
    COALESCE(h.n_restaurantes, 0) AS n_restaurantes,
    COALESCE(h.n_cultura, 0) AS n_cultura,
    COALESCE(h.n_naturaleza, 0) AS n_naturaleza,
    COALESCE(h.n_pois_institucionales, 0) AS n_pois_institucionales,
    COALESCE(h.n_paradas_bus, 0) AS n_paradas_bus,
    
    -- 9. Factores Ambientales, Clima y Satélite (NDVI, NDBI, VIIRS)
    h.altitud_media_m,
    h.temp_media_anual,
    h.lluvia_mm_anual,
    h.pct_area_enp_medio,
    COALESCE(h.tiene_zona_turistica_oficial, FALSE) AS tiene_zona_turistica_oficial,
    h.ndvi_medio,
    h.ndvi_2022,
    h.ndvi_2026,
    h.ndbi_medio,
    h.ndbi_2022,
    h.ndbi_2026,
    ROUND((h.ndbi_2026 - h.ndbi_2022)::numeric, 3) AS cambio_ndbi_absoluto,
    h.viirs_medio,
    h.viirs_2022,
    h.viirs_2026,
    COALESCE(ROUND(((h.viirs_2026 - h.viirs_2022) / NULLIF(h.viirs_2022, 0) * 100)::numeric, 1), 0) AS cambio_luz_nocturna_pct,
    
    -- 10. Geometría PostGIS para visualización coroplética
    m.geometry

FROM muni_geo m
LEFT JOIN h3_agg h ON m.cod_municipio = h.cod_municipio
LEFT JOIN istac_2022 i2 ON m.cod_municipio = i2.municipio_cod
LEFT JOIN istac_turismo_actual it ON m.cod_municipio = it.municipio_cod
LEFT JOIN empleo_2026 e ON m.cod_municipio = e.municipio_cod
ORDER BY m.cod_municipio
