import os
import sys
import json
import time
import argparse
import logging
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
from datetime import datetime
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

load_dotenv(os.path.abspath(os.path.join(current_dir, "..", "..", ".env")), override=True)
load_dotenv(os.path.abspath(os.path.join(current_dir, "..", "..", "..", ".env")), override=True)

from agrocabildo_client import AgrocabildoAPIClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("AgrocabildoBackfill")

DEFAULT_CSV_PATH = os.path.abspath(os.path.join(current_dir, "..", "..", "..", "estaciones-meteorologicas.csv"))
SQL_SCHEMA_PATH = os.path.abspath(os.path.join(current_dir, "..", "..", "sql", "agrocabildo_schema.sql"))
STATE_FILE_PATH = os.path.join(current_dir, "backfill_progress.json")

class AgrocabildoHistoricalBackfill:
    def __init__(self, csv_path: str = DEFAULT_CSV_PATH):
        self.csv_path = csv_path
        self.client = AgrocabildoAPIClient(min_request_interval=6.5)

    def get_db_connection(self):
        """Abre una conexión con la base de datos PostgreSQL de Azure (o Neon como fallback)."""
        # Priorizar credenciales de Azure, usar Neon como fallback
        db_user = os.getenv("AZURE_DB_USER") or os.getenv("DB_USER")
        db_password = os.getenv("AZURE_DB_PASSWORD") or os.getenv("DB_PASSWORD")
        db_host = os.getenv("AZURE_DB_HOST") or os.getenv("DB_HOST")
        db_name = os.getenv("AZURE_DB_NAME") or os.getenv("DB_NAME")
        db_url = os.getenv("AZURE_DB_URL") or os.getenv("DB_URL")

        try:
            if db_host and db_user and db_password and db_name:
                conn = psycopg2.connect(
                    host=db_host,
                    user=db_user,
                    password=db_password,
                    dbname=db_name,
                    port="5432",
                    sslmode="require"
                )
                return conn
            elif db_url:
                conn = psycopg2.connect(db_url)
                return conn
        except Exception as e:
            logger.error(f"❌ Error al conectar a la base de datos: {e}")
        return None

    def init_db(self):
        """Crea el esquema raw_data y las tablas clima_horario_agrocabildo."""
        conn = self.get_db_connection()
        if not conn:
            raise ConnectionError("No se pudo establecer conexión con la base de datos.")

        try:
            with conn.cursor() as cursor:
                if os.path.exists(SQL_SCHEMA_PATH):
                    with open(SQL_SCHEMA_PATH, "r", encoding="utf-8") as f:
                        sql_script = f.read()
                    cursor.execute(sql_script)
                    conn.commit()
                    logger.info("✅ Esquema 'raw_data' y tablas verificadas en la base de datos.")
                else:
                    logger.error(f"No se encontró el archivo SQL en {SQL_SCHEMA_PATH}")
        finally:
            conn.close()

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
        """Guarda la metainformación de las estaciones en raw_data.estaciones_agrocabildo."""
        conn = self.get_db_connection()
        if not conn:
            return

        try:
            with conn.cursor() as cursor:
                stations_data = []
                for _, row in df_stations.iterrows():
                    stations_data.append((
                        int(row["estacion_id"]),
                        str(row["estacion_nombre"]),
                        str(row.get("municipio_nombre", "") or ""),
                        float(row["latitud"]) if pd.notnull(row.get("latitud")) else None,
                        float(row["longitud"]) if pd.notnull(row.get("longitud")) else None,
                        float(row["altitud"]) if pd.notnull(row.get("altitud")) else None,
                        pd.to_datetime(row["fecha_instalacion"]).to_pydatetime() if pd.notnull(row.get("fecha_instalacion")) else None
                    ))

                sql = """
                    INSERT INTO raw_data.estaciones_agrocabildo 
                    (id_estacion, nombre, municipio, latitud, longitud, altitud, fecha_instalacion)
                    VALUES %s
                    ON CONFLICT (id_estacion) DO UPDATE SET
                        nombre = EXCLUDED.nombre,
                        municipio = EXCLUDED.municipio,
                        latitud = EXCLUDED.latitud,
                        longitud = EXCLUDED.longitud,
                        altitud = EXCLUDED.altitud,
                        fecha_instalacion = EXCLUDED.fecha_instalacion,
                        actualizado_en = CURRENT_TIMESTAMP;
                """
                execute_values(cursor, sql, stations_data)
                conn.commit()
                logger.info(f"✅ Guardadas {len(stations_data)} estaciones en raw_data.estaciones_agrocabildo.")
        finally:
            conn.close()

    @staticmethod
    def safe_float(val: Any) -> Optional[float]:
        if val is None or val == "":
            return None
        try:
            return float(val)
        except (ValueError, TypeError):
            return None

    def upsert_hourly_readings(self, records: List[Dict[str, Any]]) -> int:
        """Inserta lote de lecturas en raw_data.clima_horario_agrocabildo."""
        if not records:
            return 0

        conn = self.get_db_connection()
        if not conn:
            return 0

        try:
            with conn.cursor() as cursor:
                readings_data = []
                for rec in records:
                    readings_data.append((
                        int(rec["id_weatherstation"]),
                        int(rec["id_weatherstationsensor"]),
                        pd.to_datetime(rec["timestamp"]).to_pydatetime(),
                        self.safe_float(rec.get("observation_value")),
                        self.safe_float(rec.get("validated_value")),
                        bool(rec.get("is_validated", True))
                    ))

                # Deduplicar en memoria para evitar CardinalityViolation dentro del mismo lote
                readings_data = list({(r[0], r[1], r[2]): r for r in readings_data}.values())

                sql = """
                    INSERT INTO raw_data.clima_horario_agrocabildo (id_estacion, id_sensor, timestamp, valor_observado, valor_validado, es_validado)
                    VALUES %s
                    ON CONFLICT (id_estacion, id_sensor, timestamp) DO UPDATE SET
                        valor_observado = EXCLUDED.valor_observado,
                        valor_validado = EXCLUDED.valor_validado,
                        es_validado = EXCLUDED.es_validado;
                """
                execute_values(cursor, sql, readings_data, page_size=1000)
                conn.commit()
                return len(readings_data)
        finally:
            conn.close()

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

    def run_backfill(self, start_year: int = 2020, end_year: int = None, max_stations: Optional[int] = None, station_range: Optional[str] = None):
        """
        Ejecuta el proceso completo de backfill histórico para todas las estaciones pre-2020.
        """
        self.init_db()

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
                logger.error(f"❌ Error al procesar --station-range '{station_range}': {e}")
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
                            logger.info(f"  -> {state_key}: {inserted_count} lecturas guardadas en raw_data.clima_horario_agrocabildo")
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
