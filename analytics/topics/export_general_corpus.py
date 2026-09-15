"""Exporta el corpus del MODELO A ("vision general") a CSV para entrenar en
Colab -- necesario porque hdbscan no se puede importar en local en esta
maquina (Windows Smart App Control bloquea su libreria nativa, ver
analytics/contexto.md).

Dos fuentes:
- YouTube: silver.sentiment_results (source='youtube_comment', is_relevant=true).
- LosViajeros SIN ubicacion detectada: silver.stg_losviajeros_mensajes que NO
  tienen fila en gold.geo_mentions (ver analytics/geo/extract_toponyms.py).
  Los que SI tienen ubicacion van al Modelo B (ver export_geo_corpus.py) --
  antes de esto los mensajes sin ubicacion no entraban en ningun modelo,
  quedaban huerfanos.

El cruce con gold.geo_mentions es por hash MD5 del texto limpio, NO por
id_mensaje -- id_mensaje se reutiliza para mensajes distintos en esta tabla
(creada a mano, sin PK; ver analytics/geo/extract_toponyms.py para el
detalle verificado contra la BD real).

Uso:
    python analytics/topics/export_general_corpus.py
    -> analytics/topics/export/general_corpus.csv (source,source_id,text)
"""

import csv
import hashlib
import os
import re
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

load_dotenv(override=True)

SOURCE_YOUTUBE = "youtube_comment"
SOURCE_LOSVIAJEROS = "losviajeros_message"
MIN_TEXT_LENGTH = 15
OUT_PATH = Path(__file__).resolve().parent / "export" / "general_corpus.csv"

QUOTE_RE = re.compile(r".*\bEscribi[oó]:\s*", re.DOTALL)


def strip_nested_quotes(text: str) -> str:
    match = QUOTE_RE.match(text)
    return text[match.end():].strip() if match else text.strip()


def stable_id(texto_limpio: str) -> str:
    """Hash MD5 del texto ya limpio -- id_mensaje no es fiable, ver docstring del modulo."""
    return hashlib.md5(texto_limpio.encode("utf-8")).hexdigest()


def get_db_connection():
    return psycopg2.connect(
        user=os.getenv("AZURE_DB_USER"),
        password=os.getenv("AZURE_DB_PASSWORD"),
        host=os.getenv("AZURE_DB_HOST"),
        database=os.getenv("AZURE_DB_NAME"),
        port="5432",
        sslmode="require",
    )


def fetch_youtube(conn) -> list[tuple[str, str, str]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT source_id, text
            FROM silver.silver_sentiment_results
            WHERE source = %s AND is_relevant = true AND length(text) > %s
            """,
            (SOURCE_YOUTUBE, MIN_TEXT_LENGTH),
        )
        return [(SOURCE_YOUTUBE, sid, text) for sid, text in cur.fetchall()]


def fetch_losviajeros_sin_ubicacion(conn) -> list[tuple[str, str, str]]:
    """LosViajeros SIN ubicacion detectada. El cruce con gold.geo_mentions es por
    hash del texto limpio (calculado aqui, no leido de la BD) -- no por id_mensaje,
    ver docstring del modulo."""
    with conn.cursor() as cur:
        cur.execute("SELECT texto FROM silver.silver_losviajeros_mensajes")
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


def main():
    conn = get_db_connection()
    youtube = fetch_youtube(conn)
    losviajeros = fetch_losviajeros_sin_ubicacion(conn)
    conn.close()

    print(f"YouTube: {len(youtube)} comentarios")
    print(f"LosViajeros (sin ubicacion): {len(losviajeros)} mensajes")

    rows = youtube + losviajeros
    print(f"\nTotal: {len(rows)}")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["source", "source_id", "text"])
        writer.writerows(rows)

    print(f"\nExportado a {OUT_PATH}")
    print("Sube este CSV a Colab y usa topic_modeling_A_general_colab.ipynb.")


if __name__ == "__main__":
    main()
