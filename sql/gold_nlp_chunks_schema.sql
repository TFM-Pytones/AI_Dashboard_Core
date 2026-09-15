-- Fase 1 del RAG (ver plan_rag.md) -- Corpus fragmentado y enriquecido con
-- metadatos para recuperacion.
--
-- Una fila por fragmento de texto. Los documentos de hasta 1.000 caracteres
-- (el 95,5% del corpus) entran enteros como chunk_index = 0; solo se trocean
-- los largos, casi todos de LosViajeros.
--
-- La columna `embedding` NO se crea aqui a proposito: la extension pgvector
-- todavia no esta en la allowlist de Azure (azure.extensions solo tiene
-- POSTGIS). Se anade en la Fase 2 con gold_nlp_chunks_embedding.sql, de forma
-- que la Fase 1 se puede ejecutar sin esperar a ese desbloqueo.

CREATE SCHEMA IF NOT EXISTS gold;

CREATE TABLE IF NOT EXISTS gold.nlp_chunks (
    chunk_id        SERIAL PRIMARY KEY,
    source          TEXT NOT NULL,     -- booking_review | tripadvisor_review | losviajeros_message | youtube_comment
    source_id       TEXT NOT NULL,     -- enlaza con gold.nlp_topics
    chunk_index     INTEGER NOT NULL,  -- 0 si el documento no se troceo
    text            TEXT NOT NULL,

    -- Metadatos de filtrado previo a la busqueda vectorial:
    topic_id        INTEGER,           -- de gold.nlp_topics (BERTopic)
    topic_label     TEXT,
    municipio       TEXT,              -- Booking/TripAdvisor: resuelto; LosViajeros: solo si place_type='municipio'
    zona            TEXT,              -- solo LosViajeros con place_type='zona' (ej. 'Parque Nacional del Teide')
    h3_index        TEXT,              -- solo fuentes con coordenadas reales (Booking, TripAdvisor)
    fecha           DATE,              -- Booking: review_date; TripAdvisor: fecha_publicacion; resto NULL
    pais_resenante  TEXT,              -- solo Booking
    rating          REAL,              -- Booking y TripAdvisor

    processed_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source, source_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_nlp_chunks_municipio ON gold.nlp_chunks(municipio);
CREATE INDEX IF NOT EXISTS idx_nlp_chunks_zona      ON gold.nlp_chunks(zona);
CREATE INDEX IF NOT EXISTS idx_nlp_chunks_h3        ON gold.nlp_chunks(h3_index);
CREATE INDEX IF NOT EXISTS idx_nlp_chunks_topic     ON gold.nlp_chunks(topic_id);
CREATE INDEX IF NOT EXISTS idx_nlp_chunks_fecha     ON gold.nlp_chunks(fecha);
CREATE INDEX IF NOT EXISTS idx_nlp_chunks_source    ON gold.nlp_chunks(source);
