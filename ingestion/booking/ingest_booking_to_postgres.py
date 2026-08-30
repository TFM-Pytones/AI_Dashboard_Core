"""Script puente: sube todos los Parquet de Booking desde bronce-raw (Azure Blob)
hacia el esquema raw_data en Azure PostgreSQL.

Basado en el patrón de ingestion/postgres/ingest_bronze_to_postgres.py, adaptado
para el caso específico de Booking:
    - Múltiples archivos Parquet por corrida (uno por establecimiento, con
      timestamp único en el nombre), no un único archivo fijo.
    - Esquema "raw_data" (con guión bajo, válido en SQL), no "bronce-raw"
      (ese nombre es el del CONTENEDOR de Blob Storage, no debe reutilizarse
      como nombre de esquema de Postgres).
    - Modo "append": la deduplicación se resuelve después, en el modelo dbt
      hacia Silver — no acá. "replace" borraría el histórico en cada corrida.

Uso:
    python ingest_booking_to_postgres.py
"""

import io
import os

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

from utils.azure_storage import get_container_client, list_files

load_dotenv()

PG_USER = os.getenv("AZURE_DB_USER")
PG_PASS = os.getenv("AZURE_DB_PASSWORD")
PG_HOST = os.getenv("AZURE_DB_HOST")
PG_PORT = "5432"
PG_DB = os.getenv("AZURE_DB_NAME")

SCHEMA = "bronze"  # alineado con dbt_project/models/silver/sources.yml (no "raw_data")


def get_pg_engine():
    """Crea la conexión a Azure PostgreSQL."""
    missing = [
        name for name, val in [
            ("AZURE_DB_USER", PG_USER), ("AZURE_DB_PASSWORD", PG_PASS),
            ("AZURE_DB_HOST", PG_HOST), ("AZURE_DB_NAME", PG_DB),
        ] if not val
    ]
    if missing:
        raise RuntimeError(f"Faltan variables en el .env: {', '.join(missing)}")

    connection_string = f"postgresql://{PG_USER}:{PG_PASS}@{PG_HOST}:{PG_PORT}/{PG_DB}"
    return create_engine(connection_string, connect_args={"sslmode": "require"})


# Columnas que DEBEN ser numéricas — si pandas las combina como "object" al
# concatenar Parquets de distintas corridas/fuentes (laptop + VM, con
# pequeñas diferencias de cómo se generó cada archivo), Postgres terminaría
# creando la columna como TEXT en vez de NUMERIC/FLOAT, rompiendo comparaciones
# numéricas más adelante (ej. en los modelos/tests de dbt).
NUMERIC_COLUMNS_BY_TABLE = {
    "booking_establishments": ["latitude", "longitude"],
    "booking_reviews": ["rating"],
}


def _normalize_numeric_columns(df: pd.DataFrame, table_name: str) -> pd.DataFrame:
    """Fuerza a numérico (float) las columnas que deben serlo, sin importar
    cómo haya quedado el dtype tras el pd.concat() de múltiples Parquets.
    Valores no convertibles quedan como NaN (errors='coerce'), no rompen la carga.
    """
    columns = NUMERIC_COLUMNS_BY_TABLE.get(table_name, [])
    for col in columns:
        if col in df.columns:
            before_dtype = df[col].dtype
            df[col] = pd.to_numeric(df[col], errors="coerce")
            if before_dtype != df[col].dtype:
                print(f"  [AVISO] Columna '{col}' normalizada: {before_dtype} -> {df[col].dtype}")
    return df


def download_parquet_to_df(blob_name: str) -> pd.DataFrame:
    container_client = get_container_client("bronce-raw")
    blob_client = container_client.get_blob_client(blob_name)
    data = blob_client.download_blob().readall()
    return pd.read_parquet(io.BytesIO(data))


def ingest_prefix(prefix: str, table_name: str, engine) -> int:
    """Descarga TODOS los Parquet que empiecen con `prefix` y los concatena
    en una sola tabla de Postgres, en modo append.

    Devuelve la cantidad total de filas insertadas.
    """
    blob_names = list_files(container="bronce-raw", prefix=prefix)
    if not blob_names:
        print(f"[AVISO] No se encontraron archivos con prefijo '{prefix}'")
        return 0

    print(f"Encontrados {len(blob_names)} archivo(s) con prefijo '{prefix}'")

    dataframes = []
    for blob_name in blob_names:
        try:
            df = download_parquet_to_df(blob_name)
            dataframes.append(df)
        except Exception as e:
            print(f"  [AVISO] No se pudo descargar/leer {blob_name}: {e}")
            continue

    if not dataframes:
        print(f"[AVISO] Ningún archivo se pudo leer correctamente para '{prefix}'")
        return 0

    full_df = pd.concat(dataframes, ignore_index=True)
    print(f"Total combinado: {len(full_df)} filas (antes de subir, puede tener duplicados — se resuelven en dbt)")

    full_df = _normalize_numeric_columns(full_df, table_name)

    full_df.to_sql(
        name=table_name,
        con=engine,
        schema=SCHEMA,
        if_exists="append",
        index=False,
        method="multi",
        chunksize=1000,
    )
    print(f"[OK] Subidas {len(full_df)} filas a {SCHEMA}.{table_name}")
    return len(full_df)


def ensure_schema_exists(engine):
    """Crea el esquema raw_data si todavía no existe."""
    with engine.connect() as conn:
        conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA};"))
        conn.commit()


def main():
    print("Conectando a Azure PostgreSQL...")
    engine = get_pg_engine()
    ensure_schema_exists(engine)

    total_establishments = ingest_prefix(
        "booking/booking_establishments", "booking_establishments", engine
    )
    total_reviews = ingest_prefix(
        "booking/booking_reviews", "booking_reviews", engine
    )

    print(f"\n=== Ingesta completa: {total_establishments} filas de establecimientos, "
          f"{total_reviews} filas de reseñas subidas a {SCHEMA} ===")
    print("Nota: pueden existir duplicados si se corrió este script más de una vez, "
          "o si el scraper re-procesó los mismos establecimientos en distintas corridas. "
          "La deduplicación final se hace en el modelo dbt hacia el esquema silver.")


if __name__ == "__main__":
    main()
