-- ============================================================
-- Tarea #68 — Cruce NLP → Hexágono H3
-- Une los resultados de sentimiento (2.1) y aspectos (2.2) con
-- la geometría de establecimientos, agregado por hexágono de la
-- malla H3 (silver.silver_h3_grid).
--
-- Corregido contra los nombres reales de las tablas del proyecto
-- (el SQL original del ticket #68 usaba nombres genéricos que no
-- existen: silver.booking_reviews, silver.h3_grid, s.plataforma...).
--
-- Validado: LIMIT 20 y conjunto completo (~2.500 hexágonos),
-- resultados coherentes en ambos casos (ver notas al final).
-- ============================================================

SELECT
    h.h3_index,
    ROUND(AVG(s.score)::numeric, 2)                                     AS sentimiento_medio,
    COUNT(DISTINCT s.resena_id)                                         AS n_resenas,
    COUNT(DISTINCT s.resena_id) FILTER (WHERE s.fuente = 'booking')     AS n_resenas_booking,
    COUNT(DISTINCT s.resena_id) FILTER (WHERE s.fuente = 'tripadvisor') AS n_resenas_tripadvisor,
    MODE() WITHIN GROUP (ORDER BY a.aspecto_normalizado)                AS queja_principal
FROM silver.silver_h3_grid h
LEFT JOIN silver.silver_booking_establishments e_b
    ON ST_Contains(h.geometry, ST_SetSRID(ST_MakePoint(e_b.longitude, e_b.latitude), 4326))
LEFT JOIN silver.tripadvisor_ubicaciones e_t
    ON ST_Contains(h.geometry, ST_Transform(e_t.geometry, 4326))
LEFT JOIN gold.nlp_sentimiento_resenas s
    ON s.hotel_id = e_b.establishment_id OR s.hotel_id = e_t.location_id::text
LEFT JOIN gold.nlp_aspectos_resenas a ON a.resena_id = s.resena_id
GROUP BY h.h3_index;

-- ============================================================
-- Notas
-- ============================================================
-- 1. COUNT(DISTINCT s.resena_id) es imprescindible: sin el DISTINCT,
--    al unir con gold.nlp_aspectos_resenas (varias filas por reseña,
--    una por aspecto detectado), cada reseña se contaría una vez por
--    cada aspecto que tenga, inflando n_resenas artificialmente.
--
-- 2. queja_principal usa aspecto_normalizado, no aspecto en bruto --
--    si no, "location"/"ubicación"/"posizione" se cuentan como
--    conceptos distintos al calcular la moda (ver tarea 2.2).
--
-- 3. Limitación conocida y aceptada: en hexágonos con pocas reseñas,
--    la moda puede caer en un término de la cola larga sin normalizar
--    (ej. "el personal del hotel", "budín de chocolate"), porque solo
--    se normalizaron los ~135-150 aspectos más frecuentes del total
--    de ~11.000 detectados por PyABSA. No es un fallo del JOIN.
--
-- 4. silver.silver_booking_establishments no tiene columna de
--    geometría -- se construye al vuelo con ST_MakePoint a partir de
--    latitude/longitude (EPSG:4326, mismo sistema que la malla H3).
--
-- 5. Esta consulta produce el resultado en el momento (SELECT puro),
--    no crea ninguna tabla. El destino final (gold.h3_master) lo
--    gestiona Roberto -- no se ha escrito nada ahí desde este script.
-- ============================================================
