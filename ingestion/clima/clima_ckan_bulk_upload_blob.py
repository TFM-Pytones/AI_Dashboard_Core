"""
clima_ckan_bulk_upload_blob.py
─────────────────────────────────────────────────────────────────────────────
Propósito: Ingesta masiva de series meteorológicas históricas diezminutales
           de la red de Agrocabildo (Cabildo de Tenerife) mediante el catálogo
           abierto de CKAN (datos.tenerife.es).

Ventajas vs API anterior (/api/meteo/latest):
  - Descargas directas de volcados anuales completos por estación en JSON.
  - Pasa de tardar 7-10 días a solo ~15-20 segundos por estación/año.
  - Guarda en Azure Blob Storage (bronce-raw) con particionado Hive:
    clima/mediciones/año=YYYY/mes=MM/estacion_{id}.parquet

Uso:
  # Probar con 5 estaciones para el año 2024 (subiendo a Azure Blob):
  python ingestion/clima/clima_ckan_bulk_upload_blob.py --max-stations 5 --years 2024 --upload-blob

  # Descarga histórica completa (2019 a 2024) para todas las estaciones:
  python ingestion/clima/clima_ckan_bulk_upload_blob.py --years 2019-2024 --upload-blob
─────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import argparse
import io
import json
import logging
import os
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import requests
from dotenv import load_dotenv

# Cargar variables de entorno del proyecto
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"), override=True)

# Azure Blob Storage (opcional según argumentos)
try:
    from azure.storage.blob import BlobServiceClient
except ImportError:
    BlobServiceClient = None

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("ClimaCKANBulk")

CKAN_SEARCH_URL = "https://datos.tenerife.es/ckan/api/action/package_search"
DEFAULT_CONTAINER = "bronce-raw"


class ClimaCKANBulkIngestor:
    def __init__(
        self,
        upload_blob: bool = False,
        local_dir: Optional[str] = None,
        blob_prefix: str = "clima/mediciones",
        skip_existing: bool = False,
    ):
        self.upload_blob = upload_blob
        self.local_dir = local_dir
        self.blob_prefix = blob_prefix.rstrip("/")
        self.skip_existing = skip_existing
        self.blob_service_client = None
        self.container_name = DEFAULT_CONTAINER

        if self.upload_blob:
            conn_str = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
            if not conn_str:
                logger.warning("AZURE_STORAGE_CONNECTION_STRING no configurado. Solo se guardará en local.")
                self.upload_blob = False
            elif BlobServiceClient is None:
                logger.error("Librería azure-storage-blob no disponible. Desactivando subida a blob.")
                self.upload_blob = False
            else:
                conn_str = conn_str.strip('"').strip("'")
                if "AccountName=" not in conn_str and "DefaultEndpointsProtocol=" not in conn_str:
                    conn_str = f"DefaultEndpointsProtocol=https;AccountName=datalaketfmtenerife;AccountKey={conn_str};EndpointSuffix=core.windows.net"
                self.blob_service_client = BlobServiceClient.from_connection_string(conn_str)
                logger.info("Conexión con Azure Blob Storage inicializada.")

        if self.local_dir:
            os.makedirs(self.local_dir, exist_ok=True)

    def fetch_ckan_catalog(self) -> List[Dict[str, Any]]:
        """Obtiene la lista de conjuntos de datos diezminutales disponibles en CKAN."""
        logger.info("Consultando catálogo CKAN de datos meteorológicos diezminutales...")
        params = {
            "q": "diezminutales",
            "rows": 100,  # Actualmente hay 68 estaciones
        }
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AI-Dashboard/1.0"}
        res = requests.get(CKAN_SEARCH_URL, params=params, headers=headers, timeout=30)
        res.raise_for_status()
        data = res.json()

        if not data.get("success"):
            raise RuntimeError(f"Fallo al consultar la API de CKAN: {data}")

        packages = data.get("result", {}).get("results", [])
        logger.info(f"Total estaciones encontradas en CKAN: {len(packages)}")
        return packages

    @staticmethod
    def parse_years_arg(years_str: str) -> List[int]:
        """Parsea strings como '2024', '2019-2024' o '2021,2023,2024'."""
        years = []
        for part in years_str.split(","):
            part = part.strip()
            if "-" in part:
                start_y, end_y = part.split("-")
                years.extend(range(int(start_y), int(end_y) + 1))
            elif part.isdigit():
                years.append(int(part))
        return sorted(list(set(years)))

    def filter_resources(
        self, package: Dict[str, Any], target_years: List[int]
    ) -> List[Tuple[int, str]]:
        """
        Extrae los recursos JSON correspondientes a los años solicitados.
        Retorna lista de tuplas: (año, url_descarga)
        """
        results = []
        resources = package.get("resources", [])
        for r in resources:
            fmt = r.get("format", "").upper()
            url = r.get("url", "")
            name = r.get("name", "")

            # Nos interesan únicamente los archivos JSON
            if fmt == "JSON" or url.endswith(".json"):
                for year in target_years:
                    if str(year) in name or str(year) in url:
                        results.append((year, url))
                        break
        return sorted(results, key=lambda x: x[0])

    def download_and_parse_json(self, url: str) -> Tuple[pd.DataFrame, int, str]:
        """Descarga el dump JSON anual y lo convierte en un DataFrame normalizado."""
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        t0 = time.time()
        res = requests.get(url, headers=headers, timeout=120)
        res.raise_for_status()
        t_download = time.time() - t0

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
                rows.append({
                    "id_estacion": st_id,
                    "id_sensor": s_id,
                    "timestamp": v.get("fecha_observacion"),
                    "valor_observado": float(val_obs) if val_obs is not None else None,
                    "valor_validado": float(val_valid) if val_valid is not None else None,
                    "es_validado": val_valid is not None
                })

        df = pd.DataFrame(rows)
        if not df.empty:
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df["año"] = df["timestamp"].dt.year
            df["mes"] = df["timestamp"].dt.month

        return df, st_id, st_name

    def upload_monthly_partitions(self, df_year: pd.DataFrame, st_id: int):
        """Particiona el DataFrame por mes y lo sube en formato Parquet a Azure Blob / local."""
        if df_year.empty:
            return

        grouped = df_year.groupby(["año", "mes"])
        for (anio, mes), df_month in grouped:
            anio = int(anio)
            mes = int(mes)
            blob_path = f"{self.blob_prefix}/año={anio}/mes={mes:02d}/estacion_{st_id}.parquet"

            buffer = io.BytesIO()
            df_month.to_parquet(buffer, index=False, compression="snappy")
            parquet_bytes = buffer.getvalue()

            # 1. Guardar localmente si se indicó
            if self.local_dir:
                local_month_dir = os.path.join(self.local_dir, f"año={anio}", f"mes={mes:02d}")
                os.makedirs(local_month_dir, exist_ok=True)
                local_file = os.path.join(local_month_dir, f"estacion_{st_id}.parquet")
                with open(local_file, "wb") as f:
                    f.write(parquet_bytes)

            # 2. Subir a Azure Blob Storage
            if self.upload_blob and self.blob_service_client:
                try:
                    blob_client = self.blob_service_client.get_blob_client(
                        container=self.container_name, blob=blob_path
                    )
                    blob_client.upload_blob(parquet_bytes, overwrite=True)
                except Exception as e:
                    logger.error(f"Error subiendo {blob_path} a Azure: {e}")

    def run(
        self,
        target_years: List[int],
        max_stations: Optional[int] = None,
        station_filter: Optional[List[str]] = None,
        reset_progress: bool = False,
    ) -> Dict[str, Any]:
        """Ejecuta el pipeline de extracción masiva con tolerancia a interrupciones."""
        start_time = time.time()
        packages = self.fetch_ckan_catalog()

        # Filtrar estaciones si se solicitaron específicas
        if station_filter:
            packages = [
                p for p in packages
                if any(f.lower() in p["title"].lower() or f.lower() in p["name"].lower() for f in station_filter)
            ]

        if max_stations:
            packages = packages[:max_stations]

        # Cargar checkpoint de progreso si existe
        state_file = os.path.join(CURRENT_DIR, "clima_ckan_progress.json")
        completed_keys = set()
        if not reset_progress and os.path.exists(state_file):
            try:
                with open(state_file, "r", encoding="utf-8") as f:
                    saved_state = json.load(f)
                    completed_keys = set(saved_state.get("completed_keys", []))
                logger.info(f"Progreso previo detectado: {len(completed_keys)} volcados ya completados.")
            except Exception as e:
                logger.warning(f"No se pudo cargar el archivo de progreso previo: {e}")

        logger.info(f"Procesando {len(packages)} estaciones para los años: {target_years}")
        logger.info(f"Destino en Azure Blob: contenedor '{self.container_name}', prefijo '{self.blob_prefix}'")

        total_readings = 0
        stations_processed = 0

        for idx, pkg in enumerate(packages, start=1):
            title = pkg.get("title", "")
            pkg_name = pkg.get("name", title)
            resources = self.filter_resources(pkg, target_years)

            logger.info(f"\n[{idx}/{len(packages)}] Estación: {title}")
            if not resources:
                logger.warning(f"  -> No se encontraron recursos JSON para los años solicitados.")
                continue

            for year, download_url in resources:
                ckpt_key = f"{self.blob_prefix}_{pkg_name}_{year}"
                if ckpt_key in completed_keys:
                    logger.info(f"  ⏭️ Año {year} ya procesado anteriormente. Omitiendo.")
                    continue

                t_step = time.time()
                try:
                    logger.info(f"  -> Descargando año {year}...")
                    df_year, st_id, st_name = self.download_and_parse_json(download_url)
                    rows_count = len(df_year)
                    total_readings += rows_count

                    # Particionar y subir
                    self.upload_monthly_partitions(df_year, st_id)

                    # Guardar checkpoint de progreso
                    completed_keys.add(ckpt_key)
                    try:
                        with open(state_file, "w", encoding="utf-8") as f:
                            json.dump({"completed_keys": sorted(list(completed_keys))}, f, indent=2)
                    except Exception:
                        pass

                    elapsed = time.time() - t_step
                    logger.info(
                        f"  ✓ {year}: {rows_count:,} lecturas procesadas y particionadas en {elapsed:.2f}s "
                        f"(ID={st_id} - {st_name})"
                    )
                except Exception as e:
                    logger.error(f"  ✗ Error procesando año {year} ({download_url}): {e}")

            stations_processed += 1

        total_elapsed = time.time() - start_time
        logger.info("\n" + "=" * 60)
        logger.info(f"RESUMEN DE CARGA MASIVA CKAN")
        logger.info(f"Estaciones procesadas: {stations_processed}")
        logger.info(f"Años solicitados: {target_years}")
        logger.info(f"Total mediciones guardadas en este lote: {total_readings:,}")
        logger.info(f"Tiempo total: {total_elapsed:.2f} segundos ({total_elapsed/60:.2f} minutos)")
        logger.info("=" * 60)

        return {
            "stations_processed": stations_processed,
            "total_readings": total_readings,
            "total_seconds": total_elapsed,
        }


def main():
    parser = argparse.ArgumentParser(description="Ingesta Masiva CKAN Agrocabildo a Azure Blob")
    parser.add_argument(
        "--years",
        type=str,
        default="2024",
        help="Años a descargar: ej. '2024', '2019-2024', o '2022,2023,2024' (por defecto '2024')",
    )
    parser.add_argument(
        "--max-stations",
        type=int,
        default=None,
        help="Número máximo de estaciones a procesar (para pruebas, ej. 5)",
    )
    parser.add_argument(
        "--stations",
        type=str,
        default=None,
        help="Filtro de nombres de estaciones separado por comas (ej. 'Vilaflor,Victoria')",
    )
    parser.add_argument(
        "--upload-blob",
        action="store_true",
        help="Subir las particiones Parquet directamente a Azure Blob Storage",
    )
    parser.add_argument(
        "--blob-prefix",
        type=str,
        default="clima/mediciones",
        help="Prefijo de carpeta en Azure Blob Storage (ej. 'clima_prueba/mediciones' o 'clima/mediciones')",
    )
    parser.add_argument(
        "--local-dir",
        type=str,
        default=os.path.join(PROJECT_ROOT, "data", "clima_ckan_test"),
        help="Directorio local donde guardar las particiones Parquet",
    )
    parser.add_argument(
        "--no-local",
        action="store_true",
        help="No guardar copias en disco local (solo procesar en memoria y subir a Azure)",
    )
    parser.add_argument(
        "--reset-progress",
        action="store_true",
        help="Ignorar el archivo de progreso y reprocesar desde el principio",
    )

    args = parser.parse_args()
    years = ClimaCKANBulkIngestor.parse_years_arg(args.years)
    station_filter = [s.strip() for s in args.stations.split(",")] if args.stations else None
    local_dir = None if args.no_local else args.local_dir

    ingestor = ClimaCKANBulkIngestor(
        upload_blob=args.upload_blob,
        local_dir=local_dir,
        blob_prefix=args.blob_prefix,
    )
    ingestor.run(
        target_years=years,
        max_stations=args.max_stations,
        station_filter=station_filter,
        reset_progress=args.reset_progress,
    )


if __name__ == "__main__":
    main()
