-- Issue #17 — Inferencia de Sentimiento por Lotes
-- Tabla generica de resultados de sentimiento, reutilizable para cualquier fuente de texto
-- (YouTube ahora; TripAdvisor/Booking #12 y Reddit #14 mas adelante).

CREATE SCHEMA IF NOT EXISTS processed_data;

CREATE TABLE IF NOT EXISTS processed_data.sentiment_results (
    id              SERIAL PRIMARY KEY,
    source          TEXT NOT NULL,        -- ej. 'youtube_comment', 'tripadvisor_review', 'reddit_comment'
    source_id       TEXT NOT NULL,        -- id original en su tabla raw_data (ej. comment_id)
    text            TEXT NOT NULL,        -- texto ya limpiado, el que se le paso al modelo
    label           TEXT NOT NULL,        -- 'positive' | 'neutral' | 'negative'
    score           REAL NOT NULL,
    model_name      TEXT NOT NULL,
    processed_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source, source_id)
);

CREATE INDEX IF NOT EXISTS idx_sentiment_results_source ON processed_data.sentiment_results(source);
CREATE INDEX IF NOT EXISTS idx_sentiment_results_label ON processed_data.sentiment_results(label);
