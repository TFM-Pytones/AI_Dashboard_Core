"""Subtarea 3.2 -- Generacion de Informe Narrativo Global.

Convierte los topicos del MODELO A (vision general -- YouTube + LosViajeros
SIN ubicacion detectada, ver analytics/topics/topic_modeling.py) en un
informe ejecutivo de 3 parrafos via LLM (Groq).

Nota sobre el prompt original repartido en el equipo: decia "temas mas
discutidos en YouTube y foros de viajeros" -- eso encaja ahora que LosViajeros
(la parte sin ubicacion, ver analytics/contexto.md) volvio al Modelo A junto
a YouTube.

Filtro de fecha (>= 2022, tal y como pedia el prompt original): solo aplica a
YouTube (bronze.bronze_youtube_comments.published_at). LosViajeros no tiene una
fecha real del mensaje (solo fecha_extraccion, que es cuando se scrapeo, no
cuando se escribio), asi que sus filas entran siempre -- filtrarlas por una
fecha que no es la suya seria inventar un dato. Se aplica sobre el conteo que
ve el LLM, no sobre el entrenamiento de BERTopic (los topicos ya estan
calculados sobre todo el corpus).
"""

import os
import sys
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

from llm_client import LLMClient

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")  # consola Windows (cp1252) no soporta todos los caracteres que puede devolver el LLM

load_dotenv(override=True)

FECHA_MINIMA = "2022-01-01"
AMBITO = "general"
# Debe coincidir con MODEL_NAME en analytics/topics/topic_modeling.py
MODEL_NAME_TOPICOS = "BERTopic+paraphrase-multilingual-mpnet-base-v2 (modelo A: general)"

PROMPT_TEMPLATE = """Eres un analista senior de turismo de TUI. Los tópicos más discutidos en comentarios de YouTube (desde 2022) y mensajes del foro de viajeros LosViajeros sobre Tenerife son:

{lista_topicos}

Escribe un informe ejecutivo de 3 párrafos resumiendo:
1. La percepción general de Tenerife como destino
2. Los principales problemas mencionados por los visitantes
3. Las oportunidades de mejora para TUI
"""


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
    schema_path = Path(__file__).resolve().parents[2] / "sql" / "gold_nlp_informe_global_schema.sql"
    with conn.cursor() as cur:
        cur.execute(schema_path.read_text())
    conn.commit()


def fetch_topic_summary(conn) -> tuple[list[tuple[str, int]], int]:
    """Topicos del Modelo A (topic_id != -1) con su nº de comentarios.
    YouTube se filtra por FECHA_MINIMA; LosViajeros entra siempre (no tiene
    fecha real del mensaje, ver docstring del modulo).
    Devuelve (lista de (label, count) ordenada desc, total de comentarios incluidos)."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT t.topic_label, COUNT(*) AS n
            FROM gold.nlp_topics t
            LEFT JOIN bronze.bronze_youtube_comments c
              ON t.source = 'youtube_comment' AND c.comment_id = t.source_id
            WHERE t.model_name = %s
              AND t.topic_id != -1
              AND (t.source != 'youtube_comment' OR c.published_at >= %s)
            GROUP BY t.topic_label
            ORDER BY n DESC
            """,
            (MODEL_NAME_TOPICOS, FECHA_MINIMA),
        )
        rows = cur.fetchall()
    total = sum(n for _, n in rows)
    return rows, total


def build_prompt(topic_counts: list[tuple[str, int]]) -> str:
    lista = "\n".join(f"- {label} ({n} comentarios)" for label, n in topic_counts)
    return PROMPT_TEMPLATE.format(lista_topicos=lista)


def save_informe(conn, informe: str, modelo_llm: str, n_comentarios: int, n_topicos: int):
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO gold.nlp_informe_global (informe, modelo_llm, n_comentarios, n_topicos, ambito)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (informe, modelo_llm, n_comentarios, n_topicos, AMBITO),
        )
    conn.commit()


def main():
    conn = get_db_connection()
    ensure_schema(conn)

    topic_counts, total = fetch_topic_summary(conn)
    if not topic_counts:
        print(f"No hay topicos de {MODEL_NAME_TOPICOS!r} en gold.nlp_topics. Corre antes analytics/topics/topic_modeling.py (o importa el resultado del Colab retraining).")
        conn.close()
        return

    print(f"{len(topic_counts)} topicos, {total} comentarios (desde {FECHA_MINIMA}).")

    prompt = build_prompt(topic_counts)
    client = LLMClient()
    print(f"Generando informe con {client.model!r}...")
    informe = client.complete(prompt)

    save_informe(conn, informe, client.model, total, len(topic_counts))
    conn.close()

    print("\n--- INFORME ---\n")
    print(informe)
    print("\nGuardado en gold.nlp_informe_global.")


if __name__ == "__main__":
    main()
