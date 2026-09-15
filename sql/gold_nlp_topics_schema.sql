-- Issue #19 — Modelado de Topicos (BERTopic)
-- Una fila por comentario con el topico asignado.
--
-- Desde el reentrenamiento local (analytics/topics/entrenar_topicos.py):
--   topic_label    = nombre legible del tema en español, generado con LLM
--   topic_keywords = palabras mas representativas del tema (c-TF-IDF)
--   probability    = similitud coseno entre el documento y el centro de su tema
-- Con k-means todos los documentos tienen tema: topic_id = -1 (el "outlier"
-- de HDBSCAN de la version entrenada en Colab) ya no aparece.

CREATE SCHEMA IF NOT EXISTS gold;

CREATE TABLE IF NOT EXISTS gold.nlp_topics (
    id             SERIAL PRIMARY KEY,
    source         TEXT NOT NULL,
    source_id      TEXT NOT NULL,
    text           TEXT NOT NULL,
    topic_id       INTEGER NOT NULL,
    topic_label    TEXT,
    topic_keywords TEXT,
    topic_size     INTEGER,
    probability    REAL,
    model_name     TEXT NOT NULL,
    processed_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source, source_id)
);

-- Tablas creadas antes de que existiera la columna.
ALTER TABLE gold.nlp_topics ADD COLUMN IF NOT EXISTS topic_keywords TEXT;

CREATE INDEX IF NOT EXISTS idx_gold_nlp_topics_source ON gold.nlp_topics(source);
CREATE INDEX IF NOT EXISTS idx_gold_nlp_topics_topic_id ON gold.nlp_topics(topic_id);
