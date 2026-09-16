-- Issue #18 — Extraccion de Aspectos por Lotes (PyABSA ATEPC)
-- Una fila por aspecto detectado, asi que un mismo comentario puede tener
-- varias filas o ninguna.
--
-- Este fichero faltaba en el repo (punto 14 de la revision de codigo): tanto
-- analytics/aspects/batch_inference.py como
-- migration/migrate_youtube_pipeline_to_azure.py lo leian y petaban al correr
-- en limpio. Se reconstruye a partir del INSERT de esos dos scripts y de la
-- tabla ya existente en Azure.
--
-- Sin UNIQUE(source, source_id) a proposito: al haber varias filas por
-- comentario, la deteccion de "ya procesado" se hace con NOT EXISTS sobre
-- source_id, no con una constraint.

CREATE SCHEMA IF NOT EXISTS silver;

CREATE TABLE IF NOT EXISTS silver.aspect_results (
    id               SERIAL PRIMARY KEY,
    source           TEXT NOT NULL,
    source_id        TEXT NOT NULL,
    text             TEXT NOT NULL,
    aspect           TEXT,
    aspect_sentiment TEXT,
    confidence       REAL,
    model_name       TEXT NOT NULL,
    processed_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_silver_aspect_results_source
    ON silver.aspect_results(source, source_id);
