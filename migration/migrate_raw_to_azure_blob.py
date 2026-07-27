import os
import sys
import tempfile
import pandas as pd
import psycopg2
from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient

current_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.abspath(os.path.join(current_dir, "..", "..", ".env"))
load_dotenv(env_path, override=True)

# 1. Verificar conexión a Azure Blob Storage
conn_str = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
account_name = "datalaketfmtenerife"

if not conn_str:
    print("\n[ERROR] Falta la variable 'AZURE_STORAGE_CONNECTION_STRING' en el archivo .env.")
    print("Por favor, copia la cadena de conexión de tu cuenta de almacenamiento 'datalaketfmtenerife'")
    print("en el portal de Azure (Storage Account -> Access keys -> Connection string) y agrégala a:")
    print(env_path)
    sys.exit(1)

# Limpiar posibles comillas
conn_str = conn_str.strip('"').strip("'")

# Si el usuario metió solo el Account Key (clave de acceso), construir la cadena de conexión completa automáticamente
if "AccountName=" not in conn_str and "DefaultEndpointsProtocol=" not in conn_str:
    print("-> Se detectó que ingresaste la Clave de Acceso (Access Key).")
    print("   Construyendo la cadena de conexión automáticamente...")
    conn_str = f"DefaultEndpointsProtocol=https;AccountName={account_name};AccountKey={conn_str};EndpointSuffix=core.windows.net"

container_name = "bronce-raw"

tables_to_migrate = [
    "limites_municipales",
    "zonas_turisticas",
    "gtfs_paradas",
    "gtfs_rutas",
    "youtube_videos",
    "youtube_comments",
    "estaciones_agrocabildo",
    "clima_horario_agrocabildo"
]

print("Conectando a Neon PostgreSQL...")
try:
    neon_conn = psycopg2.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        dbname=os.getenv("DB_NAME"),
        port="5432",
        sslmode="require"
    )
except Exception as e:
    print(f"[ERROR] No se pudo conectar a Neon DB: {e}")
    sys.exit(1)

print("Conectando a Azure Blob Storage...")
try:
    blob_service_client = BlobServiceClient.from_connection_string(conn_str)
    container_client = blob_service_client.get_container_client(container_name)
    # Crear el contenedor si no existe
    if not container_client.exists():
        container_client.create_container()
        print(f"Contenedor '{container_name}' creado con éxito.")
except Exception as e:
    print(f"[ERROR] No se pudo conectar a Azure Blob Storage: {e}")
    neon_conn.close()
    sys.exit(1)

# Crear directorio temporal local para guardar los archivos Parquet antes de subirlos
temp_dir = tempfile.mkdtemp()
print(f"Directorio temporal creado en: {temp_dir}")

try:
    for table in tables_to_migrate:
        print(f"\nProcesando tabla: raw_data.{table}...")
        
        # 1. Leer los datos desde Neon
        query = f"SELECT * FROM raw_data.{table};"
        try:
            df = pd.read_sql(query, neon_conn)
            print(f"  -> Filas leídas: {len(df)}")
        except Exception as e:
            print(f"  -> [WARNING] No se pudo leer la tabla {table}: {e}")
            continue

        if len(df) == 0:
            print("  -> Tabla vacía. Se omite la migración de esta tabla.")
            continue

        # 2. Convertir a Parquet
        local_file_path = os.path.join(temp_dir, f"{table}.parquet")
        df.to_parquet(local_file_path, compression="snappy")
        print(f"  -> Parquet guardado localmente en: {local_file_path}")

        # 3. Subir a Azure Blob Storage
        blob_name = f"{table}.parquet"
        print(f"  -> Subiendo a Azure Blob Storage como '{blob_name}'...")
        blob_client = container_client.get_blob_client(blob_name)
        with open(local_file_path, "rb") as data:
            blob_client.upload_blob(data, overwrite=True)
        print(f"  -> [OK] Tabla {table} migrada con éxito a Azure Blob Storage.")

    print("\n=======================================================")
    print("MIGRACIÓN COMPLETADA CON ÉXITO")
    print("=======================================================")

finally:
    neon_conn.close()
    # Eliminar directorio temporal
    try:
        import shutil
        shutil.rmtree(temp_dir)
    except Exception:
        pass
