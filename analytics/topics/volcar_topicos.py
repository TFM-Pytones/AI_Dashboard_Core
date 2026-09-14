"""Vuelca a Azure los temas reentrenados con entrenar_topicos.py.

1. gold.nlp_topics: actualiza tema, nombre, palabras clave, tamaño, confianza
   y modelo de cada documento. No borra ni inserta filas: el corpus es el mismo
   (entrenar_topicos.py lo lee de esta tabla) y el texto no cambia. Si el numero
   de documentos no coincide, aborta sin tocar nada.
2. Blob Storage, contenedor model-artifacts, carpeta topics_v2/<fecha>/: los
   modelos BERTopic, las medias de centrado por idioma, el CSV de resultados y
   la descripcion de los temas. Hasta ahora ahi solo estaban los resultados de
   la version de Colab del 30-08.

Despues hay que refrescar lo que depende de los temas:
    python analytics/rag/build_chunks.py
    python run_dbt.py run --select gold_topicos_h3 gold_topicos_municipio

Uso:
    python analytics/topics/volcar_topicos.py
    python analytics/topics/volcar_topicos.py --sin-blob
"""

import argparse
import csv
import os
import sys
from datetime import date
from pathlib import Path

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv(override=True)

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

AQUI = Path(__file__).resolve().parent
EXPORT = AQUI / "export"
RESULTADOS_CSV = EXPORT / "topicos_v2_resultados.csv"
TEMAS_JSON = EXPORT / "topicos_v2_temas.json"
DIR_MODELOS = EXPORT / "modelos_v2"
CONTENEDOR = "model-artifacts"


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


def cargar_resultados() -> list[tuple]:
    if not RESULTADOS_CSV.exists():
        raise SystemExit(f"No existe {RESULTADOS_CSV}: ejecuta antes analytics/topics/entrenar_topicos.py")
    with open(RESULTADOS_CSV, newline="", encoding="utf-8") as f:
        return [
            (r["source"], r["source_id"], int(r["topic_id"]), r["topic_label"], r["topic_keywords"],
             int(r["topic_size"]), float(r["probability"]), r["model_name"])
            for r in csv.DictReader(f)
        ]


def actualizar_topics(conn, filas: list[tuple]):
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM gold.nlp_topics")
        en_bd = cur.fetchone()[0]
        if en_bd != len(filas):
            raise SystemExit(f"El CSV tiene {len(filas)} documentos y gold.nlp_topics {en_bd}: el corpus ha "
                             "cambiado desde el entrenamiento. Vuelve a ejecutar entrenar_topicos.py.")
        cur.execute("""
            CREATE TEMP TABLE temas_nuevos (
                source TEXT, source_id TEXT, topic_id INTEGER, topic_label TEXT, topic_keywords TEXT,
                topic_size INTEGER, probability REAL, model_name TEXT
            ) ON COMMIT DROP
        """)
        psycopg2.extras.execute_values(cur, "INSERT INTO temas_nuevos VALUES %s", filas, page_size=2000)
        cur.execute("""
            UPDATE gold.nlp_topics t
            SET topic_id = n.topic_id, topic_label = n.topic_label, topic_keywords = n.topic_keywords,
                topic_size = n.topic_size, probability = n.probability, model_name = n.model_name,
                processed_at = now()
            FROM temas_nuevos n
            WHERE t.source = n.source AND t.source_id = n.source_id
        """)
        if cur.rowcount != len(filas):
            conn.rollback()
            raise SystemExit(f"Solo {cur.rowcount} de {len(filas)} documentos del CSV existen en gold.nlp_topics. "
                             "No se ha cambiado nada.")
    conn.commit()
    print(f"gold.nlp_topics: {len(filas)} documentos actualizados")


def subir_artefactos():
    from azure.storage.blob import BlobServiceClient

    cadena = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    contenedor = BlobServiceClient.from_connection_string(cadena).get_container_client(CONTENEDOR)
    prefijo = f"topics_v2/{date.today().isoformat()}"
    archivos = [RESULTADOS_CSV, TEMAS_JSON] + sorted(p for p in DIR_MODELOS.rglob("*") if p.is_file())
    for ruta in archivos:
        nombre = f"{prefijo}/{ruta.relative_to(EXPORT).as_posix()}"
        with open(ruta, "rb") as f:
            contenedor.upload_blob(nombre, f, overwrite=True)
    print(f"Blob: {len(archivos)} archivos en {CONTENEDOR}/{prefijo}/")


def resumen(conn):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT model_name, COUNT(DISTINCT topic_id), COUNT(*), ROUND(AVG(probability)::numeric, 3)
            FROM gold.nlp_topics GROUP BY 1 ORDER BY 1
        """)
        for modelo, temas, docs, confianza in cur.fetchall():
            print(f"  {modelo}: {temas} temas, {docs} documentos, confianza media {confianza}")


def main():
    parser = argparse.ArgumentParser(description="Vuelca los temas reentrenados a Azure.")
    parser.add_argument("--sin-blob", action="store_true", help="no subir los artefactos a Blob Storage")
    args = parser.parse_args()

    filas = cargar_resultados()
    conn = get_db_connection()
    ensure_schema(conn)
    actualizar_topics(conn, filas)
    resumen(conn)
    conn.close()
    if not args.sin_blob:
        subir_artefactos()
    print("\nSiguiente: python analytics/rag/build_chunks.py y "
          "python run_dbt.py run --select gold_topicos_h3 gold_topicos_municipio")


if __name__ == "__main__":
    main()
