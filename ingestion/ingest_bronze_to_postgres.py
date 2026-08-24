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
    """Descarga un archivo .csv o .parquet de Azure Blob Storage a un DataFrame de Pandas."""
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

def ingest_to_postgres(df: pd.DataFrame, table_name: str, engine, if_exists: str = "replace"):
    """Inserta un DataFrame en el esquema 'bronze' de PostgreSQL."""
    print(f"  -> Cargando {len(df)} filas en '{TARGET_SCHEMA}.{table_name}' ({if_exists})...")
    df.to_sql(
        name=table_name,
        con=engine,
        schema=TARGET_SCHEMA,
        if_exists=if_exists,
        index=False,
        method="multi",
        chunksize=2000
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

    # 1. TABLAS TABULARES / ISTAC / AENA / REGISTRO TURISTICO
    # -------------------------------------------------------------
    mapping_directo = {
        # AENA
        "tabular/aena/aena_pasajeros_tenerife.parquet": "aena_pasajeros",
        # Registro Turistico
        "tabular/registro_turistico/registro_extrahoteleros_tenerife.parquet": "registro_extrahoteleros",
        "tabular/registro_turistico/registro_hoteles_tenerife.parquet": "registro_hoteles",
        "tabular/registro_turistico/registro_viviendas_vacacionales_tenerife.parquet": "registro_viviendas_vacacionales",
        # GTFS
        "gtfs_paradas.parquet": "gtfs_paradas",
        "gtfs_rutas.parquet": "gtfs_rutas",
        # YouTube
        "youtube_comments.parquet": "youtube_comments",
        "youtube_videos.parquet": "youtube_videos",
        # Spatial Vectorial (como DataFrame)
        "limites_municipales.parquet": "limites_municipales",
        "zonas_turisticas.parquet": "zonas_turisticas",
        "espacial/osm/osm_pois_tenerife.geojson": "osm_pois_tenerife",
        # Metadatos Estaciones
        "estaciones_agrocabildo.parquet": "estaciones_agrocabildo",
        # Forecast / Validacion
        "forecast_gfs/hist_forecast_gfs_seamless_consolidado.parquet": "open_meteo_forecast",
        "satelite_era5land/era5land_consolidado.parquet": "open_meteo_era5land",
        "leadtime_gfs/leadtime_gfs_seamless_consolidado.parquet": "open_meteo_leadtime"
    }

    # Añadir dinámicamente los 18 archivos Parquet de ISTAC
    for blob in blobs:
        if blob.startswith("tabular/istac/") and blob.endswith(".parquet"):
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

    # 2. LECTURAS PARTICIONADAS DE AGROCABILDO
    # -------------------------------------------------------------
    print("\n--- 2. Carga de Lecturas Particionadas de Agrocabildo (Capa Bronce) ---")
    clima_blobs = [b for b in blobs if b.startswith("clima_horario_agrocabildo/estacion_") and b.endswith(".parquet")]
    
    if clima_blobs:
        print(f"Encontrados {len(clima_blobs)} archivos de estaciones meteorologicas.")
        first = True
        for blob_name in clima_blobs:
            try:
                df_st = download_blob_to_dataframe(blob_service_client, blob_name)
                mode = "replace" if first else "append"
                ingest_to_postgres(df_st, "clima_horario_agrocabildo", engine, if_exists=mode)
                first = False
            except Exception as e:
                print(f"  [ERROR] Error al procesar lecturas de {blob_name}: {e}")
    else:
        print("  [Info] No se encontraron archivos en clima_horario_agrocabildo/")

    print("\n======================================================================")
    print("PROCESO DE INGESTA COMPLETO HACIA AZURE POSTGRESQL (SCHEMA: BRONZE)")
    print("======================================================================")

if __name__ == "__main__":
    main()
