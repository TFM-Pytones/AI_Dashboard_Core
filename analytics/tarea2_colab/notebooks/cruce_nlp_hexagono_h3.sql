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
-- ADAPTACION A COLAB (ver analytics/tarea2_colab/docs/README.md):
-- copia corregida de analytics/tarea2/cruce_nlp_hexagono_h3.sql.
-- El original de Guille queda intacto -- este archivo corrige un
-- bug encontrado en el diagnostico de ese original: la query
-- referenciaba `a.aspecto_normalizado`, una columna que no existe
-- en ningun CREATE TABLE real (ni en gold.nlp_aspectos_resenas, que
-- solo tiene `aspecto` en bruto). Lo que sí existe es
-- `gold.aspecto_traducciones.aspecto_traducido` (tabla de mapeo
-- creada por traducir_aspectos.ipynb), a la que faltaba el JOIN.
-- Se agrego ese JOIN abajo -- ver nota 2.
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
    MODE() WITHIN GROUP (ORDER BY t.aspecto_traducido)                  AS queja_principal
FROM silver.silver_h3_grid h
LEFT JOIN silver.silver_booking_establishments e_b
    ON ST_Contains(h.geometry, ST_SetSRID(ST_MakePoint(e_b.longitude, e_b.latitude), 4326))
LEFT JOIN silver.tripadvisor_ubicaciones e_t
    ON ST_Contains(h.geometry, ST_Transform(e_t.geometry, 4326))
LEFT JOIN gold.nlp_sentimiento_resenas s
    ON s.hotel_id = e_b.establishment_id OR s.hotel_id = e_t.location_id::text
LEFT JOIN gold.nlp_aspectos_resenas a ON a.resena_id = s.resena_id
LEFT JOIN gold.aspecto_traducciones t ON t.aspecto_original = a.aspecto
GROUP BY h.h3_index;

-- ============================================================
-- Notas
-- ============================================================
-- 1. COUNT(DISTINCT s.resena_id) es imprescindible: sin el DISTINCT,
--    al unir con gold.nlp_aspectos_resenas (varias filas por reseña,
--    una por aspecto detectado), cada reseña se contaría una vez por
--    cada aspecto que tenga, inflando n_resenas artificialmente.
--
-- 2. [CORREGIDO -- adaptacion Colab] queja_principal usa
--    t.aspecto_traducido (tabla gold.aspecto_traducciones, creada
--    por traducir_aspectos.ipynb), no a.aspecto en bruto -- si no,
--    "location"/"ubicación"/"posizione" se cuentan como conceptos
--    distintos al calcular la moda. La version original de este
--    archivo (analytics/tarea2/cruce_nlp_hexagono_h3.sql) referenciaba
--    `a.aspecto_normalizado`, una columna que no existe en ningun
--    CREATE TABLE real -- esa query no podia ejecutarse tal cual
--    estaba. El JOIN contra gold.aspecto_traducciones que faltaba se
--    agrego arriba.
--
-- 3. Consecuencia de usar aspecto_traducido via LEFT JOIN: un
--    aspecto que todavia no fue procesado por traducir_aspectos.ipynb
--    (o que no llego a esa tabla por algun motivo) aparece como NULL
--    en t.aspecto_traducido para esa fila, en vez de con su valor en
--    bruto. En hexágonos con pocas reseñas esto puede hacer que
--    queja_principal salga NULL o caiga en un término de la cola
--    larga sin traducir. No es un fallo del JOIN -- es el
--    comportamiento esperado de una tabla de traduccion que se llena
--    de forma incremental (ver traducir_aspectos.ipynb). Correr ese
--    notebook hasta agotar `df_pendientes` antes de confiar en esta
--    query para el reporte final.
--
-- 4. silver.silver_booking_establishments no tiene columna de
--    geometría -- se construye al vuelo con ST_MakePoint a partir de
--    latitude/longitude (EPSG:4326, mismo sistema que la malla H3).
--
-- 5. Esta consulta produce el resultado en el momento (SELECT puro),
--    no crea ninguna tabla. El destino final (gold.h3_master) lo
--    gestiona Roberto -- no se ha escrito nada ahí desde este script.
-- ============================================================
