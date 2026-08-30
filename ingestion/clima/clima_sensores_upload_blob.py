import os
import io
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine
from azure.storage.blob import BlobServiceClient

# Cargar variables de entorno
load_dotenv()
AZURE_CONN_STR = os.getenv('AZURE_STORAGE_CONNECTION_STRING')
DB_URL = os.getenv('AZURE_DB_URL')

if not AZURE_CONN_STR or not DB_URL:
    print("Faltan credenciales en el archivo .env")
    exit(1)

# Rutas
csv_path = r'C:\Users\ROBERTO\Proyectos_Python\TFM_TUI_Tenerife\AI_Dashboard_Core\data\clima_horario_agrocabildo\sensores-meteorologicos.csv'
blob_container = 'bronce-raw'
blob_path = 'clima/sensores/sensores_meteorologicos.parquet'
table_name = 'sensores_meteorologicos'
schema_name = 'bronze'

print(f"Leyendo CSV desde {csv_path}...")
df = pd.read_csv(csv_path)

# Convertir a Parquet en memoria
print("Convirtiendo a Parquet...")
parquet_buffer = io.BytesIO()
df.to_parquet(parquet_buffer, index=False)
parquet_buffer.seek(0)

# 1. Subir a Azure Blob Storage
print(f"Subiendo a Azure Blob Storage ({blob_container}/{blob_path})...")
blob_service_client = BlobServiceClient.from_connection_string(AZURE_CONN_STR)
container_client = blob_service_client.get_container_client(blob_container)

try:
    container_client.create_container()
except Exception:
    pass # Ya existe

blob_client = container_client.get_blob_client(blob_path)
blob_client.upload_blob(parquet_buffer, overwrite=True)
print(" Archivo Parquet subido al Datalake con éxito.")

# 2. Subir a PostgreSQL
print(f"Subiendo a PostgreSQL ({schema_name}.{table_name})...")
engine = create_engine(DB_URL)
df.to_sql(table_name, engine, schema=schema_name, if_exists='replace', index=False)
print(" Datos cargados en PostgreSQL con éxito.")
