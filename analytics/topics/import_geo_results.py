"""Carga en gold.nlp_topics los resultados del MODELO B ("por ubicacion"),
entrenado en Google Colab con GPU (ver topic_modeling_geo_colab.ipynb) porque
el corpus (Booking + TripAdvisor + LosViajeros georreferenciado, 38.341 docs)
es demasiado grande para entrenar en CPU local en un tiempo razonable.

Uso:
    python analytics/topics/import_geo_results.py ruta/a/geo_topics_results.csv
"""

import csv
import os
import sys
from pathlib import Path

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv(override=True)


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


def load_csv(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = []
        for row in reader:
            rows.append({
                "source": row["source"],
                "source_id": row["source_id"],
                "text": row["text"],
                "topic_id": int(row["topic_id"]),
                "topic_label": row["topic_label"] or None,
                "topic_size": int(row["topic_size"]) if row["topic_size"] else None,
                "probability": float(row["probability"]) if row["probability"] else None,
                "model_name": row["model_name"],
            })
        return rows


def save_results(conn, results: list[dict]):
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
            page_size=500,
        )
    conn.commit()


def main():
    if len(sys.argv) != 2:
        print("Uso: python analytics/topics/import_geo_results.py ruta/a/geo_topics_results.csv")
        sys.exit(1)

    csv_path = Path(sys.argv[1])
    if not csv_path.exists():
        print(f"No existe: {csv_path}")
        sys.exit(1)

    results = load_csv(csv_path)
    print(f"{len(results)} filas leidas de {csv_path}")

    by_source: dict[str, int] = {}
    for r in results:
        by_source[r["source"]] = by_source.get(r["source"], 0) + 1
    for source, n in by_source.items():
        print(f"  {source}: {n}")

    conn = get_db_connection()
    ensure_schema(conn)
    save_results(conn, results)
    conn.close()

    print(f"\nCargados en gold.nlp_topics.")


if __name__ == "__main__":
    main()
