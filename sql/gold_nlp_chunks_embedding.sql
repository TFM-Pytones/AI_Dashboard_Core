-- Fase 2 del RAG (ver plan_rag.md) -- Anade la columna de embeddings a
-- gold.nlp_chunks, una vez pgvector esta disponible.
--
-- Va en un archivo aparte de gold_nlp_chunks_schema.sql a proposito: la Fase 1
-- se diseño para poder ejecutarse antes de que VECTOR estuviera en la
-- allowlist de Azure, asi que la tabla se crea sin esta columna y se amplia
-- aqui.
--
-- 768 dimensiones = las que produce paraphrase-multilingual-mpnet-base-v2, el
-- mismo modelo de embeddings que ya usa BERTopic en analytics/topics/. Usar el
-- mismo da coherencia metodologica y evita mantener dos espacios vectoriales
-- distintos sobre el mismo corpus.
--
-- El indice HNSW NO se crea aqui: construirlo sobre una tabla vacia y luego
-- insertar es mucho mas lento que insertar primero e indexar despues. Lo crea
-- analytics/rag/import_embeddings.py al terminar la carga.

CREATE EXTENSION IF NOT EXISTS vector;

ALTER TABLE gold.nlp_chunks
    ADD COLUMN IF NOT EXISTS embedding vector(768);
