"""
cabildo_pois_upload_blob.py
---------------------------
Descarga los GeoJSON de Puntos de Interés (Oficinas de Turismo, BIC) del 
Portal de Datos Abiertos del Cabildo de Tenerife y los sube directamente 
a Azure Blob Storage sin pasar por disco local.
"""

import os
import io
import requests
import logging
import geopandas as gpd
from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("CabildoPOIs")

load_dotenv()
AZURE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
BLOB_CONTAINER_NAME = "bronce-raw"

DATASETS = [
    {
        "name": "oficinas_turismo_tenerife.parquet",
        "url": "https://datos.tenerife.es/ckan/dataset/89d42ef7-009b-4ec2-8b9b-f6ed50d19998/resource/21beb26c-9862-4b13-9170-ba72de9c739b/download/oficinas-de-informacion-turistica-de-tenerife.geojson",
        "blob_path": "espacial/oficina_turismo/oficinas_turismo_tenerife.parquet"
    },
    {
        "name": "bienes_interes_cultural_tenerife.parquet",
        "url": "https://datos.tenerife.es/ckan/dataset/83530250-3418-43d0-8019-18345a211271/resource/a6766279-e2a7-4cb5-b736-ff2fe028c6b9/download/bic_inmuebles_entornos.geojson",
        "blob_path": "espacial/bienes_interes_cultural/bienes_interes_cultural_tenerife.parquet"
    },
    {
        "name": "limites_municipales_tenerife.parquet",
        "url": "https://datos.tenerife.es/ckan/dataset/d0fae4ae-3bd5-41fc-939b-d7b16e3d5bda/resource/98e3a02c-d7bf-4e1e-b54f-a13ca4fee148/download/municip_4326.geojson",
        "blob_path": "espacial/limites_municipales/limites_municipales_tenerife.parquet"
    }
]

def download_and_upload():
    if not AZURE_CONNECTION_STRING:
        logger.error("AZURE_STORAGE_CONNECTION_STRING no está definido en .env")
        return

    try:
        blob_service_client = BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)
    except Exception as e:
        logger.error(f"Error al conectar con Azure Blob Storage: {e}")
        return

    for ds in DATASETS:
        logger.info(f"Descargando {ds['name']} desde {ds['url']}...")
        try:
            resp = requests.get(ds["url"])
            resp.raise_for_status()
            
            logger.info(f"Convirtiendo a Parquet...")
            gdf = gpd.read_file(io.BytesIO(resp.content))
            parquet_buffer = io.BytesIO()
            gdf.to_parquet(parquet_buffer, index=False)
            parquet_buffer.seek(0)
            
            logger.info(f"Subiendo a Azure: {ds['blob_path']}")
            blob_client = blob_service_client.get_blob_client(container=BLOB_CONTAINER_NAME, blob=ds["blob_path"])
            blob_client.upload_blob(parquet_buffer.read(), overwrite=True)
            logger.info(f"Éxito: {ds['name']} subido correctamente.")
            
        except Exception as e:
            logger.error(f"Error procesando {ds['name']}: {e}")

if __name__ == "__main__":
    download_and_upload()
