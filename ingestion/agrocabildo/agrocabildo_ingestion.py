import os
import sys
import logging
import io
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

# Cargar variables de entorno desde .env si existe
load_dotenv(os.path.abspath(os.path.join(current_dir, "..", "..", ".env")), override=True)
load_dotenv(os.path.abspath(os.path.join(current_dir, "..", "..", "..", ".env")), override=True)

from agrocabildo_client import AgrocabildoAPIClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("AgrocabildoIngestion")

DEFAULT_CSV_PATH = os.path.abspath(os.path.join(current_dir, "..", "..", "..", "estaciones-meteorologicas.csv"))
DEFAULT_OUTPUT_DIR = os.path.abspath(os.path.join(current_dir, "..", "..", "data"))

class AgrocabildoIngestionPipeline:
    def __init__(self, csv_estaciones: str = DEFAULT_CSV_PATH, output_dir: str = DEFAULT_OUTPUT_DIR):
        self.csv_estaciones_path = csv_estaciones
        self.output_dir = output_dir
        self.client = AgrocabildoAPIClient(min_request_interval=6.5)
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Conexión a Azure Blob Storage
        conn_str = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
        self.container_name = "bronce-raw"
        if conn_str:
            conn_str = conn_str.strip('"').strip("'")
            if "AccountName=" not in conn_str and "DefaultEndpointsProtocol=" not in conn_str:
                conn_str = f"DefaultEndpointsProtocol=https;AccountName=datalaketfmtenerife;AccountKey={conn_str};EndpointSuffix=core.windows.net"
            self.blob_service_client = BlobServiceClient.from_connection_string(conn_str)
        else:
            self.blob_service_client = None
            logger.warning("⚠️ AZURE_STORAGE_CONNECTION_STRING no configurado. Solo se guardará en local.")

    def read_parquet_from_blob(self, blob_name: str) -> pd.DataFrame:
        """Lee un archivo Parquet existente del contenedor bronce-raw."""
        if not self.blob_service_client:
            return pd.DataFrame()
        try:
            blob_client = self.blob_service_client.get_blob_client(container=self.container_name, blob=blob_name)
            stream = blob_client.download_blob()
            data = stream.readall()
            return pd.read_parquet(io.BytesIO(data))
        except Exception as e:
            logger.warning(f"No se pudo descargar {blob_name} de Azure Blob (puede ser la primera ingesta): {e}")
            return pd.DataFrame()

    def write_parquet_to_blob(self, df: pd.DataFrame, blob_name: str):
        """Escribe un DataFrame como archivo Parquet en el contenedor bronce-raw."""
        if not self.blob_service_client:
            return
        try:
            blob_client = self.blob_service_client.get_blob_client(container=self.container_name, blob=blob_name)
            buffer = io.BytesIO()
            df.to_parquet(buffer, index=False, compression="snappy")
            buffer.seek(0)
            blob_client.upload_blob(buffer, overwrite=True)
            logger.info(f"✅ Archivo {blob_name} guardado/actualizado con éxito en Azure Blob Storage.")
        except Exception as e:
            logger.error(f"❌ Error al subir {blob_name} a Azure Blob: {e}")

    @staticmethod
    def safe_float(val: Any) -> Optional[float]:
        if val is None or val == "":
            return None
        try:
            return float(val)
        except (ValueError, TypeError):
            return None

    def save_to_azure_blob(self, df_stations: pd.DataFrame, df_readings: pd.DataFrame):
        """Fusiona y guarda de forma incremental las lecturas y estaciones en Azure Blob Storage."""
        # 1. Procesar lecturas meteorológicas
        if not df_readings.empty:
            # Asegurar formato homogéneo del DataFrame nuevo
            new_readings = pd.DataFrame({
                "id_estacion": df_readings["id_weatherstation"].astype(int),
                "id_sensor": df_readings["id_weatherstationsensor"].astype(int),
                "timestamp": pd.to_datetime(df_readings["timestamp"]),
                "valor_observado": df_readings["observation_value"].apply(self.safe_float),
                "valor_validado": df_readings["validated_value"].apply(self.safe_float),
                "es_validado": df_readings["is_validated"].astype(bool)
            })

            # Agrupar por id_estacion para guardar de forma particionada
            grouped = new_readings.groupby("id_estacion")
            for st_id, df_group in grouped:
                st_id = int(st_id)
                blob_name = f"clima_horario_agrocabildo/estacion_{st_id}.parquet"
                
                # Leer el histórico existente de esta estación
                df_existing_readings = self.read_parquet_from_blob(blob_name)
                
                if not df_existing_readings.empty:
                    df_existing_readings["timestamp"] = pd.to_datetime(df_existing_readings["timestamp"])
                    combined = pd.concat([df_existing_readings, df_group], ignore_index=True)
                    combined.drop_duplicates(subset=["id_estacion", "id_sensor", "timestamp"], keep="last", inplace=True)
                else:
                    combined = df_group

                # Guardar el Parquet actualizado de esta estación en la Capa Bronce
                self.write_parquet_to_blob(combined, blob_name)
                logger.info(f"Consolidación completada: {len(combined)} lecturas de estación {st_id} en la Capa Bronce.")
        
        # 2. Procesar metadatos de estaciones
        if not df_stations.empty:
            new_stations = pd.DataFrame({
                "id_estacion": df_stations["estacion_id"].astype(int),
                "nombre": df_stations["estacion_nombre"].astype(str),
                "municipio": df_stations.get("municipio_nombre", "").astype(str),
                "latitud": df_stations["latitud"].apply(self.safe_float),
                "longitud": df_stations["longitud"].apply(self.safe_float),
                "altitud": df_stations["altitud"].apply(self.safe_float),
                "fecha_instalacion": pd.to_datetime(df_stations["fecha_instalacion"])
            })

            df_existing_stations = self.read_parquet_from_blob("estaciones_agrocabildo.parquet")
            
            if not df_existing_stations.empty:
                combined_stations = pd.concat([df_existing_stations, new_stations], ignore_index=True)
                combined_stations.drop_duplicates(subset=["id_estacion"], keep="last", inplace=True)
            else:
                combined_stations = new_stations

            self.write_parquet_to_blob(combined_stations, "estaciones_agrocabildo.parquet")

    def load_target_stations(self) -> pd.DataFrame:
        """Carga y valida el archivo CSV de estaciones asignadas para el TFM."""
        candidate_paths = [
            os.path.abspath(os.path.join(current_dir, "..", "..", "data", "estaciones-meteorologicas.csv")),
            self.csv_estaciones_path,
            os.path.abspath(os.path.join(current_dir, "..", "..", "..", "estaciones-meteorologicas.csv")),
            os.path.abspath(os.path.join(current_dir, "..", "..", "estaciones_agrocabildo_coordenadas.csv")),
            os.path.join(os.getcwd(), "estaciones-meteorologicas.csv")
        ]

        found_path = None
        for path in candidate_paths:
            if os.path.exists(path):
                found_path = path
                break

        if not found_path:
            raise FileNotFoundError(f"No se encontró el archivo CSV de estaciones en ninguna de las rutas: {candidate_paths}")
        
        df = pd.read_csv(found_path, encoding="utf-8-sig")
        df.columns = [c.strip().lstrip('\ufeff') for c in df.columns]
        logger.info(f"Cargadas {len(df)} estaciones objetivo desde {found_path}")

        # Normalizar nombres de columnas
        col_map = {
            "id_weatherstation": "estacion_id",
            "name": "estacion_nombre",
            "weatherstation_name": "estacion_nombre",
            "municipality_name": "municipio_nombre",
            "latitude": "latitud",
            "longitude": "longitud",
            "altitude": "altitud",
            "date_install": "fecha_instalacion"
        }
        df.rename(columns=col_map, inplace=True)

        if "fecha_instalacion" not in df.columns:
            df["fecha_instalacion"] = None

        return df

    def run_realtime_ingestion(self, days_back: int = 2, max_stations: Optional[int] = None) -> pd.DataFrame:
        """
        Ejecuta la ingesta de datos meteorológicos en tiempo real filtrados a horas en punto.
        Guarda los datos tanto en Neon DB como en un backup Parquet local.
        """
        # Ingesta incremental hacia Azure Blob Storage

        df_target = self.load_target_stations()
        
        if max_stations:
            df_target = df_target.head(max_stations)
            logger.info(f"Modo prueba activo: Procesando solo {max_stations} estaciones.")

        today = datetime.now()
        date_to = today.strftime("%Y-%m-%d")
        date_from = (today - timedelta(days=days_back)).strftime("%Y-%m-%d")

        logger.info(f"--- Inicio de Ingesta Horaria Agrocabildo ({date_from} -> {date_to}) ---")
        
        all_records = []

        for idx, row in df_target.iterrows():
            station_id = int(row["estacion_id"])
            station_name = str(row["estacion_nombre"])
            lat = row.get("latitud")
            lon = row.get("longitud")
            alt = row.get("altitud")

            logger.info(f"[{idx+1}/{len(df_target)}] Procesando estación ID {station_id} ({station_name})...")
            
            sensors = self.client.get_station_sensors(station_id)
            if not sensors:
                logger.warning(f"No se obtuvieron sensores para la estación {station_id}")
                continue

            for sensor in sensors:
                sensor_id = sensor.get("id_weatherstationsensor")
                sensor_alias = sensor.get("sensor_alias", "")
                sensor_name = sensor.get("sensor_name", "")
                unit = sensor.get("unit", "")

                if not sensor_id:
                    continue

                records = self.client.extract_hourly_readings(
                    station_id=station_id,
                    sensor_id=sensor_id,
                    date_from=date_from,
                    date_to=date_to,
                    max_pages=2
                )

                for rec in records:
                    rec.update({
                        "estacion_nombre": station_name,
                        "sensor_alias": sensor_alias,
                        "sensor_name": sensor_name,
                        "unit": unit,
                        "latitud": lat,
                        "longitud": lon,
                        "altitud": alt
                    })
                    all_records.append(rec)

        df_result = pd.DataFrame(all_records)
        
        if not df_result.empty:
            df_result["id_weatherstation"] = df_result["id_weatherstation"].astype(int)
            df_result["id_weatherstationsensor"] = df_result["id_weatherstationsensor"].astype(int)
            df_result["timestamp"] = pd.to_datetime(df_result["timestamp"])

            # Limpiar columnas numericas de strings vacios para evitar fallos de PyArrow
            for col in ["observation_value", "validated_value"]:
                if col in df_result.columns:
                    df_result[col] = pd.to_numeric(df_result[col].astype(str).str.strip().replace("", None), errors="coerce")

            # 1. Guardar en Azure Blob Storage (Capa Bronce)
            self.save_to_azure_blob(df_target, df_result)

            # 2. Guardar en Parquet local como backup
            output_parquet = os.path.join(self.output_dir, "agrocabildo_hourly.parquet")
            if os.path.exists(output_parquet):
                try:
                    df_existing = pd.read_parquet(output_parquet)
                    df_combined = pd.concat([df_existing, df_result], ignore_index=True)
                    df_combined.drop_duplicates(subset=["id_weatherstation", "id_weatherstationsensor", "timestamp"], inplace=True)
                    df_combined.to_parquet(output_parquet, index=False, compression="snappy")
                    logger.info(f"✅ Backup Parquet actualizado con {len(df_combined)} registros: {output_parquet}")
                    return df_combined
                except Exception as e:
                    logger.error(f"Error al actualizar Parquet ({e}), creando nuevo archivo...")
            
            df_result.to_parquet(output_parquet, index=False, compression="snappy")
            logger.info(f"✅ Backup Parquet guardado con {len(df_result)} registros: {output_parquet}")
            return df_result
        else:
            logger.warning("⚠️ No se obtuvieron registros en esta ingesta.")
            return pd.DataFrame()

if __name__ == "__main__":
    pipeline = AgrocabildoIngestionPipeline()
    pipeline.run_realtime_ingestion(days_back=1, max_stations=2)
