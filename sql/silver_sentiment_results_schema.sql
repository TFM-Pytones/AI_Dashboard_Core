-- Version Azure (esquema silver) de sentiment_results_schema.sql.
-- Tabla generica de resultados de sentimiento, reutilizable para cualquier fuente de texto.

CREATE SCHEMA IF NOT EXISTS silver;

CREATE TABLE IF NOT EXISTS silver.sentiment_results (
    id              SERIAL PRIMARY KEY,
    source          TEXT NOT NULL,
    source_id       TEXT NOT NULL,
    text            TEXT NOT NULL,
    label           TEXT NOT NULL,
    score           REAL NOT NULL,
    model_name      TEXT NOT NULL,
    processed_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_relevant     BOOLEAN NOT NULL DEFAULT true,
    relevance_score REAL,
    UNIQUE (source, source_id)
);

CREATE INDEX IF NOT EXISTS idx_silver_sentiment_results_source ON silver.sentiment_results(source);
CREATE INDEX IF NOT EXISTS idx_silver_sentiment_results_label ON silver.sentiment_results(label);
CREATE INDEX IF NOT EXISTS idx_silver_sentiment_results_is_relevant ON silver.sentiment_results(is_relevant);
