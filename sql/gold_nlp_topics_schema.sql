-- Issue #19 — Modelado de Topicos (BERTopic)
-- Una fila por comentario con el topico asignado. topic_id = -1 es la
-- convencion de BERTopic para "outlier" (no encaja en ningun topico).

CREATE SCHEMA IF NOT EXISTS gold;

CREATE TABLE IF NOT EXISTS gold.nlp_topics (
    id             SERIAL PRIMARY KEY,
    source         TEXT NOT NULL,
    source_id      TEXT NOT NULL,
    text           TEXT NOT NULL,
    topic_id       INTEGER NOT NULL,
    topic_label    TEXT,
    topic_size     INTEGER,
    probability    REAL,
    model_name     TEXT NOT NULL,
    processed_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source, source_id)
);

CREATE INDEX IF NOT EXISTS idx_gold_nlp_topics_source ON gold.nlp_topics(source);
CREATE INDEX IF NOT EXISTS idx_gold_nlp_topics_topic_id ON gold.nlp_topics(topic_id);
