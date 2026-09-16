"""Extraccion de Aspectos por Lotes (PyABSA ATEPC) -- todas las fuentes.

Unifica lo que antes estaba partido en dos sitios (punto 5 de la revision de
codigo): este script, que solo hacia YouTube, y el notebook manual
analytics/tarea2/nlp_aspectos_tarea_2_2.ipynb, que hacia Booking + TripAdvisor
fuera de Airflow. Ahora es un unico comando parametrizado por fuente.

    python analytics/aspects/batch_inference.py --source youtube
    python analytics/aspects/batch_inference.py --source booking
    python analytics/aspects/batch_inference.py --source tripadvisor
    python analytics/aspects/batch_inference.py --source resenas   # booking + tripadvisor
    python analytics/aspects/batch_inference.py --source todas

Mismo modelo (checkpoint 'multilingual' de ATEPC) en las dos ramas; lo que
cambia es de donde se lee y donde se escribe, y eso se respeta tal cual estaba
para no invalidar lo ya calculado en Azure:

  youtube   bronze.bronze_youtube_comments -> silver.aspect_results
            (columnas en ingles: aspect / aspect_sentiment / confidence)

  resenas   silver.tripadvisor_resenas + silver.silver_booking_reviews, desde
            2022 -> gold.nlp_aspectos_resenas (columnas en español: aspecto /
            sentimiento / confianza). Es la tabla que consume el modelo dbt
            gold_sentimiento_h3 para la columna queja_principal.

Un mismo texto puede generar varias filas (una por aspecto) o ninguna. Por eso
la deteccion de "ya procesado" usa NOT EXISTS sobre el id, no una constraint
UNIQUE; y en la rama de reseñas se guarda una fila con aspecto/sentimiento en
NULL cuando no se detecta ninguno, para no reintentarla en cada ejecucion.

Dos bugs arreglados aqui (puntos 14 y 15 de la revision):
  - ensure_schema() leia sql/silver_aspect_results_schema.sql, que no existia
    en el repo y hacia petar el script en limpio. El fichero ya esta creado.
  - la rama de YouTube leia bronze.youtube_comments (destino de la migracion
    antigua desde Neon); la tabla que declara dbt en models/silver/sources.yml
    y que llena la ingesta es bronze.bronze_youtube_comments.
"""

import argparse
import os
import re
import sys
from pathlib import Path

# pyabsa usa internamente `from distutils.version import ...`, que ya no existe
# en Python 3.12+. Importar setuptools primero registra un shim compatible.
import setuptools  # noqa: F401

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv(override=True)

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

CHECKPOINT = "multilingual"
MODEL_NAME = "pyabsa-multilingual-ATEPC"
SOURCE_YOUTUBE = "youtube_comment"
BATCH_SIZE = 32
MIN_TEXT_LENGTH = 3
ANIO_MINIMO_RESENAS = 2021  # el filtro real es "> 2021", es decir, de 2022 en adelante

URL_RE = re.compile(r"https?://\S+")

FUENTES = ("youtube", "booking", "tripadvisor", "resenas", "todas")

RUTA_DDL_SILVER = Path(__file__).resolve().parents[2] / "sql" / "silver_aspect_results_schema.sql"

DDL_GOLD_ASPECTOS = """
    CREATE TABLE IF NOT EXISTS gold.nlp_aspectos_resenas (
        resena_id text,
        hotel_id text,
        aspecto text,
        sentimiento text,
        confianza double precision,
        fuente text
    )
"""

# bronze_youtube_comments (con prefijo) es la tabla que declara dbt en
# models/silver/sources.yml y la que llena la ingesta.
SQL_PENDIENTES_YOUTUBE = """
    SELECT c.comment_id, c.text
    FROM bronze.bronze_youtube_comments c
    WHERE c.text IS NOT NULL
      AND NOT EXISTS (
          SELECT 1 FROM silver.aspect_results r
          WHERE r.source = %s AND r.source_id = c.comment_id
      )
"""

SQL_PENDIENTES_TRIPADVISOR = """
    SELECT 'tripadvisor' AS fuente, r.review_id::text AS resena_id,
           r.location_id::text AS hotel_id, r.texto AS review_text
    FROM silver.tripadvisor_resenas r
    WHERE r.texto IS NOT NULL AND EXTRACT(YEAR FROM r.fecha_publicacion) > %s
      AND NOT EXISTS (
          SELECT 1 FROM gold.nlp_aspectos_resenas g
          WHERE g.resena_id = r.review_id::text AND g.fuente = 'tripadvisor'
      )
"""

SQL_PENDIENTES_BOOKING = """
    SELECT 'booking' AS fuente, b.review_id AS resena_id,
           b.establishment_id AS hotel_id, b.review_text
    FROM silver.silver_booking_reviews b
    WHERE b.review_text IS NOT NULL AND EXTRACT(YEAR FROM b.review_date) > %s
      AND NOT EXISTS (
          SELECT 1 FROM gold.nlp_aspectos_resenas g
          WHERE g.resena_id = b.review_id AND g.fuente = 'booking'
      )
"""

SQL_PENDIENTES_RESENAS = {
    "tripadvisor": SQL_PENDIENTES_TRIPADVISOR,
    "booking": SQL_PENDIENTES_BOOKING,
}


def fuentes_de_resenas(source: str) -> list[str]:
    """Que fuentes de reseñas toca procesar para el --source pedido."""
    if source in ("resenas", "todas"):
        return ["tripadvisor", "booking"]
    if source in ("booking", "tripadvisor"):
        return [source]
    return []


def get_db_connection():
    return psycopg2.connect(
        user=os.getenv("AZURE_DB_USER"),
        password=os.getenv("AZURE_DB_PASSWORD"),
        host=os.getenv("AZURE_DB_HOST"),
        database=os.getenv("AZURE_DB_NAME"),
        port="5432",
        sslmode="require",
    )


def ensure_schema_youtube(conn):
    with conn.cursor() as cur:
        cur.execute(RUTA_DDL_SILVER.read_text(encoding="utf-8"))
    conn.commit()


def ensure_schema_resenas(conn):
    with conn.cursor() as cur:
        cur.execute(DDL_GOLD_ASPECTOS)
    conn.commit()


def clean_text(text: str) -> str:
    text = URL_RE.sub("", text or "")
    return re.sub(r"\s+", " ", text).strip()


def cargar_extractor():
    """El checkpoint tarda minutos en cargar y pesa ~1.1GB la primera vez."""
    from pyabsa import AspectTermExtraction as ATEPC

    print(f"Cargando checkpoint {CHECKPOINT!r} de pyabsa (primera vez descarga ~1.1GB)...")
    return ATEPC.AspectExtractor(CHECKPOINT, auto_device=True)


# --- Rama YouTube ------------------------------------------------------------

def fetch_pending_comments(conn) -> list[tuple[str, str]]:
    """Comentarios de YouTube sin aspectos extraidos todavia. Devuelve (comment_id, text)."""
    with conn.cursor() as cur:
        cur.execute(SQL_PENDIENTES_YOUTUBE, (SOURCE_YOUTUBE,))
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


def procesar_youtube():
    conn = get_db_connection()
    ensure_schema_youtube(conn)

    pending = fetch_pending_comments(conn)
    if not pending:
        print("[youtube] No hay comentarios nuevos por procesar. Todo al día.")
        conn.close()
        return

    items = []
    for comment_id, text in pending:
        cleaned = clean_text(text)
        if len(cleaned) >= MIN_TEXT_LENGTH:
            items.append((comment_id, cleaned))

    print(f"[youtube] {len(pending)} comentarios pendientes, {len(items)} con texto útil tras limpieza.")
    if not items:
        print("[youtube] Nada que procesar (todo lo pendiente quedó vacío tras limpiar). Fin.")
        conn.close()
        return

    conn.close()  # el checkpoint tarda minutos en cargar; no dejar la conexión abierta e inactiva
    extractor = cargar_extractor()

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
                    "source": SOURCE_YOUTUBE,
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

    print(f"\n[youtube] Guardadas {total_saved} filas de aspectos en silver.aspect_results.")
    print(f"[youtube] {comments_with_aspects}/{len(items)} comentarios tenían al menos un aspecto detectado.")


# --- Rama reseñas (Booking / TripAdvisor) ------------------------------------

def fetch_pending_resenas(conn, fuentes: list[str]) -> list[tuple[str, str, str, str]]:
    """Reseñas sin aspectos todavia. Devuelve (fuente, resena_id, hotel_id, texto)."""
    consultas = [SQL_PENDIENTES_RESENAS[f] for f in fuentes]
    sql = "\n    UNION ALL\n".join(consultas)
    with conn.cursor() as cur:
        cur.execute(sql, tuple(ANIO_MINIMO_RESENAS for _ in consultas))
        return cur.fetchall()


def parsear_resultado(fuente: str, resena_id: str, hotel_id: str, pred: dict) -> list[tuple]:
    """Convierte la salida de PyABSA para UNA reseña en filas (una por aspecto).
    Si no se detecta ningun aspecto devuelve una unica fila con aspecto y
    sentimiento en None, para marcarla como procesada y no reintentarla."""
    aspectos = pred.get("aspect") or []
    sentimientos = pred.get("sentiment") or []
    confianzas = pred.get("confidence") or []

    if not aspectos:
        return [(resena_id, hotel_id, None, None, None, fuente)]

    return [
        (resena_id, hotel_id, aspecto, sentimiento, float(confianza), fuente)
        for aspecto, sentimiento, confianza in zip(aspectos, sentimientos, confianzas)
    ]


def guardar_resenas(conn, filas: list[tuple]):
    if not filas:
        return
    with conn.cursor() as cur:
        psycopg2.extras.execute_values(
            cur,
            """
            INSERT INTO gold.nlp_aspectos_resenas
                (resena_id, hotel_id, aspecto, sentimiento, confianza, fuente)
            VALUES %s
            """,
            filas,
            page_size=500,
        )
    conn.commit()


def procesar_resenas(fuentes: list[str]):
    conn = get_db_connection()
    ensure_schema_resenas(conn)

    pendientes = fetch_pending_resenas(conn, fuentes)
    if not pendientes:
        print(f"[resenas] No hay reseñas nuevas de {', '.join(fuentes)}. Todo al día.")
        conn.close()
        return

    items = []
    for fuente, resena_id, hotel_id, texto in pendientes:
        limpio = clean_text(texto)
        if len(limpio) >= MIN_TEXT_LENGTH:
            items.append((fuente, resena_id, hotel_id, limpio))

    print(f"[resenas] {len(pendientes)} reseñas pendientes, {len(items)} con texto útil tras limpieza.")
    if not items:
        print("[resenas] Nada que procesar. Fin.")
        conn.close()
        return

    conn.close()
    extractor = cargar_extractor()

    total_filas = 0
    con_aspectos = 0
    for start in range(0, len(items), BATCH_SIZE):
        chunk = items[start:start + BATCH_SIZE]
        textos = [t for _, _, _, t in chunk]
        predicciones = extractor.predict(textos, save_result=False, print_result=False)

        filas = []
        for (fuente, resena_id, hotel_id, _), pred in zip(chunk, predicciones):
            nuevas = parsear_resultado(fuente, resena_id, hotel_id, pred)
            if nuevas[0][2] is not None:
                con_aspectos += 1
            filas.extend(nuevas)

        conn_bloque = get_db_connection()
        guardar_resenas(conn_bloque, filas)
        conn_bloque.close()
        total_filas += len(filas)

        print(f"  -> {min(start + BATCH_SIZE, len(items))}/{len(items)} reseñas procesadas y guardadas...")

    print(f"\n[resenas] Guardadas {total_filas} filas en gold.nlp_aspectos_resenas.")
    print(f"[resenas] {con_aspectos}/{len(items)} reseñas tenían al menos un aspecto detectado.")


# --- Entrada -----------------------------------------------------------------

def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Extraccion de aspectos por lotes para YouTube, Booking y TripAdvisor.",
    )
    parser.add_argument(
        "--source",
        choices=FUENTES,
        default="todas",
        help="Fuente a procesar. 'resenas' = booking + tripadvisor; 'todas' = esas dos y youtube.",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)

    resenas = fuentes_de_resenas(args.source)
    if resenas:
        procesar_resenas(resenas)

    if args.source in ("youtube", "todas"):
        procesar_youtube()


if __name__ == "__main__":
    main()
