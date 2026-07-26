"""
spatial_layers_ingestion.py
---------------------------
Pipeline de Ingesta a Capa Bronce para datos espaciales vectoriales de Tenerife:

  1. Espacios Naturales Protegidos (ENP)
     Fuente: Portal de Datos Abiertos del Gobierno de Canarias (SITCAN/GRAFCAN)
     URL: https://opendata.sitcan.es/
     Fichero: espacios_naturales_protegidos_canarias.zip (GeoPackage o Shapefile)

  2. Zonas Turisticas / Nucleos Turisticos
     Fuente: IDECanarias - Cartografia Estadistica
     URL: https://datos.canarias.es/
     Alternativa WFS: servicio WFS de IDECanarias

Los datos se filtran a la provincia de Santa Cruz de Tenerife (isla de Tenerife)
y se guardan como GeoJSON en Azure Blob Storage bajo bronce-raw/spatial/.

Uso:
    python ingestion/microdatos/spatial_layers_ingestion.py

Autor: TFM - AI Dashboard Core
"""

import os
import sys
import logging
import io
import json
import zipfile
import tempfile
from datetime import datetime, timezone
from typing import Optional

import requests
import pandas as pd
from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient

try:
    import geopandas as gpd
    GEOPANDAS_AVAILABLE = True
except ImportError:
    GEOPANDAS_AVAILABLE = False

# ---------------------------------------------------------------------------
# Rutas del proyecto
# ---------------------------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.abspath(os.path.join(current_dir, "..", ".."))

if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

load_dotenv(os.path.abspath(os.path.join(root_dir, ".env")), override=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger("SpatialLayersBronzeIngestion")

DEFAULT_OUTPUT_DIR = os.path.abspath(os.path.join(root_dir, "data", "bronce", "spatial"))

# ---------------------------------------------------------------------------
# URLs y configuracion de fuentes
#
# IMPORTANTE: Las URLs del portal SITCAN/IDECanarias pueden cambiar.
# Si alguna URL devuelve 404, accede manualmente a:
#   - ENP:            https://opendata.sitcan.es/
#   - Zonas Turisticas: https://datos.canarias.es/
# y busca el dataset. Descarga el fichero y coloca en data/bronce/spatial/raw/
# ---------------------------------------------------------------------------

# ENP: Espacios Naturales Protegidos de Canarias (GRAFCAN/Gobierno de Canarias)
ENP_SOURCES = {
    # Opcion 1: Descarga directa del portal SITCAN (GeoPackage)
    "sitcan_gpkg": (
        "https://opendata.sitcan.es/upload/medio-ambiente/"
        "espacios_naturales_protegidos_canarias.zip"
    ),
    # Opcion 2: Servicio WFS de IDECanarias (GeoJSON)
    "idecanarias_wfs": (
        "https://idecan2.grafcan.es/ServicioWFS/EspNat?"
        "SERVICE=WFS&VERSION=2.0.0&REQUEST=GetFeature"
        "&TYPENAMES=espnat:ENP"
        "&outputFormat=application/json"
        "&SRSNAME=EPSG:4326"
    ),
}

# Zonas Turisticas: Nucleos Turisticos (IDECanarias Cartografia Estadistica)
ZONAS_TURISTICAS_SOURCES = {
    # Opcion 1: WFS de Nucleos Turisticos (cartografia estadistica INE adaptada)
    "idecanarias_wfs_nucleos": (
        "https://idecan2.grafcan.es/ServicioWFS/CartografiaEstadistica?"
        "SERVICE=WFS&VERSION=2.0.0&REQUEST=GetFeature"
        "&TYPENAMES=cartEst:NucleoTuristico"
        "&outputFormat=application/json"
        "&SRSNAME=EPSG:4326"
    ),
    # Opcion 2: Portal datos abiertos Gobierno de Canarias
    "datos_canarias": (
        "https://datos.canarias.es/api/estadisticas/statistical-resources/v1.0/"
        "datasets/ISTAC/C00010A_000006/~latest/data"
        "?fields=id,title&lang=es"
    ),
}

# Identificadores para filtrar Tenerife dentro de Canarias
TENERIFE_CODES = {
    "isla": "38",          # Codigo INE de isla de Tenerife
    "provincia": "38",     # Codigo INE de provincia Santa Cruz de Tenerife
    "municipios_ini": "38", # Los municipios de Tenerife empiezan con "38"
}

# CRS de trabajo: WGS84 (EPSG:4326) para almacenamiento en Bronce
OUTPUT_CRS = "EPSG:4326"


class SpatialLayersBronzeIngestionPipeline:
    """
    Pipeline de ingesta de capas vectoriales (ENP, Zonas Turisticas) a Capa Bronce.

    Estrategia por capa:
      - ENP: Intenta WFS de IDECanarias -> fallback a descarga ZIP SITCAN
      - Zonas Turisticas: Intenta WFS de IDECanarias -> fallback a descarga manual

    Los datos se filtran a Tenerife y se guardan como GeoJSON + Parquet en Azure.
    """

    def __init__(
        self,
        output_dir: str = DEFAULT_OUTPUT_DIR,
        container_name: str = "bronce-raw",
    ):
        self.output_dir = output_dir
        self.container_name = container_name
        os.makedirs(self.output_dir, exist_ok=True)

        conn_str = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
        if conn_str:
            conn_str = conn_str.strip('"').strip("'")
            if "AccountName=" not in conn_str and "DefaultEndpointsProtocol=" not in conn_str:
                conn_str = (
                    "DefaultEndpointsProtocol=https;"
                    "AccountName=datalaketfmtenerife;"
                    f"AccountKey={conn_str};"
                    "EndpointSuffix=core.windows.net"
                )
            try:
                self.blob_service_client = BlobServiceClient.from_connection_string(conn_str)
                logger.info(f"Conectado a Azure Blob Storage ('{self.container_name}').")
            except Exception as e:
                logger.error(f"Error al inicializar Azure Blob: {e}")
                self.blob_service_client = None
        else:
            self.blob_service_client = None
            logger.warning("AZURE_STORAGE_CONNECTION_STRING no configurada.")

    # ------------------------------------------------------------------
    # Azure Blob I/O
    # ------------------------------------------------------------------

    def _save_geojson_to_blob(self, gdf, blob_name: str) -> bool:
        """Guarda un GeoDataFrame como GeoJSON en local y en Azure Blob."""
        local_path = os.path.join(
            self.output_dir, blob_name.replace("/", "_")
        )
        os.makedirs(os.path.dirname(local_path), exist_ok=True)

        geojson_str = gdf.to_json(ensure_ascii=False, indent=2)
        with open(local_path, "w", encoding="utf-8") as f:
            f.write(geojson_str)
        logger.info(f"  GeoJSON local: {local_path} ({len(gdf)} features)")

        if not self.blob_service_client:
            return False
        try:
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name, blob=blob_name
            )
            blob_client.upload_blob(
                geojson_str.encode("utf-8"), overwrite=True,
                content_settings={"content_type": "application/geo+json"},
            )
            logger.info(f"  Azure: {self.container_name}/{blob_name}")
            return True
        except Exception as e:
            logger.error(f"  Error subiendo {blob_name}: {e}")
            return False

    # ------------------------------------------------------------------
    # Utilidades de descarga
    # ------------------------------------------------------------------

    @staticmethod
    def _get_json(url: str, timeout: int = 60) -> Optional[dict]:
        """Descarga un JSON desde una URL."""
        try:
            headers = {"User-Agent": "TFM-TUI-Tenerife/1.0 (academic research)"}
            resp = requests.get(url, timeout=timeout, headers=headers)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.warning(f"  Error descargando JSON de {url}: {e}")
            return None

    @staticmethod
    def _get_zip_extract(url: str, raw_dir: str, name: str, timeout: int = 120) -> Optional[str]:
        """Descarga un ZIP y lo descomprime. Devuelve el directorio de extraccion."""
        zip_path = os.path.join(raw_dir, f"{name}.zip")
        try:
            headers = {"User-Agent": "TFM-TUI-Tenerife/1.0 (academic research)"}
            resp = requests.get(url, timeout=timeout, stream=True, headers=headers)
            resp.raise_for_status()
            with open(zip_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=512 * 1024):
                    if chunk:
                        f.write(chunk)
        except Exception as e:
            logger.warning(f"  Error descargando ZIP {url}: {e}")
            return None

        extract_dir = os.path.join(raw_dir, name)
        os.makedirs(extract_dir, exist_ok=True)
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(extract_dir)
            return extract_dir
        except Exception as e:
            logger.error(f"  Error descomprimiendo {zip_path}: {e}")
            return None

    def _filter_tenerife(self, gdf) -> "gpd.GeoDataFrame":
        """
        Filtra un GeoDataFrame a las entidades de la isla de Tenerife.

        Estrategias (en orden de preferencia):
          1. Columna 'isla' o 'codIsla' con valor '38'
          2. Columna 'municipio' o 'codMunicipio' empezando por '38'
          3. Interseccion espacial con bbox de Tenerife (fallback)
        """
        # Tenerife bounding box aproximado (WGS84)
        TENERIFE_BBOX = {
            "minx": -16.95, "maxx": -16.10,
            "miny": 27.90,  "maxy": 28.60,
        }

        cols = [c.lower() for c in gdf.columns]

        # Estrategia 1: columna de isla
        for col in gdf.columns:
            if col.lower() in ("isla", "codisla", "cod_isla", "c_isla"):
                mask = gdf[col].astype(str).str.startswith("38")
                filtered = gdf[mask]
                if len(filtered) > 0:
                    logger.info(f"  Filtrado por columna '{col}': {len(filtered)} entidades")
                    return filtered

        # Estrategia 2: columna de municipio
        for col in gdf.columns:
            if col.lower() in ("municipio", "codmunicipio", "cod_municipio", "cmun"):
                mask = gdf[col].astype(str).str.startswith("38")
                filtered = gdf[mask]
                if len(filtered) > 0:
                    logger.info(f"  Filtrado por columna '{col}': {len(filtered)} entidades")
                    return filtered

        # Estrategia 3: bbox espacial
        logger.info("  Filtrando por bbox espacial de Tenerife (fallback)")
        filtered = gdf.cx[
            TENERIFE_BBOX["minx"]:TENERIFE_BBOX["maxx"],
            TENERIFE_BBOX["miny"]:TENERIFE_BBOX["maxy"],
        ]
        logger.info(f"  Resultado bbox: {len(filtered)} entidades de {len(gdf)} totales")
        return filtered

    # ------------------------------------------------------------------
    # 1. Espacios Naturales Protegidos (ENP)
    # ------------------------------------------------------------------

    def run_enp_ingestion(self) -> Optional["gpd.GeoDataFrame"]:
        """
        Descarga e ingesta los Espacios Naturales Protegidos de Tenerife.

        Flujo:
          1. Intenta WFS GeoJSON de IDECanarias
          2. Fallback: descarga ZIP desde SITCAN
          3. Fallback: busca fichero manual en data/bronce/spatial/raw/enp/

        Returns:
            GeoDataFrame con ENP de Tenerife (o None si hay error)
        """
        if not GEOPANDAS_AVAILABLE:
            logger.error("geopandas no instalado. Ejecuta: pip install geopandas")
            return None

        logger.info("\n" + "="*60)
        logger.info("INGESTA: Espacios Naturales Protegidos (ENP) Tenerife")
        logger.info("="*60)

        now_utc = datetime.now(timezone.utc).isoformat()
        raw_dir = os.path.join(self.output_dir, "raw", "enp")
        os.makedirs(raw_dir, exist_ok=True)

        gdf = None

        # --- Opcion 1: WFS IDECanarias ---
        logger.info("  Intentando WFS IDECanarias (ENP)...")
        wfs_url = ENP_SOURCES["idecanarias_wfs"]
        try:
            resp = requests.get(wfs_url, timeout=60,
                                headers={"User-Agent": "TFM-TUI-Tenerife/1.0"})
            if resp.status_code == 200 and "FeatureCollection" in resp.text:
                gdf = gpd.read_file(io.StringIO(resp.text))
                logger.info(f"  WFS exitoso: {len(gdf)} entidades descargadas")
            else:
                logger.warning(f"  WFS devolvio status {resp.status_code}")
        except Exception as e:
            logger.warning(f"  WFS fallido: {e}")

        # --- Opcion 2: ZIP desde SITCAN ---
        if gdf is None:
            logger.info("  Intentando descarga ZIP desde SITCAN...")
            extract_dir = self._get_zip_extract(
                ENP_SOURCES["sitcan_gpkg"], raw_dir, "enp_canarias"
            )
            if extract_dir:
                import glob
                gpkg_files = glob.glob(os.path.join(extract_dir, "**/*.gpkg"), recursive=True)
                shp_files = glob.glob(os.path.join(extract_dir, "**/*.shp"), recursive=True)
                geojson_files = glob.glob(os.path.join(extract_dir, "**/*.geojson"), recursive=True)
                candidates = gpkg_files or shp_files or geojson_files
                if candidates:
                    gdf = gpd.read_file(candidates[0])
                    logger.info(f"  ZIP exitoso: {len(gdf)} entidades de {candidates[0]}")

        # --- Opcion 3: Fichero manual ---
        if gdf is None:
            import glob
            manual_files = (
                glob.glob(os.path.join(raw_dir, "**/*.gpkg"), recursive=True)
                + glob.glob(os.path.join(raw_dir, "**/*.shp"), recursive=True)
                + glob.glob(os.path.join(raw_dir, "**/*.geojson"), recursive=True)
            )
            if manual_files:
                gdf = gpd.read_file(manual_files[0])
                logger.info(f"  Fichero manual: {manual_files[0]} ({len(gdf)} entidades)")

        if gdf is None:
            logger.error(
                "  No se pudo obtener ENP. Descarga manual:\n"
                "  -> https://opendata.sitcan.es/ (buscar 'Espacios Naturales Protegidos')\n"
                f"  -> Coloca el fichero en: {raw_dir}"
            )
            return None

        # Reproyectar a WGS84
        if gdf.crs and gdf.crs.to_epsg() != 4326:
            gdf = gdf.to_crs(OUTPUT_CRS)

        # Filtrar Tenerife
        gdf_tenerife = self._filter_tenerife(gdf)
        gdf_tenerife = gdf_tenerife.copy()
        gdf_tenerife["ingested_at_utc"] = now_utc
        gdf_tenerife["source"] = "IDECanarias/GRAFCAN"
        gdf_tenerife["layer"] = "enp"

        # Guardar
        blob_name = "spatial/enp/tenerife_espacios_naturales_protegidos.geojson"
        self._save_geojson_to_blob(gdf_tenerife, blob_name)

        logger.info(f"  ENP Tenerife: {len(gdf_tenerife)} espacios naturales")
        return gdf_tenerife

    # ------------------------------------------------------------------
    # 2. Zonas Turisticas
    # ------------------------------------------------------------------

    def run_zonas_turisticas_ingestion(self) -> Optional["gpd.GeoDataFrame"]:
        """
        Descarga e ingesta las Zonas / Nucleos Turisticos de Tenerife.

        Flujo:
          1. Intenta WFS de Nucleos Turisticos IDECanarias
          2. Fallback: busca fichero manual en data/bronce/spatial/raw/zonas_turisticas/

        Returns:
            GeoDataFrame con zonas turisticas de Tenerife (o None si hay error)
        """
        if not GEOPANDAS_AVAILABLE:
            logger.error("geopandas no instalado. Ejecuta: pip install geopandas")
            return None

        logger.info("\n" + "="*60)
        logger.info("INGESTA: Zonas Turisticas Tenerife")
        logger.info("="*60)

        now_utc = datetime.now(timezone.utc).isoformat()
        raw_dir = os.path.join(self.output_dir, "raw", "zonas_turisticas")
        os.makedirs(raw_dir, exist_ok=True)

        gdf = None

        # --- Opcion 1: WFS IDECanarias Nucleos Turisticos ---
        logger.info("  Intentando WFS IDECanarias (Nucleos Turisticos)...")
        wfs_url = ZONAS_TURISTICAS_SOURCES["idecanarias_wfs_nucleos"]
        try:
            resp = requests.get(wfs_url, timeout=60,
                                headers={"User-Agent": "TFM-TUI-Tenerife/1.0"})
            if resp.status_code == 200 and "FeatureCollection" in resp.text:
                gdf = gpd.read_file(io.StringIO(resp.text))
                logger.info(f"  WFS exitoso: {len(gdf)} nucleos turisticos descargados")
            else:
                logger.warning(f"  WFS devolvio status {resp.status_code}")
        except Exception as e:
            logger.warning(f"  WFS fallido: {e}")

        # --- Opcion 2: Fichero manual ---
        if gdf is None:
            import glob
            manual_files = (
                glob.glob(os.path.join(raw_dir, "**/*.gpkg"), recursive=True)
                + glob.glob(os.path.join(raw_dir, "**/*.shp"), recursive=True)
                + glob.glob(os.path.join(raw_dir, "**/*.geojson"), recursive=True)
            )
            if manual_files:
                gdf = gpd.read_file(manual_files[0])
                logger.info(f"  Fichero manual: {manual_files[0]} ({len(gdf)} entidades)")

        if gdf is None:
            logger.error(
                "  No se pudo obtener Zonas Turisticas. Descarga manual:\n"
                "  -> https://datos.canarias.es/ (buscar 'zonas turisticas' o 'nucleos turisticos')\n"
                "  -> https://www.tenerife.es/ Portal Cabildo Tenerife\n"
                "  -> IDECanarias Visor: https://idecan2.grafcan.es/ (capa CartEst NucleoTuristico)\n"
                f"  -> Coloca el fichero en: {raw_dir}"
            )
            return None

        # Reproyectar a WGS84
        if gdf.crs and gdf.crs.to_epsg() != 4326:
            gdf = gdf.to_crs(OUTPUT_CRS)

        # Filtrar Tenerife
        gdf_tenerife = self._filter_tenerife(gdf)
        gdf_tenerife = gdf_tenerife.copy()
        gdf_tenerife["ingested_at_utc"] = now_utc
        gdf_tenerife["source"] = "IDECanarias/GRAFCAN"
        gdf_tenerife["layer"] = "zonas_turisticas"

        blob_name = "spatial/zonas_turisticas/tenerife_zonas_turisticas.geojson"
        self._save_geojson_to_blob(gdf_tenerife, blob_name)

        logger.info(f"  Zonas Turisticas Tenerife: {len(gdf_tenerife)} entidades")
        return gdf_tenerife

    # ------------------------------------------------------------------
    # Pipeline completo
    # ------------------------------------------------------------------

    def run_full_spatial_ingestion(self) -> dict:
        """Ejecuta la ingesta completa de capas espaciales vectoriales."""
        logger.info("Iniciando Pipeline Capas Espaciales Vectoriales -> Capa Bronce...")
        results = {}

        enp = self.run_enp_ingestion()
        if enp is not None:
            results["enp"] = enp

        zonas = self.run_zonas_turisticas_ingestion()
        if zonas is not None:
            results["zonas_turisticas"] = zonas

        logger.info(f"\nPipeline Espacial completado: {list(results.keys())} ingestados.")
        return results


if __name__ == "__main__":
    pipeline = SpatialLayersBronzeIngestionPipeline()
    pipeline.run_full_spatial_ingestion()
