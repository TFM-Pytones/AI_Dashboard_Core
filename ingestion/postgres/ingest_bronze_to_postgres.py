import os
import io
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine
from azure.storage.blob import BlobServiceClient

# Cargar variables de entorno locales
load_dotenv()

# --- Configuración Azure Blob Storage (Capa Bronce) ---
AZURE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
BLOB_CONTAINER_NAME = "bronce-raw"

# --- Configuración Azure PostgreSQL (Capa Plata / Esquema Raw) ---
PG_USER = os.getenv("AZURE_DB_USER")
PG_PASS = os.getenv("AZURE_DB_PASSWORD")
PG_HOST = os.getenv("AZURE_DB_HOST")
PG_PORT = "5432"
PG_DB = os.getenv("AZURE_DB_NAME")

def get_pg_engine():
    """Crea la conexión a Azure PostgreSQL"""
    connection_string = f"postgresql://{PG_USER}:{PG_PASS}@{PG_HOST}:{PG_PORT}/{PG_DB}"
    # Se añade sslmode=require para Azure Flexible Server
    return create_engine(connection_string, connect_args={'sslmode': 'require'})

def download_blob_to_dataframe(blob_service_client, blob_name):
    """Descarga un archivo .csv o .parquet de Azure Blob Storage a un DataFrame de pandas"""
    blob_client = blob_service_client.get_blob_client(container=BLOB_CONTAINER_NAME, blob=blob_name)
    download_stream = blob_client.download_blob()
    
    if blob_name.endswith('.csv'):
        df = pd.read_csv(io.BytesIO(download_stream.readall()))
    elif blob_name.endswith('.parquet'):
        df = pd.read_parquet(io.BytesIO(download_stream.readall()))
    else:
        raise ValueError(f"Formato de archivo no soportado: {blob_name}")
    
    return df

def ingest_to_postgres(df, table_name, engine):
    """Inserta el DataFrame en el esquema bronze de PostgreSQL"""
    print(f"Ingestando {len(df)} filas en la tabla bronze.{table_name}...")
    
    # Escribimos los datos en el esquema 'bronze'. dbt se encargará luego de pasarlos a 'silver'
    df.to_sql(
        name=table_name,
        con=engine,
        schema="bronze",
        if_exists="replace", # o 'append' dependiendo de la lógica incremental
        index=False,
        method="multi", # optimización de inserción
        chunksize=1000
    )
    print(f"[OK] Ingesta en bronze.{table_name} completada.")

def main():
    if not AZURE_CONNECTION_STRING:
        print("[ERROR] AZURE_STORAGE_CONNECTION_STRING no está definido en el archivo .env")
        return
        
    print("Conectando a Azure Blob Storage...")
    blob_service_client = BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)
    engine = get_pg_engine()
    
    # -------------------------------------------------------------
    # EJEMPLO DE INGESTA: Modifica esto según los nombres de tus archivos
    # -------------------------------------------------------------
    archivos_a_ingestar = [
        # ("nombre_del_blob_en_azure.csv/.parquet", "nombre_de_la_tabla_en_postgres")
        # ("clima/historico_agrocabildo.csv", "estaciones_clima"),
        ("tabular/istac/istac_municipios_cifras_tenerife.parquet", "istac_municipios"),
    ]
    
    for blob_name, table_name in archivos_a_ingestar:
        try:
            print(f"\nDescargando '{blob_name}' desde Capa Bronce...")
            df = download_blob_to_dataframe(blob_service_client, blob_name)
            
            # (Opcional) Si necesitas hacer alguna limpieza ligerísima antes de guardar en raw:
            # df = df.dropna(how='all') 
            
            ingest_to_postgres(df, table_name, engine)
            
        except Exception as e:
            print(f"[ERROR] Error al procesar {blob_name}: {e}")

if __name__ == "__main__":
    main()
