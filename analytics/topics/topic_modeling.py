"""Issue #19 — Modelado de Topicos (BERTopic). MODELO A -- "Vision general".

Dos fuentes, sin pretension de ubicacion:
- YouTube: silver.sentiment_results (source='youtube_comment', is_relevant=true).
  Ya viene limpio y filtrado por relevancia tematica (Issue #17).
- LosViajeros SIN ubicacion detectada (gold.geo_mentions no tiene fila para
  ese mensaje, ver analytics/geo/extract_toponyms.py). Los que SI tienen
  ubicacion (46% de cobertura) van al MODELO B (Booking + TripAdvisor +
  LosViajeros georreferenciado): por su volumen (55.787 reseñas de Booking)
  ese modelo se entrena aparte con GPU en Colab, no aqui -- ver
  analytics/topics/export_geo_corpus.py y topic_modeling_geo_colab.ipynb.

Antes este script era solo YouTube y los mensajes de LosViajeros sin
ubicacion (854 de 1.590, el 54%) no entraban en ningun modelo: no tenian
ubicacion para el B, y este script solo miraba YouTube. Su texto sigue
siendo opinion valida aunque el gazetteer no encontrara un lugar, asi que
ahora se suman aqui.

No hay campo `periodo_covid` en la fuente (verificado contra la BD real): es
un concepto del documento de planificacion que nunca se implemento, asi que
no se filtra por el aqui.

- Primera ejecucion: entrena BERTopic sobre todo el corpus elegible y guarda
  el modelo en disco (bertopic_model/) para no tener que re-entrenar.
- Ejecuciones siguientes: si ya existe el modelo guardado, solo transforma
  (topic_model.transform) los documentos nuevos que aun no tengan topico
  asignado en gold.nlp_topics -- no reentrena desde cero.
"""

import hashlib
import os
import re
from pathlib import Path

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv(override=True)

SOURCE_YOUTUBE = "youtube_comment"
SOURCE_LOSVIAJEROS = "losviajeros_message"
SOURCES = (SOURCE_YOUTUBE, SOURCE_LOSVIAJEROS)

EMBEDDING_MODEL_NAME = "paraphrase-multilingual-mpnet-base-v2"
MODEL_NAME = f"BERTopic+{EMBEDDING_MODEL_NAME} (modelo A: general)"
MIN_TOPIC_SIZE = 15
MIN_TEXT_LENGTH = 15  # BERTopic necesita texto con contenido, no solo relevancia de tema
MIN_CORPUS_SIZE = 500  # por debajo de esto los topicos salen incoherentes (ver docs/models.md)

MODEL_DIR = Path(__file__).resolve().parent / "bertopic_model"

# Stopwords ES+EN para el vectorizador de palabras representativas de cada topico.
# BERTopic con language="multilingual" no trae stopwords en espanol por defecto,
# asi que sin esto las etiquetas de topico salen como "de, que, la, el, en, no".
SPANISH_STOPWORDS = {
    "de", "la", "que", "el", "en", "y", "a", "los", "del", "se", "las", "por",
    "un", "para", "con", "no", "una", "su", "al", "lo", "como", "mas", "más",
    "pero", "sus", "le", "ya", "o", "este", "si", "sí", "porque", "esta",
    "entre", "cuando", "muy", "sin", "sobre", "tambien", "también", "me",
    "hasta", "hay", "donde", "dónde", "quien", "quién", "desde", "todo",
    "nos", "durante", "todos", "uno", "les", "ni", "contra", "otros", "ese",
    "eso", "ante", "ellos", "e", "esto", "mi", "antes", "algunos", "que",
    "unos", "yo", "otro", "otras", "otra", "el", "tanto", "esa", "estos",
    "mucho", "quienes", "nada", "muchos", "cual", "cuál", "poco", "ella",
    "estar", "estas", "algunas", "algo", "nosotros", "mi", "mis", "tu", "tú",
    "te", "ti", "tus", "ellas", "nosotras", "vosotros", "vosotras", "os",
    "mio", "mío", "mia", "mía", "tuyo", "tuya", "suyo", "suya", "es", "soy",
    "eres", "somos", "sois", "son", "esté", "esta", "estan", "están", "fue",
    "ser", "voy", "vamos", "va", "van", "puede", "pueden", "hace", "hacer",
    "gracias", "hola", "saludos", "pues", "asi", "así", "aqui", "aquí",
    "alli", "allí", "ahi", "ahí",
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
    schema_path = Path(__file__).resolve().parents[2] / "sql" / "gold_nlp_topics_schema.sql"
    with conn.cursor() as cur:
        cur.execute(schema_path.read_text())
    conn.commit()


QUOTE_RE = re.compile(r".*\bEscribi[oó]:\s*", re.DOTALL)


def strip_nested_quotes(text: str) -> str:
    match = QUOTE_RE.match(text)
    return text[match.end():].strip() if match else text.strip()


def stable_id(texto_limpio: str) -> str:
    """Hash MD5 del texto ya limpio -- id_mensaje no es fiable, ver analytics/geo/extract_toponyms.py."""
    return hashlib.md5(texto_limpio.encode("utf-8")).hexdigest()


def fetch_eligible_youtube(conn) -> list[tuple[str, str, str]]:
    """(source, source_id, text) de comentarios de YouTube ya limpios y relevantes."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT source_id, text
            FROM silver.sentiment_results
            WHERE source = %s
              AND is_relevant = true
              AND length(text) > %s
            """,
            (SOURCE_YOUTUBE, MIN_TEXT_LENGTH),
        )
        return [(SOURCE_YOUTUBE, sid, text) for sid, text in cur.fetchall()]


def fetch_eligible_losviajeros_sin_ubicacion(conn) -> list[tuple[str, str, str]]:
    """(source, source_id, text) de mensajes de LosViajeros SIN ubicacion detectada
    (los que si tienen ubicacion van al Modelo B, ver export_geo_corpus.py). Cruce
    con gold.geo_mentions por hash del texto limpio, no por id_mensaje (no es
    fiable en esta tabla, ver analytics/geo/extract_toponyms.py)."""
    with conn.cursor() as cur:
        cur.execute("SELECT texto_mensaje_limpio FROM silver.stg_losviajeros_mensajes")
        raw_texts = [r[0] for r in cur.fetchall()]
        cur.execute("SELECT source_id FROM gold.geo_mentions WHERE source = %s", (SOURCE_LOSVIAJEROS,))
        geo_ids = {r[0] for r in cur.fetchall()}
    items = []
    seen = set()
    for raw_text in raw_texts:
        cleaned = strip_nested_quotes(raw_text)
        if len(cleaned) <= MIN_TEXT_LENGTH:
            continue
        sid = stable_id(cleaned)
        if sid not in geo_ids and sid not in seen:
            seen.add(sid)
            items.append((SOURCE_LOSVIAJEROS, sid, cleaned))
    return items


def fetch_already_processed(conn) -> set[tuple[str, str]]:
    with conn.cursor() as cur:
        cur.execute("SELECT source, source_id FROM gold.nlp_topics WHERE source = ANY(%s)", (list(SOURCES),))
        return {(row[0], row[1]) for row in cur.fetchall()}


def save_results(conn, results: list[dict]):
    if not results:
        return
    with conn.cursor() as cur:
        psycopg2.extras.execute_batch(
            cur,
            """
            INSERT INTO gold.nlp_topics
                (source, source_id, text, topic_id, topic_label, topic_size, probability, model_name)
            VALUES (%(source)s, %(source_id)s, %(text)s, %(topic_id)s, %(topic_label)s,
                    %(topic_size)s, %(probability)s, %(model_name)s)
            ON CONFLICT (source, source_id) DO NOTHING
            """,
            results,
        )
    conn.commit()


def build_results(pending: list[tuple[str, str, str]], topics: list[int], probs, topic_info: dict) -> list[dict]:
    results = []
    for (source, source_id, text), topic_id, prob in zip(pending, topics, probs):
        label, size = topic_info.get(topic_id, (None, None))
        results.append({
            "source": source,
            "source_id": source_id,
            "text": text,
            "topic_id": int(topic_id),
            "topic_label": label,
            "topic_size": size,
            "probability": float(prob) if prob is not None else None,
            "model_name": MODEL_NAME,
        })
    return results


def build_topic_info(topic_model) -> dict:
    """topic_id -> (top palabras como label legible, tamano del topico)."""
    info = {}
    for row in topic_model.get_topic_info().itertuples():
        words = [w for w, _ in topic_model.get_topic(row.Topic)] if row.Topic != -1 else []
        info[row.Topic] = (", ".join(words[:6]) if words else "outlier / sin tema claro", row.Count)
    return info


def build_topic_model(embedding_model):
    """HDBSCAN con cluster_selection_method='leaf' en vez del 'eom' por defecto:
    'eom' prioriza pocos clusters grandes y estables -- con este corpus (mucha
    charla generica sobre Tenerife entremezclada con contenido especifico) eso
    producia un unico topico gigante con el 70% de los documentos. 'leaf'
    extrae clusters mas pequenos y especificos en vez de los mas "estables".
    """
    from bertopic import BERTopic
    from bertopic.vectorizers import ClassTfidfTransformer
    from hdbscan import HDBSCAN
    from sklearn.feature_extraction.text import CountVectorizer, ENGLISH_STOP_WORDS

    hdbscan_model = HDBSCAN(
        min_cluster_size=MIN_TOPIC_SIZE,
        min_samples=5,  # menos exigente que el default (=min_cluster_size) para marcar ruido
        metric="euclidean",
        cluster_selection_method="leaf",  # temas mas especificos que 'eom' (que da pocos temas muy anchos)
        prediction_data=True,
    )
    vectorizer_model = CountVectorizer(
        stop_words=list(ENGLISH_STOP_WORDS | SPANISH_STOPWORDS),
        ngram_range=(1, 2),
        min_df=2,
    )
    return BERTopic(
        embedding_model=embedding_model,
        hdbscan_model=hdbscan_model,
        vectorizer_model=vectorizer_model,
        ctfidf_model=ClassTfidfTransformer(reduce_frequent_words=True),
        min_topic_size=MIN_TOPIC_SIZE,
        language="multilingual",
    )


def reassign_outliers(topic_model, texts: list[str], topics: list[int], probs) -> tuple[list[int], list]:
    """Reasigna los outliers (-1) al topico existente mas parecido por
    contenido (c-TF-IDF) en vez de dejarlos sin clasificar. Necesario en este
    corpus: sin este paso, entre el 83% y el 88% de los documentos quedaba
    como -1 con cualquier combinacion de embedding/hiperparametros de HDBSCAN
    probada (ver analytics/contexto.md para el detalle de las pruebas). La
    probabilidad de los reasignados se pierde (era la de "no encaja en nada"),
    asi que se guarda como None en vez de un numero que no significa nada.
    """
    was_outlier = [t == -1 for t in topics]
    n_before = sum(was_outlier)
    new_topics = topic_model.reduce_outliers(texts, topics, strategy="c-tf-idf")
    n_after = new_topics.count(-1)
    print(f"Outliers reasignados por similitud de contenido: {n_before} -> {n_after}.")
    new_probs = [None if wo else p for wo, p in zip(was_outlier, probs)]
    return new_topics, new_probs


def train_and_save(texts: list[str]):
    from sentence_transformers import SentenceTransformer

    print(f"Cargando embedding model {EMBEDDING_MODEL_NAME!r}...")
    embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)

    print(f"Entrenando BERTopic sobre {len(texts)} documentos (min_topic_size={MIN_TOPIC_SIZE})...")
    topic_model = build_topic_model(embedding_model)
    topics, probs = topic_model.fit_transform(texts)
    topics, probs = reassign_outliers(topic_model, texts, topics, probs)
    # Recalcula las representaciones (palabras top, tamanos) con el corpus completo
    # ya reasignado -- si no, las etiquetas seguirian basadas solo en los docs
    # "core" originales de cada topico, ignorando los recien incorporados.
    # OJO: sin pasar vectorizer_model/ctfidf_model explicitamente, update_topics
    # los resetea a los de BERTopic por defecto (sin stopwords) en vez de
    # reutilizar los personalizados del modelo -- volvian las etiquetas
    # "que, de, no, los, la, el".
    topic_model.update_topics(
        texts,
        topics=topics,
        vectorizer_model=topic_model.vectorizer_model,
        ctfidf_model=topic_model.ctfidf_model,
    )

    MODEL_DIR.parent.mkdir(parents=True, exist_ok=True)
    topic_model.save(str(MODEL_DIR), serialization="safetensors", save_ctfidf=True, save_embedding_model=EMBEDDING_MODEL_NAME)
    print(f"Modelo guardado en {MODEL_DIR} (no hace falta reentrenar en la siguiente ejecucion).")

    return topic_model, topics, probs


def transform_with_saved_model(texts: list[str]):
    from bertopic import BERTopic

    print(f"Cargando modelo guardado de {MODEL_DIR}...")
    topic_model = BERTopic.load(str(MODEL_DIR))
    print(f"Asignando topico a {len(texts)} documentos nuevos (sin reentrenar)...")
    topics, probs = topic_model.transform(texts)
    # No se llama a update_topics aqui: un lote incremental pequeno no debe
    # reescribir las representaciones de topico aprendidas con el corpus
    # completo de entrenamiento.
    topics, probs = reassign_outliers(topic_model, texts, topics, probs)
    return topic_model, topics, probs


def print_summary(topic_info: dict) -> None:
    print("\nTopicos:")
    for topic_id, (label, size) in sorted(topic_info.items(), key=lambda kv: -kv[1][1]):
        tag = "outlier" if topic_id == -1 else f"#{topic_id}"
        print(f"  {tag:>8} ({size:>4} docs): {label}")


def main():
    conn = get_db_connection()
    ensure_schema(conn)

    eligible = fetch_eligible_youtube(conn) + fetch_eligible_losviajeros_sin_ubicacion(conn)
    processed = fetch_already_processed(conn)
    pending = [item for item in eligible if (item[0], item[1]) not in processed]

    print(f"{len(eligible)} documentos elegibles (YouTube + LosViajeros sin ubicacion), {len(pending)} pendientes de topico.")
    if not pending:
        print("No hay documentos nuevos por procesar. Todo al día.")
        conn.close()
        return

    texts = [text for _, _, text in pending]
    conn.close()  # cargar el modelo (embeddings) tarda; no dejar la conexion abierta e inactiva

    if MODEL_DIR.exists():
        topic_model, topics, probs = transform_with_saved_model(texts)
    else:
        if len(eligible) < MIN_CORPUS_SIZE:
            print(
                f"Aviso: solo hay {len(eligible)} documentos elegibles (< {MIN_CORPUS_SIZE} recomendados). "
                "Los topicos pueden salir poco coherentes, pero se entrena igualmente."
            )
        topic_model, topics, probs = train_and_save(texts)

    topic_info = build_topic_info(topic_model)
    results = build_results(pending, topics, probs, topic_info)

    save_conn = get_db_connection()
    save_results(save_conn, results)
    save_conn.close()

    print(f"\nGuardados {len(results)} resultados nuevos en gold.nlp_topics.")
    print_summary(topic_info)


if __name__ == "__main__":
    main()
