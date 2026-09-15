{{ config(
    materialized='table',
    tags=['gold', 'nlp', 'bloque3'],
    indexes=[
      {'columns': ['municipio'], 'unique': True}
    ]
) }}

/*
  Modelo Gold: gold_topicos_municipio (ver plan_rag.md, Fase 1.b)

  Igual que gold_topicos_h3 pero a nivel municipal, que es la granularidad
  real de LosViajeros: gold.geo_mentions detecta el nombre del lugar citado en
  el mensaje, no unas coordenadas. Al bajar a municipio entran las tres fuentes
  georreferenciadas en vez de solo las dos con coordenadas.

  El proyecto ya usa esta doble granularidad en otras tablas
  (gold_h3_master / gold_municipio_master).

  LIMITACION a documentar en la memoria: agregar por municipio mete ruido,
  porque un mensaje de foro puede mencionar un municipio de pasada aunque trate
  de otra cosa. Verificado con datos reales: entre los temas de Arona aparece
  "icod, icod vinos, garachico, teno", que viene de un mensaje sobre un
  itinerario que cita Arona sin ser su asunto principal. La columna `fuentes`
  permite ver cuanto de cada celda viene de foro frente a reseñas.
*/

WITH documentos AS (
    SELECT DISTINCT source, source_id, topic_id, topic_label, municipio
    FROM {{ source('gold_nlp', 'nlp_chunks') }}
    WHERE municipio IS NOT NULL
      AND topic_id <> -1
),

conteo AS (
    SELECT municipio, topic_id, topic_label, COUNT(*) AS n
    FROM documentos
    GROUP BY municipio, topic_id, topic_label
),

ranking AS (
    SELECT *,
           ROW_NUMBER() OVER (PARTITION BY municipio ORDER BY n DESC, topic_id) AS rn
    FROM conteo
),

-- Reparto por fuente: sirve para juzgar cuanta confianza dar a cada municipio
-- (no es lo mismo 500 reseñas de Booking que 4 mensajes de foro).
por_fuente AS (
    SELECT municipio,
           jsonb_object_agg(source, n_docs) AS fuentes
    FROM (
        SELECT municipio, source, COUNT(*) AS n_docs
        FROM documentos GROUP BY municipio, source
    ) f
    GROUP BY municipio
),

agregado AS (
    SELECT
        municipio,
        SUM(n)                                          AS n_opiniones,
        COUNT(*)                                        AS n_topicos_distintos,
        MAX(topic_id)    FILTER (WHERE rn = 1)          AS topic_id_principal,
        MAX(topic_label) FILTER (WHERE rn = 1)          AS topico_principal,
        MAX(n)           FILTER (WHERE rn = 1)          AS n_opiniones_principal,
        jsonb_agg(
            jsonb_build_object('topic_id', topic_id, 'label', topic_label, 'n', n)
            ORDER BY rn
        ) FILTER (WHERE rn <= 3)                        AS topicos_top3
    FROM ranking
    GROUP BY municipio
)

-- El join con por_fuente va DESPUES de agregar: ambas partes ya tienen una
-- fila por municipio, asi que no hace falta (ni existe) un MAX sobre jsonb.
SELECT
    a.municipio,
    a.n_opiniones,
    a.n_topicos_distintos,
    a.topic_id_principal,
    a.topico_principal,
    a.n_opiniones_principal,
    a.topicos_top3,
    f.fuentes
FROM agregado a
LEFT JOIN por_fuente f ON f.municipio = a.municipio
