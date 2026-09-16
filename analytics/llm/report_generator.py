"""Subtarea 3.2 -- Generacion de Informe Narrativo por ambito.

Convierte los topicos de BERTopic en un informe ejecutivo de 3 parrafos via
LLM (Groq) y lo guarda en gold.nlp_informe_global.

Dos ambitos, que antes vivian en dos scripts casi identicos (report_generator.py
y report_generator_alojamiento.py, fusionados aqui en el punto 7 de la revision
de codigo):

  --ambito general      Modelo A: YouTube + LosViajeros SIN ubicacion detectada.
                        Es el que pedia el prompt original repartido en el
                        equipo ("temas mas discutidos en YouTube y foros de
                        viajeros"), que encaja ahora que LosViajeros (la parte
                        sin ubicacion, ver analytics/contexto.md) volvio al
                        Modelo A junto a YouTube.

  --ambito alojamiento  Modelo B: Booking + TripAdvisor + LosViajeros
                        georreferenciado. No estaba en el prompt original, pero
                        sin esto los >38.000 comentarios del Modelo B (16x el
                        volumen de YouTube) no tenian ningun informe narrativo.

Filtro de fecha (>= 2022, tal y como pedia el prompt original): solo se aplica
al ambito general, y dentro de el solo a YouTube
(bronze.bronze_youtube_comments.published_at). LosViajeros no tiene una fecha
real del mensaje (solo fecha_extraccion, que es cuando se scrapeo, no cuando se
escribio), asi que sus filas entran siempre -- filtrarlas por una fecha que no
es la suya seria inventar un dato. El ambito alojamiento no filtra: Booking y
TripAdvisor si tienen fecha real, pero LosViajeros no, y aplicarlo solo a dos de
las tres fuentes sesgaria el informe hacia ellas. El filtro se aplica sobre el
conteo que ve el LLM, no sobre el entrenamiento de BERTopic (los topicos ya
estan calculados sobre todo el corpus).

Uso:
    python analytics/llm/report_generator.py --ambito general
    python analytics/llm/report_generator.py --ambito alojamiento
"""

import argparse
import os
import sys
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

# Permite ejecutarlo como script suelto (python analytics/llm/report_generator.py,
# que es como lo lanza Airflow) ademas de importarlo como analytics.llm.*
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from analytics.llm.llm_client import LLMClient  # noqa: E402

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")  # consola Windows (cp1252) no soporta todos los caracteres que puede devolver el LLM

load_dotenv(override=True)

FECHA_MINIMA = "2022-01-01"

# Deben coincidir con los model_name de MODELOS en analytics/topics/entrenar_topicos.py.
# La v2 reescribe esas mismas filas de gold.nlp_topics conservando el nombre del
# modelo, por eso estos informes siguen valiendo despues del reentrenamiento.
MODEL_NAME_A = "BERTopic+paraphrase-multilingual-mpnet-base-v2 (modelo A: general)"
MODEL_NAME_B = "BERTopic+paraphrase-multilingual-mpnet-base-v2 (modelo B: geo)"

PROMPT_GENERAL = """Eres un analista senior de turismo de TUI. Los tópicos más discutidos en comentarios de YouTube (desde 2022) y mensajes del foro de viajeros LosViajeros sobre Tenerife son:

{lista_topicos}

Escribe un informe ejecutivo de 3 párrafos resumiendo:
1. La percepción general de Tenerife como destino
2. Los principales problemas mencionados por los visitantes
3. Las oportunidades de mejora para TUI
"""

PROMPT_ALOJAMIENTO = """Eres un analista senior de turismo de TUI. Los tópicos más discutidos en reseñas de alojamiento (Booking, TripAdvisor) y mensajes georreferenciados de viajeros sobre Tenerife son:

{lista_topicos}

Escribe un informe ejecutivo de 3 párrafos resumiendo:
1. La percepción general de la experiencia de alojamiento en Tenerife
2. Los principales problemas mencionados por los huéspedes
3. Las oportunidades de mejora para TUI
"""

# El ambito general filtra YouTube por fecha, por eso necesita el LEFT JOIN
# contra bronze; el de alojamiento no filtra y se queda dentro de gold.nlp_topics.
QUERY_GENERAL = """
    SELECT t.topic_label, COUNT(*) AS n
    FROM gold.nlp_topics t
    LEFT JOIN bronze.bronze_youtube_comments c
      ON t.source = 'youtube_comment' AND c.comment_id = t.source_id
    WHERE t.model_name = %s
      AND t.topic_id != -1
      AND (t.source != 'youtube_comment' OR c.published_at >= %s)
    GROUP BY t.topic_label
    ORDER BY n DESC
"""

QUERY_ALOJAMIENTO = """
    SELECT topic_label, COUNT(*) AS n
    FROM gold.nlp_topics
    WHERE model_name = %s
      AND topic_id != -1
    GROUP BY topic_label
    ORDER BY n DESC
"""

AMBITOS = {
    "general": {
        "model_name": MODEL_NAME_A,
        "prompt": PROMPT_GENERAL,
        "query": QUERY_GENERAL,
        "params": (MODEL_NAME_A, FECHA_MINIMA),
        "unidad": "comentarios",
        "pista": "Corre antes export_general_corpus.py + cargar_corpus.py --modelo A (carga "
                 "inicial del corpus) y despues entrenar_topicos.py + volcar_topicos.py.",
    },
    "alojamiento": {
        "model_name": MODEL_NAME_B,
        "prompt": PROMPT_ALOJAMIENTO,
        "query": QUERY_ALOJAMIENTO,
        "params": (MODEL_NAME_B,),
        "unidad": "reseñas/mensajes",
        "pista": "Corre antes export_geo_corpus.py + cargar_corpus.py --modelo B (carga "
                 "inicial del corpus) y despues entrenar_topicos.py + volcar_topicos.py.",
    },
}


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
        cur.execute(schema_path.read_text(encoding="utf-8"))
    conn.commit()


def fetch_topic_summary(conn, ambito: str) -> tuple[list[tuple[str, int]], int]:
    """Topicos del modelo de este ambito (topic_id != -1) con su nº de documentos.
    Devuelve (lista de (label, count) ordenada desc, total de documentos incluidos)."""
    conf = AMBITOS[ambito]
    with conn.cursor() as cur:
        cur.execute(conf["query"], conf["params"])
        rows = cur.fetchall()
    total = sum(n for _, n in rows)
    return rows, total


def build_prompt(topic_counts: list[tuple[str, int]], ambito: str) -> str:
    lista = "\n".join(f"- {label} ({n} comentarios)" for label, n in topic_counts)
    return AMBITOS[ambito]["prompt"].format(lista_topicos=lista)


def save_informe(conn, informe: str, modelo_llm: str, n_comentarios: int, n_topicos: int, ambito: str):
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO gold.nlp_informe_global (informe, modelo_llm, n_comentarios, n_topicos, ambito)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (informe, modelo_llm, n_comentarios, n_topicos, ambito),
        )
    conn.commit()


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Informe narrativo de topicos por ambito (Groq).",
    )
    parser.add_argument(
        "--ambito",
        choices=sorted(AMBITOS),
        default="general",
        help="general = Modelo A (YouTube + foros sin ubicacion); "
             "alojamiento = Modelo B (Booking + TripAdvisor + foros georreferenciados)",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    ambito = args.ambito
    conf = AMBITOS[ambito]

    conn = get_db_connection()
    ensure_schema(conn)

    topic_counts, total = fetch_topic_summary(conn, ambito)
    if not topic_counts:
        print(f"No hay topicos de {conf['model_name']!r} en gold.nlp_topics. {conf['pista']}")
        conn.close()
        return

    print(f"[{ambito}] {len(topic_counts)} topicos, {total} {conf['unidad']}.")

    prompt = build_prompt(topic_counts, ambito)
    client = LLMClient()
    print(f"Generando informe con {client.model!r}...")
    informe = client.complete(prompt)

    save_informe(conn, informe, client.model, total, len(topic_counts), ambito)
    conn.close()

    print("\n--- INFORME ---\n")
    print(informe)
    print(f"\nGuardado en gold.nlp_informe_global (ambito='{ambito}').")


if __name__ == "__main__":
    main()
