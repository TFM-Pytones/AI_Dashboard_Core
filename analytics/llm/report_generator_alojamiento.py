"""Informe Narrativo -- Modelo B ("alojamiento", por ubicacion).

Hermano de analytics/llm/report_generator.py (Modelo A / vision general):
mismo patron (topicos de BERTopic -> LLM -> gold.nlp_informe_global), pero
sobre el Modelo B -- Booking + TripAdvisor + LosViajeros georreferenciado
(ver analytics/topics/topic_modeling_geo_colab.ipynb). No estaba en el
prompt original repartido en el equipo (ese solo pedia el Modelo A), pero
sin esto los >38.000 comentarios del Modelo B (16x el volumen de YouTube)
no tenian ningun informe narrativo.

Sin filtro de fecha: Booking y TripAdvisor si tienen fecha real, pero
LosViajeros no (ver report_generator.py), y aplicar el filtro solo a dos de
las tres fuentes sesgaria el informe hacia ellas. Se deja como posible mejora
futura, no como filtro silencioso.
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

AMBITO = "alojamiento"
# Debe coincidir con MODEL_NAME en analytics/topics/topic_modeling_geo_colab.ipynb
MODEL_NAME_TOPICOS = "BERTopic+paraphrase-multilingual-mpnet-base-v2 (modelo B: geo)"

PROMPT_TEMPLATE = """Eres un analista senior de turismo de TUI. Los tópicos más discutidos en reseñas de alojamiento (Booking, TripAdvisor) y mensajes georreferenciados de viajeros sobre Tenerife son:

{lista_topicos}

Escribe un informe ejecutivo de 3 párrafos resumiendo:
1. La percepción general de la experiencia de alojamiento en Tenerife
2. Los principales problemas mencionados por los huéspedes
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
    """Topicos del Modelo B (topic_id != -1) con su nº de reseñas/mensajes.
    Devuelve (lista de (label, count) ordenada desc, total incluido)."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT topic_label, COUNT(*) AS n
            FROM gold.nlp_topics
            WHERE model_name = %s
              AND topic_id != -1
            GROUP BY topic_label
            ORDER BY n DESC
            """,
            (MODEL_NAME_TOPICOS,),
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
        print(f"No hay topicos de {MODEL_NAME_TOPICOS!r} en gold.nlp_topics. Corre antes el entrenamiento del Modelo B (topic_modeling_geo_colab.ipynb + import_geo_results.py).")
        conn.close()
        return

    print(f"{len(topic_counts)} topicos, {total} reseñas/mensajes.")

    prompt = build_prompt(topic_counts)
    client = LLMClient()
    print(f"Generando informe con {client.model!r}...")
    informe = client.complete(prompt)

    save_informe(conn, informe, client.model, total, len(topic_counts))
    conn.close()

    print("\n--- INFORME ---\n")
    print(informe)
    print("\nGuardado en gold.nlp_informe_global (ambito='alojamiento').")


if __name__ == "__main__":
    main()
