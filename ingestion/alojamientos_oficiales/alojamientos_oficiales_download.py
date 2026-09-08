import os
import io
import requests
import pandas as pd
import logging
from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("AlojamientosOficiales")

load_dotenv()

AZURE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
BLOB_CONTAINER_NAME = "bronce-raw"
BLOB_FOLDER = "alojamientos_oficiales"

DATASETS = [
    {
        "name": "registro_hoteles",
        "url": "https://datos.canarias.es/catalogos/general/dataset/429db33d-cbce-4920-b1b6-b4dde9e5f90f/resource/87741d75-2ce2-4a45-8131-ad8263257664/download/establecimientos-hoteleros-inscritos-en-el-registro-general-turistico-de-canarias.csv",
    },
    {
        "name": "registro_extrahoteleros",
        "url": "https://datos.canarias.es/catalogos/general/dataset/1364104c-b86c-4ab9-8ef5-12fdf399aa01/resource/d98c2617-db26-4d15-8ee4-3b2da1130bd0/download/establecimientos-extrahoteleros-sin-viviendas-vacacionales-inscritos-en-el-registro-general-turi.csv",
    },
    {
        "name": "registro_viviendas_vacacionales",
        "url": "https://datos.canarias.es/catalogos/general/dataset/9f4355a2-d086-4384-ba72-d8c99aa2d544/resource/8ff8cc43-c00b-4513-8f42-a5b961c579e1/download/establecimientos-extrahoteleros-de-tipologia-vivienda-vacacional-inscritos-en-el-registro-genera.csv",
    },
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

    for dataset in DATASETS:
        dataset_name = dataset["name"]
        url = dataset["url"]
        parquet_filename = f"{dataset_name}_tenerife.parquet"
        blob_destination_path = f"{BLOB_FOLDER}/{parquet_filename}"

        try:
            logger.info(f"\n--- Descargando en memoria: {dataset_name} ---")
            response = requests.get(url)
            response.raise_for_status()
            
            # Cargar el CSV directamente en memoria
            csv_bytes = io.BytesIO(response.content)
            df = pd.read_csv(csv_bytes, sep=';', dtype=str)
            initial_rows = len(df)
            
            # Filtrar solo Tenerife
            if 'direccion_isla_nombre' in df.columns:
                df_tf = df[df['direccion_isla_nombre'] == 'Tenerife'].copy()
                logger.info(f"Filtro 'Tenerife' aplicado: {initial_rows:,} -> {len(df_tf):,} filas.")
            else:
                logger.warning(f"No se encontró la columna 'direccion_isla_nombre' en {dataset_name}. Subiendo sin filtrar.")
                df_tf = df.copy()

            # Convertir a Parquet en memoria
            parquet_buffer = io.BytesIO()
            df_tf.to_parquet(parquet_buffer, index=False, compression="snappy")
            parquet_buffer.seek(0)
            
            parquet_size = len(parquet_buffer.getvalue()) / (1024 * 1024)
            logger.info(f"Conversión en memoria completada. Tamaño Parquet: {parquet_size:.2f} MB")

            # Subir a Azure directamente desde el buffer
            blob_client = blob_service_client.get_blob_client(container=BLOB_CONTAINER_NAME, blob=blob_destination_path)
            logger.info(f"Subiendo a Azure: '{BLOB_CONTAINER_NAME}/{blob_destination_path}'...")
            blob_client.upload_blob(parquet_buffer, overwrite=True)
            logger.info(f" {parquet_filename} subido correctamente.")

        except Exception as e:
            logger.error(f"Error procesando {dataset_name}: {e}")

    logger.info("\nProceso de extracción, filtrado y subida a Azure completado 100% en memoria.")

if __name__ == "__main__":
    process_and_upload()
