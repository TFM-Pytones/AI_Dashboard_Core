"""Fase 1 del RAG (ver plan_rag.md) -- Construye gold.nlp_chunks: el corpus de
gold.nlp_topics fragmentado y enriquecido con los metadatos que permiten
filtrar ANTES de la busqueda vectorial (municipio, hexagono, fecha, pais,
topico de BERTopic).

Se puede volver a ejecutar: los fragmentos que ya existen conservan su texto y
su embedding, y solo se actualizan los metadatos que hayan cambiado (por
ejemplo el tema, tras analytics/topics/volcar_topicos.py). Los fragmentos
nuevos entran sin embedding: calcularlo despues con export_chunks.py, el
notebook de Colab e import_embeddings.py.

Cada fuente llega a su ubicacion por un camino distinto:
- booking_review     -> review_id -> establishment_id -> geometry -> ST_Contains
                        contra gold_h3_master (da h3_index y municipio).
- tripadvisor_review -> review_id -> location_id -> silver_tripadvisor_ubicaciones,
                        que ya trae municipio resuelto, + geometry para el hexagono.
- losviajeros_message-> source_id (hash MD5) -> gold.geo_mentions, que da un
                        nombre de lugar (municipio o zona) pero NO coordenadas:
                        por eso estas filas no llevan h3_index. La fecha del
                        mensaje se recupera de silver por el mismo hash.
- youtube_comment    -> sin ubicacion por diseño (percepcion de marca global);
                        fecha del comentario desde silver.

El municipio se unifica al nombre de gold.gold_municipio_master, para que las
agregaciones por municipio crucen con el resto de tablas.

Uso:
    python analytics/rag/build_chunks.py
"""

import hashlib
import os
import re
import sys
from pathlib import Path

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

from filtros import normalizar

load_dotenv(override=True)

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

# Por debajo de este umbral el documento entra entero (el 95,5% del corpus).
MAX_LEN_SIN_TROCEAR = 1000
CHUNK_SIZE = 800
CHUNK_OVERLAP = 100

FIN_DE_FRASE = re.compile(r"(?<=[.!?\n])\s+")

# Mismo recorte de cita anidada que analytics/topics/export_*_corpus.py: el
# source_id de LosViajeros es el MD5 del texto ya recortado.
QUOTE_RE = re.compile(r".*\bEscribi[oó]:\s*", re.DOTALL)

# Nombre oficial largo frente al nombre de gold_municipio_master. Las
# diferencias de tildes no hace falta declararlas: las cubre normalizar().
ALIAS_MUNICIPIO = {
    "san cristobal de la laguna": "la laguna",
    "vilaflor de chasna": "vilaflor",
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
    schema_path = Path(__file__).resolve().parents[2] / "sql" / "gold_nlp_chunks_schema.sql"
    with conn.cursor() as cur:
        cur.execute(schema_path.read_text(encoding="utf-8"))
    conn.commit()


def split_text(text: str) -> list[str]:
    """Trocea por frases hasta CHUNK_SIZE, con solape para no cortar una idea
    justo en la frontera. Una frase mas larga que CHUNK_SIZE se deja entera:
    partirla a medias produciria un fragmento sin sentido."""
    text = text.strip()
    if len(text) <= MAX_LEN_SIN_TROCEAR:
        return [text]

    frases = [f for f in FIN_DE_FRASE.split(text) if f.strip()]
    chunks: list[str] = []
    actual = ""
    for frase in frases:
        if actual and len(actual) + len(frase) + 1 > CHUNK_SIZE:
            chunks.append(actual.strip())
            cola = actual[-CHUNK_OVERLAP:] if len(actual) > CHUNK_OVERLAP else actual
            actual = cola + " " + frase
        else:
            actual = f"{actual} {frase}".strip()
    if actual.strip():
        chunks.append(actual.strip())
    return chunks or [text]


# -- Consultas por fuente -----------------------------------------------------
# Cada una devuelve las mismas 11 columnas para poder tratarlas igual despues.

SQL_BOOKING = """
    SELECT t.source, t.source_id, t.text, t.topic_id, t.topic_label,
           m.municipio, NULL::text AS zona, m.h3_index,
           r.review_date AS fecha, r.reviewer_country AS pais, r.rating::real
    FROM gold.nlp_topics t
    JOIN silver.silver_booking_reviews r ON r.review_id = t.source_id
    LEFT JOIN silver.silver_booking_establishments e ON e.establishment_id = r.establishment_id
    LEFT JOIN gold.gold_h3_master m ON ST_Contains(m.geometry, e.geometry)
    WHERE t.source = 'booking_review'
"""

# DISTINCT ON: silver_tripadvisor_resenas tiene 807 filas para 804 review_id
# distintos; sin esto las 3 duplicadas entrarian dos veces.
SQL_TRIPADVISOR = """
    SELECT DISTINCT ON (t.source_id)
           t.source, t.source_id, t.text, t.topic_id, t.topic_label,
           u.municipio, NULL::text AS zona, m.h3_index,
           r.fecha_publicacion AS fecha, NULL::text AS pais, r.rating::real
    FROM gold.nlp_topics t
    JOIN silver.silver_tripadvisor_resenas r ON r.review_id = t.source_id
    LEFT JOIN silver.silver_tripadvisor_ubicaciones u ON u.location_id = r.location_id
    LEFT JOIN gold.gold_h3_master m ON ST_Contains(m.geometry, u.geometry)
    WHERE t.source = 'tripadvisor_review'
    ORDER BY t.source_id
"""

# geo_mentions da nombre de lugar, no coordenadas -> h3_index queda NULL. La
# fecha se rellena en Python (ver fechas_losviajeros).
SQL_LOSVIAJEROS = """
    SELECT t.source, t.source_id, t.text, t.topic_id, t.topic_label,
           CASE WHEN g.place_type = 'municipio' THEN g.place_name END AS municipio,
           CASE WHEN g.place_type = 'zona'      THEN g.place_name END AS zona,
           NULL::text AS h3_index,
           NULL::date AS fecha, NULL::text AS pais, NULL::real AS rating
    FROM gold.nlp_topics t
    LEFT JOIN gold.geo_mentions g
           ON g.source_id = t.source_id AND g.source = 'losviajeros_message'
    WHERE t.source = 'losviajeros_message'
"""

SQL_YOUTUBE = """
    SELECT DISTINCT ON (t.source_id)
           t.source, t.source_id, t.text, t.topic_id, t.topic_label,
           NULL::text AS municipio, NULL::text AS zona, NULL::text AS h3_index,
           c.fecha_comentario AS fecha, NULL::text AS pais, NULL::real AS rating
    FROM gold.nlp_topics t
    LEFT JOIN silver.silver_youtube_comentarios c ON c.comment_id = t.source_id
    WHERE t.source = 'youtube_comment'
    ORDER BY t.source_id, c.fecha_comentario
"""

CONSULTAS = {
    "booking_review": SQL_BOOKING,
    "tripadvisor_review": SQL_TRIPADVISOR,
    "losviajeros_message": SQL_LOSVIAJEROS,
    "youtube_comment": SQL_YOUTUBE,
}


def fetch_documentos(conn, sql: str) -> list[tuple]:
    with conn.cursor() as cur:
        cur.execute(sql)
        return cur.fetchall()


def fechas_losviajeros(conn) -> dict:
    """gold.nlp_topics no guarda la fecha del mensaje: se recupera de silver
    calculando el mismo hash del texto recortado que se usa como source_id. Si
    un texto aparece varias veces (moderadores re-pegando), vale la mas antigua."""
    fechas: dict = {}
    with conn.cursor() as cur:
        cur.execute("SELECT texto, fecha_mensaje FROM silver.silver_losviajeros_mensajes "
                    "WHERE texto IS NOT NULL AND fecha_mensaje IS NOT NULL")
        for texto, fecha in cur.fetchall():
            coincidencia = QUOTE_RE.match(texto)
            limpio = texto[coincidencia.end():].strip() if coincidencia else texto.strip()
            source_id = hashlib.md5(limpio.encode("utf-8")).hexdigest()
            if source_id not in fechas or fecha < fechas[source_id]:
                fechas[source_id] = fecha
    return fechas


def municipios_oficiales(conn) -> dict[str, str]:
    """El mismo municipio llega escrito distinto segun la fuente: Booking via
    gold_h3_master ('Guia de Isora'), TripAdvisor y el foro con tildes o con el
    nombre oficial largo ('Guía de Isora', 'San Cristóbal de La Laguna'). Eso
    partia gold_topicos_municipio en 37 filas, 6 de las cuales no cruzaban con
    gold_municipio_master."""
    with conn.cursor() as cur:
        cur.execute("SELECT municipio FROM gold.gold_municipio_master")
        return {normalizar(m): m for (m,) in cur.fetchall()}


def unificar_municipio(nombre: str | None, oficiales: dict[str, str]) -> str | None:
    if nombre is None:
        return None
    clave = normalizar(nombre)
    return oficiales.get(ALIAS_MUNICIPIO.get(clave, clave), nombre)


def ajustar(fila: tuple, oficiales: dict[str, str], fechas_foro: dict) -> tuple:
    source, source_id, text, topic_id, topic_label, municipio, zona, h3_index, fecha, pais, rating = fila
    if source == "losviajeros_message" and fecha is None:
        fecha = fechas_foro.get(source_id)
    return (source, source_id, text, topic_id, topic_label, unificar_municipio(municipio, oficiales),
            zona, h3_index, fecha, pais, rating)


def documentos_a_chunks(filas: list[tuple]) -> list[tuple]:
    chunks = []
    for (source, source_id, text, topic_id, topic_label,
         municipio, zona, h3_index, fecha, pais, rating) in filas:
        for i, trozo in enumerate(split_text(text)):
            chunks.append((source, source_id, i, trozo, topic_id, topic_label,
                           municipio, zona, h3_index, fecha, pais, rating))
    return chunks


def save_chunks(conn, chunks: list[tuple]) -> tuple[int, int]:
    """Inserta los fragmentos nuevos y, en los existentes, actualiza solo los
    metadatos. El texto y el embedding no se tocan: el troceo es determinista,
    asi que un fragmento existente ya tiene ese texto, y su embedding solo se
    recalcula con GPU (ver import_embeddings.py).

    IS DISTINCT FROM evita reescribir filas iguales: cada UPDATE en esta tabla
    reescribe tambien su entrada en el indice HNSW. DISTINCT ON por si un
    establecimiento cae justo en el borde de dos hexagonos."""
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TEMP TABLE chunks_entrantes (
                source TEXT, source_id TEXT, chunk_index INTEGER, text TEXT,
                topic_id INTEGER, topic_label TEXT, municipio TEXT, zona TEXT,
                h3_index TEXT, fecha DATE, pais_resenante TEXT, rating REAL
            ) ON COMMIT DROP
        """)
        psycopg2.extras.execute_values(cur, "INSERT INTO chunks_entrantes VALUES %s", chunks, page_size=2000)
        cur.execute("""
            INSERT INTO gold.nlp_chunks AS c
                (source, source_id, chunk_index, text, topic_id, topic_label,
                 municipio, zona, h3_index, fecha, pais_resenante, rating)
            SELECT DISTINCT ON (source, source_id, chunk_index)
                   source, source_id, chunk_index, text, topic_id, topic_label,
                   municipio, zona, h3_index, fecha, pais_resenante, rating
            FROM chunks_entrantes
            ORDER BY source, source_id, chunk_index
            ON CONFLICT (source, source_id, chunk_index) DO UPDATE
            SET topic_id = EXCLUDED.topic_id, topic_label = EXCLUDED.topic_label,
                municipio = EXCLUDED.municipio, zona = EXCLUDED.zona, h3_index = EXCLUDED.h3_index,
                fecha = EXCLUDED.fecha, pais_resenante = EXCLUDED.pais_resenante,
                rating = EXCLUDED.rating, processed_at = now()
            WHERE (c.topic_id, c.topic_label, c.municipio, c.zona, c.h3_index, c.fecha, c.pais_resenante, c.rating)
                  IS DISTINCT FROM
                  (EXCLUDED.topic_id, EXCLUDED.topic_label, EXCLUDED.municipio, EXCLUDED.zona,
                   EXCLUDED.h3_index, EXCLUDED.fecha, EXCLUDED.pais_resenante, EXCLUDED.rating)
            RETURNING (xmax = 0) AS insertado
        """)
        resultado = [fila[0] for fila in cur.fetchall()]
    conn.commit()
    nuevos = sum(resultado)
    return nuevos, len(resultado) - nuevos


def informe_cobertura(conn):
    """La cobertura geografica es lo que hace util el filtrado por metadatos:
    si cae, el RAG pierde su ventaja, asi que se reporta explicitamente."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT source,
                   COUNT(*)                                              AS chunks,
                   COUNT(DISTINCT source_id)                             AS docs,
                   COUNT(*) FILTER (WHERE municipio IS NOT NULL)         AS con_municipio,
                   COUNT(*) FILTER (WHERE zona IS NOT NULL)              AS con_zona,
                   COUNT(*) FILTER (WHERE h3_index IS NOT NULL)          AS con_hexagono,
                   COUNT(*) FILTER (WHERE fecha IS NOT NULL)             AS con_fecha,
                   COUNT(*) FILTER (WHERE embedding IS NULL)             AS sin_embedding
            FROM gold.nlp_chunks GROUP BY source ORDER BY 2 DESC
        """)
        print(f"\n{'fuente':22s} {'chunks':>8} {'docs':>7} {'municipio':>10} {'zona':>7} "
              f"{'hexagono':>9} {'fecha':>7} {'sin emb.':>9}")
        print("-" * 86)
        for s, ch, docs, muni, zona, hexa, fecha, sin_emb in cur.fetchall():
            print(f"{s:22s} {ch:>8} {docs:>7} {muni:>10} {zona:>7} {hexa:>9} {fecha:>7} {sin_emb:>9}")

        cur.execute("SELECT COUNT(*), COUNT(DISTINCT municipio) FROM gold.nlp_chunks")
        total, municipios = cur.fetchone()
        print(f"\nTotal de fragmentos en gold.nlp_chunks: {total} | municipios distintos: {municipios}")


def main():
    conn = get_db_connection()
    ensure_schema(conn)
    oficiales = municipios_oficiales(conn)
    fechas_foro = fechas_losviajeros(conn)

    for source, sql in CONSULTAS.items():
        filas = [ajustar(f, oficiales, fechas_foro) for f in fetch_documentos(conn, sql)]
        chunks = documentos_a_chunks(filas)
        nuevos, actualizados = save_chunks(conn, chunks)
        print(f"{source:22s} {len(filas):>6} docs -> {len(chunks):>6} fragmentos "
              f"| {nuevos} nuevos, {actualizados} con metadatos actualizados")

    informe_cobertura(conn)
    conn.close()


if __name__ == "__main__":
    main()
