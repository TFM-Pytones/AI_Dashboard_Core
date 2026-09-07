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
  Modelo Gold: gold_h3_master (BLOQUE 1)
  Tabla maestra que unifica todos los indicadores del proyecto a nivel hexagonal (H3 Res 8).
  Incluye interpolación meteorológica avanzada IDW (K=3) + Corrección de Gradiente Térmico.
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
    SELECT
        h.h3_index,
        m.cod_municipio,
        m.nombre_municipio AS municipio
    FROM h3 h
    LEFT JOIN {{ ref('silver_limites_municipales') }} m
        ON ST_Intersects(h.geometry, m.geometry)
        AND ST_Area(ST_Intersection(h.geometry, m.geometry)) = 
            (SELECT MAX(ST_Area(ST_Intersection(h.geometry, m2.geometry)))
             FROM {{ ref('silver_limites_municipales') }} m2
             WHERE ST_Intersects(h.geometry, m2.geometry))
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
        COUNT(r.review_id) FILTER (WHERE NOT r.periodo_covid) AS n_reviews_validas_booking
    FROM h3 h
    LEFT JOIN {{ ref('silver_booking_establishments') }} e ON ST_Contains(h.geometry, e.geometry)
    LEFT JOIN {{ ref('silver_booking_reviews') }} r ON r.establishment_id = e.establishment_id
    GROUP BY h.h3_index
),

tripadvisor AS (
    SELECT
        h.h3_index,
        COUNT(DISTINCT e.location_id) AS n_establecimientos_tripadvisor,
        ROUND(AVG(r.rating)::numeric, 2) AS rating_tripadvisor_medio
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
        -- MDT Completo (Altitud, Pendiente, Orientacion, Relieve)
        m.elevation_mean, m.elevation_min, m.elevation_max,
        m.slope_mean, m.slope_min, m.slope_max,
        m.aspect_mean, m.aspect_min, m.aspect_max,
        m.hillshade_mean, m.hillshade_min, m.hillshade_max,
        -- Indices de Satelite
        s.ndvi_medio,
        s.ndbi_medio,
        s.viirs_medio
    FROM h3 h
    LEFT JOIN {{ source('bronze', 'bronze_mdt_stats') }} m ON h.h3_index = m.h3_index
    LEFT JOIN (
        SELECT h3_index, AVG(ndvi_mean) AS ndvi_medio, AVG(ndbi_mean) AS ndbi_medio, AVG(viirs_mean) AS viirs_medio
        FROM {{ source('bronze', 'bronze_satelite_stats') }}
        WHERE "year" NOT BETWEEN 2020 AND 2021
        GROUP BY h3_index
    ) s ON h.h3_index = s.h3_index
),

-- Subtarea 1.7: Variables Climáticas Avanzadas (IDW + Gradiente)
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
        AVG(valor_limpio) FILTER (WHERE variable_nombre ILIKE '%Radiaci%') AS insolacion_media,
        -- Panza de burro (Mediodía: 12-16h)
        AVG(valor_limpio) FILTER (WHERE variable_nombre ILIKE '%Radiaci%' AND EXTRACT(HOUR FROM "timestamp") BETWEEN 12 AND 16) AS radiacion_mediodia
    FROM {{ ref('silver_clima_agrocabildo') }}
    GROUP BY id_estacion, date_trunc('day', "timestamp"), EXTRACT(QUARTER FROM "timestamp")
),
estaciones_clima AS (
    SELECT 
        id_estacion,
        
        -- INDICADORES ESG Y EXTREMOS
        COUNT(*) FILTER (WHERE temp_max >= 35 AND humedad_min <= 30 AND dir_viento_media BETWEEN 60 AND 200) AS dias_ola_calor_anual,
        AVG(temp_max - temp_min) AS amplitud_termica_media,
        AVG(radiacion_mediodia) FILTER (WHERE trimestre = 3) AS radiacion_mediodia_q3,
        AVG(radiacion_mediodia) FILTER (WHERE trimestre = 1) AS radiacion_mediodia_q1,

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
        AVG(humedad_media) FILTER (WHERE trimestre = 4) AS humedad_media_q4,
        
        AVG(insolacion_media) AS insolacion_media_anual,
        AVG(insolacion_media) FILTER (WHERE trimestre = 1) AS insolacion_media_q1,
        AVG(insolacion_media) FILTER (WHERE trimestre = 2) AS insolacion_media_q2,
        AVG(insolacion_media) FILTER (WHERE trimestre = 3) AS insolacion_media_q3,
        AVG(insolacion_media) FILTER (WHERE trimestre = 4) AS insolacion_media_q4
        
    FROM clima_diario
    GROUP BY id_estacion
),
estaciones_con_altitud AS (
    SELECT
        c.*,
        e.altitud_m AS station_altitud,
        e.geometry
    FROM estaciones_clima c
    JOIN {{ ref('silver_estaciones_agrocabildo') }} e ON c.id_estacion = e.id_estacion
),
h3_con_altitud AS (
    SELECT h.h3_index, h.geometry, m.elevation_mean AS h3_altitud
    FROM h3 h
    LEFT JOIN {{ source('bronze', 'bronze_mdt_stats') }} m ON h.h3_index = m.h3_index
),
h3_vecinos_clima AS (
    -- Para cada H3, buscamos las 3 estaciones más cercanas y calculamos distancia y peso (IDW)
    SELECT
        h.h3_index,
        h.h3_altitud,
        est.*,
        -- Peso: 1 / distancia^2 (si distancia es 0 o muy pequeña, se capea a 1)
        1.0 / POWER(GREATEST(ST_Distance(h.geometry::geography, est.geometry::geography), 1), 2) AS peso
    FROM h3_con_altitud h
    CROSS JOIN LATERAL (
        SELECT *
        FROM estaciones_con_altitud e
        ORDER BY h.geometry <-> e.geometry
        LIMIT 3
    ) est
),
h3_clima AS (
    -- Hacemos la agregación final (media ponderada IDW + Ajuste Gradiente Térmico para temperaturas)
    SELECT
        h3_index,
        
        -- INDICADORES ESG Y EXTREMOS (IDW Puro)
        SUM(dias_ola_calor_anual * peso) / NULLIF(SUM(peso), 0) AS dias_ola_calor_anual,
        SUM(radiacion_mediodia_q3 * peso) / NULLIF(SUM(peso), 0) AS radiacion_mediodia_q3,
        SUM(radiacion_mediodia_q1 * peso) / NULLIF(SUM(peso), 0) AS radiacion_mediodia_q1,

        -- TEMPERATURA Y AMPLITUD (IDW + Gradiente Térmico de -0.0065 ºC por metro)
        -- Formula: Temp_H3 = Temp_Estacion + ((Altitud_Estacion - Altitud_H3) * 0.0065)
        SUM((temp_media_anual + ((COALESCE(station_altitud, 0) - COALESCE(h3_altitud, 0)) * 0.0065)) * peso) / NULLIF(SUM(peso), 0) AS temp_media_anual,
        SUM((temp_media_q1 + ((COALESCE(station_altitud, 0) - COALESCE(h3_altitud, 0)) * 0.0065)) * peso) / NULLIF(SUM(peso), 0) AS temp_media_q1,
        SUM((temp_media_q2 + ((COALESCE(station_altitud, 0) - COALESCE(h3_altitud, 0)) * 0.0065)) * peso) / NULLIF(SUM(peso), 0) AS temp_media_q2,
        SUM((temp_media_q3 + ((COALESCE(station_altitud, 0) - COALESCE(h3_altitud, 0)) * 0.0065)) * peso) / NULLIF(SUM(peso), 0) AS temp_media_q3,
        SUM((temp_media_q4 + ((COALESCE(station_altitud, 0) - COALESCE(h3_altitud, 0)) * 0.0065)) * peso) / NULLIF(SUM(peso), 0) AS temp_media_q4,
        SUM(amplitud_termica_media * peso) / NULLIF(SUM(peso), 0) AS amplitud_termica_media,

        -- RESTO DE VARIABLES CLIMATICAS (IDW Puro)
        SUM(lluvia_mm_anual * peso) / NULLIF(SUM(peso), 0) AS lluvia_mm_anual,
        SUM(lluvia_mm_q1 * peso) / NULLIF(SUM(peso), 0) AS lluvia_mm_q1,
        SUM(lluvia_mm_q2 * peso) / NULLIF(SUM(peso), 0) AS lluvia_mm_q2,
        SUM(lluvia_mm_q3 * peso) / NULLIF(SUM(peso), 0) AS lluvia_mm_q3,
        SUM(lluvia_mm_q4 * peso) / NULLIF(SUM(peso), 0) AS lluvia_mm_q4,

        SUM(vel_viento_media_anual * peso) / NULLIF(SUM(peso), 0) AS vel_viento_media_anual,
        SUM(vel_viento_media_q1 * peso) / NULLIF(SUM(peso), 0) AS vel_viento_media_q1,
        SUM(vel_viento_media_q2 * peso) / NULLIF(SUM(peso), 0) AS vel_viento_media_q2,
        SUM(vel_viento_media_q3 * peso) / NULLIF(SUM(peso), 0) AS vel_viento_media_q3,
        SUM(vel_viento_media_q4 * peso) / NULLIF(SUM(peso), 0) AS vel_viento_media_q4,

        SUM(humedad_media_anual * peso) / NULLIF(SUM(peso), 0) AS humedad_media_anual,
        SUM(humedad_media_q1 * peso) / NULLIF(SUM(peso), 0) AS humedad_media_q1,
        SUM(humedad_media_q2 * peso) / NULLIF(SUM(peso), 0) AS humedad_media_q2,
        SUM(humedad_media_q3 * peso) / NULLIF(SUM(peso), 0) AS humedad_media_q3,
        SUM(humedad_media_q4 * peso) / NULLIF(SUM(peso), 0) AS humedad_media_q4,

        SUM(insolacion_media_anual * peso) / NULLIF(SUM(peso), 0) AS insolacion_media_anual,
        SUM(insolacion_media_q1 * peso) / NULLIF(SUM(peso), 0) AS insolacion_media_q1,
        SUM(insolacion_media_q2 * peso) / NULLIF(SUM(peso), 0) AS insolacion_media_q2,
        SUM(insolacion_media_q3 * peso) / NULLIF(SUM(peso), 0) AS insolacion_media_q3,
        SUM(insolacion_media_q4 * peso) / NULLIF(SUM(peso), 0) AS insolacion_media_q4
    FROM h3_vecinos_clima
    GROUP BY h3_index
),

enp AS (
    SELECT
        h.h3_index,
        BOOL_OR(e.geometry IS NOT NULL) AS es_enp,
        ROUND((SUM(ST_Area(ST_Intersection(h.geometry, e.geometry))) / h.area_km2 / 1000000)::numeric, 4) AS pct_area_enp
    FROM h3 h
    LEFT JOIN {{ ref('silver_enp') }} e ON ST_Intersects(h.geometry, e.geometry)
    GROUP BY h.h3_index, h.area_km2
),

dinamismo AS (
    SELECT
        h.h3_index,
        'ES' AS mercado_principal_idioma,
        0.0 AS crecimiento_oferta_pct
    FROM h3 h
),

zonas_turisticas AS (
    SELECT
        h.h3_index,
        BOOL_OR(z.geometry IS NOT NULL) AS es_zona_turistica_oficial
    FROM h3 h
    LEFT JOIN {{ ref('silver_zonas_turisticas') }} z ON ST_Intersects(h.geometry, z.geometry)
    GROUP BY h.h3_index
),

costa AS (
    -- Extraemos el borde de la isla (línea de costa) uniendo todos los municipios
    SELECT ST_Boundary(ST_Union(geometry)) AS geometry
    FROM {{ ref('silver_limites_municipales') }}
)

SELECT
    h.h3_index,
    mun.cod_municipio,
    mun.municipio,
    h.area_km2,
    h.centroide_lon,
    h.centroide_lat,
    
    -- Alojamiento
    COALESCE(aloj.n_establecimientos_registro, 0) AS n_establecimientos_registro,
    COALESCE(aloj.n_plazas_registro, 0) AS n_plazas_registro,
    COALESCE(aloj.n_hoteles, 0) AS n_hoteles,
    COALESCE(aloj.n_vv, 0) AS n_vv,
    COALESCE(aloj.n_extrahoteleros, 0) AS n_extrahoteleros,
    
    -- Plataformas
    COALESCE(b.n_establecimientos_booking, 0) AS n_establecimientos_booking,
    b.rating_booking_medio,
    COALESCE(b.n_reviews_validas_booking, 0) AS n_reviews_booking,
    COALESCE(t.n_establecimientos_tripadvisor, 0) AS n_establecimientos_tripadvisor,
    t.rating_tripadvisor_medio,
    
    -- POIs
    COALESCE(p.n_pois_total, 0) AS n_pois_total,
    COALESCE(p.n_restaurantes, 0) AS n_restaurantes,
    COALESCE(p.n_cultura, 0) AS n_cultura,
    COALESCE(p.n_naturaleza, 0) AS n_naturaleza,
    COALESCE(p.n_pois_institucionales, 0) AS n_pois_institucionales,
    
    -- Transporte
    COALESCE(pb.n_paradas_bus, 0) AS n_paradas_bus,
    
    -- MDT y Topografía Avanzada
    sm.elevation_mean, sm.elevation_min, sm.elevation_max,
    sm.slope_mean, sm.slope_min, sm.slope_max,
    sm.aspect_mean, sm.aspect_min, sm.aspect_max,
    sm.hillshade_mean, sm.hillshade_min, sm.hillshade_max,
    
    -- Satélite (Copernicus)
    sm.ndvi_medio,
    sm.ndbi_medio,
    sm.viirs_medio,
    
    -- Clima (Agrocabildo) - ESG y Riesgos
    hc.dias_ola_calor_anual,
    hc.amplitud_termica_media,
    hc.radiacion_mediodia_q1,
    hc.radiacion_mediodia_q3,
    
    -- Clima (Agrocabildo) - Estacional
    hc.temp_media_anual, hc.temp_media_q1, hc.temp_media_q2, hc.temp_media_q3, hc.temp_media_q4,
    hc.lluvia_mm_anual, hc.lluvia_mm_q1, hc.lluvia_mm_q2, hc.lluvia_mm_q3, hc.lluvia_mm_q4,
    hc.vel_viento_media_anual, hc.vel_viento_media_q1, hc.vel_viento_media_q2, hc.vel_viento_media_q3, hc.vel_viento_media_q4,
    hc.humedad_media_anual, hc.humedad_media_q1, hc.humedad_media_q2, hc.humedad_media_q3, hc.humedad_media_q4,
    hc.insolacion_media_anual, hc.insolacion_media_q1, hc.insolacion_media_q2, hc.insolacion_media_q3, hc.insolacion_media_q4,
    
    -- Distancia Euclidiana a la Costa
    ROUND(ST_Distance(h.geometry::geography, costa.geometry::geography)::numeric, 2) AS distancia_costa_metros,
    
    -- Dinamismo y Mercado
    din.mercado_principal_idioma,
    din.crecimiento_oferta_pct,
    
    -- Restricciones y Clasificación
    COALESCE(enp.es_enp, FALSE) AS es_enp,
    COALESCE(enp.pct_area_enp, 0) AS pct_area_enp,
    COALESCE(zt.es_zona_turistica_oficial, FALSE) AS es_zona_turistica_oficial,
    
    h.geometry

FROM h3 h
LEFT JOIN municipios mun ON h.h3_index = mun.h3_index
LEFT JOIN alojamiento aloj ON h.h3_index = aloj.h3_index
LEFT JOIN booking b ON h.h3_index = b.h3_index
LEFT JOIN tripadvisor t ON h.h3_index = t.h3_index
LEFT JOIN pois p ON h.h3_index = p.h3_index
LEFT JOIN paradas_bus pb ON h.h3_index = pb.h3_index
LEFT JOIN satelite_mdt sm ON h.h3_index = sm.h3_index
LEFT JOIN h3_clima hc ON h.h3_index = hc.h3_index
LEFT JOIN enp ON h.h3_index = enp.h3_index
LEFT JOIN dinamismo din ON h.h3_index = din.h3_index
LEFT JOIN zonas_turisticas zt ON h.h3_index = zt.h3_index
CROSS JOIN costa
