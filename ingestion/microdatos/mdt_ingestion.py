"""
mdt_ingestion.py
----------------
Pipeline de Ingesta a Capa Bronce para el Modelo Digital del Terreno (MDT)
de Tenerife desde el Centro de Descargas del CNIG (IGN).

El MDT se descarga en formato GeoTIFF (COG) con resolución 25m y se
almacena en Azure Blob Storage. A continuación se derivan tres capas clave
mediante rasterio + numpy:

    - Altitud    (Elevación en metros)
    - Pendiente  (Slope en grados)
    - Orientación (Aspect en grados, 0=Norte, 90=Este, 180=Sur, 270=Oeste)
    - Sombras    (Hillshade, 0-255)

Estas capas se usan en el TFM para:
  - Corrección por gradiente térmico (-0.0065 C/m, ~3.2 C cada 500 m)
  - Detección de alisios: orientación Norte vs Sur
  - Detección de valles encajonados: pendiente + hillshade

Fuente: Centro de Descargas CNIG/IGN
URL:    https://centrodedescargas.cnig.es/CentroDescargas/
Proyección Canarias: REGCAN95 / UTM Zona 28N (EPSG:4082)

Descarga manual (si la automática falla por CAPTCHA/sesión web):
  1. Ve a https://centrodedescargas.cnig.es/CentroDescargas/
  2. Busqueda por tipo de dato -> Modelos Digitales de Elevaciones -> MDT25
  3. Selecciona zona: Canarias / Tenerife (REGCAN95 UTM28N)
  4. Hojas a descargar: 1083, 1084, 1085, 1086, 1087, 1088
  5. Coloca los ZIP en: data/bronce/mdt/raw/
  6. Vuelve a ejecutar este script (detectara los ZIP automaticamente)

Uso:
    python ingestion/microdatos/mdt_ingestion.py

Autor: TFM - AI Dashboard Core
"""

import os
import sys
import logging
import glob
import shutil
import zipfile
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

import numpy as np
import requests
from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient

# ---------------------------------------------------------------------------
# Importaciones opcionales — rasterio
# ---------------------------------------------------------------------------
try:
    import rasterio
    RASTERIO_AVAILABLE = True
except ImportError:
    RASTERIO_AVAILABLE = False

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
logger = logging.getLogger("MDTBronzeIngestion")

DEFAULT_OUTPUT_DIR = os.path.abspath(os.path.join(root_dir, "data", "bronce", "mdt"))

# Directorio donde el usuario puede colocar los TIFs descargados manualmente
# (acepta cualquiera de estas rutas alternativas)
MANUAL_TIF_DIRS = [
    os.path.abspath(os.path.join(root_dir, "data", "bronce", "spatial", "raw", "mdt")),
    os.path.abspath(os.path.join(root_dir, "data", "bronce", "mdt", "raw")),
]

# ---------------------------------------------------------------------------
# Hojas MDT25 del CNIG que cubren Tenerife (REGCAN95 / UTM 28N)
#
# Los nombres de fichero siguen la convencion del CNIG:
#   LIDAR-PNOA_MDT25_REGCAN95_HU28_<HOJA>_LID.zip
#
# URL de descarga via API del CNIG (puede requerir sesion en algunos casos):
# ---------------------------------------------------------------------------
TENERIFE_MDT_HOJAS = {
    "1083": "https://centrodedescargas.cnig.es/CentroDescargas/downloadFile.do?codProducto=MDT25&codFile=LIDAR-PNOA_MDT25_REGCAN95_HU28_1083_LID.zip",
    "1084": "https://centrodedescargas.cnig.es/CentroDescargas/downloadFile.do?codProducto=MDT25&codFile=LIDAR-PNOA_MDT25_REGCAN95_HU28_1084_LID.zip",
    "1085": "https://centrodedescargas.cnig.es/CentroDescargas/downloadFile.do?codProducto=MDT25&codFile=LIDAR-PNOA_MDT25_REGCAN95_HU28_1085_LID.zip",
    "1086": "https://centrodedescargas.cnig.es/CentroDescargas/downloadFile.do?codProducto=MDT25&codFile=LIDAR-PNOA_MDT25_REGCAN95_HU28_1086_LID.zip",
    "1087": "https://centrodedescargas.cnig.es/CentroDescargas/downloadFile.do?codProducto=MDT25&codFile=LIDAR-PNOA_MDT25_REGCAN95_HU28_1087_LID.zip",
    "1088": "https://centrodedescargas.cnig.es/CentroDescargas/downloadFile.do?codProducto=MDT25&codFile=LIDAR-PNOA_MDT25_REGCAN95_HU28_1088_LID.zip",
}

CNIG_PORTAL_URL = "https://centrodedescargas.cnig.es/CentroDescargas/"


class MDTBronzeIngestionPipeline:
    """
    Pipeline de ingesta del MDT de Tenerife (CNIG/LIDAR) a la Capa Bronce.

    Pasos:
      1. Descarga hojas ZIP del CNIG (MDT25 REGCAN95 UTM28N)
      2. Descomprime y extrae los GeoTIFF (.tif / .asc)
      3. Calcula capas derivadas: slope, aspect, hillshade (algoritmo Horn 1981)
      4. Sube los GeoTIFF a Azure Blob Storage (contenedor 'bronce-raw')

    Estructura en Azure Blob:
        bronce-raw/
        mdt/
          elevacion/     <- altitud en metros (fuente CNIG)
          slope/         <- pendiente en grados [0, 90]
          aspect/        <- orientacion en grados [0, 360], 0=Norte
          hillshade/     <- sombras 0-255
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
            logger.warning(
                "AZURE_STORAGE_CONNECTION_STRING no configurada. "
                "Los ficheros se guardaran solo localmente."
            )

    # ------------------------------------------------------------------
    # Azure Blob I/O
    # ------------------------------------------------------------------

    def upload_file_to_blob(self, local_path: str, blob_name: str) -> bool:
        """Sube un fichero binario (GeoTIFF) al contenedor Bronce."""
        logger.info(f"  Fichero local: {local_path}")
        if not self.blob_service_client:
            return False
        try:
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name, blob=blob_name
            )
            with open(local_path, "rb") as f:
                blob_client.upload_blob(f, overwrite=True)
            logger.info(f"  Azure: {self.container_name}/{blob_name}")
            return True
        except Exception as e:
            logger.error(f"  Error subiendo {blob_name}: {e}")
            return False

    # ------------------------------------------------------------------
    # Descarga CNIG
    # ------------------------------------------------------------------

    def _download_hoja(self, hoja_id: str, url: str, raw_dir: str) -> Optional[str]:
        """
        Descarga y descomprime una hoja ZIP del MDT del CNIG.

        Returns:
            Ruta al primer .tif/.asc encontrado, o None si hay error.
        """
        zip_path = os.path.join(raw_dir, f"mdt_hoja_{hoja_id}.zip")

        logger.info(f"  Descargando hoja {hoja_id} desde CNIG...")
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 TFM-TUI-Tenerife/1.0 (academic research)",
            }
            resp = requests.get(url, timeout=300, stream=True, headers=headers)
            resp.raise_for_status()

            # Verificar que la respuesta sea un ZIP y no una pagina de error HTML
            content_type = resp.headers.get("Content-Type", "")
            if "html" in content_type.lower():
                raise ValueError(
                    f"El servidor devolvio HTML en lugar de ZIP. "
                    f"Descarga manual requerida: {CNIG_PORTAL_URL}"
                )

            with open(zip_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        f.write(chunk)
            logger.info(f"  Descargado: {zip_path} ({os.path.getsize(zip_path):,} bytes)")
        except Exception as e:
            logger.warning(
                f"  Descarga directa fallida para hoja {hoja_id}: {e}\n"
                f"       Descarga manual: {CNIG_PORTAL_URL}\n"
                f"       Coloca el ZIP en: {raw_dir}"
            )
            if not os.path.exists(zip_path):
                return None

        return self._extract_raster_from_zip(zip_path, hoja_id, raw_dir)

    def _extract_raster_from_zip(
        self, zip_path: str, hoja_id: str, raw_dir: str
    ) -> Optional[str]:
        """Descomprime un ZIP del CNIG y devuelve la ruta del raster."""
        extract_dir = os.path.join(raw_dir, f"hoja_{hoja_id}")
        os.makedirs(extract_dir, exist_ok=True)
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(extract_dir)
        except Exception as e:
            logger.error(f"  Error descomprimiendo {zip_path}: {e}")
            return None

        tif_files = glob.glob(os.path.join(extract_dir, "**", "*.tif"), recursive=True)
        asc_files = glob.glob(os.path.join(extract_dir, "**", "*.asc"), recursive=True)
        candidates = tif_files or asc_files

        if not candidates:
            logger.error(f"  No se encontro .tif/.asc en hoja {hoja_id}")
            return None

        return candidates[0]

    # ------------------------------------------------------------------
    # Calculo de capas derivadas (Horn 1981)
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_slope_aspect(
        elevation: np.ndarray, cell_size: float
    ) -> tuple:
        """
        Calcula pendiente y orientacion usando el algoritmo Horn (1981).
        Este es el mismo algoritmo que ESRI ArcGIS y GDAL gdaldem.

        Args:
            elevation: Array 2D float32 con altitud en metros (NaN = nodata)
            cell_size: Tamano del pixel en metros (ej. 25.0 para MDT25)

        Returns:
            (slope_deg, aspect_deg)
            slope_deg:  Pendiente en grados [0, 90]
            aspect_deg: Orientacion en grados [0, 360] con 0 = Norte
        """
        # Gradientes con kernel 3x3 (centrado)
        # Rellenamos bordes con el vecino mas proximo antes de calcular
        elev = np.where(np.isnan(elevation), 0.0, elevation)

        dzdx = (
            np.roll(elev, -1, axis=1) - np.roll(elev, 1, axis=1)
        ) / (2.0 * cell_size)

        dzdy = (
            np.roll(elev, -1, axis=0) - np.roll(elev, 1, axis=0)
        ) / (2.0 * cell_size)

        slope_rad = np.arctan(np.sqrt(dzdx**2 + dzdy**2))
        slope_deg = np.degrees(slope_rad).astype(np.float32)

        # Aspect: 0=Norte, 90=Este, 180=Sur, 270=Oeste (horario desde Norte)
        aspect_rad = np.arctan2(-dzdy, dzdx)
        aspect_deg = 90.0 - np.degrees(aspect_rad)
        aspect_deg[aspect_deg < 0] += 360.0
        aspect_deg = aspect_deg.astype(np.float32)

        return slope_deg, aspect_deg

    @staticmethod
    def _compute_hillshade(
        elevation: np.ndarray,
        cell_size: float,
        azimuth: float = 315.0,
        sun_altitude: float = 45.0,
    ) -> np.ndarray:
        """
        Calcula el hillshade (sombreado del relieve).

        Args:
            azimuth:      Azimut solar en grados (315 = NO, estandar cartografico)
            sun_altitude: Angulo de elevacion solar en grados (45 por defecto)

        Returns:
            hillshade: Array uint8 [0, 255]
        """
        elev = np.where(np.isnan(elevation), 0.0, elevation)

        dzdx = (np.roll(elev, -1, axis=1) - np.roll(elev, 1, axis=1)) / (2.0 * cell_size)
        dzdy = (np.roll(elev, -1, axis=0) - np.roll(elev, 1, axis=0)) / (2.0 * cell_size)

        slope_rad = np.arctan(np.sqrt(dzdx**2 + dzdy**2))
        aspect_rad = np.arctan2(-dzdy, dzdx)

        zenith_rad = np.radians(90.0 - sun_altitude)
        azimuth_math = 360.0 - azimuth + 90.0
        if azimuth_math >= 360.0:
            azimuth_math -= 360.0
        azimuth_rad = np.radians(azimuth_math)

        hs = 255.0 * (
            np.cos(zenith_rad) * np.cos(slope_rad)
            + np.sin(zenith_rad) * np.sin(slope_rad) * np.cos(azimuth_rad - aspect_rad)
        )
        return np.clip(hs, 0, 255).astype(np.uint8)

    # ------------------------------------------------------------------
    # Guardar capas raster
    # ------------------------------------------------------------------

    def _save_derived_layer(
        self,
        data: np.ndarray,
        layer_name: str,
        hoja_id: str,
        profile: dict,
        dtype: str,
    ) -> Optional[str]:
        """Guarda una capa derivada como GeoTIFF comprimido."""
        if not RASTERIO_AVAILABLE:
            logger.error("rasterio no instalado. Ejecuta: pip install rasterio")
            return None

        out_dir = os.path.join(self.output_dir, layer_name)
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(
            out_dir, f"tenerife_mdt25_{layer_name}_hoja{hoja_id}.tif"
        )

        nodata_val = -9999.0 if "float" in dtype else 255
        out_profile = {**profile, "dtype": dtype, "count": 1,
                       "compress": "lzw", "nodata": nodata_val}

        with rasterio.open(out_path, "w", **out_profile) as dst:
            dst.write(data, 1)

        logger.info(f"  Capa '{layer_name}' guardada: {out_path}")
        return out_path

    # ------------------------------------------------------------------
    # Procesar una hoja
    # ------------------------------------------------------------------

    def process_hoja(self, hoja_id: str, tif_path: str) -> dict:
        """
        Procesa un GeoTIFF de elevacion para una hoja y genera capas derivadas.

        Args:
            hoja_id:  Identificador de hoja (ej. "1083")
            tif_path: Ruta al GeoTIFF de elevacion descargado del CNIG

        Returns:
            Diccionario {nombre_capa: ruta_local}
        """
        if not RASTERIO_AVAILABLE:
            logger.error("rasterio no disponible. Instala: pip install rasterio")
            return {}

        logger.info(f"\n{'='*60}")
        logger.info(f"PROCESANDO HOJA {hoja_id}: {tif_path}")
        logger.info(f"{'='*60}")

        with rasterio.open(tif_path) as src:
            elevation = src.read(1).astype(np.float32)
            nodata = src.nodata
            cell_size = src.res[0]
            profile = src.profile
            logger.info(
                f"  Resolucion: {cell_size}m | CRS: {src.crs} | "
                f"Shape: {elevation.shape} | Nodata: {nodata}"
            )

        if nodata is not None:
            elevation[elevation == nodata] = np.nan

        generated = {}

        # 1. Elevacion (copia directa del fichero CNIG)
        elev_dir = os.path.join(self.output_dir, "elevacion")
        os.makedirs(elev_dir, exist_ok=True)
        elev_path = os.path.join(
            elev_dir, f"tenerife_mdt25_elevacion_hoja{hoja_id}.tif"
        )
        shutil.copy2(tif_path, elev_path)
        generated["elevacion"] = elev_path
        logger.info(f"  Elevacion copiada: {elev_path}")

        # 2. Slope y Aspect (calculo conjunto, 1 solo paso sobre el array)
        slope_deg, aspect_deg = self._compute_slope_aspect(elevation, cell_size)

        slope_path = self._save_derived_layer(
            slope_deg, "slope", hoja_id, profile, "float32"
        )
        if slope_path:
            generated["slope"] = slope_path

        aspect_path = self._save_derived_layer(
            aspect_deg, "aspect", hoja_id, profile, "float32"
        )
        if aspect_path:
            generated["aspect"] = aspect_path

        # 3. Hillshade
        hillshade = self._compute_hillshade(elevation, cell_size)
        hillshade_path = self._save_derived_layer(
            hillshade, "hillshade", hoja_id, profile, "uint8"
        )
        if hillshade_path:
            generated["hillshade"] = hillshade_path

        # 4. Subir a Azure Blob Storage
        for layer_name, local_path in generated.items():
            blob_name = f"mdt/{layer_name}/{Path(local_path).name}"
            self.upload_file_to_blob(local_path, blob_name)

        logger.info(f"  Hoja {hoja_id} procesada: {list(generated.keys())}")
        return generated

    # ------------------------------------------------------------------
    # Pipeline principal
    # ------------------------------------------------------------------

    def run_full_mdt_ingestion(self) -> dict:
        """
        Pipeline completo MDT:
          Descarga hojas CNIG -> Extraccion -> Calculo capas -> Azure Blob

        Returns:
            Dict {hoja_id: {capa: ruta_local}}
        """
        logger.info("Iniciando Pipeline MDT Tenerife (CNIG/LIDAR) -> Capa Bronce...")

        if not RASTERIO_AVAILABLE:
            logger.error(
                "rasterio no instalado. Ejecuta:\n"
                "  pip install rasterio\n"
                "  (en Windows puede requerir: pip install GDAL primero)"
            )
            return {}

        raw_dir = os.path.join(self.output_dir, "raw")
        os.makedirs(raw_dir, exist_ok=True)

        all_results = {}

        for hoja_id, url in TENERIFE_MDT_HOJAS.items():
            logger.info(f"\n{'-'*60}")
            logger.info(f"Hoja {hoja_id}")
            logger.info(f"{'-'*60}")

            tif_path = None

            # Intento 1: TIF ya disponible en alguna de las carpetas manuales conocidas
            for manual_dir in MANUAL_TIF_DIRS:
                candidates = glob.glob(
                    os.path.join(manual_dir, f"*{hoja_id}*.tif"), recursive=False
                ) + glob.glob(
                    os.path.join(manual_dir, "**", f"*{hoja_id}*.tif"), recursive=True
                )
                if candidates:
                    tif_path = candidates[0]
                    logger.info(f"  TIF local encontrado: {tif_path}")
                    break

            # Intento 2: ZIP manual en alguna de las carpetas conocidas
            if tif_path is None:
                for manual_dir in MANUAL_TIF_DIRS + [raw_dir]:
                    manual_zips = glob.glob(os.path.join(manual_dir, f"*{hoja_id}*.zip"))
                    if manual_zips:
                        logger.info(f"  ZIP manual encontrado: {manual_zips[0]}")
                        tif_path = self._extract_raster_from_zip(
                            manual_zips[0], hoja_id, raw_dir
                        )
                        if tif_path:
                            break

            # Intento 3: descarga automatica desde CNIG (solo si no hay nada local)
            if tif_path is None:
                logger.info(f"  No encontrado localmente. Intentando descarga CNIG...")
                tif_path = self._download_hoja(hoja_id, url, raw_dir)

            if tif_path is None:
                logger.warning(
                    f"  Hoja {hoja_id} omitida. Coloca el TIF en:\n"
                    f"  -> {MANUAL_TIF_DIRS[0]}\n"
                    f"  O descarga desde: {CNIG_PORTAL_URL}"
                )
                continue

            results = self.process_hoja(hoja_id, tif_path)
            all_results[hoja_id] = results

        n_ok = len(all_results)
        n_total = len(TENERIFE_MDT_HOJAS)
        logger.info(f"\nPipeline MDT completado: {n_ok}/{n_total} hojas procesadas.")
        logger.info("Capas generadas por hoja: elevacion, slope, aspect, hillshade")
        return all_results


if __name__ == "__main__":
    pipeline = MDTBronzeIngestionPipeline()
    pipeline.run_full_mdt_ingestion()
