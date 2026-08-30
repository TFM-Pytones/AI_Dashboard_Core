import os
import io
import pandas as pd
from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("RepartitionClima")

load_dotenv()
AZURE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
CONTAINER_NAME = "bronce-raw"
SOURCE_PREFIX = "clima/mediciones/"
DEST_PREFIX = "clima/mediciones/"

def repartition_blob(blob_service_client, blob_name):
    try:
        logger.info(f"Procesando {blob_name}...")
        blob_client = blob_service_client.get_blob_client(container=CONTAINER_NAME, blob=blob_name)
        
        # Download blob
        download_stream = blob_client.download_blob()
        df = pd.read_parquet(io.BytesIO(download_stream.readall()))
        
        if 'timestamp' not in df.columns:
            logger.warning(f"No se encontró la columna 'timestamp' en {blob_name}. Saltando...")
            return

        # Convert to datetime
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Extract año and mes
        df['año'] = df['timestamp'].dt.year
        df['mes'] = df['timestamp'].dt.month
        
        basename = os.path.basename(blob_name)
        
        # Group by año and mes and upload
        groups = df.groupby(['año', 'mes'])
        for (anio, mes), group_df in groups:
            # Construct new path: clima/mediciones_particionadas/año=YYYY/mes=MM/estacion_X.parquet
            new_blob_path = f"{DEST_PREFIX}año={anio}/mes={mes:02d}/{basename}"
            
            # Save to buffer
            parquet_buffer = io.BytesIO()
            group_df.to_parquet(parquet_buffer, index=False)
            parquet_buffer.seek(0)
            
            # Upload
            new_blob_client = blob_service_client.get_blob_client(container=CONTAINER_NAME, blob=new_blob_path)
            new_blob_client.upload_blob(parquet_buffer.read(), overwrite=True)
            
        # Al terminar todas las particiones, borramos el blob original para no duplicar datos
        blob_client.delete_blob()
        logger.info(f"Completado {blob_name}: dividido en {len(groups)} particiones y original eliminado.")
        
    except Exception as e:
        logger.error(f"Error procesando {blob_name}: {e}")

def main():
    if not AZURE_CONNECTION_STRING:
        logger.error("Falta AZURE_STORAGE_CONNECTION_STRING en .env")
        return
        
    blob_service_client = BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)
    container_client = blob_service_client.get_container_client(CONTAINER_NAME)
    
    # List all blobs in the source prefix
    blobs = container_client.list_blobs(name_starts_with=SOURCE_PREFIX)
    # Seleccionamos solo los archivos antiguos (los que no tienen 'año=' en la ruta)
    blob_list = [b.name for b in blobs if b.name.endswith('.parquet') and 'año=' not in b.name]
    
    logger.info(f"Encontrados {len(blob_list)} archivos antiguos para particionar.")
    
    for blob_name in blob_list:
        repartition_blob(blob_service_client, blob_name)
        
    logger.info("¡Particionado completado!")

if __name__ == "__main__":
    main()
