import os
import sys
import json
import time
import io
import argparse
import logging
import pandas as pd
from datetime import datetime
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

load_dotenv(os.path.abspath(os.path.join(current_dir, "..", "..", ".env")), override=True)
load_dotenv(os.path.abspath(os.path.join(current_dir, "..", "..", "..", ".env")), override=True)

from agrocabildo_client import AgrocabildoAPIClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("AgrocabildoBackfill")

DEFAULT_CSV_PATH = os.path.abspath(os.path.join(current_dir, "..", "..", "..", "estaciones-meteorologicas.csv"))
STATE_FILE_PATH = os.path.join(current_dir, "backfill_progress.json")

class AgrocabildoHistoricalBackfill:
    def __init__(self, csv_path: str = DEFAULT_CSV_PATH):
        self.csv_path = csv_path
        self.client = AgrocabildoAPIClient(min_request_interval=6.5)
        
        # Rutas locales para persistencia temporal
        self.local_dir = os.path.abspath(os.path.join(current_dir, "..", "..", "data"))
        os.makedirs(self.local_dir, exist_ok=True)
        self.local_readings_path = os.path.join(self.local_dir, "clima_horario_agrocabildo.parquet")
        self.local_stations_path = os.path.join(self.local_dir, "estaciones_agrocabildo.parquet")
        
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

    def download_from_blob(self, blob_name: str, local_path: str):
        """Descarga un archivo del contenedor bronce-raw al disco local."""
        if not self.blob_service_client:
            return
        try:
            blob_client = self.blob_service_client.get_blob_client(container=self.container_name, blob=blob_name)
            with open(local_path, "wb") as f:
                data = blob_client.download_blob()
                data.readinto(f)
            logger.info(f"📥 Archivo {blob_name} descargado de Azure Blob a local.")
        except Exception as e:
            logger.warning(f"No se pudo descargar {blob_name} de Azure Blob: {e}")

    def upload_to_blob(self, local_path: str, blob_name: str):
        """Sube un archivo local al contenedor bronce-raw de Azure Blob."""
        if not self.blob_service_client:
            return
        if not os.path.exists(local_path):
            return
        try:
            blob_client = self.blob_service_client.get_blob_client(container=self.container_name, blob=blob_name)
            with open(local_path, "rb") as f:
                blob_client.upload_blob(f, overwrite=True)
            logger.info(f"Archivo {blob_name} subido con éxito a Azure Blob Storage.")
        except Exception as e:
            logger.error(f"Error al subir {blob_name} a Azure Blob: {e}")

    def load_target_stations(self) -> pd.DataFrame:
        """Carga el archivo CSV de estaciones y aplica filtro si existe fecha_instalacion."""
        candidate_paths = [
            os.path.abspath(os.path.join(current_dir, "..", "..", "data", "estaciones-meteorologicas.csv")),
            self.csv_path,
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
            raise FileNotFoundError(f"No se encontró el archivo CSV de estaciones.")

        df = pd.read_csv(found_path, encoding="utf-8-sig")
        df.columns = [c.strip().lstrip('\ufeff') for c in df.columns]
        logger.info(f"Cargadas {len(df)} estaciones objetivo desde {found_path}")
        
        # Mapeo de columnas
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

    def save_stations_metadata(self, df_stations: pd.DataFrame):
        """Guarda la metainformación de las estaciones en formato Parquet local y en Azure Blob."""
        new_stations = pd.DataFrame({
            "id_estacion": df_stations["estacion_id"].astype(int),
            "nombre": df_stations["estacion_nombre"].astype(str),
            "municipio": df_stations.get("municipio_nombre", "").astype(str),
            "latitud": df_stations["latitud"].apply(self.safe_float),
            "longitud": df_stations["longitud"].apply(self.safe_float),
            "altitud": df_stations["altitud"].apply(self.safe_float),
            "fecha_instalacion": pd.to_datetime(df_stations["fecha_instalacion"])
        })

        if os.path.exists(self.local_stations_path):
            try:
                df_existing = pd.read_parquet(self.local_stations_path)
                combined = pd.concat([df_existing, new_stations], ignore_index=True)
                combined.drop_duplicates(subset=["id_estacion"], keep="last", inplace=True)
            except Exception:
                combined = new_stations
        else:
            combined = new_stations

        combined.to_parquet(self.local_stations_path, index=False, compression="snappy")
        self.upload_to_blob(self.local_stations_path, "estaciones_agrocabildo.parquet")
        logger.info(f"Guardadas {len(combined)} estaciones en estaciones_agrocabildo.parquet (local y Azure).")

    @staticmethod
    def safe_float(val: Any) -> Optional[float]:
        if val is None or val == "":
            return None
        try:
            return float(val)
        except (ValueError, TypeError):
            return None

    def upsert_hourly_readings(self, records: List[Dict[str, Any]]) -> int:
        """Inserta lote de lecturas en formato Parquet local."""
        if not records:
            return 0

        new_readings = pd.DataFrame(records)
        new_readings = pd.DataFrame({
            "id_estacion": new_readings["id_weatherstation"].astype(int),
            "id_sensor": new_readings["id_weatherstationsensor"].astype(int),
            "timestamp": pd.to_datetime(new_readings["timestamp"]),
            "valor_observado": new_readings["observation_value"].apply(self.safe_float),
            "valor_validado": new_readings["validated_value"].apply(self.safe_float),
            "es_validado": new_readings["is_validated"].astype(bool)
        })

        if os.path.exists(self.local_readings_path):
            try:
                df_existing = pd.read_parquet(self.local_readings_path)
                # Asegurar tipo datetime para alineación correcta
                df_existing["timestamp"] = pd.to_datetime(df_existing["timestamp"])
                combined = pd.concat([df_existing, new_readings], ignore_index=True)
                combined.drop_duplicates(subset=["id_estacion", "id_sensor", "timestamp"], keep="last", inplace=True)
            except Exception as e:
                logger.error(f"Error al leer Parquet local: {e}. Creando nuevo.")
                combined = new_readings
        else:
            combined = new_readings

        combined.to_parquet(self.local_readings_path, index=False, compression="snappy")
        return len(new_readings)

    def _deduplicate_and_save_parquet(self, local_path: str, remote_path: str):
        """Fusiona y deduplica dos archivos Parquet de forma eficiente en memoria usando PyArrow."""
        import pyarrow as pa
        import pyarrow.parquet as pq
        import pyarrow.compute as pc
        
        logger.info("Cargando archivos Parquet con PyArrow para fusionar...")
        table_local = pq.read_table(local_path)
        table_remote = pq.read_table(remote_path)
        
        logger.info(f"Concatenando tablas (Local: {table_local.num_rows} filas, Azure: {table_remote.num_rows} filas)...")
        combined_table = pa.concat_tables([table_remote, table_local])
        
        logger.info("Deduplicando registros de forma eficiente por estación...")
        unique_stations = pc.unique(combined_table.column("id_estacion")).to_pylist()
        
        clean_tables = []
        for station_id in unique_stations:
            station_table = combined_table.filter(pc.field("id_estacion") == station_id)
            df_station = station_table.to_pandas()
            df_station.drop_duplicates(subset=["id_sensor", "timestamp"], keep="last", inplace=True)
            station_clean_table = pa.Table.from_pandas(df_station, schema=combined_table.schema, preserve_index=False)
            clean_tables.append(station_clean_table)
            
        final_table = pa.concat_tables(clean_tables)
        logger.info(f"Guardando archivo consolidado limpio ({final_table.num_rows} filas)...")
        pq.write_table(final_table, local_path, compression="snappy")

    def download_and_merge_at_start(self):
        """Descarga el Parquet y el Progreso de Azure Blob al inicio del backfill y los fusiona."""
        if not self.blob_service_client:
            return
        
        # 1. Sincronizar clima_horario_agrocabildo.parquet
        temp_remote_path = self.local_readings_path + ".remote_init"
        try:
            blob_client = self.blob_service_client.get_blob_client(container=self.container_name, blob="clima_horario_agrocabildo.parquet")
            if blob_client.exists():
                logger.info("Descargando histórico actual de Azure Blob al inicio para consolidar...")
                with open(temp_remote_path, "wb") as f:
                    data = blob_client.download_blob()
                    data.readinto(f)
                
                if os.path.exists(self.local_readings_path) and os.path.exists(temp_remote_path):
                    logger.info("Iniciando fusión de Parquets en memoria...")
                    self._deduplicate_and_save_parquet(self.local_readings_path, temp_remote_path)
                elif os.path.exists(temp_remote_path):
                    if os.path.exists(self.local_readings_path):
                        os.remove(self.local_readings_path)
                    os.rename(temp_remote_path, self.local_readings_path)
                    logger.info("Archivo Parquet descargado e inicializado como local.")
            else:
                logger.info("El archivo clima_horario_agrocabildo.parquet no existe en el Blob. Se usará el local si existe.")
        except Exception as e:
            logger.warning(f"No se pudo descargar o fusionar el histórico inicial: {e}")
        finally:
            if os.path.exists(temp_remote_path):
                try:
                    os.remove(temp_remote_path)
                except Exception:
                    pass

        # 2. Sincronizar backfill_progress.json
        temp_progress_path = STATE_FILE_PATH + ".remote_init"
        try:
            blob_client_prog = self.blob_service_client.get_blob_client(container=self.container_name, blob="backfill_progress.json")
            if blob_client_prog.exists():
                logger.info("Descargando archivo de progreso desde Azure Blob al inicio para consolidar...")
                with open(temp_progress_path, "wb") as f:
                    data = blob_client_prog.download_blob()
                    data.readinto(f)
                
                if os.path.exists(STATE_FILE_PATH) and os.path.exists(temp_progress_path):
                    with open(STATE_FILE_PATH, "r", encoding="utf-8") as f:
                        local_prog = json.load(f)
                    with open(temp_progress_path, "r", encoding="utf-8") as f:
                        remote_prog = json.load(f)
                    
                    local_keys = set(local_prog.get("completed_keys", []))
                    remote_keys = set(remote_prog.get("completed_keys", []))
                    
                    merged_keys = sorted(list(local_keys.union(remote_keys)))
                    merged_prog = {"completed_keys": merged_keys}
                    
                    with open(STATE_FILE_PATH, "w", encoding="utf-8") as f:
                        json.dump(merged_prog, f, indent=2)
                    logger.info(f"Progreso unificado al inicio. Total llaves: {len(merged_keys)}")
                elif os.path.exists(temp_progress_path):
                    if os.path.exists(STATE_FILE_PATH):
                        os.remove(STATE_FILE_PATH)
                    os.rename(temp_progress_path, STATE_FILE_PATH)
                    logger.info("Progreso descargado e inicializado como local.")
            else:
                logger.info("El archivo backfill_progress.json no existe en el Blob. Se usará el local si existe.")
        except Exception as e:
            logger.warning(f"No se pudo descargar o fusionar el progreso inicial: {e}")
        finally:
            if os.path.exists(temp_progress_path):
                try:
                    os.remove(temp_progress_path)
                except Exception:
                    pass

    def consolidate_and_upload_at_end(self):
        """Consolida el archivo local con el del Blob Storage y lo sube al final del proceso."""
        logger.info("Iniciando consolidación final con Azure Blob Storage...")
        
        # 1. Consolidar clima_horario_agrocabildo.parquet
        temp_remote_path = self.local_readings_path + ".remote"
        if self.blob_service_client:
            try:
                blob_client = self.blob_service_client.get_blob_client(container=self.container_name, blob="clima_horario_agrocabildo.parquet")
                if blob_client.exists():
                    logger.info("Descargando la versión más reciente del Blob para fusionar...")
                    with open(temp_remote_path, "wb") as f:
                        data = blob_client.download_blob()
                        data.readinto(f)
                    
                    if os.path.exists(self.local_readings_path) and os.path.exists(temp_remote_path):
                        logger.info("Iniciando fusión final de Parquets en memoria...")
                        self._deduplicate_and_save_parquet(self.local_readings_path, temp_remote_path)
                else:
                    logger.info("El archivo clima_horario_agrocabildo.parquet no existe aún en el Blob. Se subirá el local directamente.")
            except Exception as e:
                logger.error(f"Error al descargar o consolidar con el Blob: {e}. Se intentará subir el local de todos modos.")
            finally:
                if os.path.exists(temp_remote_path):
                    try:
                        os.remove(temp_remote_path)
                    except Exception:
                        pass
        
        logger.info("Subiendo archivo final a Azure Blob...")
        self.upload_to_blob(self.local_readings_path, "clima_horario_agrocabildo.parquet")
        self.verify_blob_upload("clima_horario_agrocabildo.parquet")

        # 2. Consolidar y subir backfill_progress.json
        temp_progress_path = STATE_FILE_PATH + ".remote"
        if self.blob_service_client:
            try:
                blob_client_prog = self.blob_service_client.get_blob_client(container=self.container_name, blob="backfill_progress.json")
                if blob_client_prog.exists():
                    logger.info("Descargando la versión más reciente del progreso de Azure Blob para fusionar...")
                    with open(temp_progress_path, "wb") as f:
                        data = blob_client_prog.download_blob()
                        data.readinto(f)
                    
                    if os.path.exists(STATE_FILE_PATH) and os.path.exists(temp_progress_path):
                        with open(STATE_FILE_PATH, "r", encoding="utf-8") as f:
                            local_prog = json.load(f)
                        with open(temp_progress_path, "r", encoding="utf-8") as f:
                            remote_prog = json.load(f)
                        
                        local_keys = set(local_prog.get("completed_keys", []))
                        remote_keys = set(remote_prog.get("completed_keys", []))
                        
                        merged_keys = sorted(list(local_keys.union(remote_keys)))
                        merged_prog = {"completed_keys": merged_keys}
                        
                        with open(STATE_FILE_PATH, "w", encoding="utf-8") as f:
                            json.dump(merged_prog, f, indent=2)
                        logger.info(f"Progreso unificado al final. Total llaves: {len(merged_keys)}")
            except Exception as e:
                logger.error(f"Error al consolidar progreso al final: {e}")
            finally:
                if os.path.exists(temp_progress_path):
                    try:
                        os.remove(temp_progress_path)
                    except Exception:
                        pass
        
        logger.info("Subiendo archivo de progreso a Azure Blob...")
        self.upload_to_blob(STATE_FILE_PATH, "backfill_progress.json")
        self.verify_blob_upload("backfill_progress.json")

    def verify_blob_upload(self, blob_name: str):
        """Verifica que el archivo se ha subido correctamente a Azure Blob."""
        if not self.blob_service_client:
            logger.warning("No se puede verificar la subida porque Azure Blob no está configurado.")
            return
        try:
            blob_client = self.blob_service_client.get_blob_client(container=self.container_name, blob=blob_name)
            if blob_client.exists():
                properties = blob_client.get_blob_properties()
                size_mb = properties.size / (1024 * 1024)
                last_modified = properties.last_modified
                logger.info(f"VERIFICADO: El archivo '{blob_name}' está subido en Azure Blob.")
                logger.info(f"Tamaño en Azure: {size_mb:.2f} MB")
                logger.info(f"Última modificación: {last_modified}")
            else:
                logger.error(f"ERROR DE VERIFICACIÓN: El archivo '{blob_name}' NO se encuentra en Azure Blob.")
        except Exception as e:
            logger.error(f"Error al verificar el archivo en Azure Blob: {e}")

    def load_progress_state(self) -> Dict[str, Any]:
        """Carga el estado del progreso del archivo JSON para reanudar."""
        if os.path.exists(STATE_FILE_PATH):
            try:
                with open(STATE_FILE_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"completed_keys": []}

    def save_progress_state(self, state: Dict[str, Any]):
        """Guarda el progreso de la extracción."""
        with open(STATE_FILE_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)

    def run_backfill(self, start_year: int = 2019, end_year: int = None, max_stations: Optional[int] = None, station_range: Optional[str] = None):
        """
        Ejecuta el proceso completo de backfill histórico para todas las estaciones pre-2019.
        """
        # Descargar el histórico inicial y fusionarlo para no perder progreso local
        self.download_and_merge_at_start()
        self.download_from_blob("estaciones_agrocabildo.parquet", self.local_stations_path)

        df_target = self.load_target_stations()
        self.save_stations_metadata(df_target)

        # Filtrar por rango de estaciones si se especifica
        if station_range:
            try:
                start_r, end_r = map(int, station_range.split("-"))
                # Filtrar por el índice posicional (1-indexed para el usuario)
                df_target = df_target.iloc[start_r - 1 : end_r]
                logger.info(f"Paralelización activa: Procesando rango de estaciones {start_r} al {end_r} (Total: {len(df_target)}).")
            except Exception as e:
                logger.error(f"Error al procesar --station-range '{station_range}': {e}")
                sys.exit(1)

        if max_stations:
            df_target = df_target.head(max_stations)
            logger.info(f"Modo prueba/limite activo: Procesando solo {max_stations} estaciones.")

        current_year = datetime.now().year
        if not end_year:
            end_year = current_year

        years = list(range(start_year, end_year + 1))
        logger.info(f"--- Iniciando Backfill Histórico ({start_year} -> {end_year}) para {len(df_target)} estaciones ---")

        progress_state = self.load_progress_state()
        completed_keys = set(progress_state.get("completed_keys", []))

        total_inserted = 0

        # Iterar sobre las estaciones seleccionadas
        for idx, row in df_target.iterrows():
            station_id = int(row["estacion_id"])
            station_name = str(row["estacion_nombre"])
            
            # Usar idx + 1 como número real en el CSV original para claridad del usuario
            logger.info(f"Procesando Estación {idx + 1} de la lista original: ID {station_id} ({station_name})")
            
            sensors = self.client.get_station_sensors(station_id)
            if not sensors:
                continue

            for sensor in sensors:
                sensor_id = sensor.get("id_weatherstationsensor")
                if not sensor_id:
                    continue

                for year in years:
                    state_key = f"{station_id}_{sensor_id}_{year}"
                    if state_key in completed_keys:
                        logger.debug(f"Omitiendo {state_key} (ya procesado).")
                        continue

                    date_from = f"{year}-01-01"
                    date_to = f"{year}-12-31" if year < current_year else datetime.now().strftime("%Y-%m-%d")

                    # Extraer lecturas horarias en punto
                    records = self.client.extract_hourly_readings(
                        station_id=station_id,
                        sensor_id=sensor_id,
                        date_from=date_from,
                        date_to=date_to,
                        max_pages=38  # 38 páginas cubren un año completo
                    )

                    if records:
                        inserted_count = self.upsert_hourly_readings(records)
                        if inserted_count > 0:
                            total_inserted += inserted_count
                            logger.info(f"  -> {state_key}: {inserted_count} lecturas guardadas en clima_horario_agrocabildo.parquet.")
                            completed_keys.add(state_key)
                            progress_state["completed_keys"] = list(completed_keys)
                            self.save_progress_state(progress_state)
                        else:
                            logger.warning(f"  -> {state_key}: 0 lecturas insertadas.")
                    else:
                        completed_keys.add(state_key)
                        progress_state["completed_keys"] = list(completed_keys)
                        self.save_progress_state(progress_state)

        logger.info(f"=== Backfill Histórico Completado. Total Registros Guardados: {total_inserted} ===")
        self.consolidate_and_upload_at_end()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill Histórico Agrocabildo a Azure Database")
    parser.add_argument("--test", action="store_true", help="Ejecuta una prueba rápida con 1 estación para el año 2020")
    parser.add_argument("--max-stations", type=int, default=None, help="Número máximo de estaciones a procesar")
    parser.add_argument("--start-year", type=int, default=2019, help="Año de inicio (defecto 2019)")
    parser.add_argument("--end-year", type=int, default=None, help="Año de fin (defecto año actual)")
    parser.add_argument("--station-range", type=str, default=None, help="Rango de estaciones a procesar (ej. 1-30)")
    args = parser.parse_args()

    backfill = AgrocabildoHistoricalBackfill()
    if args.test:
        logger.info("--- MODO PRUEBA HISTÓRICA (1 estación, año 2020) ---")
        backfill.run_backfill(start_year=2020, end_year=2020, max_stations=1)
    else:
        backfill.run_backfill(
            start_year=args.start_year, 
            end_year=args.end_year, 
            max_stations=args.max_stations, 
            station_range=args.station_range
        )
