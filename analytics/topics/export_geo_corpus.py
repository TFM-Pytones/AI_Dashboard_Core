"""Exporta el corpus del MODELO B ("por ubicacion") a un CSV.

El CSV lo carga despues cargar_corpus.py en gold.nlp_topics, y de ahi lo lee
entrenar_topicos.py. La version vieja entrenaba BERTopic en Google Colab con GPU
porque las decenas de miles de reseñas de Booking hacian inviable HDBSCAN en CPU
local (ver analytics/contexto.md); con k-means y embeddings cacheados ya no.

Fuentes, las tres CON ubicacion real:
- Booking: silver.silver_booking_reviews (review_text). Ubicacion via
  establishment_id -> silver.silver_booking_establishments (lat/lon).
- TripAdvisor: silver.tripadvisor_resenas (texto). Ubicacion via
  location_id -> silver.tripadvisor_ubicaciones (lat/lon).
- LosViajeros: silver.stg_losviajeros_mensajes, pero SOLO los mensajes con
  ubicacion detectada en gold.geo_mentions (analytics/geo/extract_toponyms.py)
  -- el resto no tiene ubicacion y va al Modelo A (ver
  analytics/topics/export_general_corpus.py). El cruce se hace por hash MD5
  del texto limpio, NO por id_mensaje -- id_mensaje se reutiliza para
  mensajes distintos en esta tabla (creada a mano, sin PK; ver
  analytics/geo/extract_toponyms.py para el detalle).

Uso:
    python analytics/topics/export_geo_corpus.py
    -> analytics/topics/export/geo_corpus.csv (source,source_id,text)

Despues:
    python analytics/topics/cargar_corpus.py --modelo B
"""

import csv
import hashlib
import os
import re
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

load_dotenv(override=True)

MIN_TEXT_LENGTH = 15
OUT_PATH = Path(__file__).resolve().parent / "export" / "geo_corpus.csv"

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


def fetch_booking(conn) -> list[tuple[str, str, str]]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT review_id, review_text FROM silver.silver_booking_reviews "
            "WHERE review_text IS NOT NULL AND length(review_text) > %s",
            (MIN_TEXT_LENGTH,),
        )
        return [("booking_review", rid, text.strip()) for rid, text in cur.fetchall()]


def fetch_tripadvisor(conn) -> list[tuple[str, str, str]]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT review_id, texto FROM silver.silver_tripadvisor_resenas "
            "WHERE texto IS NOT NULL AND length(texto) > %s",
            (MIN_TEXT_LENGTH,),
        )
        return [("tripadvisor_review", str(rid), text.strip()) for rid, text in cur.fetchall()]


def fetch_losviajeros_geo(conn) -> list[tuple[str, str, str]]:
    """LosViajeros CON ubicacion detectada. El cruce con gold.geo_mentions es por
    hash del texto limpio (calculado aqui, no leido de la BD) -- no por id_mensaje,
    ver docstring del modulo."""
    with conn.cursor() as cur:
        cur.execute("SELECT texto FROM silver.silver_losviajeros_mensajes")
        raw_texts = [r[0] for r in cur.fetchall()]
        cur.execute("SELECT source_id FROM gold.geo_mentions WHERE source = 'losviajeros_message'")
        geo_ids = {r[0] for r in cur.fetchall()}

    items = []
    seen = set()
    for raw_text in raw_texts:
        cleaned = strip_nested_quotes(raw_text)
        if len(cleaned) <= MIN_TEXT_LENGTH:
            continue
        sid = stable_id(cleaned)
        if sid in geo_ids and sid not in seen:
            seen.add(sid)
            items.append(("losviajeros_message", sid, cleaned))
    return items


def dedupe_exact(items: list[tuple[str, str, str]]) -> list[tuple[str, str, str]]:
    seen: set[str] = set()
    out = []
    for source, source_id, text in items:
        if text in seen:
            continue
        seen.add(text)
        out.append((source, source_id, text))
    return out


def main():
    conn = get_db_connection()
    booking = fetch_booking(conn)
    tripadvisor = fetch_tripadvisor(conn)
    losviajeros = fetch_losviajeros_geo(conn)
    conn.close()

    print(f"Booking: {len(booking)} reseñas")
    print(f"TripAdvisor: {len(tripadvisor)} reseñas")
    print(f"LosViajeros (con ubicacion): {len(losviajeros)} mensajes")

    todos = dedupe_exact(booking + tripadvisor + losviajeros)
    print(f"\nTotal tras deduplicar texto exacto: {len(todos)}")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["source", "source_id", "text"])
        writer.writerows(todos)

    print(f"\nExportado a {OUT_PATH}")
    print("Ahora cargalo: python analytics/topics/cargar_corpus.py --modelo B")


if __name__ == "__main__":
    main()
