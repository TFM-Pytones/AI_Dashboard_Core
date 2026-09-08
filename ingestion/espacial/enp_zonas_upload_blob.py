"""
enp_zonas_upload_blob.py
---------------------------
Pipeline de Ingesta a Capa Bronce para datos espaciales vectoriales de Tenerife:

  1. Espacios Naturales Protegidos (ENP)
  2. Zonas Turisticas / Nucleos Turisticos

Esta versión asume que los archivos espaciales (.shp, .gpkg, etc.) 
ya se han descargado manualmente en las rutas `data/enp/` y `data/zonas_turisticas/`.
Los datos se filtran a la isla de Tenerife y se guardan como **GeoParquet** 
en Azure Blob Storage bajo bronce-raw/espacial/.

Autor: TFM - AI Dashboard Core
"""

import os
import sys
import logging
import io
from datetime import datetime, timezone
from typing import Optional

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

DEFAULT_OUTPUT_DIR = os.path.abspath(os.path.join(root_dir, "data", "bronce", "espacial"))

# CRS de trabajo: WGS84 (EPSG:4326) para almacenamiento en Bronce
OUTPUT_CRS = "EPSG:4326"


class SpatialLayersBronzeIngestionPipeline:
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

    def _save_parquet_to_blob(self, gdf, blob_name: str) -> bool:
        """Guarda un GeoDataFrame como GeoParquet en Azure Blob."""
        if not self.blob_service_client:
            logger.error("No hay conexion a Azure para subir el Parquet.")
            return False

        try:
            # Escribir GeoParquet a un buffer en memoria
            parquet_buffer = io.BytesIO()
            gdf.to_parquet(parquet_buffer, index=False, compression="snappy")
            parquet_buffer.seek(0)

            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name, blob=blob_name
            )
            blob_client.upload_blob(parquet_buffer, overwrite=True)
            logger.info(f"Subido con éxito: {self.container_name}/{blob_name}")
            return True
        except Exception as e:
            logger.error(f"Error subiendo {blob_name}: {e}")
            return False

    def _filter_tenerife(self, gdf) -> "gpd.GeoDataFrame":
        """Filtra un GeoDataFrame a las entidades de la isla de Tenerife."""
        TENERIFE_BBOX = {
            "minx": -16.95, "maxx": -16.10,
            "miny": 27.90,  "maxy": 28.60,
        }

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
        if not GEOPANDAS_AVAILABLE:
            return None

        logger.info("\n" + "="*60)
        logger.info("INGESTA: Espacios Naturales Protegidos (ENP) Tenerife")
        logger.info("="*60)

        raw_dir = os.path.join(root_dir, "data", "enp")
        shp_file = os.path.join(raw_dir, "eennpp.shp")
        
        if not os.path.exists(shp_file):
            logger.error(f"No se encontró el archivo Shapefile en: {shp_file}")
            return None
            
        try:
            logger.info(f"Leyendo Shapefile local: {shp_file}")
            gdf = gpd.read_file(shp_file)
            logger.info(f"Leídas {len(gdf)} entidades del Shapefile.")
        except Exception as e:
            logger.error(f"Error al leer el Shapefile: {e}")
            return None

        # Reproyectar a WGS84
        if gdf.crs and gdf.crs.to_epsg() != 4326:
            gdf = gdf.to_crs(OUTPUT_CRS)

        gdf_tenerife = self._filter_tenerife(gdf).copy()
        gdf_tenerife["ingested_at_utc"] = datetime.now(timezone.utc).isoformat()
        gdf_tenerife["source"] = "Manual_SITCAN"
        gdf_tenerife["layer"] = "enp"

        # Guardar como Parquet
        blob_name = "espacial/enp/tenerife_espacios_naturales_protegidos.parquet"
        self._save_parquet_to_blob(gdf_tenerife, blob_name)

        logger.info(f"  ENP Tenerife procesado: {len(gdf_tenerife)} espacios naturales")
        return gdf_tenerife

    # ------------------------------------------------------------------
    # 2. Zonas Turisticas
    # ------------------------------------------------------------------
    def run_zonas_turisticas_ingestion(self) -> Optional["gpd.GeoDataFrame"]:
        if not GEOPANDAS_AVAILABLE:
            return None

        logger.info("\n" + "="*60)
        logger.info("INGESTA: Zonas Turisticas Tenerife")
        logger.info("="*60)

        raw_dir = os.path.join(root_dir, "data", "zonas_turisticas")
        
        import glob
        manual_files = glob.glob(os.path.join(raw_dir, "**/*.shp"), recursive=True)
        
        if not manual_files:
            logger.error(f"No se encontró ningún archivo espacial en la carpeta: {raw_dir}")
            return None

        target_file = manual_files[0]
        try:
            logger.info(f"Leyendo archivo local: {target_file}")
            gdf = gpd.read_file(target_file)
            logger.info(f"Leídas {len(gdf)} entidades.")
        except Exception as e:
            logger.error(f"Error al leer el archivo {target_file}: {e}")
            return None

        # Reproyectar a WGS84
        if gdf.crs and gdf.crs.to_epsg() != 4326:
            gdf = gdf.to_crs(OUTPUT_CRS)

        gdf_tenerife = self._filter_tenerife(gdf).copy()
        # --- Limpieza de zonas turísticas ---
        # 1. Quedarnos solo con las columnas esenciales (ahorra espacio)
        cols_to_keep = ['GEOCODE', 'ETIQUETA', 'LONGITUD', 'LATITUD', 'geometry']
        gdf_tenerife = gdf_tenerife[[c for c in cols_to_keep if c in gdf_tenerife.columns]].copy()
        
        # 2. Corregir mojibake (Shapefile en UTF-8 que fue leído como Latin-1)
        if 'ETIQUETA' in gdf_tenerife.columns:
            def fix_latin1_utf8(s):
                try:
                    return str(s).encode('latin-1').decode('utf-8')
                except Exception:
                    return s
            gdf_tenerife['ETIQUETA'] = gdf_tenerife['ETIQUETA'].map(fix_latin1_utf8)

        # Guardar como Parquet
        blob_name = "espacial/zonas_turisticas/tenerife_zonas_turisticas.parquet"
        self._save_parquet_to_blob(gdf_tenerife, blob_name)

        logger.info(f"  Zonas Turisticas Tenerife procesadas: {len(gdf_tenerife)} entidades")
        return gdf_tenerife

    # ------------------------------------------------------------------
    # Pipeline completo
    # ------------------------------------------------------------------
    def run_full_spatial_ingestion(self) -> dict:
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
