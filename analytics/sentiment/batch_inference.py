"""Inferencia de Sentimiento por Lotes -- todas las fuentes en un solo script.

Unifica lo que antes estaba partido en dos sitios (punto 4 de la revision de
codigo): este script, que solo hacia YouTube, y el notebook manual
analytics/tarea2/nlp_sentimiento_2_1.ipynb, que hacia Booking + TripAdvisor
fuera de Airflow. Ahora es un unico comando parametrizado por fuente, que
Airflow puede lanzar sin que nadie abra un notebook a mano.

    python analytics/sentiment/batch_inference.py --source youtube
    python analytics/sentiment/batch_inference.py --source booking
    python analytics/sentiment/batch_inference.py --source tripadvisor
    python analytics/sentiment/batch_inference.py --source resenas   # booking + tripadvisor
    python analytics/sentiment/batch_inference.py --source todas

Son dos pipelines distintos de verdad, no dos copias del mismo: se mantiene cada
uno tal y como estaba, porque cambiarlos invalidaria los resultados ya
calculados y guardados en Azure.

  youtube      Comentarios sueltos, muchos fuera de tema (hablan del video o del
               canal), sin ubicacion. Pasa primero un filtro de relevancia
               zero-shot y luego un clasificador de 3 clases
               (positive/neutral/negative). Escribe en bronze.ml_sentiment_results.

  resenas      Reseñas de alojamiento (Booking, TripAdvisor) desde 2022. Ya son
               todas sobre la estancia, asi que no hay filtro de relevancia, y
               el modelo devuelve una nota de 1 a 5 estrellas. Se les resuelve
               el hexagono H3 del establecimiento en el momento del analisis.
               Escribe en gold.nlp_sentimiento_resenas, que es la tabla que
               consume el modelo dbt gold_sentimiento_h3.

Pendiente de decidir por el equipo: YouTube no llega a la capa Gold. Si se
aborda, tiene que ser SIN tocar lo que ya hay -- nada de reprocesar encima.

Lo que NO se puede hacer: sustituir las filas de bronze.ml_sentiment_results
por notas de estrellas. Esa tabla no es solo un resultado: su columna
is_relevant sale por el modelo dbt silver_sentiment_results y es lo que
export_general_corpus.py usa para decidir que comentarios de YouTube entran en
el corpus del Modelo A de BERTopic. Pisarlas vaciaria el corpus de temas en
silencio. Ademas la tabla tiene UNIQUE (source, source_id), asi que no admite
una segunda fila por comentario: una nota de estrellas tendria que ir a una
tabla nueva al lado, nunca encima.

Y el cuello de botella real no es el modelo, es la ubicacion: extract_toponyms.py
solo procesa losviajeros_message, asi que YouTube no tiene ninguna fila en
gold.geo_mentions. Sin ubicacion no hay h3_index, y gold_sentimiento_h3 filtra
por h3_index IS NOT NULL. El primer paso seria extender extract_toponyms.py a
YouTube (filas nuevas, con su propio source y ON CONFLICT DO NOTHING: no toca
nada de lo existente), y solo despues plantearse la nota de 1 a 5.

Incremental en las dos ramas: si se repite, solo procesa lo que no tenga
resultado todavia. La de reseñas ademas guarda por bloques de ~320, asi que un
corte solo pierde el bloque a medias.
"""

import argparse
import os
import re
import sys
import time

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv(override=True)

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

# --- Modelos -----------------------------------------------------------------
# YouTube: 3 clases. Reseñas: 1-5 estrellas (es el que alimenta Gold).
MODEL_NAME_YOUTUBE = "cardiffnlp/twitter-xlm-roberta-base-sentiment"
MODEL_NAME_RESENAS = "nlptown/bert-base-multilingual-uncased-sentiment"
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

SOURCE_YOUTUBE = "youtube_comment"
BATCH_SIZE = 32
FILAS_POR_CHECKPOINT = 320  # reseñas: se guarda en gold cada ~10 lotes
MIN_TEXT_LENGTH = 3
ANIO_MINIMO_RESENAS = 2021  # el filtro real es "> 2021", es decir, de 2022 en adelante

URL_RE = re.compile(r"https?://\S+")

FUENTES = ("youtube", "booking", "tripadvisor", "resenas", "todas")


def fuentes_de_resenas(source: str) -> list[str]:
    """Que fuentes de reseñas toca procesar para el --source pedido."""
    if source in ("resenas", "todas"):
        return ["tripadvisor", "booking"]
    if source in ("booking", "tripadvisor"):
        return [source]
    return []


# --- SQL ---------------------------------------------------------------------

DDL_GOLD_SENTIMIENTO = """
    CREATE TABLE IF NOT EXISTS gold.nlp_sentimiento_resenas (
        resena_id text,
        hotel_id text,
        score integer,
        h3_index text,
        fuente text
    )
"""

DDL_BRONZE_SENTIMIENTO = """
    CREATE SCHEMA IF NOT EXISTS bronze;
    CREATE TABLE IF NOT EXISTS bronze.ml_sentiment_results (
        id              SERIAL PRIMARY KEY,
        source          TEXT NOT NULL,
        source_id       TEXT NOT NULL,
        text            TEXT NOT NULL,
        label           TEXT NOT NULL,
        score           REAL NOT NULL,
        model_name      TEXT NOT NULL,
        processed_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
        is_relevant     BOOLEAN NOT NULL DEFAULT true,
        relevance_score REAL,
        UNIQUE (source, source_id)
    );
"""

INDICES_GOLD_SENTIMIENTO = (
    "CREATE INDEX IF NOT EXISTS idx_nlp_sentimiento_hotel_id ON gold.nlp_sentimiento_resenas (hotel_id)",
    "CREATE INDEX IF NOT EXISTS idx_nlp_sentimiento_h3_index ON gold.nlp_sentimiento_resenas (h3_index)",
)

# bronze_youtube_comments (con prefijo) es la tabla que declara dbt en
# models/silver/sources.yml y la que llena la ingesta; bronze.youtube_comments,
# sin prefijo, era el destino de la migracion antigua desde Neon.
SQL_PENDIENTES_YOUTUBE = """
    SELECT c.comment_id, c.text
    FROM bronze.bronze_youtube_comments c
    LEFT JOIN bronze.ml_sentiment_results r
        ON r.source = %s AND r.source_id = c.comment_id
    WHERE r.id IS NULL AND c.text IS NOT NULL
"""

SQL_PENDIENTES_TRIPADVISOR = """
    SELECT 'tripadvisor' AS fuente, r.review_id::text AS resena_id,
           r.location_id::text AS hotel_id, r.texto AS review_text
    FROM silver.tripadvisor_resenas r
    WHERE r.texto IS NOT NULL AND EXTRACT(YEAR FROM r.fecha_publicacion) > %s
      AND NOT EXISTS (
          SELECT 1 FROM gold.nlp_sentimiento_resenas g
          WHERE g.resena_id = r.review_id::text AND g.fuente = 'tripadvisor'
      )
"""

SQL_PENDIENTES_BOOKING = """
    SELECT 'booking' AS fuente, b.review_id AS resena_id,
           b.establishment_id AS hotel_id, b.review_text
    FROM silver.silver_booking_reviews b
    WHERE b.review_text IS NOT NULL AND EXTRACT(YEAR FROM b.review_date) > %s
      AND NOT EXISTS (
          SELECT 1 FROM gold.nlp_sentimiento_resenas g
          WHERE g.resena_id = b.review_id AND g.fuente = 'booking'
      )
"""

SQL_PENDIENTES_RESENAS = {
    "tripadvisor": SQL_PENDIENTES_TRIPADVISOR,
    "booking": SQL_PENDIENTES_BOOKING,
}

# TripAdvisor ya trae geometria (EPSG:32628); Booking solo lat/long, asi que se
# construye el punto al vuelo. Ambas se reproyectan al SRID real de la malla.
SQL_CRUCE_H3 = """
    WITH establecimientos_geo AS (
        SELECT location_id::text AS hotel_id, ST_Transform(geometry, {srid}) AS geometry
        FROM silver.tripadvisor_ubicaciones

        UNION ALL

        SELECT establishment_id AS hotel_id,
               ST_Transform(ST_SetSRID(ST_MakePoint(longitude, latitude), 4326), {srid}) AS geometry
        FROM silver.silver_booking_establishments
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL
    )
    SELECT e.hotel_id, h.h3_index
    FROM establecimientos_geo e
    JOIN silver.silver_h3_grid h ON ST_Contains(h.geometry, e.geometry)
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


def clean_text(text: str) -> str:
    text = URL_RE.sub("", text or "")
    return re.sub(r"\s+", " ", text).strip()


def prepare_items(pending: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Limpia texto y descarta lo demasiado corto para aportar señal."""
    items = []
    for comment_id, text in pending:
        cleaned = clean_text(text)
        if len(cleaned) >= MIN_TEXT_LENGTH:
            items.append((comment_id, cleaned))
    return items


def estrellas(label: str) -> int:
    """nlptown devuelve '4 stars' / '1 star' -> 4 / 1."""
    return int(label.split()[0])


# --- Rama YouTube ------------------------------------------------------------

def ensure_schema_youtube(conn):
    with conn.cursor() as cur:
        cur.execute(DDL_BRONZE_SENTIMIENTO)
    conn.commit()


def fetch_pending_comments(conn) -> list[tuple[str, str]]:
    """Comentarios de YouTube sin resultado todavia. Devuelve (comment_id, text)."""
    with conn.cursor() as cur:
        cur.execute(SQL_PENDIENTES_YOUTUBE, (SOURCE_YOUTUBE,))
        return cur.fetchall()


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
            "source": SOURCE_YOUTUBE,
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

    from transformers import pipeline

    print(f"Cargando modelo {MODEL_NAME_YOUTUBE!r}...")
    classifier = pipeline("sentiment-analysis", model=MODEL_NAME_YOUTUBE, tokenizer=MODEL_NAME_YOUTUBE)

    texts = [text for _, text, _ in relevant]
    predictions = classifier(texts, batch_size=BATCH_SIZE, truncation=True, max_length=512)

    return [
        {
            "source": SOURCE_YOUTUBE,
            "source_id": comment_id,
            "text": text,
            "label": pred["label"],
            "score": float(pred["score"]),
            "model_name": MODEL_NAME_YOUTUBE,
            "is_relevant": True,
            "relevance_score": relevance_score,
        }
        for (comment_id, text, relevance_score), pred in zip(relevant, predictions)
    ]


def print_summary(results: list[dict]) -> None:
    counts = {}
    for r in results:
        counts[r["label"]] = counts.get(r["label"], 0) + 1
    print(f"\nGuardados {len(results)} resultados nuevos en bronze.ml_sentiment_results.")
    print("Distribución:", counts)


def save_results(conn, results: list[dict]):
    if not results:
        return
    with conn.cursor() as cur:
        psycopg2.extras.execute_batch(
            cur,
            """
            INSERT INTO bronze.ml_sentiment_results
                (source, source_id, text, label, score, model_name, is_relevant, relevance_score)
            VALUES (%(source)s, %(source_id)s, %(text)s, %(label)s, %(score)s, %(model_name)s,
                    %(is_relevant)s, %(relevance_score)s)
            ON CONFLICT (source, source_id) DO NOTHING
            """,
            results,
        )
    conn.commit()


def procesar_youtube():
    from transformers import pipeline

    conn = get_db_connection()
    ensure_schema_youtube(conn)

    pending = fetch_pending_comments(conn)
    if not pending:
        print("[youtube] No hay comentarios nuevos por procesar. Todo al día.")
        conn.close()
        return

    items = prepare_items(pending)
    print(f"[youtube] {len(pending)} comentarios pendientes, {len(items)} con texto útil tras limpieza.")
    if not items:
        print("[youtube] Nada que procesar (todo lo pendiente quedó vacío tras limpiar). Fin.")
        conn.close()
        return

    print(f"Cargando modelo de relevancia {TOPIC_MODEL_NAME!r}...")
    topic_classifier = pipeline("zero-shot-classification", model=TOPIC_MODEL_NAME, device=-1)
    texts = [text for _, text in items]
    relevance = classify_relevance(topic_classifier, texts)

    relevant, off_topic = split_by_relevance(items, relevance)
    print(f"[youtube] {len(relevant)} relevantes, {len(off_topic)} descartados por tema.")

    results = build_off_topic_results(off_topic) + run_sentiment(relevant)
    save_results(conn, results)
    print_summary(results)

    conn.close()


# --- Rama reseñas (Booking / TripAdvisor) ------------------------------------

def ensure_schema_resenas(conn):
    with conn.cursor() as cur:
        cur.execute(DDL_GOLD_SENTIMIENTO)
    conn.commit()


def crear_indices_resenas(conn):
    with conn.cursor() as cur:
        for sql in INDICES_GOLD_SENTIMIENTO:
            cur.execute(sql)
    conn.commit()


def fetch_pending_resenas(conn, fuentes: list[str]) -> list[tuple[str, str, str, str]]:
    """Reseñas sin sentimiento todavia. Devuelve (fuente, resena_id, hotel_id, texto)."""
    consultas = [SQL_PENDIENTES_RESENAS[f] for f in fuentes]
    sql = "\n    UNION ALL\n".join(consultas)
    with conn.cursor() as cur:
        cur.execute(sql, tuple(ANIO_MINIMO_RESENAS for _ in consultas))
        return cur.fetchall()


def mapa_hotel_h3(conn) -> dict[str, str]:
    """hotel_id -> h3_index, resuelto una sola vez antes de procesar."""
    with conn.cursor() as cur:
        cur.execute("SELECT ST_SRID(geometry) FROM silver.silver_h3_grid LIMIT 1")
        fila = cur.fetchone()
        if not fila:
            raise SystemExit("silver.silver_h3_grid esta vacia: no se puede asignar hexagono.")
        srid = fila[0]
        cur.execute(SQL_CRUCE_H3.format(srid=srid))
        mapa = dict(cur.fetchall())
    print(f"[resenas] SRID de la malla H3: {srid}. Establecimientos con hexagono: {len(mapa)}.")
    return mapa


def guardar_resenas(conn, filas: list[tuple]):
    if not filas:
        return
    with conn.cursor() as cur:
        psycopg2.extras.execute_values(
            cur,
            """
            INSERT INTO gold.nlp_sentimiento_resenas (resena_id, hotel_id, score, h3_index, fuente)
            VALUES %s
            """,
            filas,
            page_size=500,
        )
    conn.commit()


def procesar_resenas(fuentes: list[str]):
    from transformers import pipeline
    import torch

    conn = get_db_connection()
    ensure_schema_resenas(conn)

    pendientes = fetch_pending_resenas(conn, fuentes)
    if not pendientes:
        print(f"[resenas] No hay reseñas nuevas de {', '.join(fuentes)}. Todo al día.")
        conn.close()
        return

    por_fuente = {}
    for fuente, *_ in pendientes:
        por_fuente[fuente] = por_fuente.get(fuente, 0) + 1
    print(f"[resenas] {len(pendientes)} reseñas nuevas a analizar: {por_fuente}")

    hotel_h3 = mapa_hotel_h3(conn)
    conn.close()  # cargar el modelo tarda; no dejar la conexion abierta e inactiva

    dispositivo = 0 if torch.cuda.is_available() else -1
    print(f"Usando {'GPU' if dispositivo == 0 else 'CPU (sera mas lento)'}")
    print(f"Cargando modelo {MODEL_NAME_RESENAS!r}...")
    pipe = pipeline("text-classification", model=MODEL_NAME_RESENAS, device=dispositivo)

    total = len(pendientes)
    procesadas = 0
    inicio = time.time()

    for comienzo in range(0, total, FILAS_POR_CHECKPOINT):
        bloque = pendientes[comienzo:comienzo + FILAS_POR_CHECKPOINT]
        textos = [texto for _, _, _, texto in bloque]

        predicciones = []
        for i in range(0, len(textos), BATCH_SIZE):
            lote = textos[i:i + BATCH_SIZE]
            predicciones.extend(pipe(lote, batch_size=BATCH_SIZE, truncation=True, max_length=512))

        filas = [
            (resena_id, hotel_id, estrellas(pred["label"]), hotel_h3.get(hotel_id), fuente)
            for (fuente, resena_id, hotel_id, _), pred in zip(bloque, predicciones)
        ]

        # Conexion nueva por bloque: el INSERT es rapido, y evita que Azure
        # cierre la conexion por inactividad durante la inferencia.
        conn_bloque = get_db_connection()
        guardar_resenas(conn_bloque, filas)
        conn_bloque.close()

        procesadas += len(bloque)
        transcurrido = time.time() - inicio
        velocidad = procesadas / transcurrido if transcurrido > 0 else 0
        eta_min = ((total - procesadas) / velocidad / 60) if velocidad > 0 else 0
        print(f"  Guardadas {procesadas}/{total} -- {velocidad:.1f} reseñas/seg -- estimado restante: {eta_min:.0f} min")

    conn = get_db_connection()
    crear_indices_resenas(conn)
    conn.close()
    print(f"\n[resenas] Completado. Procesadas y guardadas en esta ejecucion: {procesadas}.")


# --- Entrada -----------------------------------------------------------------

def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Sentimiento por lotes para YouTube, Booking y TripAdvisor.",
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
