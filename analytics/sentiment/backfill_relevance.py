"""Backfill de relevancia tematica sobre resultados ya existentes.

batch_inference.py solo aplica el filtro zero-shot a comentarios nuevos
(los que aun no tienen fila en sentiment_results). Este script reclasifica
los que ya se procesaron antes de que existiera el filtro, para marcar
is_relevant/relevance_score y pasar a label='off_topic' los que no hablan
de turismo en Tenerife.

Procesa en lotes chicos (fetch -> clasificar -> guardar -> commit) para no
sostener la conexion a la DB abierta e inactiva durante toda la clasificacion
(Azure corta conexiones SSL inactivas) y para no perder el progreso si algo
falla a mitad de camino: al reintentar, la consulta ya salta lo clasificado.
"""

import psycopg2
from transformers import pipeline

from batch_inference import (
    SOURCE,
    TOPIC_MODEL_NAME,
    classify_relevance,
    get_db_connection,
)

CHUNK_SIZE = 150
MAX_RETRIES = 3


def fetch_unclassified_chunk(conn, limit: int) -> list[tuple[int, str]]:
    """Proxima tanda de sentiment_results sin filtro de relevancia aplicado."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, text
            FROM silver.sentiment_results
            WHERE source = %s AND relevance_score IS NULL
            ORDER BY id
            LIMIT %s
            """,
            (SOURCE, limit),
        )
        return cur.fetchall()


def apply_relevance(conn, rows: list[tuple[int, str]], relevance: list[tuple[bool, float]]) -> None:
    with conn.cursor() as cur:
        for (row_id, _text), (is_relevant, score) in zip(rows, relevance):
            if is_relevant:
                cur.execute(
                    """
                    UPDATE silver.sentiment_results
                    SET is_relevant = true, relevance_score = %s
                    WHERE id = %s
                    """,
                    (score, row_id),
                )
            else:
                cur.execute(
                    """
                    UPDATE silver.sentiment_results
                    SET is_relevant = false, relevance_score = %s,
                        label = 'off_topic', score = %s, model_name = %s
                    WHERE id = %s
                    """,
                    (score, score, TOPIC_MODEL_NAME, row_id),
                )
    conn.commit()


def apply_relevance_with_retry(rows: list[tuple[int, str]], relevance: list[tuple[bool, float]]) -> None:
    """Reintenta con una conexion nueva si la DB corta la conexion a mitad de guardado.
    No hace falta re-clasificar: la clasificacion (lo caro) ya esta en `relevance`."""
    for attempt in range(1, MAX_RETRIES + 1):
        conn = get_db_connection()
        try:
            apply_relevance(conn, rows, relevance)
            return
        except psycopg2.OperationalError as e:
            if attempt == MAX_RETRIES:
                raise
            print(f"  conexion perdida al guardar ({e}); reintentando ({attempt}/{MAX_RETRIES})...")
        finally:
            conn.close()


def main():
    print(f"Cargando modelo de relevancia {TOPIC_MODEL_NAME!r}...")
    topic_classifier = pipeline("zero-shot-classification", model=TOPIC_MODEL_NAME, device=-1)

    total_done = 0
    total_off_topic = 0
    while True:
        conn = get_db_connection()
        rows = fetch_unclassified_chunk(conn, CHUNK_SIZE)
        if not rows:
            conn.close()
            break

        texts = [text for _, text in rows]
        relevance = classify_relevance(topic_classifier, texts)
        conn.close()
        apply_relevance_with_retry(rows, relevance)

        off_topic_count = sum(1 for is_relevant, _ in relevance if not is_relevant)
        total_done += len(rows)
        total_off_topic += off_topic_count
        print(f"  ...{total_done} procesados hasta ahora ({total_off_topic} off_topic).")

    print(f"Fin. Actualizados {total_done} registros: {total_done - total_off_topic} relevantes, {total_off_topic} marcados off_topic.")


if __name__ == "__main__":
    main()
