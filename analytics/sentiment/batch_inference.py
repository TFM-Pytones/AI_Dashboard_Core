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
TOPIC_MODEL_NAME = "MoritzLaurer/mDeBERTa-v3-base-mnli-xnli"
RELEVANT_LABEL = "comentario sobre turismo, viajes o el impacto del turismo en Canarias o Tenerife"
CANDIDATE_LABELS = [
    RELEVANT_LABEL,
    "comentario sobre el video o el canal de YouTube",
    "conversación personal no relacionada con turismo",
    "spam o publicidad",
]
OFF_TOPIC_MARGIN = 0.25  # exigir que off_topic gane por margen grande: evita descartar opiniones/criticas validas
TOPIC_BATCH_SIZE = 8  # zero-shot multi-label evalua 4 hipotesis por texto: batch grande satura memoria de GPU
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


def prepare_items(pending: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Limpia texto y descarta lo demasiado corto para aportar señal."""
    items = []
    for comment_id, text in pending:
        cleaned = clean_text(text)
        if len(cleaned) >= MIN_TEXT_LENGTH:
            items.append((comment_id, cleaned))
    return items


def classify_relevance(topic_classifier, texts: list[str]) -> list[tuple[bool, float]]:
    """Zero-shot multi-label: todos los videos ya son de turismo en Tenerife,
    asi que se compara la probabilidad de "opinion de viaje" contra la mejor
    categoria de ruido (video/canal, chat personal, spam) en vez de un umbral fijo."""
    outputs = topic_classifier(texts, CANDIDATE_LABELS, batch_size=TOPIC_BATCH_SIZE, multi_label=True)
    if isinstance(outputs, dict):
        outputs = [outputs]
    results = []
    for out in outputs:
        scores = dict(zip(out["labels"], out["scores"]))
        relevant_score = scores[RELEVANT_LABEL]
        off_topic_score = max(score for label, score in scores.items() if label != RELEVANT_LABEL)
        is_relevant = relevant_score >= off_topic_score - OFF_TOPIC_MARGIN
        results.append((is_relevant, relevant_score))
    return results


def split_by_relevance(
    items: list[tuple[str, str]], relevance: list[tuple[bool, float]]
) -> tuple[list[tuple[str, str, float]], list[tuple[str, str, float]]]:
    """Separa items en (relevantes, descartados) segun el resultado del zero-shot."""
    relevant, off_topic = [], []
    for (comment_id, text), (is_relevant, score) in zip(items, relevance):
        target = relevant if is_relevant else off_topic
        target.append((comment_id, text, score))
    return relevant, off_topic


def build_off_topic_results(off_topic: list[tuple[str, str, float]]) -> list[dict]:
    return [
        {
            "source": SOURCE,
            "source_id": comment_id,
            "text": text,
            "label": "off_topic",
            "score": score,
            "model_name": TOPIC_MODEL_NAME,
            "is_relevant": False,
            "relevance_score": score,
        }
        for comment_id, text, score in off_topic
    ]


def run_sentiment(relevant: list[tuple[str, str, float]]) -> list[dict]:
    if not relevant:
        return []

    print(f"Cargando modelo {MODEL_NAME!r}...")
    classifier = pipeline("sentiment-analysis", model=MODEL_NAME, tokenizer=MODEL_NAME)

    texts = [text for _, text, _ in relevant]
    predictions = classifier(texts, batch_size=BATCH_SIZE, truncation=True, max_length=512)

    return [
        {
            "source": SOURCE,
            "source_id": comment_id,
            "text": text,
            "label": pred["label"],
            "score": float(pred["score"]),
            "model_name": MODEL_NAME,
            "is_relevant": True,
            "relevance_score": relevance_score,
        }
        for (comment_id, text, relevance_score), pred in zip(relevant, predictions)
    ]


def print_summary(results: list[dict]) -> None:
    counts = {}
    for r in results:
        counts[r["label"]] = counts.get(r["label"], 0) + 1
    print(f"\nGuardados {len(results)} resultados nuevos en processed_data.sentiment_results.")
    print("Distribución:", counts)


def save_results(conn, results: list[dict]):
    if not results:
        return
    with conn.cursor() as cur:
        psycopg2.extras.execute_batch(
            cur,
            """
            INSERT INTO processed_data.sentiment_results
                (source, source_id, text, label, score, model_name, is_relevant, relevance_score)
            VALUES (%(source)s, %(source_id)s, %(text)s, %(label)s, %(score)s, %(model_name)s,
                    %(is_relevant)s, %(relevance_score)s)
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

    items = prepare_items(pending)
    print(f"{len(pending)} comentarios pendientes, {len(items)} con texto útil tras limpieza.")
    if not items:
        print("Nada que procesar (todo lo pendiente quedó vacío tras limpiar). Fin.")
        conn.close()
        return

    print(f"Cargando modelo de relevancia {TOPIC_MODEL_NAME!r}...")
    topic_classifier = pipeline("zero-shot-classification", model=TOPIC_MODEL_NAME, device=-1)
    texts = [text for _, text in items]
    relevance = classify_relevance(topic_classifier, texts)

    relevant, off_topic = split_by_relevance(items, relevance)
    print(f"{len(relevant)} relevantes, {len(off_topic)} descartados por tema.")

    results = build_off_topic_results(off_topic) + run_sentiment(relevant)
    save_results(conn, results)
    print_summary(results)

    conn.close()


if __name__ == "__main__":
    main()
