-- Version Azure (esquema silver) de aspect_results_schema.sql.
-- Un mismo comentario puede mencionar varios aspectos, por eso no reutiliza
-- sentiment_results (que es 1 fila por comentario).

CREATE SCHEMA IF NOT EXISTS silver;

CREATE TABLE IF NOT EXISTS silver.aspect_results (
    id              SERIAL PRIMARY KEY,
    source          TEXT NOT NULL,
    source_id       TEXT NOT NULL,
    text            TEXT NOT NULL,
    aspect          TEXT NOT NULL,
    aspect_sentiment TEXT NOT NULL,
    confidence      REAL,
    model_name      TEXT NOT NULL,
    processed_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_silver_aspect_results_source ON silver.aspect_results(source, source_id);
CREATE INDEX IF NOT EXISTS idx_silver_aspect_results_aspect ON silver.aspect_results(aspect);
