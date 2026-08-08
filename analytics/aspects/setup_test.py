"""Issue #18 — Configuracion de Extraccion de Aspectos (pyabsa).

Valida que el entorno de pyabsa funciona de punta a punta: conecta a Azure, saca
comentarios reales de YouTube y detecta sobre que aspectos turisticos habla cada
uno (playas, precio, trafico...) y el sentimiento de cada aspecto por separado.

No procesa el dataset completo, es solo la validacion del setup (equivalente al
Issue #16 pero para pyabsa en vez del modelo de sentimiento general).
"""

import os

# pyabsa usa internamente `from distutils.version import ...`, que ya no existe
# en Python 3.12+. Importar setuptools primero registra un shim compatible.
import setuptools  # noqa: F401

import psycopg2
from dotenv import load_dotenv
from pyabsa import AspectTermExtraction as ATEPC

load_dotenv(override=True)

CHECKPOINT = "multilingual"
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
            WHERE text IS NOT NULL AND length(text) > 30
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

    print(f"Cargando checkpoint {CHECKPOINT!r} de pyabsa (primera vez descarga ~1.1GB)...")
    extractor = ATEPC.AspectExtractor(CHECKPOINT, auto_device=True)

    print(f"\nProbando con {len(comments)} comentarios reales de bronze.youtube_comments:\n")
    results = extractor.predict(comments, save_result=False, print_result=False)

    for r in results:
        preview = r["sentence"].replace("\n", " ")[:100]
        if not r["aspect"]:
            print(f"[sin aspectos detectados]  {preview}")
            continue
        aspectos = ", ".join(
            f"{asp} ({sent} {conf:.2f})"
            for asp, sent, conf in zip(r["aspect"], r["sentiment"], r["confidence"])
        )
        print(f"[{aspectos}]  {preview}")

    print("\nSetup verificado: Azure -> texto real -> pyabsa -> aspectos + sentimiento por aspecto. OK.")


if __name__ == "__main__":
    main()
