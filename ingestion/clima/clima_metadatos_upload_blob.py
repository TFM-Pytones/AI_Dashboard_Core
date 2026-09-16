"""
clima_metadatos_upload_blob.py
─────────────────────────────────────────────────────────────────────────────
Propósito: Ingesta de metadatos de las estaciones y sensores meteorológicos
           de la red de Agrocabildo (Cabildo de Tenerife) mediante el catálogo
           abierto de CKAN (datos.tenerife.es).

Ventajas vs API anterior (/api/meteo/latest):
  - No depende de endpoints con cuotas ni rate limits de 6.5s.
  - Extrae el censo oficial y completo de 68 estaciones y 378 sensores.
  - Guarda en Azure Blob Storage (bronce-raw):
      * clima/estaciones/estaciones_agrocabildo.parquet
      * clima/sensores/sensores_meteorologicos.parquet (catálogo dbt compatible)
      * clima/sensores/sensores_inventario.parquet (inventario físico de 378 sensores)
─────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import io
import logging
import os
from typing import Dict, Optional

import pandas as pd
import requests
from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient

# Cargar variables de entorno
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"), override=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("ClimaMetadatosCKAN")

AZURE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
BLOB_CONTAINER_NAME = "bronce-raw"

CKAN_API_BASE = "https://datos.tenerife.es/ckan/api/action"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AI-Dashboard/1.0"}

# Mapeo estándar para compatibilidad con dbt (silver_clima_agrocabildo.sql)
WEATHER_DATATYPE_MAP: Dict[str, Dict[str, any]] = {
    "TEMP": {"id_weatherdatatype": 10, "alias": "TEMP", "name": "Temperatura", "unit": "°C"},
    "HUM":  {"id_weatherdatatype": 11, "alias": "HUM",  "name": "Humedad relativa", "unit": "%"},
    "RAIN": {"id_weatherdatatype": 12, "alias": "RAIN", "name": "Precipitación", "unit": "mm"},
    "WSP":  {"id_weatherdatatype": 13, "alias": "WSP",  "name": "Velocidad del viento", "unit": "m/s"},
    "WDR":  {"id_weatherdatatype": 14, "alias": "WDR",  "name": "Dirección del viento", "unit": "deg."},
    "RAD":  {"id_weatherdatatype": 15, "alias": "RAD",  "name": "Radiación solar", "unit": "W/m²"},
}


def get_ckan_resource_url(package_id: str, format_pref: str = "CSV") -> Optional[str]:
    """Obtiene dinámicamente la URL de descarga de un recurso desde CKAN."""
    url = f"{CKAN_API_BASE}/package_show?id={package_id}"
    res = requests.get(url, headers=HEADERS, timeout=30)
    res.raise_for_status()
    pkg = res.json().get("result", {})
    resources = pkg.get("resources", [])
    
    for r in resources:
        if r.get("format", "").upper() == format_pref.upper():
            return r.get("url")
            
    # Fallback al primer recurso disponible
    if resources:
        return resources[0].get("url")
    return None


def fetch_and_upload_stations(blob_service_client: BlobServiceClient) -> pd.DataFrame:
    """Descarga el censo de estaciones desde CKAN y lo sube a Azure Blob Storage."""
    logger.info("Consultando catálogo CKAN para 'estaciones-meteorologicas-de-tenerife'...")
    csv_url = get_ckan_resource_url("estaciones-meteorologicas-de-tenerife", "CSV")
    if not csv_url:
        csv_url = "https://datos.tenerife.es/ckan/dataset/5809d81d-455a-4936-af3b-56b3078a37df/resource/8af0cd69-d6d2-4df0-b19c-02bad07b2c80/download/estaciones-meteorologicas.csv"

    logger.info(f"Descargando estaciones desde: {csv_url}")
    df = pd.read_csv(csv_url, sep=None, engine="python", encoding="utf-8-sig")

    # Normalizar nombres de columnas (eliminar BOM si persiste y espacios)
    df.columns = [c.replace("\ufeff", "").strip().lower() for c in df.columns]

    col_map = {
        "estacion_id": "estacion_id",
        "estacion_nombre": "estacion_nombre",
        "municipio_nombre": "municipio_nombre",
        "latitud": "latitud",
        "longitud": "longitud",
        "altitud": "altitud",
        "fecha_instalacion": "fecha_instalacion"
    }

    cols_to_keep = [
        "estacion_id", "estacion_nombre", "municipio_nombre",
        "latitud", "longitud", "altitud", "fecha_instalacion"
    ]
    df_clean = df[[c for c in cols_to_keep if c in df.columns]].copy()

    # Asegurar tipos de datos adecuados
    df_clean["estacion_id"] = pd.to_numeric(df_clean["estacion_id"], errors="coerce").fillna(-1).astype(int)
    df_clean["latitud"] = pd.to_numeric(df_clean["latitud"], errors="coerce")
    df_clean["longitud"] = pd.to_numeric(df_clean["longitud"], errors="coerce")
    df_clean["altitud"] = pd.to_numeric(df_clean["altitud"], errors="coerce")
    df_clean["estacion_nombre"] = df_clean["estacion_nombre"].astype(str).str.strip()
    df_clean["municipio_nombre"] = df_clean["municipio_nombre"].astype(str).str.strip()

    logger.info(f"Se procesaron {len(df_clean)} estaciones meteorológicas.")

    parquet_buffer = io.BytesIO()
    df_clean.to_parquet(parquet_buffer, index=False, compression="snappy")
    parquet_buffer.seek(0)

    blob_destination = "clima/estaciones/estaciones_agrocabildo.parquet"
    blob_client = blob_service_client.get_blob_client(container=BLOB_CONTAINER_NAME, blob=blob_destination)
    blob_client.upload_blob(parquet_buffer, overwrite=True)
    logger.info(f"✓ Estaciones guardadas en Azure Blob: {blob_destination}")

    return df_clean


def fetch_and_upload_sensors(blob_service_client: BlobServiceClient) -> pd.DataFrame:
    """Descarga el catálogo e inventario de sensores desde CKAN y lo sube a Azure Blob."""
    logger.info("Consultando catálogo CKAN para 'sensores-de-las-estaciones-meteorologicas-de-tenerife'...")
    csv_url = get_ckan_resource_url("sensores-de-las-estaciones-meteorologicas-de-tenerife", "CSV")
    if not csv_url:
        csv_url = "https://datos.tenerife.es/ckan/dataset/e66f8fd3-e032-41a5-a941-8bd2c1ca0beb/resource/6e27a0ca-be4a-4426-8828-dba98eb38915/download/sensores-meteorologicos.csv"

    logger.info(f"Descargando inventario de sensores desde: {csv_url}")
    df_sensores = pd.read_csv(csv_url, sep=None, engine="python", encoding="utf-8-sig")
    df_sensores.columns = [c.replace("\ufeff", "").strip().lower() for c in df_sensores.columns]

    logger.info(f"Se procesaron {len(df_sensores)} sensores físicos instalados en la red.")

    # 1. Subir inventario físico detallado de sensores
    inv_buffer = io.BytesIO()
    df_sensores.to_parquet(inv_buffer, index=False, compression="snappy")
    inv_buffer.seek(0)
    blob_inv = "clima/sensores/sensores_inventario.parquet"
    blob_service_client.get_blob_client(container=BLOB_CONTAINER_NAME, blob=blob_inv).upload_blob(
        inv_buffer, overwrite=True
    )
    logger.info(f"✓ Inventario de sensores guardado en Azure Blob: {blob_inv}")

    # 2. Generar y subir catálogo canónico compatible con dbt (id_weatherdatatype, alias, name, unit)
    rows_types = []
    # Identificar las variables únicas presentes en el inventario
    found_aliases = set(df_sensores["sensor_alias"].dropna().str.strip().str.upper().unique())
    
    # Asegurar que todas las 6 variables canónicas estén presentes
    for alias, meta in WEATHER_DATATYPE_MAP.items():
        rows_types.append(meta)

    # Añadir cualquier otra variable detectada que no estuviera en el mapa estándar
    next_id = 20
    for alias in sorted(found_aliases):
        if alias not in WEATHER_DATATYPE_MAP:
            sub = df_sensores[df_sensores["sensor_alias"].str.upper() == alias].iloc[0]
            rows_types.append({
                "id_weatherdatatype": next_id,
                "alias": alias,
                "name": str(sub.get("sensor_nombre", alias)),
                "unit": str(sub.get("sensor_unidad", ""))
            })
            next_id += 1

    df_types = pd.DataFrame(rows_types)
    types_buffer = io.BytesIO()
    df_types.to_parquet(types_buffer, index=False, compression="snappy")
    types_buffer.seek(0)

    blob_types = "clima/sensores/sensores_meteorologicos.parquet"
    blob_service_client.get_blob_client(container=BLOB_CONTAINER_NAME, blob=blob_types).upload_blob(
        types_buffer, overwrite=True
    )
    logger.info(f"✓ Catálogo de variables guardado en Azure Blob: {blob_types}")

    return df_types


def main():
    if not AZURE_CONNECTION_STRING:
        logger.error("AZURE_STORAGE_CONNECTION_STRING no está definido en el archivo .env")
        return

    conn_str = AZURE_CONNECTION_STRING.strip('"').strip("'")
    if "AccountName=" not in conn_str and "DefaultEndpointsProtocol=" not in conn_str:
        conn_str = f"DefaultEndpointsProtocol=https;AccountName=datalaketfmtenerife;AccountKey={conn_str};EndpointSuffix=core.windows.net"

    try:
        blob_service_client = BlobServiceClient.from_connection_string(conn_str)
    except Exception as e:
        logger.error(f"Error al conectar con Azure Blob Storage: {e}")
        return

    try:
        fetch_and_upload_stations(blob_service_client)
        fetch_and_upload_sensors(blob_service_client)
        logger.info("Pipeline de metadatos CKAN de clima completado con éxito.")
    except Exception as e:
        logger.error(f"Error durante la ingesta de metadatos: {e}", exc_info=True)


if __name__ == "__main__":
    main()
