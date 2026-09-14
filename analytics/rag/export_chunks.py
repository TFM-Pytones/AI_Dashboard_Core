"""Fase 2 del RAG (ver plan_rag.md) -- Exporta gold.nlp_chunks a CSV para
calcular los embeddings en Google Colab con GPU.

Se calculan fuera porque en CPU local los ~88.000 fragmentos tardan horas,
mientras que en una T4 gratuita son unos minutos. Es el mismo patron que ya se
uso para entrenar BERTopic (analytics/topics/export_geo_corpus.py).

Colab no puede conectarse a la BD de Azure (el firewall del servidor no
permite sus IPs), asi que el intercambio es por archivo: CSV de ida,
embeddings de vuelta.

Uso:
    python analytics/rag/export_chunks.py
    -> analytics/rag/export/chunks_para_embeddings.csv (chunk_id,text)
"""

import csv
import os
import sys
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

load_dotenv(override=True)

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

OUT_PATH = Path(__file__).resolve().parent / "export" / "chunks_para_embeddings.csv"


def get_db_connection():
    return psycopg2.connect(
        user=os.getenv("AZURE_DB_USER"),
        password=os.getenv("AZURE_DB_PASSWORD"),
        host=os.getenv("AZURE_DB_HOST"),
        database=os.getenv("AZURE_DB_NAME"),
        port="5432",
        sslmode="require",
    )


def fetch_chunks(conn) -> list[tuple[int, str]]:
    """Solo los fragmentos sin embedding, para poder reanudar si la carga se
    corta a medias sin recalcular lo que ya esta hecho."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_schema='gold' AND table_name='nlp_chunks' AND column_name='embedding'
        """)
        tiene_columna = cur.fetchone() is not None

        if tiene_columna:
            cur.execute("SELECT chunk_id, text FROM gold.nlp_chunks WHERE embedding IS NULL ORDER BY chunk_id")
        else:
            cur.execute("SELECT chunk_id, text FROM gold.nlp_chunks ORDER BY chunk_id")
        return cur.fetchall()


def main():
    conn = get_db_connection()
    filas = fetch_chunks(conn)
    conn.close()

    if not filas:
        print("Todos los fragmentos ya tienen embedding. Nada que exportar.")
        return

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["chunk_id", "text"])
        writer.writerows(filas)

    mb = OUT_PATH.stat().st_size / 1024 / 1024
    print(f"{len(filas)} fragmentos exportados a {OUT_PATH} ({mb:.1f} MB)")
    print("\nSiguiente paso:")
    print("  1. Sube el CSV a tu Google Drive (raiz 'Mi unidad').")
    print("  2. Abre analytics/rag/embed_chunks_colab.ipynb en Colab con GPU.")
    print("  3. Ejecuta todas las celdas y descarga embeddings.npz.")
    print("  4. python analytics/rag/import_embeddings.py ruta/a/embeddings.npz")


if __name__ == "__main__":
    main()
