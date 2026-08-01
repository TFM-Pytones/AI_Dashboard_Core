"""
upload_istac_to_blob.py
-----------------------
Convierte el dataset local consolidado de ISTAC (CSV) a Parquet 
con compresión snappy y lo sube al contenedor Azure Blob Storage 'bronce-raw'.
"""

import os
import io
import pandas as pd
import logging
from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("UploadISTAC")

# Cargar variables de entorno
load_dotenv()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CSV_FILE = os.path.join(BASE_DIR, "data", "bronce", "tabular", "raw", "istac_municipios_cifras_tenerife.csv")
PARQUET_FILE = os.path.join(BASE_DIR, "data", "bronce", "tabular", "raw", "istac_municipios_cifras_tenerife.parquet")


AZURE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
BLOB_CONTAINER_NAME = "bronce-raw"
BLOB_DESTINATION_PATH = "tabular/istac/istac_municipios_cifras_tenerife.parquet"

def main():
    if not AZURE_CONNECTION_STRING:
        logger.error("❌ AZURE_STORAGE_CONNECTION_STRING no está definido en el archivo .env")
        return

    if not os.path.exists(CSV_FILE):
        logger.error(f"❌ No se encontró el archivo CSV origen: {CSV_FILE}")
        return

    # 1. Leer el CSV consolidado
    logger.info(f"Leyendo CSV consolidado: {CSV_FILE}")
    df = pd.read_csv(CSV_FILE)
    logger.info(f"Datos cargados: {len(df):,} filas.")

    # 2. Guardar localmente como Parquet (compresión Snappy)
    logger.info(f"Convirtiendo a formato Parquet...")
    df.to_parquet(PARQUET_FILE, index=False, compression="snappy")
    
    csv_size = os.path.getsize(CSV_FILE) / (1024 * 1024)
    parquet_size = os.path.getsize(PARQUET_FILE) / (1024 * 1024)
    logger.info(f"Conversión completada. Tamaño CSV: {csv_size:.2f} MB -> Tamaño Parquet: {parquet_size:.2f} MB")

    # 3. Subir a Azure Blob Storage
    logger.info("Conectando a Azure Blob Storage...")
    try:
        blob_service_client = BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)
        blob_client = blob_service_client.get_blob_client(container=BLOB_CONTAINER_NAME, blob=BLOB_DESTINATION_PATH)
        
        logger.info(f"Subiendo a contenedor '{BLOB_CONTAINER_NAME}', ruta '{BLOB_DESTINATION_PATH}'...")
        with open(PARQUET_FILE, "rb") as data:
            blob_client.upload_blob(data, overwrite=True)
            
        logger.info("✅ Subida completada exitosamente.")
    except Exception as e:
        logger.error(f"❌ Error al subir a Azure: {e}")

if __name__ == "__main__":
    main()
