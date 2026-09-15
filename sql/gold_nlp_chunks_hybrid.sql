-- Fase 4 del RAG (ver plan_rag.md) -- Mitad lexica de la busqueda hibrida.
--
-- La busqueda vectorial difumina los nombres propios: preguntar por "Siam
-- Park" o por el nombre de un hotel concreto devuelve fragmentos
-- semanticamente parecidos pero que no mencionan ese sitio. El indice de texto
-- completo los encuentra literalmente, y los dos rankings se fusionan por
-- Reciprocal Rank Fusion en analytics/rag/retriever.py.
--
-- Configuracion 'simple' y no 'spanish': el corpus es multilingue (ingles,
-- aleman, italiano, neerlandes, polaco...) y 'spanish' aplicaria stemming y
-- stopwords españolas a todo, degradando las demas lenguas. 'simple' se limita
-- a partir en palabras y pasar a minusculas, que es lo que interesa aqui.
--
-- pg_trgm no esta en la allowlist de Azure, pero tsvector es nativo de
-- PostgreSQL y no necesita extension.

ALTER TABLE gold.nlp_chunks
    ADD COLUMN IF NOT EXISTS tsv tsvector
    GENERATED ALWAYS AS (to_tsvector('simple', text)) STORED;

CREATE INDEX IF NOT EXISTS idx_nlp_chunks_tsv
    ON gold.nlp_chunks USING GIN (tsv);
