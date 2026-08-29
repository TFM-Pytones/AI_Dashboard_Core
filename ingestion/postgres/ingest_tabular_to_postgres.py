import os
import io
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from azure.storage.blob import BlobServiceClient

# Cargar variables de entorno locales
load_dotenv()

# --- Configuración Azure Blob Storage (Capa Bronce / Raw) ---
AZURE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
BLOB_CONTAINER_NAME = "bronce-raw"

# --- Configuración de Ingesta Incremental (Clima) ---
INCREMENTAL_LOAD = True  # Cambiar a False para ingesta histórica completa

# --- Configuración Azure PostgreSQL (Flexible Server) ---
PG_USER = os.getenv("AZURE_DB_USER")
PG_PASS = os.getenv("AZURE_DB_PASSWORD")
PG_HOST = os.getenv("AZURE_DB_HOST")
PG_PORT = os.getenv("AZURE_DB_PORT", "5432")
PG_DB = os.getenv("AZURE_DB_NAME")

TARGET_SCHEMA = "bronze"

def get_pg_engine():
    """Crea la conexión a Azure PostgreSQL (Capa Bronze)."""
    connection_string = f"postgresql://{PG_USER}:{PG_PASS}@{PG_HOST}:{PG_PORT}/{PG_DB}"
    return create_engine(connection_string, connect_args={'sslmode': 'require'})

def ensure_schema_exists(engine, schema_name: str = TARGET_SCHEMA):
    """Crea el esquema objetivo en PostgreSQL si no existe."""
    with engine.connect() as conn:
        conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema_name};"))
        conn.commit()

def download_blob_to_dataframe(blob_service_client, blob_name: str) -> pd.DataFrame:
    """Descarga un archivo .csv, .parquet o .geojson de Azure Blob Storage a un DataFrame de Pandas."""
    blob_client = blob_service_client.get_blob_client(container=BLOB_CONTAINER_NAME, blob=blob_name)
    download_stream = blob_client.download_blob()
    content_bytes = download_stream.readall()
    
    if blob_name.endswith('.csv'):
        return pd.read_csv(io.BytesIO(content_bytes))
    elif blob_name.endswith('.parquet'):
        return pd.read_parquet(io.BytesIO(content_bytes))
    elif blob_name.endswith('.geojson'):
        import json
        geojson_dict = json.loads(content_bytes.decode('utf-8'))
        records = []
        for feature in geojson_dict.get('features', []):
            props = feature.get('properties', {})
            geom = feature.get('geometry', {})
            if geom and geom.get('type') == 'Point':
                coords = geom.get('coordinates', [])
                if len(coords) == 2:
                    props['lon'] = coords[0]
                    props['lat'] = coords[1]
            records.append(props)
        return pd.DataFrame(records)
    else:
        raise ValueError(f"Formato no soportado para lectura directa en DataFrame: {blob_name}")

import csv

def psql_insert_copy(table, conn, keys, data_iter):
    """Ejecuta un COPY de PostgreSQL (100x más rápido que INSERTs)"""
    dbapi_conn = conn.connection
    with dbapi_conn.cursor() as cur:
        s_buf = io.StringIO()
        writer = csv.writer(s_buf)
        writer.writerows(data_iter)
        s_buf.seek(0)
        columns = ', '.join([f'"{k}"' for k in keys])
        table_name = f'"{table.schema}"."{table.name}"' if table.schema else f'"{table.name}"'
        sql = f'COPY {table_name} ({columns}) FROM STDIN WITH CSV'
        cur.copy_expert(sql=sql, file=s_buf)

def ingest_to_postgres(df: pd.DataFrame, table_name: str, engine, if_exists: str = "replace"):
    """Inserta un DataFrame en el esquema 'bronze' de PostgreSQL usando COPY."""
    print(f"  -> Cargando {len(df)} filas en '{TARGET_SCHEMA}.{table_name}' ({if_exists})...")
    df.to_sql(
        name=table_name,
        con=engine,
        schema=TARGET_SCHEMA,
        if_exists=if_exists,
        index=False,
        method=psql_insert_copy,
        chunksize=250000
    )
    print(f"  [OK] Tabla '{TARGET_SCHEMA}.{table_name}' actualizada correctamente.")

def main():
    if not AZURE_CONNECTION_STRING:
        print("[ERROR] AZURE_STORAGE_CONNECTION_STRING no esta definido en el archivo .env")
        return
        
    print("======================================================================")
    print("INGESTA DESDE AZURE BLOB STORAGE -> AZURE POSTGRESQL (ESQUEMA BRONZE)")
    print("======================================================================")
    
    blob_service_client = BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)
    engine = get_pg_engine()
    ensure_schema_exists(engine, TARGET_SCHEMA)

    container_client = blob_service_client.get_container_client(BLOB_CONTAINER_NAME)
    blobs = [b.name for b in container_client.list_blobs()]

    # 1. TABLAS TABULARES / ISTAC / AENA / ALOJAMIENTOS / GTFS / YOUTUBE / ESPACIALES
    # ---------------------------------------------------------------------------------
    mapping_directo = {
        # AENA
        "aena/aena_pasajeros_tenerife.parquet": "aena_pasajeros",
        # Alojamientos Oficiales (Registro Turístico)
        "alojamientos_oficiales/registro_extrahoteleros_tenerife.parquet": "registro_extrahoteleros",
        "alojamientos_oficiales/registro_hoteles_tenerife.parquet": "registro_hoteles",
        "alojamientos_oficiales/registro_viviendas_vacacionales_tenerife.parquet": "registro_viviendas_vacacionales",
        # GTFS
        "gtfs/gtfs_paradas.parquet": "gtfs_paradas",
        "gtfs/gtfs_rutas.parquet": "gtfs_rutas",
        # YouTube
        "youtube/youtube_comments.parquet": "youtube_comments",
        "youtube/youtube_videos.parquet": "youtube_videos",
        # Metadatos Estaciones
        "clima/estaciones/estaciones_agrocabildo.parquet": "estaciones_agrocabildo",
        "clima/sensores/sensores_meteorologicos.parquet": "sensores_meteorologicos"        
    }

    # Añadir dinámicamente todos los archivos Parquet de ISTAC
    for blob in blobs:
        if blob.startswith("istac/") and blob.endswith(".parquet"):
            table_name = blob.split("/")[-1].replace(".parquet", "")
            mapping_directo[blob] = table_name

    print("\n--- 1. Carga de Datasets Directos (ISTAC, AENA, Registro, GTFS, YouTube, Espaciales) ---")
    for blob_name, table_name in mapping_directo.items():
        if blob_name in blobs:
            try:
                print(f"\nProcesando Blob: {blob_name}")
                df = download_blob_to_dataframe(blob_service_client, blob_name)
                ingest_to_postgres(df, table_name, engine, if_exists="replace")
            except Exception as e:
                print(f"  [ERROR] Error procesando {blob_name}: {e}")
        else:
            print(f"  [Omitido] Blob no encontrado aun en Azure: {blob_name}")

    # 2. LECTURAS PARTICIONADAS DE CLIMA (AGROCABILDO)
    # -------------------------------------------------------------
    print("\n--- 2. Carga de Lecturas Particionadas de Clima (Capa Bronce) ---")
    clima_blobs = [b for b in blobs if b.startswith("clima/mediciones/") and b.endswith(".parquet")]
    
    if INCREMENTAL_LOAD:
        from datetime import datetime
        now = datetime.now()
        current_year = now.year
        current_month = now.month
        # Filtramos para quedarnos solo con la partición del mes y año actual
        prefix_to_find = f"año={current_year}/mes={current_month:02d}/"
        clima_blobs = [b for b in clima_blobs if prefix_to_find in b]
        print(f"Modo INCREMENTAL activado. Filtrando por partición: {prefix_to_find}")
    else:
        print("Modo FULL LOAD activado. Se procesarán TODAS las particiones históricas.")

    if clima_blobs:
        print(f"Encontrados {len(clima_blobs)} archivos de particiones de clima.")
        first = not INCREMENTAL_LOAD # Si es incremental, hacemos 'append' a la tabla existente. Si es full load, 'replace' la primera vez.
        for blob_name in clima_blobs:
            try:
                df_st = download_blob_to_dataframe(blob_service_client, blob_name)
                mode = "replace" if first else "append"
                ingest_to_postgres(df_st, "clima_horario_agrocabildo", engine, if_exists=mode)
                first = False
            except Exception as e:
                print(f"  [ERROR] Error al procesar lecturas de {blob_name}: {e}")
    else:
        print("  [Info] No se encontraron archivos particionados para ingestar.")

    print("\n======================================================================")
    print("PROCESO DE INGESTA COMPLETO HACIA AZURE POSTGRESQL (SCHEMA: BRONZE)")
    print("======================================================================")

if __name__ == "__main__":
    main()
