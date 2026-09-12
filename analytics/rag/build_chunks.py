"""Fase 1 del RAG (ver plan_rag.md) -- Construye gold.nlp_chunks: el corpus de
gold.nlp_topics fragmentado y enriquecido con los metadatos que permiten
filtrar ANTES de la busqueda vectorial (municipio, hexagono, fecha, pais,
topico de BERTopic).

Cada fuente llega a su ubicacion por un camino distinto:
- booking_review     -> review_id -> establishment_id -> geometry -> ST_Contains
                        contra gold_h3_master (da h3_index y municipio).
- tripadvisor_review -> review_id -> location_id -> silver_tripadvisor_ubicaciones,
                        que ya trae municipio resuelto, + geometry para el hexagono.
- losviajeros_message-> source_id (hash MD5) -> gold.geo_mentions, que da un
                        nombre de lugar (municipio o zona) pero NO coordenadas:
                        por eso estas filas no llevan h3_index.
- youtube_comment    -> sin ubicacion por diseño (percepcion de marca global).

Uso:
    python analytics/rag/build_chunks.py
"""

import os
import re
import sys
from pathlib import Path

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv(override=True)

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

# Por debajo de este umbral el documento entra entero (el 95,5% del corpus).
MAX_LEN_SIN_TROCEAR = 1000
CHUNK_SIZE = 800
CHUNK_OVERLAP = 100

FIN_DE_FRASE = re.compile(r"(?<=[.!?\n])\s+")


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
# Cada una devuelve las mismas 10 columnas para poder tratarlas igual despues.

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

# geo_mentions da nombre de lugar, no coordenadas -> h3_index queda NULL.
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
    SELECT t.source, t.source_id, t.text, t.topic_id, t.topic_label,
           NULL::text AS municipio, NULL::text AS zona, NULL::text AS h3_index,
           NULL::date AS fecha, NULL::text AS pais, NULL::real AS rating
    FROM gold.nlp_topics t
    WHERE t.source = 'youtube_comment'
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


def documentos_a_chunks(filas: list[tuple]) -> list[dict]:
    chunks = []
    for (source, source_id, text, topic_id, topic_label,
         municipio, zona, h3_index, fecha, pais, rating) in filas:
        for i, trozo in enumerate(split_text(text)):
            chunks.append({
                "source": source, "source_id": source_id, "chunk_index": i,
                "text": trozo, "topic_id": topic_id, "topic_label": topic_label,
                "municipio": municipio, "zona": zona, "h3_index": h3_index,
                "fecha": fecha, "pais_resenante": pais, "rating": rating,
            })
    return chunks


def save_chunks(conn, chunks: list[dict]):
    with conn.cursor() as cur:
        psycopg2.extras.execute_batch(
            cur,
            """
            INSERT INTO gold.nlp_chunks
                (source, source_id, chunk_index, text, topic_id, topic_label,
                 municipio, zona, h3_index, fecha, pais_resenante, rating)
            VALUES (%(source)s, %(source_id)s, %(chunk_index)s, %(text)s,
                    %(topic_id)s, %(topic_label)s, %(municipio)s, %(zona)s,
                    %(h3_index)s, %(fecha)s, %(pais_resenante)s, %(rating)s)
            ON CONFLICT (source, source_id, chunk_index) DO NOTHING
            """,
            chunks,
            page_size=500,
        )
    conn.commit()


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
                   COUNT(*) FILTER (WHERE h3_index IS NOT NULL)          AS con_hexagono
            FROM gold.nlp_chunks GROUP BY source ORDER BY 2 DESC
        """)
        print(f"\n{'fuente':22s} {'chunks':>8} {'docs':>7} {'municipio':>10} {'zona':>7} {'hexagono':>9}")
        print("-" * 68)
        for s, ch, docs, muni, zona, hexa in cur.fetchall():
            print(f"{s:22s} {ch:>8} {docs:>7} {muni:>10} {zona:>7} {hexa:>9}")

        cur.execute("SELECT COUNT(*) FROM gold.nlp_chunks")
        print(f"\nTotal de fragmentos en gold.nlp_chunks: {cur.fetchone()[0]}")


def main():
    conn = get_db_connection()
    ensure_schema(conn)

    total = 0
    for source, sql in CONSULTAS.items():
        filas = fetch_documentos(conn, sql)
        chunks = documentos_a_chunks(filas)
        save_chunks(conn, chunks)
        troceados = len(chunks) - len(filas)
        print(f"{source:22s} {len(filas):>6} docs -> {len(chunks):>6} fragmentos (+{troceados} por troceo)")
        total += len(chunks)

    informe_cobertura(conn)
    conn.close()


if __name__ == "__main__":
    main()
