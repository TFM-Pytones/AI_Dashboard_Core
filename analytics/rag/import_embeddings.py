"""Fase 2 del RAG (ver plan_rag.md) -- Carga en gold.nlp_chunks.embedding los
vectores calculados en Colab (embed_chunks_colab.ipynb) y construye el indice
HNSW.

Uso:
    python analytics/rag/import_embeddings.py ruta/a/embeddings.npz
"""

import os
import sys
from pathlib import Path

import numpy as np
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv(override=True)

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

DIMENSIONES = 768
PAGE_SIZE = 1000


def get_db_connection():
    return psycopg2.connect(
        user=os.getenv("AZURE_DB_USER"),
        password=os.getenv("AZURE_DB_PASSWORD"),
        host=os.getenv("AZURE_DB_HOST"),
        database=os.getenv("AZURE_DB_NAME"),
        port="5432",
        sslmode="require",
    )


def ensure_column(conn):
    schema_path = Path(__file__).resolve().parents[2] / "sql" / "gold_nlp_chunks_embedding.sql"
    with conn.cursor() as cur:
        cur.execute(schema_path.read_text(encoding="utf-8"))
    conn.commit()


def as_pgvector(fila: np.ndarray) -> str:
    """pgvector acepta el literal '[1,2,3]'. Formatearlo a mano evita depender
    del paquete `pgvector` solo para esto."""
    return "[" + ",".join(f"{v:.6f}" for v in fila) + "]"


def load_embeddings(conn, chunk_ids: np.ndarray, embeddings: np.ndarray):
    """Carga via tabla temporal + UPDATE ... FROM. Lanzar 88.000 UPDATE sueltos
    contra Azure tarda muchisimo mas por la latencia de ida y vuelta."""
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TEMP TABLE tmp_embeddings (
                chunk_id  INTEGER PRIMARY KEY,
                embedding vector(%s)
            ) ON COMMIT DROP
        """ % DIMENSIONES)

        psycopg2.extras.execute_batch(
            cur,
            "INSERT INTO tmp_embeddings (chunk_id, embedding) VALUES (%s, %s)",
            [(int(cid), as_pgvector(emb)) for cid, emb in zip(chunk_ids, embeddings)],
            page_size=PAGE_SIZE,
        )

        cur.execute("""
            UPDATE gold.nlp_chunks c
            SET embedding = t.embedding
            FROM tmp_embeddings t
            WHERE c.chunk_id = t.chunk_id
        """)
        actualizados = cur.rowcount
    conn.commit()
    return actualizados


def create_index(conn):
    """El indice se crea despues de cargar: construirlo sobre la tabla vacia e
    ir insertando es bastante mas lento."""
    with conn.cursor() as cur:
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_nlp_chunks_embedding
            ON gold.nlp_chunks USING hnsw (embedding vector_cosine_ops)
            WITH (m = 16, ef_construction = 64)
        """)
    conn.commit()


def main():
    if len(sys.argv) != 2:
        print("Uso: python analytics/rag/import_embeddings.py ruta/a/embeddings.npz")
        sys.exit(1)

    npz_path = Path(sys.argv[1])
    if not npz_path.exists():
        print(f"No existe: {npz_path}")
        sys.exit(1)

    datos = np.load(npz_path, allow_pickle=False)
    chunk_ids = datos["chunk_ids"]
    embeddings = datos["embeddings"].astype(np.float32)  # se guardaron en float16 para aligerar la descarga

    if embeddings.shape[0] != chunk_ids.shape[0]:
        print(f"Descuadre: {chunk_ids.shape[0]} ids frente a {embeddings.shape[0]} vectores.")
        sys.exit(1)
    if embeddings.shape[1] != DIMENSIONES:
        print(f"Se esperaban {DIMENSIONES} dimensiones y vienen {embeddings.shape[1]}.")
        sys.exit(1)

    print(f"{len(chunk_ids)} vectores de {embeddings.shape[1]} dimensiones leidos de {npz_path.name}")

    conn = get_db_connection()
    ensure_column(conn)

    print("Cargando en gold.nlp_chunks...")
    actualizados = load_embeddings(conn, chunk_ids, embeddings)
    print(f"{actualizados} fragmentos actualizados.")

    print("Construyendo indice HNSW (puede tardar un par de minutos)...")
    create_index(conn)

    with conn.cursor() as cur:
        cur.execute("""
            SELECT COUNT(*) FILTER (WHERE embedding IS NOT NULL), COUNT(*)
            FROM gold.nlp_chunks
        """)
        con_emb, total = cur.fetchone()
    conn.close()

    print(f"\nListo: {con_emb} de {total} fragmentos con embedding.")
    if con_emb < total:
        print(f"Faltan {total - con_emb}. Vuelve a correr export_chunks.py: exporta solo los que quedan.")


if __name__ == "__main__":
    main()
