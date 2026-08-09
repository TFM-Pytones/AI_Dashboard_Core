-- Issue #18 — Configuracion de Extraccion de Aspectos (pyabsa)
-- Un mismo comentario puede mencionar varios aspectos (ej. "playas geniales pero trafico
-- horrible" -> 2 filas), por eso no reutiliza sentiment_results (que es 1 fila por comentario).

CREATE SCHEMA IF NOT EXISTS processed_data;

CREATE TABLE IF NOT EXISTS processed_data.aspect_results (
    id              SERIAL PRIMARY KEY,
    source          TEXT NOT NULL,        -- ej. 'youtube_comment'
    source_id       TEXT NOT NULL,        -- id original en su tabla raw_data
    text            TEXT NOT NULL,        -- texto completo analizado
    aspect          TEXT NOT NULL,        -- ej. 'playas', 'trafico', 'precio'
    aspect_sentiment TEXT NOT NULL,       -- 'Positive' | 'Neutral' | 'Negative'
    confidence      REAL,
    model_name      TEXT NOT NULL,
    processed_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_aspect_results_source ON processed_data.aspect_results(source, source_id);
CREATE INDEX IF NOT EXISTS idx_aspect_results_aspect ON processed_data.aspect_results(aspect);
