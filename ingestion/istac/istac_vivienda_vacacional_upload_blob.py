"""
istac_vivienda_vacacional_upload_blob.py
----------------------------------------
Descarga estadísticas de vivienda vacacional del ISTAC via API.

Uso:
    python ingestion/istac/istac_vivienda_vacacional_upload_blob.py
"""

import os
import io
import pandas as pd
import requests
import logging
from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ISTAC_VV")

load_dotenv()
AZURE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
BLOB_CONTAINER_NAME = "bronce-raw"

API_URL = "https://datos.canarias.es/api/estadisticas/statistical-resources/v1.0/datasets/ISTAC/C00065A_000061/~latest.csv"

# 31 Municipios de Tenerife (nombres exactos + variantes del ISTAC)
MUNICIPIOS_TENERIFE_NOMBRES = {
    "Adeje", "Arafo", "Arico", "Arona", "Buenavista del Norte", 
    "Candelaria", "Fasnia", "Garachico", "Granadilla de Abona", 
    "La Guancha", "Guía de Isora", "Güímar", "Icod de los Vinos", 
    "San Cristóbal de La Laguna", "La Matanza de Acentejo", "La Orotava", 
    "Puerto de la Cruz", "Puerto de La Cruz",
    "Los Realejos", "El Rosario", "San Juan de la Rambla", 
    "San Miguel de Abona", "Santa Cruz de Tenerife", "Santa Úrsula", 
    "Santiago del Teide", "El Sauzal", "Los Silos", "Tacoronte", 
    "El Tanque", "Tegueste", "La Victoria de Acentejo", "Vilaflor de Chasna",
    "La Laguna", "San Cristóbal de L"
}

METRIC_MAP = {
    'Plazas disponibles': 'plazas_vv',
    'Tasa de vivienda reservada': 'tasa_ocupacion_vv',
    'Estancia media en la vivienda vacacional': 'estancia_media_vv',
    'Ingresos totales': 'ingresos_vv',
    'Viviendas vacacionales disponibles': 'alojamientos_abiertos_vv'
}

def fetch_and_process():
    if not AZURE_CONNECTION_STRING:
        logger.error("AZURE_STORAGE_CONNECTION_STRING no está definido.")
        return

    try:
        blob_service_client = BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)
    except Exception as e:
        logger.error(f"Error al conectar con Azure Blob Storage: {e}")
        return

    logger.info(f"Descargando datos VV desde {API_URL}")
    r = requests.get(API_URL, timeout=120)
    r.raise_for_status()
    
    df = pd.read_csv(io.StringIO(r.content.decode('utf-8')))
    logger.info(f"Datos descargados. Total filas: {len(df)}")
    
    # Filtrar Tenerife
    df_tf = df[df['TERRITORIO#es'].isin(MUNICIPIOS_TENERIFE_NOMBRES)].copy()
    logger.info(f"Filas tras filtrar municipios de Tenerife: {len(df_tf)}")

    # Filtro 'Total' en Intervalos
    if 'INTERVALOS_PLAZAS#es' in df_tf.columns:
        df_tf = df_tf[df_tf['INTERVALOS_PLAZAS#es'] == 'Total'].copy()
        logger.info(f"Filas tras filtrar INTERVALOS_PLAZAS = 'Total': {len(df_tf)}")

    # Limpiar TIME_CODE (de 2019-M01 a 2019-01)
    df_tf['TIME_CODE'] = df_tf['TIME_PERIOD_CODE'].str.replace("-M", "-", regex=False)
    
    # Procesar y guardar cada métrica
    for metric_es, indicator_name in METRIC_MAP.items():
        df_metric = df_tf[df_tf['MEDIDAS#es'] == metric_es].copy()
        
        if df_metric.empty:
            logger.warning(f"No hay datos para la métrica '{metric_es}'")
            continue
            
        # Normalizar columnas para que coincida con la capa bronce actual
        df_out = pd.DataFrame()
        # Normalizar "Puerto de La Cruz" a "Puerto de la Cruz"
        df_out['GEOGRAPHICAL'] = df_metric['TERRITORIO#es'].str.replace("Puerto de La Cruz", "Puerto de la Cruz")
        df_out['GEOGRAPHICAL_CODE'] = df_metric['TERRITORIO_CODE']
        df_out['TIME'] = df_metric['TIME_PERIOD#es']
        df_out['TIME_CODE'] = df_metric['TIME_CODE']
        df_out['MEASURE_CODE'] = 'ABSOLUTE'
        df_out['OBS_VALUE'] = df_metric['OBS_VALUE']
        df_out['_indicador'] = indicator_name
        
        
        blob_path = f"istac/istac_mun_{indicator_name}.parquet"
        try:
            buffer = io.BytesIO()
            df_out.to_parquet(buffer, index=False, compression="snappy")
            buffer.seek(0)
            blob_client = blob_service_client.get_blob_client(container=BLOB_CONTAINER_NAME, blob=blob_path)
            blob_client.upload_blob(buffer, overwrite=True)
            logger.info(f"Subido {blob_path} con {len(df_out)} filas.")
        except Exception as e:
            logger.error(f"Error subiendo {blob_path}: {e}")
        
if __name__ == "__main__":
    fetch_and_process()
