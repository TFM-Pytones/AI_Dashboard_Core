"""Issue #17 — Inferencia de Sentimiento por Lotes.

Procesa TODOS los comentarios de YouTube que aun no tengan resultado, corre el
modelo de sentimiento (el mismo del Issue #16) y guarda las predicciones en
processed_data.sentiment_results. Incremental: si se repite, solo procesa lo
nuevo (no reprocesa lo ya hecho).

La tabla de resultados es generica (columna `source`) para poder añadir
TripAdvisor/Booking (#12) y Reddit (#14) mas adelante sin cambiar el esquema.
"""

import os
import re
from pathlib import Path

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from transformers import pipeline

load_dotenv(override=True)

MODEL_NAME = "cardiffnlp/twitter-xlm-roberta-base-sentiment"
SOURCE = "youtube_comment"
BATCH_SIZE = 32
MIN_TEXT_LENGTH = 3

URL_RE = re.compile(r"https?://\S+")


def get_db_connection():
    return psycopg2.connect(
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST"),
        database=os.getenv("DB_NAME"),
        port="5432",
        sslmode="require",
    )


def ensure_schema(conn):
    schema_path = Path(__file__).resolve().parents[2] / "sql" / "sentiment_results_schema.sql"
    with conn.cursor() as cur:
        cur.execute(schema_path.read_text())
    conn.commit()


def clean_text(text: str) -> str:
    text = URL_RE.sub("", text or "")
    return re.sub(r"\s+", " ", text).strip()


def fetch_pending_comments(conn) -> list[tuple[str, str]]:
    """Comentarios de YouTube sin resultado todavia. Devuelve (comment_id, text)."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT c.comment_id, c.text
            FROM raw_data.youtube_comments c
            LEFT JOIN processed_data.sentiment_results r
                ON r.source = %s AND r.source_id = c.comment_id
            WHERE r.id IS NULL AND c.text IS NOT NULL
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
            INSERT INTO processed_data.sentiment_results
                (source, source_id, text, label, score, model_name)
            VALUES (%(source)s, %(source_id)s, %(text)s, %(label)s, %(score)s, %(model_name)s)
            ON CONFLICT (source, source_id) DO NOTHING
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

    # Limpiar y descartar texto demasiado corto para aportar señal.
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

    print(f"Cargando modelo {MODEL_NAME!r}...")
    classifier = pipeline("sentiment-analysis", model=MODEL_NAME, tokenizer=MODEL_NAME)

    texts = [t for _, t in items]
    predictions = classifier(texts, batch_size=BATCH_SIZE, truncation=True, max_length=512)

    results = [
        {
            "source": SOURCE,
            "source_id": comment_id,
            "text": text,
            "label": pred["label"],
            "score": float(pred["score"]),
            "model_name": MODEL_NAME,
        }
        for (comment_id, text), pred in zip(items, predictions)
    ]
    save_results(conn, results)

    counts = {}
    for r in results:
        counts[r["label"]] = counts.get(r["label"], 0) + 1
    print(f"\nGuardados {len(results)} resultados nuevos en processed_data.sentiment_results.")
    print("Distribución:", counts)

    conn.close()


if __name__ == "__main__":
    main()
