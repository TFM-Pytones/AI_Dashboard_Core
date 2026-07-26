"""
open_meteo_ingestion.py
-----------------------
Pipeline de Ingesta a Capa Bronce (Azure Blob Storage / Data Lakehouse) para
datos meteorológicos satelitales (ERA5-Land) y previsiones operacionales (GFS).

Arquitectura Medallón - Capa Bronce (Raw):
- Ingesta datos crudos inmutables desde la API de Open-Meteo.
- Añade metadatos de auditoría: `ingested_at_utc`, `source_api`, `model_name`.
- Almacena en formato Parquet en Azure Blob Storage (contenedor 'bronce-raw').

Uso:
  python ingestion/open_meteo/open_meteo_ingestion.py

Autor: TFM - AI Dashboard Core
"""

import os
import sys
import logging
import io
import pandas as pd
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient

# Asegurar importación de módulos desde el directorio raíz del proyecto
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.abspath(os.path.join(current_dir, "..", ".."))

if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

# Cargar variables de entorno desde .env
load_dotenv(os.path.abspath(os.path.join(root_dir, ".env")), override=True)

from validation.open_meteo_client import (
    VALIDATION_STATIONS,
    download_era5land_for_stations,
    download_historical_forecast_for_stations,
    download_leadtime_samples,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s — %(message)s")
logger = logging.getLogger("OpenMeteoBronzeIngestion")

DEFAULT_OUTPUT_DIR = os.path.abspath(os.path.join(root_dir, "data", "bronce"))


class OpenMeteoBronzeIngestionPipeline:
    """Pipeline de ingesta de datos meteorológicos satelitales y NWP a la Capa Bronce en Azure Blob Storage."""

    def __init__(self, output_dir: str = DEFAULT_OUTPUT_DIR, container_name: str = "bronce-raw"):
        self.output_dir = output_dir
        self.container_name = container_name
        os.makedirs(self.output_dir, exist_ok=True)

        # Conexión a Azure Blob Storage
        conn_str = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
        if conn_str:
            conn_str = conn_str.strip('"').strip("'")
            if "AccountName=" not in conn_str and "DefaultEndpointsProtocol=" not in conn_str:
                conn_str = f"DefaultEndpointsProtocol=https;AccountName=datalaketfmtenerife;AccountKey={conn_str};EndpointSuffix=core.windows.net"
            try:
                self.blob_service_client = BlobServiceClient.from_connection_string(conn_str)
                logger.info(f"✅ Conectado exitosamente a Azure Blob Storage (Contenedor '{self.container_name}').")
            except Exception as e:
                logger.error(f"❌ Error al inicializar cliente de Azure Blob: {e}")
                self.blob_service_client = None
        else:
            self.blob_service_client = None
            logger.warning("⚠️ AZURE_STORAGE_CONNECTION_STRING no configurada. Los datos se guardarán localmente en Capa Bronce.")

    def write_parquet_to_blob(self, df: pd.DataFrame, blob_name: str) -> bool:
        """Escribe un DataFrame en la Capa Bronce (Azure Blob Storage y copia local)."""
        if df.empty:
            logger.warning(f"Intento de escribir un DataFrame vacío en {blob_name}.")
            return False

        # 1. Guardar copia local en Capa Bronce
        local_filepath = os.path.join(self.output_dir, blob_name.replace("/", "_"))
        try:
            df.to_parquet(local_filepath, index=True, compression="snappy")
            logger.info(f"  💾 Copia local guardada: {local_filepath}")
        except Exception as e:
            logger.error(f"  ❌ Error al guardar copia local {local_filepath}: {e}")

        # 2. Subir a Azure Blob Storage
        if not self.blob_service_client:
            return False

        try:
            blob_client = self.blob_service_client.get_blob_client(container=self.container_name, blob=blob_name)
            buffer = io.BytesIO()
            df.to_parquet(buffer, index=True, compression="snappy")
            buffer.seek(0)
            blob_client.upload_blob(buffer, overwrite=True)
            logger.info(f"  ☁️ Azure Blob guardado: {self.container_name}/{blob_name} ({len(df):,} registros)")
            return True
        except Exception as e:
            logger.error(f"  ❌ Error al subir {blob_name} a Azure Blob Storage: {e}")
            return False

    def read_parquet_from_blob(self, blob_name: str) -> pd.DataFrame:
        """Lee un archivo Parquet desde la Capa Bronce de Azure Blob Storage."""
        if not self.blob_service_client:
            local_filepath = os.path.join(self.output_dir, blob_name.replace("/", "_"))
            if os.path.exists(local_filepath):
                return pd.read_parquet(local_filepath)
            return pd.DataFrame()

        try:
            blob_client = self.blob_service_client.get_blob_client(container=self.container_name, blob=blob_name)
            stream = blob_client.download_blob()
            data = stream.readall()
            return pd.read_parquet(io.BytesIO(data))
        except Exception as e:
            logger.warning(f"No se pudo descargar {blob_name} de Azure Blob: {e}")
            return pd.DataFrame()

    def run_era5_ingestion(self, start_date: str = "2022-01-01", end_date: str = "2024-12-31") -> Dict[int, pd.DataFrame]:
        """Ingesta datos de reanálisis ERA5-Land (Nivel 1) y los sube a Capa Bronce."""
        logger.info("\n" + "="*70)
        logger.info("INGESTA CAPA BRONCE: ERA5-Land Reanálisis (Nivel 1)")
        logger.info("="*70)

        era5_dfs = download_era5land_for_stations(
            VALIDATION_STATIONS,
            start_date=start_date,
            end_date=end_date,
        )

        now_utc = datetime.now(timezone.utc).isoformat()
        consolidated_list = []

        for sid, df in era5_dfs.items():
            if df.empty:
                continue

            df = df.copy()
            df["station_id"] = sid
            df["ingested_at_utc"] = now_utc
            df["source_api"] = "Open-Meteo ERA5-Land"
            df["model_name"] = "era5_land"

            blob_name = f"satelite_era5land/era5land_station_{sid}.parquet"
            self.write_parquet_to_blob(df, blob_name)
            consolidated_list.append(df)

        if consolidated_list:
            consolidated_df = pd.concat(consolidated_list)
            self.write_parquet_to_blob(consolidated_df, "satelite_era5land/era5land_consolidado.parquet")

        return era5_dfs

    def run_historical_forecast_ingestion(
        self,
        start_date: str = "2022-01-01",
        end_date: str = "2024-12-31",
        model: str = "gfs_seamless",
    ) -> Dict[int, pd.DataFrame]:
        """Ingesta pronósticos históricos operacionales GFS (Nivel 2) a Capa Bronce."""
        logger.info("\n" + "="*70)
        logger.info(f"INGESTA CAPA BRONCE: Historical Forecast NWP ({model} - Nivel 2)")
        logger.info("="*70)

        hist_dfs = download_historical_forecast_for_stations(
            VALIDATION_STATIONS,
            start_date=start_date,
            end_date=end_date,
            model=model,
        )

        now_utc = datetime.now(timezone.utc).isoformat()
        consolidated_list = []

        for sid, df in hist_dfs.items():
            if df.empty:
                continue

            df = df.copy()
            df["station_id"] = sid
            df["ingested_at_utc"] = now_utc
            df["source_api"] = "Open-Meteo Historical Forecast"
            df["model_name"] = model

            blob_name = f"forecast_gfs/hist_forecast_{model}_station_{sid}.parquet"
            self.write_parquet_to_blob(df, blob_name)
            consolidated_list.append(df)

        if consolidated_list:
            consolidated_df = pd.concat(consolidated_list)
            self.write_parquet_to_blob(consolidated_df, f"forecast_gfs/hist_forecast_{model}_consolidado.parquet")

        return hist_dfs

    def run_leadtime_ingestion(
        self,
        start_date: str = "2022-01-01",
        end_date: str = "2024-12-31",
        lead_times_days: List[int] = [1, 3, 7],
        model: str = "gfs_seamless",
    ) -> Dict[int, pd.DataFrame]:
        """Ingesta previsiones históricas por horizonte de tiempo (Lead-Time D+1, D+3, D+7) a Capa Bronce."""
        logger.info("\n" + "="*70)
        logger.info(f"INGESTA CAPA BRONCE: Previsiones Lead-Time D+1/3/7 ({model})")
        logger.info("="*70)

        lt_dfs = download_leadtime_samples(
            VALIDATION_STATIONS,
            start_date=start_date,
            end_date=end_date,
            lead_times_days=lead_times_days,
            model=model,
        )

        now_utc = datetime.now(timezone.utc).isoformat()
        consolidated_list = []

        for sid, df in lt_dfs.items():
            if df.empty:
                continue

            df = df.copy()
            df["station_id"] = sid
            df["ingested_at_utc"] = now_utc
            df["source_api"] = "Open-Meteo Previous Runs"
            df["model_name"] = model

            blob_name = f"leadtime_gfs/leadtime_{model}_station_{sid}.parquet"
            self.write_parquet_to_blob(df, blob_name)
            consolidated_list.append(df)

        if consolidated_list:
            consolidated_df = pd.concat(consolidated_list)
            self.write_parquet_to_blob(consolidated_df, f"leadtime_gfs/leadtime_{model}_consolidado.parquet")

        return lt_dfs

    def run_full_bronze_ingestion(self, start_date: str = "2022-01-01", end_date: str = "2024-12-31"):
        """Ejecuta el pipeline completo de ingesta a la Capa Bronce."""
        logger.info("🚀 Iniciando Pipeline Completo de Ingesta Meteorológica a Capa Bronce (Azure Data Lakehouse)...")
        era5 = self.run_era5_ingestion(start_date=start_date, end_date=end_date)
        gfs = self.run_historical_forecast_ingestion(start_date=start_date, end_date=end_date)
        lt = self.run_leadtime_ingestion(start_date=start_date, end_date=end_date)
        logger.info("✅ Ingesta en Capa Bronce completada con éxito.")
        return era5, gfs, lt


if __name__ == "__main__":
    pipeline = OpenMeteoBronzeIngestionPipeline()
    pipeline.run_full_bronze_ingestion()
