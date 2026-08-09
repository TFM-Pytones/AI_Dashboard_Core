"""Issue #16 — Setup Entorno Hugging Face y Modelos.

Valida que el entorno de NLP funciona de punta a punta: conecta a Azure, saca
comentarios reales de YouTube y corre el modelo de sentimiento sobre ellos.
No procesa todo el dataset (eso es el Issue #17), solo confirma que todo encaja.
"""

import os

import psycopg2
from dotenv import load_dotenv
from transformers import pipeline

load_dotenv(override=True)

MODEL_NAME = "cardiffnlp/twitter-xlm-roberta-base-sentiment"
SAMPLE_SIZE = 5


def get_db_connection():
    return psycopg2.connect(
        user=os.getenv("AZURE_DB_USER"),
        password=os.getenv("AZURE_DB_PASSWORD"),
        host=os.getenv("AZURE_DB_HOST"),
        database=os.getenv("AZURE_DB_NAME"),
        port="5432",
        sslmode="require",
    )


def fetch_sample_comments(conn, n: int) -> list[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT text FROM bronze.youtube_comments
            WHERE text IS NOT NULL AND length(text) > 20
            ORDER BY random()
            LIMIT %s
            """,
            (n,),
        )
        return [row[0] for row in cur.fetchall()]


def main():
    conn = get_db_connection()
    comments = fetch_sample_comments(conn, SAMPLE_SIZE)
    conn.close()

    if not comments:
        print("No hay comentarios en bronze.youtube_comments. Corre antes ingestion/scraping/youtube.py.")
        return

    print(f"Cargando modelo {MODEL_NAME!r} (primera vez puede tardar, se descarga ~1.1GB)...")
    classifier = pipeline("sentiment-analysis", model=MODEL_NAME, tokenizer=MODEL_NAME)

    print(f"\nProbando con {len(comments)} comentarios reales de bronze.youtube_comments:\n")
    for text in comments:
        result = classifier(text, truncation=True, max_length=512)[0]
        preview = text.replace("\n", " ")[:100]
        print(f"[{result['label']:>8} {result['score']:.2f}]  {preview}")

    print("\nSetup verificado: Azure -> texto real -> modelo Hugging Face -> predicción. OK.")


if __name__ == "__main__":
    main()
