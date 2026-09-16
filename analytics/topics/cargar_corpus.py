"""Carga inicial del corpus en gold.nlp_topics (punto 6 de la revision de codigo).

Este script cierra el unico hueco que impedia borrar la version vieja (V1) del
pipeline de temas. El reparto de responsabilidades es:

    export_general_corpus.py  ->  export/general_corpus.csv   (Modelo A)
    export_geo_corpus.py      ->  export/geo_corpus.csv       (Modelo B)
                                            |
                                   cargar_corpus.py  (esto)
                                            |
                                    gold.nlp_topics
                                            |
                                   entrenar_topicos.py   (lee el corpus de la tabla)
                                            |
                                    volcar_topicos.py    (UPDATE con tema y nombre)

Antes de esto, las filas solo las creaba la V1 (topic_modeling.py para el Modelo
A e import_geo_results.py para el Modelo B, ambos entrenando con HDBSCAN y
dejando ~30% de documentos como outliers). La v2 (entrenar_topicos.py, k-means,
0 outliers, nombres en español via LLM) no inserta: lee el corpus de
gold.nlp_topics y volcar_topicos.py solo hace UPDATE. Es decir, la v2 dependia de
que la V1 hubiera corrido antes. Con este script ya no.

Las filas se insertan SIN tema (topic_id = -1, topic_label NULL): el tema real lo
pone despues volcar_topicos.py. -1 es el valor que el esquema ya usaba para
"outlier / sin tema claro", y topic_id es NOT NULL, asi que hace de hueco.

Idempotente: ON CONFLICT (source, source_id) DO NOTHING. Relanzarlo sobre una
tabla ya poblada no pisa los temas de la v2 -- solo añade los documentos nuevos
que hayan aparecido en los CSV.

Uso:
    python analytics/topics/cargar_corpus.py                 # los dos modelos
    python analytics/topics/cargar_corpus.py --modelo A
    python analytics/topics/cargar_corpus.py --simular       # no escribe, solo cuenta
"""

import argparse
import csv
import os
import sys
from pathlib import Path

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv(override=True)

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

AQUI = Path(__file__).resolve().parent
EXPORT = AQUI / "export"

EMBEDDING_MODEL_NAME = "paraphrase-multilingual-mpnet-base-v2"

# Deben coincidir con MODELOS en entrenar_topicos.py: ese script decide si un
# documento es del modelo A o del B mirando este texto.
MODELOS = {
    "A": {
        "csv": EXPORT / "general_corpus.csv",
        "model_name": f"BERTopic+{EMBEDDING_MODEL_NAME} (modelo A: general)",
        "descripcion": "vision general (YouTube + LosViajeros sin ubicacion)",
    },
    "B": {
        "csv": EXPORT / "geo_corpus.csv",
        "model_name": f"BERTopic+{EMBEDDING_MODEL_NAME} (modelo B: geo)",
        "descripcion": "por ubicacion (Booking + TripAdvisor + LosViajeros georreferenciado)",
    },
}

TOPIC_ID_SIN_ASIGNAR = -1

SQL_INSERT = """
    INSERT INTO gold.nlp_topics (source, source_id, text, topic_id, model_name)
    VALUES %s
    ON CONFLICT (source, source_id) DO NOTHING
"""

# Los textos de Booking pasan de largo del limite por defecto del modulo csv.
csv.field_size_limit(10**9)


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
    schema_path = AQUI.parents[1] / "sql" / "gold_nlp_topics_schema.sql"
    with conn.cursor() as cur:
        cur.execute(schema_path.read_text(encoding="utf-8"))
    conn.commit()


def leer_corpus(ruta: Path, model_name: str) -> list[tuple]:
    """CSV (source, source_id, text) -> filas listas para gold.nlp_topics."""
    if not ruta.exists():
        raise SystemExit(
            f"No existe {ruta}. Genera antes el corpus:\n"
            f"    python analytics/topics/export_general_corpus.py\n"
            f"    python analytics/topics/export_geo_corpus.py"
        )

    filas = []
    with open(ruta, encoding="utf-8", newline="") as f:
        lector = csv.reader(f)
        cabecera = next(lector, None)
        if cabecera != ["source", "source_id", "text"]:
            raise SystemExit(f"{ruta.name}: cabecera inesperada {cabecera}, se esperaba [source, source_id, text].")
        for fila in lector:
            if len(fila) != 3:
                continue
            source, source_id, text = fila
            if not text.strip():
                continue
            filas.append((source, source_id, text, TOPIC_ID_SIN_ASIGNAR, model_name))
    return filas


def contar_por_fuente(filas: list[tuple]) -> dict[str, int]:
    conteo: dict[str, int] = {}
    for source, *_ in filas:
        conteo[source] = conteo.get(source, 0) + 1
    return conteo


def insertar(conn, filas: list[tuple]) -> int:
    """Inserta y devuelve cuantas filas eran nuevas de verdad."""
    if not filas:
        return 0
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM gold.nlp_topics")
        antes = cur.fetchone()[0]
        psycopg2.extras.execute_values(cur, SQL_INSERT, filas, page_size=1000)
        cur.execute("SELECT COUNT(*) FROM gold.nlp_topics")
        despues = cur.fetchone()[0]
    conn.commit()
    return despues - antes


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Carga inicial del corpus de temas en gold.nlp_topics.",
    )
    parser.add_argument(
        "--modelo",
        choices=["A", "B", "ambos"],
        default="ambos",
        help="A = vision general, B = por ubicacion, ambos = los dos (por defecto).",
    )
    parser.add_argument(
        "--simular",
        action="store_true",
        help="Lee los CSV y cuenta, pero no escribe nada en la base de datos.",
    )
    return parser.parse_args(argv)


def modelos_pedidos(modelo: str) -> list[str]:
    return ["A", "B"] if modelo == "ambos" else [modelo]


def main(argv=None):
    args = parse_args(argv)
    claves = modelos_pedidos(args.modelo)

    corpus = {}
    for clave in claves:
        conf = MODELOS[clave]
        filas = leer_corpus(conf["csv"], conf["model_name"])
        corpus[clave] = filas
        print(f"Modelo {clave} -- {conf['descripcion']}")
        print(f"  {conf['csv'].name}: {len(filas)} documentos {contar_por_fuente(filas)}")

    if args.simular:
        print("\n--simular: no se ha escrito nada en la base de datos.")
        return

    conn = get_db_connection()
    ensure_schema(conn)

    total_nuevas = 0
    for clave in claves:
        filas = corpus[clave]
        nuevas = insertar(conn, filas)
        total_nuevas += nuevas
        print(f"Modelo {clave}: {nuevas} filas nuevas insertadas "
              f"({len(filas) - nuevas} ya estaban y no se han tocado).")

    with conn.cursor() as cur:
        cur.execute("""
            SELECT model_name, COUNT(*), COUNT(*) FILTER (WHERE topic_label IS NULL)
            FROM gold.nlp_topics GROUP BY model_name ORDER BY model_name
        """)
        print("\ngold.nlp_topics:")
        for model_name, total, sin_tema in cur.fetchall():
            print(f"  {model_name}: {total} documentos, {sin_tema} sin tema asignado todavia")
    conn.close()

    if total_nuevas:
        print("\nSiguiente paso, para ponerles tema y nombre:")
        print("    python analytics/topics/entrenar_topicos.py")
        print("    python analytics/topics/volcar_topicos.py")


if __name__ == "__main__":
    main()
