import os
import sys
from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient

# Cargar el archivo .env (buscándolo en la raíz del proyecto)
load_dotenv()

# 1. Autenticación en Azure (Lógica heredada del equipo)
conn_str = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
account_name = "datalaketfmtenerife"

if not conn_str:
    print("\n[ERROR] Falta la variable 'AZURE_STORAGE_CONNECTION_STRING' en tu archivo .env.")
    sys.exit(1)

conn_str = conn_str.strip('"').strip("'")
if "AccountName=" not in conn_str and "DefaultEndpointsProtocol=" not in conn_str:
    conn_str = f"DefaultEndpointsProtocol=https;AccountName={account_name};AccountKey={conn_str};EndpointSuffix=core.windows.net"

container_name = "bronce-raw"

# 2. Archivos locales que vamos a subir
archivos_a_subir = [
    "losviajeros_temas.parquet",
    "losviajeros_mensajes.parquet"
]

print("Conectando a Azure Blob Storage...")
try:
    blob_service_client = BlobServiceClient.from_connection_string(conn_str)
    container_client = blob_service_client.get_container_client(container_name)
except Exception as e:
    print(f"[ERROR] No se pudo conectar a Azure Blob Storage: {e}")
    sys.exit(1)

# 3. Subida de archivos
for archivo in archivos_a_subir:
    if not os.path.exists(archivo):
        print(f"[WARNING] No se encontró el archivo local: {archivo}")
        continue

    print(f"\nSubiendo '{archivo}' al contenedor '{container_name}'...")
    blob_client = container_client.get_blob_client(archivo)
    
    with open(archivo, "rb") as data:
        blob_client.upload_blob(data, overwrite=True)
        
    print(f" -> [OK] {archivo} subido con éxito.")

print("\n=======================================================")
print("SUBIDA A LA CAPA BRONCE COMPLETADA")
print("=======================================================")