"""
alojamientos_oficiales_upload_blob.py
------------------------------------
Filtra los datos del Registro Turístico de Canarias para quedarse
únicamente con los establecimientos de la isla de Tenerife.
Luego los convierte a formato Parquet y los sube a Azure Blob Storage.
"""

import os
import pandas as pd
import logging
from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("RegistroTuristicoTenerife")

# Cargar variables de entorno
load_dotenv()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TABULAR_RAW_DIR = os.path.join(BASE_DIR, "data", "bronce", "tabular", "raw")

AZURE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
BLOB_CONTAINER_NAME = "bronce-raw"
BLOB_FOLDER = "alojamientos_oficiales"

FILES_TO_PROCESS = [
    "registro_hoteles.csv",
    "registro_extrahoteleros.csv",
    "registro_viviendas_vacacionales.csv"
]

def process_and_upload():
    if not AZURE_CONNECTION_STRING:
        logger.error("AZURE_STORAGE_CONNECTION_STRING no está definido en el archivo .env")
        return

    try:
        logger.info("Conectando a Azure Blob Storage...")
        blob_service_client = BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)
    except Exception as e:
        logger.error(f"Error al conectar con Azure Blob Storage: {e}")
        return

    for csv_filename in FILES_TO_PROCESS:
        csv_path = os.path.join(TABULAR_RAW_DIR, csv_filename)
        
        if not os.path.exists(csv_path):
            logger.warning(f"Archivo no encontrado, saltando: {csv_path}")
            continue

        base_name = os.path.splitext(csv_filename)[0]
        # Crear nombre específico para Tenerife
        parquet_filename = f"{base_name}_tenerife.parquet"
        parquet_path = os.path.join(TABULAR_RAW_DIR, parquet_filename)
        blob_destination_path = f"{BLOB_FOLDER}/{parquet_filename}"

        try:
            logger.info(f"\n--- Procesando: {csv_filename} ---")
            
            # El delimitador del Gobierno de Canarias suele ser ;
            df = pd.read_csv(csv_path, sep=';', dtype=str)
            initial_rows = len(df)
            
            # Filtrar solo Tenerife
            if 'direccion_isla_nombre' in df.columns:
                df_tf = df[df['direccion_isla_nombre'] == 'Tenerife'].copy()
                logger.info(f"Filtro 'Tenerife' aplicado: {initial_rows:,} -> {len(df_tf):,} filas.")
            else:
                logger.warning(f"No se encontró la columna 'direccion_isla_nombre' en {csv_filename}. Subiendo sin filtrar.")
                df_tf = df.copy()

            # Guardar Parquet localmente
            df_tf.to_parquet(parquet_path, index=False, compression="snappy")
            
            csv_size = os.path.getsize(csv_path) / (1024 * 1024)
            parquet_size = os.path.getsize(parquet_path) / (1024 * 1024)
            logger.info(f"  Conversión Parquet: {csv_size:.2f} MB CSV -> {parquet_size:.2f} MB Parquet")

            # Subir a Azure
            blob_client = blob_service_client.get_blob_client(container=BLOB_CONTAINER_NAME, blob=blob_destination_path)
            logger.info(f"  Subiendo a Azure: '{BLOB_CONTAINER_NAME}/{blob_destination_path}'...")
            with open(parquet_path, "rb") as data:
                blob_client.upload_blob(data, overwrite=True)
            logger.info(f" {parquet_filename} subido correctamente.")

        except Exception as e:
            logger.error(f"Error procesando {csv_filename}: {e}")

    logger.info("\nProceso de filtro y subida a Azure completado.")

if __name__ == "__main__":
    process_and_upload()
