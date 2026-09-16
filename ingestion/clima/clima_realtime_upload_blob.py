"""
clima_realtime_upload_blob.py
─────────────────────────────────────────────────────────────────────────────
Propósito: Ingesta incremental y en tiempo real de las series meteorológicas
           de la red de Agrocabildo (Cabildo de Tenerife) mediante el catálogo
           abierto de CKAN (datos.tenerife.es).

Ventajas vs API anterior (/api/meteo/latest):
  - Descarga concurrente multi-hilo de los volcados anuales del año en curso.
  - Pasa de tardar varias horas con pausas de 6.5s a solo ~30-50 segundos en total.
  - Actualiza de forma idempotente las particiones Parquet en Azure Blob:
    clima/mediciones/año=YYYY/mes=MM/estacion_{id}.parquet
  - Deduplica por (id_estacion, id_sensor, timestamp).

Uso:
  # Ingesta de los últimos 7 días:
  python ingestion/clima/clima_realtime_upload_blob.py --days-back 7

  # Modo automático: detecta el último dato en Azure y rellena el hueco:
  python ingestion/clima/clima_realtime_upload_blob.py --auto
─────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import argparse
import concurrent.futures
import io
import logging
import os
import sys
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import requests
from dotenv import load_dotenv

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"), override=True)

try:
    from azure.storage.blob import BlobServiceClient
except ImportError:
    BlobServiceClient = None

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("ClimaRealtimeCKAN")
logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(logging.WARNING)
logging.getLogger("azure.storage").setLevel(logging.WARNING)

CKAN_SEARCH_URL = "https://datos.tenerife.es/ckan/api/action/package_search"
DEFAULT_CONTAINER = "bronce-raw"
DEFAULT_BLOB_PREFIX = "clima/mediciones"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AI-Dashboard/1.0"}


class ClimaRealtimeCKANIngestor:
    def __init__(
        self,
        blob_prefix: str = DEFAULT_BLOB_PREFIX,
        container_name: str = DEFAULT_CONTAINER,
    ):
        self.blob_prefix = blob_prefix.rstrip("/")
        self.container_name = container_name
        self.blob_service_client = None

        conn_str = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
        if conn_str and BlobServiceClient is not None:
            conn_str = conn_str.strip('"').strip("'")
            if "AccountName=" not in conn_str and "DefaultEndpointsProtocol=" not in conn_str:
                conn_str = f"DefaultEndpointsProtocol=https;AccountName=datalaketfmtenerife;AccountKey={conn_str};EndpointSuffix=core.windows.net"
            self.blob_service_client = BlobServiceClient.from_connection_string(conn_str)
            logger.info("Conexión con Azure Blob Storage inicializada.")
        else:
            logger.warning("AZURE_STORAGE_CONNECTION_STRING no configurado. Operando sin Blob Storage.")

    def read_parquet_from_blob(self, blob_name: str) -> pd.DataFrame:
        """Lee un Parquet existente del contenedor bronce-raw."""
        if not self.blob_service_client:
            return pd.DataFrame()
        try:
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name, blob=blob_name
            )
            stream = blob_client.download_blob()
            return pd.read_parquet(io.BytesIO(stream.readall()))
        except Exception:
            return pd.DataFrame()

    def write_parquet_to_blob(self, df: pd.DataFrame, blob_name: str):
        """Escribe un DataFrame como Parquet en Azure Blob Storage."""
        if not self.blob_service_client:
            return
        try:
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name, blob=blob_name
            )
            buffer = io.BytesIO()
            df.to_parquet(buffer, index=False, compression="snappy")
            blob_client.upload_blob(buffer.getvalue(), overwrite=True)
        except Exception as e:
            logger.error(f"Error al escribir {blob_name} en Azure Blob: {e}")

    def get_last_ingested_date(self) -> Optional[datetime]:
        """Detecta la fecha más reciente almacenada en Azure Blob Storage."""
        if not self.blob_service_client:
            return None
        try:
            container_client = self.blob_service_client.get_container_client(self.container_name)
            prefix = f"{self.blob_prefix}/"
            blobs = list(container_client.list_blobs(name_starts_with=prefix))
            if not blobs:
                return None

            latest_year, latest_month = -1, -1
            for b in blobs:
                if "año=" in b.name and "mes=" in b.name:
                    parts = b.name.split("/")
                    for p in parts:
                        if p.startswith("año="):
                            y = int(p.split("=")[1])
                        elif p.startswith("mes="):
                            m = int(p.split("=")[1])
                    if y > latest_year or (y == latest_year and m > latest_month):
                        latest_year, latest_month = y, m

            if latest_year == -1:
                return None

            month_prefix = f"{self.blob_prefix}/año={latest_year}/mes={latest_month:02d}/"
            latest_blobs = [b.name for b in blobs if b.name.startswith(month_prefix)]
            if latest_blobs:
                df = self.read_parquet_from_blob(latest_blobs[0])
                if not df.empty and "timestamp" in df.columns:
                    df["timestamp"] = pd.to_datetime(df["timestamp"])
                    return df["timestamp"].max()
        except Exception as e:
            logger.warning(f"No se pudo autodetectar la última fecha: {e}")
        return None

    def fetch_current_year_resources(self, target_year: int) -> List[Dict[str, Any]]:
        """Obtiene las URLs de descarga del recurso JSON del año solicitado para todas las estaciones."""
        logger.info(f"Consultando catálogo CKAN para recursos del año {target_year}...")
        params = {"q": "diezminutales", "rows": 100}
        res = requests.get(CKAN_SEARCH_URL, params=params, headers=HEADERS, timeout=30)
        res.raise_for_status()
        data = res.json()
        packages = data.get("result", {}).get("results", [])

        resources_to_fetch = []
        for pkg in packages:
            title = pkg.get("title", "")
            pkg_name = pkg.get("name", "")
            for r in pkg.get("resources", []):
                fmt = r.get("format", "").upper()
                url = r.get("url", "")
                name = r.get("name", "")
                if (fmt == "JSON" or url.endswith(".json")) and (str(target_year) in name or str(target_year) in url):
                    resources_to_fetch.append({
                        "pkg_title": title,
                        "pkg_name": pkg_name,
                        "url": url,
                        "year": target_year
                    })
                    break

        logger.info(f"Se encontraron {len(resources_to_fetch)} estaciones con volcado para el año {target_year}.")
        return resources_to_fetch

    def download_and_parse_readings(
        self, url: str, min_timestamp: Optional[datetime] = None, max_timestamp: Optional[datetime] = None
    ) -> Tuple[pd.DataFrame, int, str]:
        """Descarga el dump JSON anual de CKAN y filtra por ventana temporal."""
        res = requests.get(url, headers=HEADERS, timeout=120)
        res.raise_for_status()
        data = res.json()

        estaciones = data.get("estaciones", [])
        if not estaciones:
            return pd.DataFrame(), -1, "Desconocido"

        est = estaciones[0]
        st_id = int(est.get("estacion_id", -1))
        st_name = est.get("estacion_nombre", "Desconocido")

        rows = []
        for sensor in est.get("sensores", []):
            s_id = int(sensor.get("sensor_id", -1))
            for v in sensor.get("valores", []):
                val_valid = v.get("valor_validado")
                val_obs = v.get("valor_observado", val_valid)
                ts_str = v.get("fecha_observacion")

                rows.append({
                    "id_estacion": st_id,
                    "id_sensor": s_id,
                    "timestamp": ts_str,
                    "valor_observado": float(val_obs) if val_obs is not None else None,
                    "valor_validado": float(val_valid) if val_valid is not None else None,
                    "es_validado": val_valid is not None
                })

        df = pd.DataFrame(rows)
        if df.empty:
            return df, st_id, st_name

        df["timestamp"] = pd.to_datetime(df["timestamp"])

        # Filtrar por ventana temporal si se especificó
        if min_timestamp:
            df = df[df["timestamp"] >= min_timestamp]
        if max_timestamp:
            df = df[df["timestamp"] <= max_timestamp]

        if not df.empty:
            df["año"] = df["timestamp"].dt.year
            df["mes"] = df["timestamp"].dt.month

        return df, st_id, st_name

    def save_and_merge_partitions(self, df_new: pd.DataFrame, st_id: int):
        """Fusiona incrementalmente las lecturas nuevas con las existentes en Azure Blob Storage."""
        if df_new.empty:
            return

        grouped = df_new.groupby(["año", "mes"])
        for (anio, mes), df_group in grouped:
            blob_name = f"{self.blob_prefix}/año={int(anio)}/mes={int(mes):02d}/estacion_{st_id}.parquet"
            df_existing = self.read_parquet_from_blob(blob_name)

            if not df_existing.empty:
                df_existing["timestamp"] = pd.to_datetime(df_existing["timestamp"])
                df_combined = pd.concat([df_existing, df_group], ignore_index=True)
                df_combined.drop_duplicates(
                    subset=["id_estacion", "id_sensor", "timestamp"],
                    keep="last",
                    inplace=True
                )
            else:
                df_combined = df_group

            self.write_parquet_to_blob(df_combined, blob_name)

    def _process_single_station(
        self, item: Dict[str, Any], min_ts: Optional[datetime], max_ts: Optional[datetime]
    ) -> Tuple[int, int, str, float]:
        t_st = time.time()
        url = item["url"]
        df_st, st_id, st_name = self.download_and_parse_readings(
            url=url, min_timestamp=min_ts, max_timestamp=max_ts
        )
        count = len(df_st)
        if count > 0:
            self.save_and_merge_partitions(df_st, st_id)
        elapsed = time.time() - t_st
        return count, st_id, st_name, elapsed

    def run(
        self,
        days_back: int = 7,
        auto_mode: bool = False,
        max_stations: Optional[int] = None,
        max_workers: int = 8,
    ) -> Dict[str, Any]:
        """Ejecuta la ingesta en tiempo real / incremental usando CKAN en paralelo."""
        t0 = time.time()
        now = datetime.now()
        target_year = now.year

        min_ts = None
        if auto_mode:
            last_ts = self.get_last_ingested_date()
            if last_ts:
                min_ts = last_ts - timedelta(days=1)  # 1 día de solape de seguridad
                logger.info(f"Modo automático: Último dato en Azure es de {last_ts.strftime('%Y-%m-%d %H:%M')}.")
                logger.info(f"Extrayendo desde {min_ts.strftime('%Y-%m-%d %H:%M')}.")
            else:
                min_ts = now - timedelta(days=days_back)
                logger.info(f"Modo automático: Sin histórico previo, usando últimos {days_back} días.")
        else:
            min_ts = now - timedelta(days=days_back)
            logger.info(f"Extrayendo lecturas de los últimos {days_back} días (desde {min_ts.strftime('%Y-%m-%d')}).")

        resources = self.fetch_current_year_resources(target_year)
        if max_stations:
            resources = resources[:max_stations]

        total_readings = 0
        stations_processed = 0

        logger.info(f"Descargando {len(resources)} estaciones en paralelo con {max_workers} hilos...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_item = {
                executor.submit(self._process_single_station, item, min_ts, now): item
                for item in resources
            }
            for idx, future in enumerate(concurrent.futures.as_completed(future_to_item), start=1):
                item = future_to_item[future]
                try:
                    count, st_id, st_name, elapsed = future.result()
                    total_readings += count
                    stations_processed += 1
                    logger.info(
                        f"  [{idx}/{len(resources)}] ID {st_id:2d} ({st_name}): "
                        f"{count:,} lecturas procesadas en {elapsed:.2f}s"
                    )
                except Exception as e:
                    logger.error(f"  [{idx}/{len(resources)}] Error procesando {item['pkg_title']}: {e}")

        total_time = time.time() - t0
        logger.info("=" * 60)
        logger.info(f"INGESTA INCREMENTAL CKAN FINALIZADA")
        logger.info(f"Estaciones procesadas: {stations_processed}/{len(resources)}")
        logger.info(f"Total lecturas consolidadas: {total_readings:,}")
        logger.info(f"Tiempo total: {total_time:.2f} segundos ({total_time/60:.2f} minutos)")
        logger.info("=" * 60)

        return {
            "stations_processed": stations_processed,
            "total_readings": total_readings,
            "total_seconds": total_time,
        }


def main():
    parser = argparse.ArgumentParser(description="Ingesta incremental y en tiempo real de datos meteorológicos vía CKAN")
    parser.add_argument(
        "--days-back",
        type=int,
        default=7,
        help="Número de días hacia atrás a descargar (por defecto 7)",
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Detecta automáticamente la última fecha descargada en Azure y rellena el hueco",
    )
    parser.add_argument(
        "--max-stations",
        type=int,
        default=None,
        help="Número máximo de estaciones para pruebas rápidas",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=8,
        help="Número de hilos para descarga paralela (por defecto 8)",
    )
    parser.add_argument(
        "--blob-prefix",
        type=str,
        default=DEFAULT_BLOB_PREFIX,
        help=f"Prefijo de almacenamiento en Azure Blob (por defecto '{DEFAULT_BLOB_PREFIX}')",
    )
    args = parser.parse_args()

    ingestor = ClimaRealtimeCKANIngestor(blob_prefix=args.blob_prefix)
    ingestor.run(
        days_back=args.days_back,
        auto_mode=args.auto,
        max_stations=args.max_stations,
        max_workers=args.workers,
    )


if __name__ == "__main__":
    main()
