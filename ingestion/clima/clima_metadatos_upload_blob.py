import os
import io
import requests
import pandas as pd
import logging
from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ClimaMetadatosIngestion")

load_dotenv()
AZURE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
BLOB_CONTAINER_NAME = "bronce-raw"

BASE_URL = "https://datos.tenerife.es/api/meteo/latest"

def fetch_and_upload_stations(blob_service_client):
    logger.info("Obteniendo lista de estaciones desde API...")
    url = f"{BASE_URL}/stations"
    response = requests.get(url)
    response.raise_for_status()
    datos = response.json()
    
    df = pd.json_normalize(datos['stations'])
    
    if not df.empty:
        col_map = {
            "id_weatherstation": "estacion_id",
            "name": "estacion_nombre",
            "municipality_name": "municipio_nombre",
            "latitude": "latitud",
            "longitude": "longitud",
            "altitude": "altitud",
            "date_install": "fecha_instalacion"
        }
        df.rename(columns=col_map, inplace=True)
        if "fecha_instalacion" not in df.columns:
            df["fecha_instalacion"] = None
            
        cols_to_keep = ['estacion_id', 'estacion_nombre', 'municipio_nombre', 'latitud', 'longitud', 'altitud', 'fecha_instalacion']
        df = df[[c for c in cols_to_keep if c in df.columns]]

    logger.info(f"Se obtuvieron {len(df)} estaciones.")
    
    parquet_buffer = io.BytesIO()
    df.to_parquet(parquet_buffer, index=False, compression="snappy")
    parquet_buffer.seek(0)
    
    blob_destination_path = "clima/estaciones/estaciones_agrocabildo.parquet"
    blob_client = blob_service_client.get_blob_client(container=BLOB_CONTAINER_NAME, blob=blob_destination_path)
    blob_client.upload_blob(parquet_buffer, overwrite=True)
    logger.info(f"✅ Estaciones subidas a: {blob_destination_path}")

def fetch_and_upload_measures(blob_service_client):
    logger.info("Obteniendo lista de sensores/medidas desde API...")
    url = f"{BASE_URL}/measures"
    response = requests.get(url)
    response.raise_for_status()
    datos = response.json()
    
    df = pd.json_normalize(datos['measures']) if 'measures' in datos else pd.DataFrame(datos)
    
    logger.info(f"Se obtuvieron {len(df)} sensores/medidas.")
    
    parquet_buffer = io.BytesIO()
    df.to_parquet(parquet_buffer, index=False, compression="snappy")
    parquet_buffer.seek(0)
    
    blob_destination_path = "clima/sensores/sensores_meteorologicos.parquet"
    blob_client = blob_service_client.get_blob_client(container=BLOB_CONTAINER_NAME, blob=blob_destination_path)
    blob_client.upload_blob(parquet_buffer, overwrite=True)
    logger.info(f"✅ Sensores subidos a: {blob_destination_path}")

def main():
    if not AZURE_CONNECTION_STRING:
        logger.error("AZURE_STORAGE_CONNECTION_STRING no esta definido en el archivo .env")
        return
        
    try:
        blob_service_client = BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)
    except Exception as e:
        logger.error(f"Error al conectar con Azure Blob Storage: {e}")
        return
        
    try:
        fetch_and_upload_stations(blob_service_client)
        fetch_and_upload_measures(blob_service_client)
        logger.info("Pipeline de metadatos de clima completado con exito.")
    except Exception as e:
        logger.error(f"Error durante el proceso: {e}")

if __name__ == "__main__":
    main()
