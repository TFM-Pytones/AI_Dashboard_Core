{{ config(
    materialized='table',
    tags=['gold', 'nlp', 'bloque3'],
    indexes=[
      {'columns': ['h3_index'], 'unique': True}
    ]
) }}

/*
  Modelo Gold: gold_topicos_h3 (ver plan_rag.md, Fase 1.b)

  Agrega por hexagono H3 los topicos de BERTopic, para poder pintarlos en el
  mapa del dashboard (Bloque 8). gold.nlp_topics por si sola no sirve: es una
  fila por opinion y no tiene h3_index. La georreferenciacion la resuelve
  gold.nlp_chunks (analytics/rag/build_chunks.py).

  Solo entran Booking y TripAdvisor: son las unicas fuentes con coordenadas
  reales. LosViajeros solo tiene nombre de lugar (gold.geo_mentions), asi que
  vive en gold_topicos_municipio -- repartir un mensaje que menciona "Adeje"
  entre los ~100 hexagonos de Adeje fabricaria una precision que el dato no
  tiene. YouTube no tiene ubicacion por diseño.

  OJO al interpretar `topico_principal` en hexagonos con pocas opiniones: con
  3 o 4 reseñas el tema dominante es ruido. El dashboard deberia exigir un
  minimo de n_opiniones antes de mostrarlo; por eso la columna se expone en vez
  de filtrarse aqui (cada consumidor elige su umbral).
*/

WITH documentos AS (
    -- DISTINCT porque nlp_chunks tiene varias filas por documento largo; todos
    -- los fragmentos de un documento comparten topico y ubicacion.
    SELECT DISTINCT source, source_id, topic_id, topic_label, h3_index
    FROM {{ source('gold_nlp', 'nlp_chunks') }}
    WHERE h3_index IS NOT NULL
      AND topic_id <> -1          -- -1 = outlier de BERTopic, sin tema asignable
),

conteo AS (
    SELECT h3_index, topic_id, topic_label, COUNT(*) AS n
    FROM documentos
    GROUP BY h3_index, topic_id, topic_label
),

ranking AS (
    SELECT *,
           ROW_NUMBER() OVER (PARTITION BY h3_index ORDER BY n DESC, topic_id) AS rn
    FROM conteo
)

SELECT
    h3_index,
    SUM(n)                                          AS n_opiniones,
    COUNT(*)                                        AS n_topicos_distintos,
    MAX(topic_id)    FILTER (WHERE rn = 1)          AS topic_id_principal,
    MAX(topic_label) FILTER (WHERE rn = 1)          AS topico_principal,
    MAX(n)           FILTER (WHERE rn = 1)          AS n_opiniones_principal,
    -- Para el panel de detalle al hacer clic en un hexagono (Subtarea 8.4).
    jsonb_agg(
        jsonb_build_object('topic_id', topic_id, 'label', topic_label, 'n', n)
        ORDER BY rn
    ) FILTER (WHERE rn <= 3)                        AS topicos_top3
FROM ranking
GROUP BY h3_index
