-- Subtarea 3.2 -- Informe Narrativo Global (LLM sobre los topicos de BERTopic).
-- Una fila por generacion (se acumulan versiones, no se sobrescribe -- permite comparar
-- informes de distintas fechas segun evoluciona el corpus).
-- ambito distingue sobre que modelo de topicos habla el informe:
--   'general'     -> Modelo A (YouTube + LosViajeros sin ubicacion), analytics/llm/report_generator.py
--   'alojamiento' -> Modelo B (Booking + TripAdvisor + LosViajeros georreferenciado), analytics/llm/report_generator_alojamiento.py

CREATE SCHEMA IF NOT EXISTS gold;

CREATE TABLE IF NOT EXISTS gold.nlp_informe_global (
    id              SERIAL PRIMARY KEY,
    informe         TEXT NOT NULL,
    modelo_llm      TEXT NOT NULL,
    n_comentarios   INTEGER NOT NULL,
    n_topicos       INTEGER NOT NULL,
    generado_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE gold.nlp_informe_global ADD COLUMN IF NOT EXISTS ambito TEXT NOT NULL DEFAULT 'general';
