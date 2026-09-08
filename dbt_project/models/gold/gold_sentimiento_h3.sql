{{ config(
    materialized='table',
    tags=['gold', 'nlp', 'bloque3'],
    indexes=[
      {'columns': ['h3_index'], 'unique': True}
    ]
) }}

/*
  Modelo Gold: gold_sentimiento_h3 (Issue #20 -- Georreferenciacion de
  Topicos y Sentimientos)

  Agrega por hexagono H3 el sentimiento (Tarea 2.1, BERT multilingue) y la
  queja/aspecto mas frecuente (Tarea 2.2, PyABSA + normalizacion) de las
  reseñas de Booking + TripAdvisor.

  gold.nlp_sentimiento_resenas ya trae `h3_index` resuelto en el momento del
  analisis -- el join hotel -> hexagono se hizo una unica vez dentro del
  notebook 2.1 (merge con df_hotel_h3) -- asi que aqui NO hace falta repetir
  el cruce espacial contra las tablas de establecimientos: basta con agregar.

  (analytics/tarea2/cruce_nlp_hexagono_h3.sql, tarea #68, intentaba
  reconstruir ese cruce espacial desde cero y usaba columnas que no existen
  en el esquema real -- e_b.longitude/latitude, silver.tripadvisor_ubicaciones
  sin el prefijo silver_, a.aspecto_normalizado como si ya viniera en
  nlp_aspectos_resenas. Este modelo lee directamente de las tablas reales que
  escriben los notebooks, incluyendo el mapeo de gold.aspecto_traducciones
  para la normalizacion de aspectos.)
*/

WITH sentimiento AS (
    SELECT
        h3_index,
        resena_id,
        fuente,
        score
    FROM {{ source('gold_nlp', 'nlp_sentimiento_resenas') }}
    WHERE h3_index IS NOT NULL
),

-- Issue tarea 2.2 normaliza los aspectos en una tabla de mapeo aparte
-- (gold.aspecto_traducciones) en vez de una columna en nlp_aspectos_resenas;
-- si un aspecto todavia no se ha traducido, usamos el original como fallback.
aspectos_normalizados AS (
    SELECT
        a.resena_id,
        COALESCE(t.aspecto_traducido, a.aspecto) AS aspecto_normalizado
    FROM {{ source('gold_nlp', 'nlp_aspectos_resenas') }} a
    LEFT JOIN {{ source('gold_nlp', 'aspecto_traducciones') }} t
        ON t.aspecto_original = a.aspecto
)

SELECT
    s.h3_index,
    ROUND(AVG(s.score)::numeric, 2)                                     AS sentimiento_medio,
    COUNT(DISTINCT s.resena_id)                                         AS n_resenas,
    COUNT(DISTINCT s.resena_id) FILTER (WHERE s.fuente = 'booking')     AS n_resenas_booking,
    COUNT(DISTINCT s.resena_id) FILTER (WHERE s.fuente = 'tripadvisor') AS n_resenas_tripadvisor,
    -- COUNT(DISTINCT ...) es imprescindible: sin el DISTINCT, al unir con
    -- aspectos (varias filas por reseña, una por aspecto detectado), cada
    -- reseña se contaria una vez por cada aspecto, inflando n_resenas.
    MODE() WITHIN GROUP (ORDER BY asp.aspecto_normalizado)              AS queja_principal
FROM sentimiento s
LEFT JOIN aspectos_normalizados asp ON asp.resena_id = s.resena_id
GROUP BY s.h3_index
