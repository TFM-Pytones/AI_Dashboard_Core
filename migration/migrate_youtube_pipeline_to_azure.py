"""Migracion unica del pipeline de YouTube (Neon) a Azure.

Copia raw_data.youtube_videos/youtube_comments -> bronze.*, y
processed_data.sentiment_results/aspect_results -> silver.* (incluye
is_relevant/relevance_score ya calculados por el backfill). A partir de esta
migracion, ingestion/scraping/youtube.py y analytics/*/batch_inference.py
escriben directo en Azure — Neon queda como archivo historico, no se vuelve
a tocar.

Idempotente: usa ON CONFLICT DO NOTHING para bronze/silver.sentiment_results
(tienen PK/UNIQUE), y salta silver.aspect_results si ya tiene filas (esa
tabla no tiene UNIQUE porque un comentario puede generar varias filas).
"""

import os
from pathlib import Path

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv(override=True)

SQL_DIR = Path(__file__).resolve().parents[1] / "sql"


def neon_connection():
    return psycopg2.connect(
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST"),
        database=os.getenv("DB_NAME"),
        port="5432",
        sslmode="require",
    )


def azure_connection():
    return psycopg2.connect(
        user=os.getenv("AZURE_DB_USER"),
        password=os.getenv("AZURE_DB_PASSWORD"),
        host=os.getenv("AZURE_DB_HOST"),
        database=os.getenv("AZURE_DB_NAME"),
        port="5432",
        sslmode="require",
    )


def ensure_schemas(azure_conn):
    with azure_conn.cursor() as cur:
        # La copia previa de sentiment_results (hecha con pandas to_sql replace)
        # no tiene UNIQUE(source, source_id): se recrea aqui para que el
        # ON CONFLICT de mas abajo funcione.
        cur.execute("DROP TABLE IF EXISTS silver.sentiment_results")
    azure_conn.commit()

    for filename in ["bronze_youtube_schema.sql", "silver_sentiment_results_schema.sql", "silver_aspect_results_schema.sql"]:
        with azure_conn.cursor() as cur:
            cur.execute((SQL_DIR / filename).read_text())
    azure_conn.commit()


def copy_table(neon_conn, azure_conn, select_sql, insert_sql, table_label):
    with neon_conn.cursor() as cur:
        cur.execute(select_sql)
        rows = cur.fetchall()

    if not rows:
        print(f"{table_label}: nada que copiar (0 filas en Neon).")
        return

    with azure_conn.cursor() as cur:
        psycopg2.extras.execute_batch(cur, insert_sql, rows)
    azure_conn.commit()
    print(f"{table_label}: {len(rows)} filas copiadas.")


def main():
    neon_conn = neon_connection()
    azure_conn = azure_connection()
    ensure_schemas(azure_conn)

    copy_table(
        neon_conn, azure_conn,
        "SELECT video_id, search_term, title, channel_title, published_at, view_count, fetched_at FROM raw_data.youtube_videos",
        """
        INSERT INTO bronze.youtube_videos (video_id, search_term, title, channel_title, published_at, view_count, fetched_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (video_id) DO NOTHING
        """,
        "bronze.youtube_videos",
    )

    copy_table(
        neon_conn, azure_conn,
        "SELECT comment_id, video_id, author, text, like_count, published_at, fetched_at FROM raw_data.youtube_comments",
        """
        INSERT INTO bronze.youtube_comments (comment_id, video_id, author, text, like_count, published_at, fetched_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (comment_id) DO NOTHING
        """,
        "bronze.youtube_comments",
    )

    copy_table(
        neon_conn, azure_conn,
        """
        SELECT source, source_id, text, label, score, model_name, processed_at, is_relevant, relevance_score
        FROM processed_data.sentiment_results
        """,
        """
        INSERT INTO silver.sentiment_results
            (source, source_id, text, label, score, model_name, processed_at, is_relevant, relevance_score)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (source, source_id) DO NOTHING
        """,
        "silver.sentiment_results",
    )

    with azure_conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM silver.aspect_results")
        already_migrated = cur.fetchone()[0] > 0

    if already_migrated:
        print("silver.aspect_results: ya tiene filas, se salta (no tiene UNIQUE, evito duplicar).")
    else:
        copy_table(
            neon_conn, azure_conn,
            """
            SELECT source, source_id, text, aspect, aspect_sentiment, confidence, model_name, processed_at
            FROM processed_data.aspect_results
            """,
            """
            INSERT INTO silver.aspect_results
                (source, source_id, text, aspect, aspect_sentiment, confidence, model_name, processed_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            "silver.aspect_results",
        )

    neon_conn.close()
    azure_conn.close()
    print("\nMigracion completa.")


if __name__ == "__main__":
    main()
