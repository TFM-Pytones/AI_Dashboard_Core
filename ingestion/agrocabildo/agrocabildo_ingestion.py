import os
import sys
import logging
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

try:
    import psycopg2
    from psycopg2.extras import execute_values
    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False

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
SQL_SCHEMA_PATH = os.path.abspath(os.path.join(current_dir, "..", "..", "sql", "agrocabildo_schema.sql"))

class AgrocabildoIngestionPipeline:
    def __init__(self, csv_estaciones: str = DEFAULT_CSV_PATH, output_dir: str = DEFAULT_OUTPUT_DIR):
        self.csv_estaciones_path = csv_estaciones
        self.output_dir = output_dir
        self.client = AgrocabildoAPIClient(min_request_interval=6.5)
        os.makedirs(self.output_dir, exist_ok=True)

    def get_db_connection(self):
        """Abre una conexión con la base de datos PostgreSQL de Azure (o Neon como fallback)."""
        if not HAS_PSYCOPG2:
            logger.warning("Módulo psycopg2 no instalado en el entorno. Se omitirá DB (guardando backup Parquet).")
            return None

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
            logger.warning(f"No se pudo conectar con la base de datos: {e}")
        return None

    def init_db(self):
        """Inicializa las tablas en Neon DB utilizando el archivo SQL de esquema."""
        conn = self.get_db_connection()
        if not conn:
            logger.warning("Omite inicialización de BD: Conexión no disponible.")
            return

        try:
            with conn.cursor() as cursor:
                if os.path.exists(SQL_SCHEMA_PATH):
                    with open(SQL_SCHEMA_PATH, "r", encoding="utf-8") as f:
                        sql_script = f.read()
                    cursor.execute(sql_script)
                    conn.commit()
                    logger.info("Tablas de Agrocabildo verificadas/creadas en la Base de Datos.")
                else:
                    logger.warning(f"No se encontró el archivo SQL en: {SQL_SCHEMA_PATH}")
        except Exception as e:
            logger.error(f"Error al inicializar la base de datos: {e}")
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

    def save_to_neon(self, df_stations: pd.DataFrame, df_readings: pd.DataFrame):
        """Guarda las estaciones y las lecturas horarias en la base de datos mediante UPSERT idempotente."""
        conn = self.get_db_connection()
        if not conn:
            return

        try:
            with conn.cursor() as cursor:
                # 1. UPSERT Estaciones
                stations_data = []
                for _, row in df_stations.iterrows():
                    stations_data.append((
                        int(row["estacion_id"]),
                        str(row["estacion_nombre"]),
                        str(row.get("municipio_nombre", "") or ""),
                        self.safe_float(row.get("latitud")),
                        self.safe_float(row.get("longitud")),
                        self.safe_float(row.get("altitud")),
                        pd.to_datetime(row["fecha_instalacion"]).to_pydatetime() if pd.notnull(row.get("fecha_instalacion")) else None
                    ))

                upsert_stations_sql = """
                    INSERT INTO raw_data.estaciones_agrocabildo (id_estacion, nombre, municipio, latitud, longitud, altitud, fecha_instalacion)
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
                if stations_data:
                    execute_values(cursor, upsert_stations_sql, stations_data)

                # 2. UPSERT Lecturas Horarias en raw_data.clima_horario_agrocabildo
                readings_data = []
                for _, row in df_readings.iterrows():
                    readings_data.append((
                        int(row["id_weatherstation"]),
                        int(row["id_weatherstationsensor"]),
                        row["timestamp"].to_pydatetime() if isinstance(row["timestamp"], pd.Timestamp) else pd.to_datetime(row["timestamp"]).to_pydatetime(),
                        self.safe_float(row.get("observation_value")),
                        self.safe_float(row.get("validated_value")),
                        bool(row.get("is_validated", True))
                    ))

                # Deduplicar en memoria dentro del lote
                readings_data = list({(r[0], r[1], r[2]): r for r in readings_data}.values())

                upsert_readings_sql = """
                    INSERT INTO raw_data.clima_horario_agrocabildo (id_estacion, id_sensor, timestamp, valor_observado, valor_validado, es_validado)
                    VALUES %s
                    ON CONFLICT (id_estacion, id_sensor, timestamp) DO UPDATE SET
                        valor_observado = EXCLUDED.valor_observado,
                        valor_validado = EXCLUDED.valor_validado,
                        es_validado = EXCLUDED.es_validado;
                """
                if readings_data:
                    execute_values(cursor, upsert_readings_sql, readings_data, page_size=1000)

                conn.commit()
                logger.info(f"✅ Guardados exitosamente {len(readings_data)} registros horarios en la Base de Datos (raw_data.clima_horario_agrocabildo).")

        except Exception as e:
            logger.error(f"Error al guardar en la Base de Datos: {e}")
        finally:
            conn.close()

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
        # Inicializar base de datos si está disponible
        self.init_db()

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

            # 1. Guardar en Neon DB
            self.save_to_neon(df_target, df_result)

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
