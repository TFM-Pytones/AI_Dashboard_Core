{{ config(
    materialized='table',
    tags=['gold', 'core', 'bloque1'],
    indexes=[
      {'columns': ['geometry'], 'type': 'gist'},
      {'columns': ['h3_index'], 'unique': True},
      {'columns': ['cod_municipio']}
    ]
) }}

/*
  Modelo Gold: gold_h3_master (BLOQUE 1 - Fase 1 Base Territorial)
  Tabla maestra unificada a nivel hexagonal (H3 Res 8, 2.579 celdas insulares consolidadas desde silver_h3_grid).
  Incluye:
    - Base espacial y municipal.
    - Oferta reglada y plataformas OTAs (Booking y TripAdvisor) con métricas unificadas.
    - POIs y transporte público TITSA.
    - Relieve MDT optimizado (altitud, desnivel interno, pendiente, orientación y sombreado).
    - Índices biofísicos Copernicus (NDVI, VIIRS, NDBI) anuales (2022-2026), trimestrales (Q1-Q4) y dinamismo temporal.
    - Clima Agrocabildo IDW (K=3) + Gradiente Térmico, con Horas de Sol Diarias Reales (Estándar OMM >= 120 W/m2) y extremos ESG.
    - Figuras ambientales ENP y Zonas Turísticas Oficiales con cobertura (%) y denominación para RAG / Text-to-SQL.
    - Distancia euclidiana a la costa en kilómetros (dist_costa_km).
*/

WITH h3 AS (
    SELECT 
        h3_index,
        ST_Area(geometry::geography) / 1000000.0 AS area_km2,
        ST_X(ST_Centroid(geometry)) AS centroide_lon,
        ST_Y(ST_Centroid(geometry)) AS centroide_lat,
        geometry
    FROM {{ ref('silver_h3_grid') }}
),

municipios AS (
    SELECT DISTINCT ON (h.h3_index)
        h.h3_index,
        m.cod_municipio,
        m.nombre_municipio AS municipio
    FROM h3 h
    JOIN {{ ref('silver_limites_municipales') }} m
        ON ST_Intersects(h.geometry, m.geometry)
    ORDER BY h.h3_index, ST_Area(ST_Intersection(h.geometry, m.geometry)) DESC
),

alojamiento AS (
    SELECT
        h.h3_index,
        COUNT(a.id) AS n_establecimientos_registro,
        COALESCE(SUM(a.plazas), 0) AS n_plazas_registro,
        COUNT(a.id) FILTER (WHERE a.tipo_alojamiento = 'hotel') AS n_hoteles,
        COUNT(a.id) FILTER (WHERE a.tipo_alojamiento = 'vivienda_vacacional') AS n_vv,
        COUNT(a.id) FILTER (WHERE a.tipo_alojamiento = 'extrahotelero') AS n_extrahoteleros
    FROM h3 h
    LEFT JOIN {{ ref('silver_alojamientos_oficiales') }} a ON ST_Contains(h.geometry, a.geometry)
    GROUP BY h.h3_index
),

booking AS (
    SELECT
        h.h3_index,
        COUNT(DISTINCT e.establishment_id) AS n_establecimientos_booking,
        ROUND(AVG(r.rating)::numeric, 2) AS rating_booking_medio,
        COUNT(r.review_id) AS n_reviews_booking
    FROM h3 h
    LEFT JOIN {{ ref('silver_booking_establishments') }} e ON ST_Contains(h.geometry, e.geometry)
    LEFT JOIN {{ ref('silver_booking_reviews') }} r ON r.establishment_id = e.establishment_id
    GROUP BY h.h3_index
),

tripadvisor AS (
    SELECT
        h.h3_index,
        COUNT(DISTINCT e.location_id) AS n_establecimientos_tripadvisor,
        ROUND(AVG(r.rating)::numeric, 2) AS rating_tripadvisor_medio,
        COUNT(r.review_id) AS n_reviews_tripadvisor
    FROM h3 h
    LEFT JOIN {{ ref('silver_tripadvisor_ubicaciones') }} e ON ST_Contains(h.geometry, e.geometry)
    LEFT JOIN {{ ref('silver_tripadvisor_resenas') }} r ON r.location_id = e.location_id
    GROUP BY h.h3_index
),

pois AS (
    SELECT
        h.h3_index,
        COUNT(p.id) AS n_pois_total,
        COUNT(p.id) FILTER (WHERE p.tipo IN ('restaurant', 'bar', 'cafe', 'fast_food', 'pub')) AS n_restaurantes,
        COUNT(p.id) FILTER (WHERE p.categoria IN ('Atracciones_Turisticas', 'Cultura')) AS n_cultura,
        COUNT(p.id) FILTER (WHERE p.categoria IN ('Naturaleza_Deporte')) AS n_naturaleza,
        COUNT(p.id) FILTER (WHERE p.fuente = 'IDE_Canarias') AS n_pois_institucionales
    FROM h3 h
    LEFT JOIN {{ ref('silver_puntos_interes_unificados') }} p ON ST_Contains(h.geometry, p.geometry)
    GROUP BY h.h3_index
),

paradas_bus AS (
    SELECT
        h.h3_index,
        COUNT(p.stop_id) AS n_paradas_bus
    FROM h3 h
    LEFT JOIN {{ ref('silver_gtfs_paradas') }} p ON ST_Contains(h.geometry, p.geometry)
    GROUP BY h.h3_index
),

satelite_mdt AS (
    SELECT
        h.h3_index,
        -- MDT Optimizado
        m.elevation_mean AS altitud_media_m,
        (m.elevation_max - m.elevation_min) AS desnivel_m,
        m.slope_mean,
        m.aspect_mean,
        m.hillshade_mean,
        -- Indices de Satelite
        s.ndvi_medio, s.ndvi_2022, s.ndvi_2023, s.ndvi_2024, s.ndvi_2025, s.ndvi_2026, s.ndvi_q1, s.ndvi_q2, s.ndvi_q3, s.ndvi_q4,
        s.viirs_medio, s.viirs_2022, s.viirs_2023, s.viirs_2024, s.viirs_2025, s.viirs_2026, s.viirs_q1, s.viirs_q2, s.viirs_q3, s.viirs_q4,
        s.cambio_luz_nocturna_pct,
        s.ndbi_medio, s.ndbi_2022, s.ndbi_2023, s.ndbi_2024, s.ndbi_2025, s.ndbi_2026
    FROM h3 h
    LEFT JOIN {{ source('bronze', 'bronze_mdt_stats') }} m ON h.h3_index = m.h3_index
    LEFT JOIN (
        SELECT 
            h3_index, 
            
            -- NDVI
            AVG(ndvi_mean) AS ndvi_medio, 
            AVG(ndvi_mean) FILTER (WHERE year = 2022) AS ndvi_2022,
            AVG(ndvi_mean) FILTER (WHERE year = 2023) AS ndvi_2023,
            AVG(ndvi_mean) FILTER (WHERE year = 2024) AS ndvi_2024,
            AVG(ndvi_mean) FILTER (WHERE year = 2025) AS ndvi_2025,
            AVG(ndvi_mean) FILTER (WHERE year = 2026) AS ndvi_2026,
            AVG(ndvi_mean) FILTER (WHERE quarter = 'Q1') AS ndvi_q1,
            AVG(ndvi_mean) FILTER (WHERE quarter = 'Q2') AS ndvi_q2,
            AVG(ndvi_mean) FILTER (WHERE quarter = 'Q3') AS ndvi_q3,
            AVG(ndvi_mean) FILTER (WHERE quarter = 'Q4') AS ndvi_q4,
            
            -- VIIRS
            AVG(viirs_mean) AS viirs_medio, 
            AVG(viirs_mean) FILTER (WHERE year = 2022) AS viirs_2022,
            AVG(viirs_mean) FILTER (WHERE year = 2023) AS viirs_2023,
            AVG(viirs_mean) FILTER (WHERE year = 2024) AS viirs_2024,
            AVG(viirs_mean) FILTER (WHERE year = 2025) AS viirs_2025,
            AVG(viirs_mean) FILTER (WHERE year = 2026) AS viirs_2026,
            AVG(viirs_mean) FILTER (WHERE quarter = 'Q1') AS viirs_q1,
            AVG(viirs_mean) FILTER (WHERE quarter = 'Q2') AS viirs_q2,
            AVG(viirs_mean) FILTER (WHERE quarter = 'Q3') AS viirs_q3,
            AVG(viirs_mean) FILTER (WHERE quarter = 'Q4') AS viirs_q4,
            ROUND((((AVG(viirs_mean) FILTER (WHERE year = 2026) - AVG(viirs_mean) FILTER (WHERE year = 2022)) / NULLIF(AVG(viirs_mean) FILTER (WHERE year = 2022), 0)) * 100)::numeric, 2) AS cambio_luz_nocturna_pct,
            
            -- NDBI
            AVG(ndbi_mean) AS ndbi_medio, 
            AVG(ndbi_mean) FILTER (WHERE year = 2022) AS ndbi_2022,
            AVG(ndbi_mean) FILTER (WHERE year = 2023) AS ndbi_2023,
            AVG(ndbi_mean) FILTER (WHERE year = 2024) AS ndbi_2024,
            AVG(ndbi_mean) FILTER (WHERE year = 2025) AS ndbi_2025,
            AVG(ndbi_mean) FILTER (WHERE year = 2026) AS ndbi_2026
            
        FROM {{ ref('silver_satelite_stats') }}
        GROUP BY h3_index
    ) s ON h.h3_index = s.h3_index
),

clima_diario AS (
    SELECT 
        id_estacion,
        date_trunc('day', "timestamp") AS fecha,
        EXTRACT(QUARTER FROM "timestamp") AS trimestre,
        -- Extremos y agregados diarios
        MAX(valor_limpio) FILTER (WHERE variable_nombre ILIKE '%Temp%') AS temp_max,
        MIN(valor_limpio) FILTER (WHERE variable_nombre ILIKE '%Temp%') AS temp_min,
        AVG(valor_limpio) FILTER (WHERE variable_nombre ILIKE '%Temp%') AS temp_media,
        SUM(valor_limpio) FILTER (WHERE variable_nombre ILIKE '%Precip%') AS lluvia_total,
        AVG(valor_limpio) FILTER (WHERE variable_nombre ILIKE '%Velocidad%') AS vel_viento_media,
        AVG(valor_limpio) FILTER (WHERE variable_nombre ILIKE '%Direcci%') AS dir_viento_media,
        AVG(valor_limpio) FILTER (WHERE variable_nombre ILIKE '%Humedad%') AS humedad_media,
        MIN(valor_limpio) FILTER (WHERE variable_nombre ILIKE '%Humedad%') AS humedad_min,
        -- Horas de sol segun estandar OMM (radiacion >= 120 W/m2 en lecturas horarias)
        COUNT(*) FILTER (WHERE variable_nombre ILIKE '%Radiaci%' AND valor_limpio >= 120) AS horas_sol_dia
    FROM {{ ref('silver_clima_agrocabildo') }}
    GROUP BY id_estacion, date_trunc('day', "timestamp"), EXTRACT(QUARTER FROM "timestamp")
),

estaciones_clima AS (
    SELECT 
        id_estacion,
        
        -- INDICADORES ESG Y EXTREMOS
        COUNT(*) FILTER (WHERE temp_max >= 35 AND humedad_min <= 30 AND dir_viento_media BETWEEN 60 AND 200) AS dias_ola_calor_anual,
        AVG(temp_max - temp_min) AS amplitud_termica_media,

        -- HORAS DE SOL REALES (ESTÁNDAR OMM)
        AVG(horas_sol_dia) AS horas_sol_diarias_media,
        AVG(horas_sol_dia) FILTER (WHERE trimestre = 1) AS horas_sol_q1,
        AVG(horas_sol_dia) FILTER (WHERE trimestre = 2) AS horas_sol_q2,
        AVG(horas_sol_dia) FILTER (WHERE trimestre = 3) AS horas_sol_q3,
        AVG(horas_sol_dia) FILTER (WHERE trimestre = 4) AS horas_sol_q4,

        -- VARIABLES ESTADISTICAS ESTACIONALES
        AVG(temp_media) AS temp_media_anual,
        AVG(temp_media) FILTER (WHERE trimestre = 1) AS temp_media_q1,
        AVG(temp_media) FILTER (WHERE trimestre = 2) AS temp_media_q2,
        AVG(temp_media) FILTER (WHERE trimestre = 3) AS temp_media_q3,
        AVG(temp_media) FILTER (WHERE trimestre = 4) AS temp_media_q4,
        
        SUM(lluvia_total) / NULLIF(COUNT(DISTINCT EXTRACT(YEAR FROM fecha)), 0) AS lluvia_mm_anual,
        SUM(lluvia_total) FILTER (WHERE trimestre = 1) / NULLIF(COUNT(DISTINCT EXTRACT(YEAR FROM fecha)), 0) AS lluvia_mm_q1,
        SUM(lluvia_total) FILTER (WHERE trimestre = 2) / NULLIF(COUNT(DISTINCT EXTRACT(YEAR FROM fecha)), 0) AS lluvia_mm_q2,
        SUM(lluvia_total) FILTER (WHERE trimestre = 3) / NULLIF(COUNT(DISTINCT EXTRACT(YEAR FROM fecha)), 0) AS lluvia_mm_q3,
        SUM(lluvia_total) FILTER (WHERE trimestre = 4) / NULLIF(COUNT(DISTINCT EXTRACT(YEAR FROM fecha)), 0) AS lluvia_mm_q4,

        AVG(vel_viento_media) AS vel_viento_media_anual,
        AVG(vel_viento_media) FILTER (WHERE trimestre = 1) AS vel_viento_media_q1,
        AVG(vel_viento_media) FILTER (WHERE trimestre = 2) AS vel_viento_media_q2,
        AVG(vel_viento_media) FILTER (WHERE trimestre = 3) AS vel_viento_media_q3,
        AVG(vel_viento_media) FILTER (WHERE trimestre = 4) AS vel_viento_media_q4,
        
        AVG(humedad_media) AS humedad_media_anual,
        AVG(humedad_media) FILTER (WHERE trimestre = 1) AS humedad_media_q1,
        AVG(humedad_media) FILTER (WHERE trimestre = 2) AS humedad_media_q2,
        AVG(humedad_media) FILTER (WHERE trimestre = 3) AS humedad_media_q3,
        AVG(humedad_media) FILTER (WHERE trimestre = 4) AS humedad_media_q4
        
    FROM clima_diario
    GROUP BY id_estacion
),

estaciones_con_topografia AS MATERIALIZED (
    SELECT DISTINCT ON (c.id_estacion)
        c.*,
        e.altitud_m AS station_altitud,
        e.geometry,
        COALESCE(acc.dist_costa_km, 0) AS station_dist_costa_km,
        COALESCE(m.aspect_mean, 180) AS station_aspect
    FROM estaciones_clima c
    JOIN {{ ref('silver_estaciones_agrocabildo') }} e ON c.id_estacion = e.id_estacion
    LEFT JOIN {{ ref('silver_h3_grid') }} h ON ST_Intersects(e.geometry, h.geometry)
    LEFT JOIN {{ source('bronze', 'bronze_mdt_stats') }} m ON h.h3_index = m.h3_index
    LEFT JOIN {{ source('gold_accesibilidad', 'gold_h3_accesibilidad') }} acc ON h.h3_index = acc.h3_index
    ORDER BY c.id_estacion
),

h3_con_topografia AS MATERIALIZED (
    SELECT 
        h.h3_index, 
        h.geometry, 
        m.elevation_mean AS h3_altitud,
        COALESCE(m.aspect_mean, 180) AS h3_aspect,
        COALESCE(acc.dist_costa_km, 0) AS h3_dist_costa_km
    FROM h3 h
    LEFT JOIN {{ source('bronze', 'bronze_mdt_stats') }} m ON h.h3_index = m.h3_index
    LEFT JOIN {{ source('gold_accesibilidad', 'gold_h3_accesibilidad') }} acc ON h.h3_index = acc.h3_index
),

h3_vecinos_clima AS (
    SELECT
        h.h3_index,
        h.h3_altitud,
        h.h3_aspect,
        h.h3_dist_costa_km,
        est.*,
        1.0 / POWER(GREATEST(ST_Distance(ST_Transform(h.geometry, 32628), ST_Transform(est.geometry, 32628)), 1), 2) AS peso
    FROM h3_con_topografia h
    CROSS JOIN LATERAL (
        SELECT *
        FROM estaciones_con_topografia e
        ORDER BY h.geometry <-> e.geometry
        LIMIT 3
    ) est
),

h3_vecinos_clima_factores AS (
    SELECT
        *,
        -- Factor Humedad H3
        (CASE WHEN h3_aspect >= 300 OR h3_aspect <= 90 THEN 
            CASE WHEN h3_altitud BETWEEN 800 AND 1500 THEN 1.25 
                 WHEN h3_altitud > 1500 THEN 0.70 
                 ELSE 1.05 END
         WHEN h3_aspect > 90 AND h3_aspect < 300 THEN 0.85
         ELSE 1.0 END) + (CASE WHEN h3_dist_costa_km < 1.5 THEN 0.15 ELSE 0 END) AS factor_hum_h3,
         
        -- Factor Humedad Estacion
        (CASE WHEN station_aspect >= 300 OR station_aspect <= 90 THEN 
            CASE WHEN station_altitud BETWEEN 800 AND 1500 THEN 1.25 
                 WHEN station_altitud > 1500 THEN 0.70 
                 ELSE 1.05 END
         WHEN station_aspect > 90 AND station_aspect < 300 THEN 0.85
         ELSE 1.0 END) + (CASE WHEN station_dist_costa_km < 1.5 THEN 0.15 ELSE 0 END) AS factor_hum_est,

        -- Factor Lluvia H3
        (CASE WHEN (h3_aspect >= 300 OR h3_aspect <= 90) AND h3_altitud < 1500 THEN 1.30
              WHEN h3_aspect > 90 AND h3_aspect < 300 THEN 0.40
              ELSE 1.0 END) AS factor_lluvia_h3,
              
        -- Factor Lluvia Estacion
        (CASE WHEN (station_aspect >= 300 OR station_aspect <= 90) AND station_altitud < 1500 THEN 1.30
              WHEN station_aspect > 90 AND station_aspect < 300 THEN 0.40
              ELSE 1.0 END) AS factor_lluvia_est,

        -- Factor Viento H3
        (CASE WHEN h3_aspect >= 0 AND h3_aspect <= 90 THEN 1.20
              WHEN h3_aspect >= 180 AND h3_aspect <= 270 THEN 0.60
              WHEN h3_altitud > 2000 THEN 1.40
              ELSE 1.0 END) AS factor_viento_h3,
              
        -- Factor Viento Estacion
        (CASE WHEN station_aspect >= 0 AND station_aspect <= 90 THEN 1.20
              WHEN station_aspect >= 180 AND station_aspect <= 270 THEN 0.60
              WHEN station_altitud > 2000 THEN 1.40
              ELSE 1.0 END) AS factor_viento_est,
              
        -- Delta Costa para Temperaturas
        (h3_dist_costa_km - station_dist_costa_km) AS delta_dist_costa
    FROM h3_vecinos_clima
),

h3_clima AS (
    SELECT
        h3_index,
        
        -- INDICADORES ESG Y EXTREMOS (IDW Puro)
        SUM(dias_ola_calor_anual * peso) / NULLIF(SUM(peso), 0) AS dias_ola_calor_anual,
        SUM(horas_sol_diarias_media * peso) / NULLIF(SUM(peso), 0) AS horas_sol_diarias_media,
        SUM(horas_sol_q1 * peso) / NULLIF(SUM(peso), 0) AS horas_sol_q1,
        SUM(horas_sol_q2 * peso) / NULLIF(SUM(peso), 0) AS horas_sol_q2,
        SUM(horas_sol_q3 * peso) / NULLIF(SUM(peso), 0) AS horas_sol_q3,
        SUM(horas_sol_q4 * peso) / NULLIF(SUM(peso), 0) AS horas_sol_q4,

        -- TEMPERATURA Y AMPLITUD (IDW + Gradiente Térmico + Termorregulación)
        SUM((temp_media_anual + COALESCE((station_altitud - h3_altitud) * 0.0065, 0)) * peso) / NULLIF(SUM(peso), 0) AS temp_media_anual,
        SUM((temp_media_q1 + COALESCE((station_altitud - h3_altitud) * 0.0065, 0) - (delta_dist_costa * 0.15)) * peso) / NULLIF(SUM(peso), 0) AS temp_media_q1,
        SUM((temp_media_q2 + COALESCE((station_altitud - h3_altitud) * 0.0065, 0) + (delta_dist_costa * 0.05)) * peso) / NULLIF(SUM(peso), 0) AS temp_media_q2,
        SUM((temp_media_q3 + COALESCE((station_altitud - h3_altitud) * 0.0065, 0) + (delta_dist_costa * 0.15)) * peso) / NULLIF(SUM(peso), 0) AS temp_media_q3,
        SUM((temp_media_q4 + COALESCE((station_altitud - h3_altitud) * 0.0065, 0) - (delta_dist_costa * 0.05)) * peso) / NULLIF(SUM(peso), 0) AS temp_media_q4,
        SUM((amplitud_termica_media + GREATEST(delta_dist_costa * 0.30, 0)) * peso) / NULLIF(SUM(peso), 0) AS amplitud_termica_media,

        -- PRECIPITACIÓN (IDW + Sombra Lluvia)
        SUM((lluvia_mm_anual * (factor_lluvia_h3 / NULLIF(factor_lluvia_est, 0.001))) * peso) / NULLIF(SUM(peso), 0) AS lluvia_mm_anual,
        SUM((lluvia_mm_q1 * (factor_lluvia_h3 / NULLIF(factor_lluvia_est, 0.001))) * peso) / NULLIF(SUM(peso), 0) AS lluvia_mm_q1,
        SUM((lluvia_mm_q2 * (factor_lluvia_h3 / NULLIF(factor_lluvia_est, 0.001))) * peso) / NULLIF(SUM(peso), 0) AS lluvia_mm_q2,
        SUM((lluvia_mm_q3 * (factor_lluvia_h3 / NULLIF(factor_lluvia_est, 0.001))) * peso) / NULLIF(SUM(peso), 0) AS lluvia_mm_q3,
        SUM((lluvia_mm_q4 * (factor_lluvia_h3 / NULLIF(factor_lluvia_est, 0.001))) * peso) / NULLIF(SUM(peso), 0) AS lluvia_mm_q4,

        -- VELOCIDAD VIENTO (IDW + Efecto Escudo)
        SUM((vel_viento_media_anual * (factor_viento_h3 / NULLIF(factor_viento_est, 0.001))) * peso) / NULLIF(SUM(peso), 0) AS vel_viento_media_anual,
        SUM((vel_viento_media_q1 * (factor_viento_h3 / NULLIF(factor_viento_est, 0.001))) * peso) / NULLIF(SUM(peso), 0) AS vel_viento_media_q1,
        SUM((vel_viento_media_q2 * (factor_viento_h3 / NULLIF(factor_viento_est, 0.001))) * peso) / NULLIF(SUM(peso), 0) AS vel_viento_media_q2,
        SUM((vel_viento_media_q3 * (factor_viento_h3 / NULLIF(factor_viento_est, 0.001))) * peso) / NULLIF(SUM(peso), 0) AS vel_viento_media_q3,
        SUM((vel_viento_media_q4 * (factor_viento_h3 / NULLIF(factor_viento_est, 0.001))) * peso) / NULLIF(SUM(peso), 0) AS vel_viento_media_q4,

        -- HUMEDAD (IDW + Mar Nubes + Costera)
        SUM((humedad_media_anual * (factor_hum_h3 / NULLIF(factor_hum_est, 0.001))) * peso) / NULLIF(SUM(peso), 0) AS humedad_media_anual,
        SUM((humedad_media_q1 * (factor_hum_h3 / NULLIF(factor_hum_est, 0.001))) * peso) / NULLIF(SUM(peso), 0) AS humedad_media_q1,
        SUM((humedad_media_q2 * (factor_hum_h3 / NULLIF(factor_hum_est, 0.001))) * peso) / NULLIF(SUM(peso), 0) AS humedad_media_q2,
        SUM((humedad_media_q3 * (factor_hum_h3 / NULLIF(factor_hum_est, 0.001))) * peso) / NULLIF(SUM(peso), 0) AS humedad_media_q3,
        SUM((humedad_media_q4 * (factor_hum_h3 / NULLIF(factor_hum_est, 0.001))) * peso) / NULLIF(SUM(peso), 0) AS humedad_media_q4
    FROM h3_vecinos_clima_factores
    GROUP BY h3_index
),

enp AS (
    SELECT
        h.h3_index,
        LEAST(1.0::numeric, ROUND((SUM(ST_Area(ST_Intersection(ST_Transform(h.geometry, 32628), ST_Transform(e.geometry, 32628)))) / ST_Area(ST_Transform(h.geometry, 32628)))::numeric, 4)) AS pct_area_enp,
        STRING_AGG(DISTINCT e.nombre_enp, ', ') AS nombre_enp
    FROM h3 h
    LEFT JOIN {{ ref('silver_enp') }} e ON ST_Intersects(h.geometry, e.geometry)
    GROUP BY h.h3_index, h.geometry
),

zonas_turisticas AS (
    SELECT
        h.h3_index,
        ROUND((SUM(ST_Area(ST_Intersection(ST_Transform(h.geometry, 32628), ST_Transform(z.geometry, 32628)))) / ST_Area(ST_Transform(h.geometry, 32628)))::numeric, 4) AS pct_area_zona_turistica,
        STRING_AGG(DISTINCT z.nombre_zona, ', ') AS nombre_zona_turistica
    FROM h3 h
    LEFT JOIN {{ ref('silver_zonas_turisticas') }} z ON ST_Intersects(h.geometry, z.geometry)
    GROUP BY h.h3_index, h.geometry
),

accesibilidad AS (
    SELECT
        h3_index,
        tiempo_aeropuerto_min,
        aeropuerto_mas_cercano,
        tiempo_tfs_min,
        tiempo_tfn_min,
        tiempo_capital_min,
        tiempo_extremo_sur_min,
        tiempo_extremo_norte_min,
        tiempo_teide_min,
        tiempo_la_laguna_min,
        tiempo_candelaria_min,
        tiempo_los_gigantes_min,
        tiempo_el_medano_min,
        tiempo_garachico_min,
        tiempo_anaga_min,
        tiempo_masca_min,
        tiempo_vilaflor_min,
        tiempo_la_orotava_min,
        tiempo_guimar_min,
        tiempo_buenavista_min,
        tiempo_arico_min,
        n_paradas_bus_200m,
        n_paradas_bus_500m,
        n_paradas_bus_1000m,
        dist_parada_cercana_m,
        dist_hospital_km,
        dist_costa_km
    FROM {{ source('gold_accesibilidad', 'gold_h3_accesibilidad') }}
)

SELECT
    h.h3_index,
    mun.cod_municipio,
    mun.municipio,
    h.area_km2,
    h.centroide_lon,
    h.centroide_lat,
    
    -- Alojamiento Oficial
    COALESCE(aloj.n_establecimientos_registro, 0) AS n_establecimientos_registro,
    COALESCE(aloj.n_plazas_registro, 0) AS n_plazas_registro,
    COALESCE(aloj.n_hoteles, 0) AS n_hoteles,
    COALESCE(aloj.n_vv, 0) AS n_vv,
    COALESCE(aloj.n_extrahoteleros, 0) AS n_extrahoteleros,
    
    -- Plataformas (Booking)
    COALESCE(b.n_establecimientos_booking, 0) AS n_establecimientos_booking,
    b.rating_booking_medio,
    COALESCE(b.n_reviews_booking, 0) AS n_reviews_booking,
    
    -- Plataformas (Tripadvisor)
    COALESCE(t.n_establecimientos_tripadvisor, 0) AS n_establecimientos_tripadvisor,
    t.rating_tripadvisor_medio,
    COALESCE(t.n_reviews_tripadvisor, 0) AS n_reviews_tripadvisor,

    -- Reputación y Reseñas Unificadas
    (COALESCE(b.n_reviews_booking, 0) + COALESCE(t.n_reviews_tripadvisor, 0)) AS n_reviews_total,
    CASE 
        WHEN (COALESCE(b.n_reviews_booking, 0) + COALESCE(t.n_reviews_tripadvisor, 0)) > 0 THEN
            ROUND((
                (COALESCE(b.rating_booking_medio, 0) * 10.0 * COALESCE(b.n_reviews_booking, 0) +
                 COALESCE(t.rating_tripadvisor_medio, 0) * 20.0 * COALESCE(t.n_reviews_tripadvisor, 0))
                / NULLIF(COALESCE(b.n_reviews_booking, 0) + COALESCE(t.n_reviews_tripadvisor, 0), 0)
            )::numeric, 2)
        ELSE NULL
    END AS rating_global_100,
    
    -- POIs
    COALESCE(p.n_pois_total, 0) AS n_pois_total,
    COALESCE(p.n_restaurantes, 0) AS n_restaurantes,
    COALESCE(p.n_cultura, 0) AS n_cultura,
    COALESCE(p.n_naturaleza, 0) AS n_naturaleza,
    COALESCE(p.n_pois_institucionales, 0) AS n_pois_institucionales,
    
    -- Transporte
    COALESCE(pb.n_paradas_bus, 0) AS n_paradas_bus,
    
    -- MDT y Topografía Optimizada
    sm.altitud_media_m,
    sm.desnivel_m,
    sm.slope_mean,
    sm.aspect_mean,
    sm.hillshade_mean,
    
    -- Satélite (Copernicus)
    sm.ndvi_medio,
    sm.ndvi_2022,
    sm.ndvi_2023,
    sm.ndvi_2024,
    sm.ndvi_2025,
    sm.ndvi_2026,
    sm.ndvi_q1,
    sm.ndvi_q2,
    sm.ndvi_q3,
    sm.ndvi_q4,
    
    sm.viirs_medio,
    sm.viirs_2022,
    sm.viirs_2023,
    sm.viirs_2024,
    sm.viirs_2025,
    sm.viirs_2026,
    sm.viirs_q1,
    sm.viirs_q2,
    sm.viirs_q3,
    sm.viirs_q4,
    sm.cambio_luz_nocturna_pct,
    
    sm.ndbi_medio,
    sm.ndbi_2022,
    sm.ndbi_2023,
    sm.ndbi_2024,
    sm.ndbi_2025,
    sm.ndbi_2026,
    
    -- Clima (Agrocabildo) - ESG y Extremos
    hc.dias_ola_calor_anual,
    hc.amplitud_termica_media,
    
    -- Clima (Agrocabildo) - Horas de Sol Reales (Estándar OMM >= 120 W/m2)
    hc.horas_sol_diarias_media,
    hc.horas_sol_q1,
    hc.horas_sol_q2,
    hc.horas_sol_q3,
    hc.horas_sol_q4,
    
    -- Clima (Agrocabildo) - Estacional
    hc.temp_media_anual, hc.temp_media_q1, hc.temp_media_q2, hc.temp_media_q3, hc.temp_media_q4,
    hc.lluvia_mm_anual, hc.lluvia_mm_q1, hc.lluvia_mm_q2, hc.lluvia_mm_q3, hc.lluvia_mm_q4,
    hc.vel_viento_media_anual, hc.vel_viento_media_q1, hc.vel_viento_media_q2, hc.vel_viento_media_q3, hc.vel_viento_media_q4,
    hc.humedad_media_anual, hc.humedad_media_q1, hc.humedad_media_q2, hc.humedad_media_q3, hc.humedad_media_q4,
    
    -- Litoralidad y Accesibilidad Vial (OpenRouteService y PostGIS)
    COALESCE(acc.dist_costa_km, h_topo.h3_dist_costa_km) AS dist_costa_km,
    acc.tiempo_aeropuerto_min,
    acc.aeropuerto_mas_cercano,
    acc.tiempo_tfs_min,
    acc.tiempo_tfn_min,
    acc.tiempo_capital_min,
    acc.tiempo_extremo_sur_min,
    acc.tiempo_extremo_norte_min,
    acc.tiempo_teide_min,
    acc.tiempo_la_laguna_min,
    acc.tiempo_candelaria_min,
    acc.tiempo_los_gigantes_min,
    acc.tiempo_el_medano_min,
    acc.tiempo_garachico_min,
    acc.tiempo_anaga_min,
    acc.tiempo_masca_min,
    acc.tiempo_vilaflor_min,
    acc.tiempo_la_orotava_min,
    acc.tiempo_guimar_min,
    acc.tiempo_buenavista_min,
    acc.tiempo_arico_min,
    acc.dist_hospital_km,
    acc.dist_parada_cercana_m,
    acc.n_paradas_bus_200m,
    acc.n_paradas_bus_500m,
    acc.n_paradas_bus_1000m,
    
    -- Restricciones Normativas y Zonas Turísticas
    COALESCE(enp.pct_area_enp, 0) AS pct_area_enp,
    enp.nombre_enp,
    COALESCE(zt.pct_area_zona_turistica, 0) AS pct_area_zona_turistica,
    zt.nombre_zona_turistica,
    
    h.geometry

FROM h3 h
LEFT JOIN municipios mun ON h.h3_index = mun.h3_index
LEFT JOIN alojamiento aloj ON h.h3_index = aloj.h3_index
LEFT JOIN booking b ON h.h3_index = b.h3_index
LEFT JOIN tripadvisor t ON h.h3_index = t.h3_index
LEFT JOIN pois p ON h.h3_index = p.h3_index
LEFT JOIN paradas_bus pb ON h.h3_index = pb.h3_index
LEFT JOIN satelite_mdt sm ON h.h3_index = sm.h3_index
LEFT JOIN h3_con_topografia h_topo ON h.h3_index = h_topo.h3_index
LEFT JOIN h3_clima hc ON h.h3_index = hc.h3_index
LEFT JOIN enp ON h.h3_index = enp.h3_index
LEFT JOIN zonas_turisticas zt ON h.h3_index = zt.h3_index
LEFT JOIN accesibilidad acc ON h.h3_index = acc.h3_index