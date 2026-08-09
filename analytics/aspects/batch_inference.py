"""Issue #18 — Extraccion de Aspectos por Lotes.

Procesa TODOS los comentarios de YouTube que aun no tengan aspectos extraidos,
corre pyabsa (ATEPC, el mismo checkpoint del setup_test.py) y guarda cada
aspecto detectado en silver.aspect_results (Azure). Incremental: si se repite,
solo procesa comentarios nuevos.

Un mismo comentario puede generar varias filas (una por aspecto detectado) o
ninguna (si no se detecta ningun aspecto), por eso la deteccion de "ya
procesado" usa source_id distinto en vez de una constraint UNIQUE.
"""

import os
import re
from pathlib import Path

# pyabsa usa internamente `from distutils.version import ...`, que ya no existe
# en Python 3.12+. Importar setuptools primero registra un shim compatible.
import setuptools  # noqa: F401

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from pyabsa import AspectTermExtraction as ATEPC

load_dotenv(override=True)

CHECKPOINT = "multilingual"
MODEL_NAME = "pyabsa-multilingual-ATEPC"
SOURCE = "youtube_comment"
BATCH_SIZE = 32
MIN_TEXT_LENGTH = 3

URL_RE = re.compile(r"https?://\S+")


def get_db_connection():
    return psycopg2.connect(
        user=os.getenv("AZURE_DB_USER"),
        password=os.getenv("AZURE_DB_PASSWORD"),
        host=os.getenv("AZURE_DB_HOST"),
        database=os.getenv("AZURE_DB_NAME"),
        port="5432",
        sslmode="require",
    )


def ensure_schema(conn):
    schema_path = Path(__file__).resolve().parents[2] / "sql" / "silver_aspect_results_schema.sql"
    with conn.cursor() as cur:
        cur.execute(schema_path.read_text())
    conn.commit()


def clean_text(text: str) -> str:
    text = URL_RE.sub("", text or "")
    return re.sub(r"\s+", " ", text).strip()


def fetch_pending_comments(conn) -> list[tuple[str, str]]:
    """Comentarios de YouTube sin aspectos extraidos todavia. Devuelve (comment_id, text)."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT c.comment_id, c.text
            FROM bronze.youtube_comments c
            WHERE c.text IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1 FROM silver.aspect_results r
                  WHERE r.source = %s AND r.source_id = c.comment_id
              )
            """,
            (SOURCE,),
        )
        return cur.fetchall()


def save_results(conn, results: list[dict]):
    if not results:
        return
    with conn.cursor() as cur:
        psycopg2.extras.execute_batch(
            cur,
            """
            INSERT INTO silver.aspect_results
                (source, source_id, text, aspect, aspect_sentiment, confidence, model_name)
            VALUES (%(source)s, %(source_id)s, %(text)s, %(aspect)s, %(aspect_sentiment)s, %(confidence)s, %(model_name)s)
            """,
            results,
        )
    conn.commit()


def main():
    conn = get_db_connection()
    ensure_schema(conn)

    pending = fetch_pending_comments(conn)
    if not pending:
        print("No hay comentarios nuevos por procesar. Todo al día.")
        conn.close()
        return

    items = []
    for comment_id, text in pending:
        cleaned = clean_text(text)
        if len(cleaned) >= MIN_TEXT_LENGTH:
            items.append((comment_id, cleaned))

    print(f"{len(pending)} comentarios pendientes, {len(items)} con texto útil tras limpieza.")
    if not items:
        print("Nada que procesar (todo lo pendiente quedó vacío tras limpiar). Fin.")
        conn.close()
        return

    conn.close()  # el checkpoint tarda minutos en cargar; no dejar la conexión abierta e inactiva

    print(f"Cargando checkpoint {CHECKPOINT!r} de pyabsa (primera vez descarga ~1.1GB)...")
    extractor = ATEPC.AspectExtractor(CHECKPOINT, auto_device=True)

    total_saved = 0
    comments_with_aspects = 0
    for start in range(0, len(items), BATCH_SIZE):
        chunk = items[start:start + BATCH_SIZE]
        texts = [t for _, t in chunk]
        predictions = extractor.predict(texts, save_result=False, print_result=False)

        batch_results = []
        for (comment_id, text), pred in zip(chunk, predictions):
            if not pred["aspect"]:
                continue
            comments_with_aspects += 1
            for aspect, sentiment, confidence in zip(pred["aspect"], pred["sentiment"], pred["confidence"]):
                batch_results.append({
                    "source": SOURCE,
                    "source_id": comment_id,
                    "text": text,
                    "aspect": aspect,
                    "aspect_sentiment": sentiment,
                    "confidence": float(confidence),
                    "model_name": MODEL_NAME,
                })

        # Conexión nueva por lote: cada INSERT es rápido, evita que Azure
        # cierre la conexión por inactividad durante la inferencia.
        batch_conn = get_db_connection()
        save_results(batch_conn, batch_results)
        batch_conn.close()
        total_saved += len(batch_results)

        print(f"  -> {min(start + BATCH_SIZE, len(items))}/{len(items)} comentarios procesados y guardados...")

    print(f"\nGuardadas {total_saved} filas de aspectos en silver.aspect_results.")
    print(f"{comments_with_aspects}/{len(items)} comentarios tenían al menos un aspecto detectado.")


if __name__ == "__main__":
    main()
