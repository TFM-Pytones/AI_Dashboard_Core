"""
download_viirs.py
-----------------
Pipeline de Descarga VIIRS Night Lights (NASA) para la Capa Bronce.
Issue #10 — Extracción Satelital (Copernicus / Sentinel) — componente VIIRS.

Arquitectura Medallón - Capa Bronce (Raw):
- Descarga composites mensuales VIIRS VNP46A2 (Black Marble) de NASA LAADS DAAC.
- Recorta al extent de Tenerife y guarda en formato GeoTIFF.
- Añade metadato `periodo_covid` (TRUE para años 2020-2021) para filtrado posterior.
- Sube los GeoTIFFs a Azure Blob Storage (bronce-raw/satelite/viirs/).

Producto NASA: VNP46A2 — VIIRS/NPP Gap-Filled Lunar BRDF-Adjusted Nighttime Lights
  - Resolución: ~500m (15 arc-seconds)
  - Periodo disponible: desde 2012-01-19
  - Formato: HDF5 (.h5) con varias capas de radianza nocturna
  - Capa de interés: 'DNB_At_Sensor_Radiance' o 'Gap_Filled_DNB_BRDF-Corrected_NTL'

Alternativa GEE (más sencilla, sin cuenta NASA):
  - Colección: 'NOAA/VIIRS/DNB/MONTHLY_V1/VCMSLCFG'
  - Este script ofrece AMBAS opciones (--source gee o --source nasa)

Periodo TFM: enero 2019 → último mes completo disponible (auto-calculado).

Requisitos:
  Para NASA LAADS DAAC:
    - Cuenta en https://urs.earthdata.nasa.gov/ (gratuita)
    - Token de autenticación en .env como EARTHDATA_TOKEN
    - pip install requests h5py rasterio numpy python-dotenv azure-storage-blob

  Para GEE:
    - earthengine authenticate (ya configurado para Sentinel-2)
    - pip install earthengine-api

Uso:
  # Opción A: descargar via GEE (recomendada, más sencilla)
  python ingestion/copernicus/download_viirs.py --source gee --export

  # Opción B: descargar directamente de NASA LAADS DAAC
  python ingestion/copernicus/download_viirs.py --source nasa --download

  # Subir GeoTIFFs locales a Azure
  python ingestion/copernicus/download_viirs.py --upload-azure

  # Ver inventario local
  python ingestion/copernicus/download_viirs.py --list

Autor: TFM — AI Dashboard Core
"""

import os
import sys
import math
import time
import logging
import argparse
import io
import calendar
from datetime import date, datetime, timezone
from typing import List, Tuple, Optional

import numpy as np
from dotenv import load_dotenv

# ─── Paths del proyecto ──────────────────────────────────────────────────────
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir    = os.path.abspath(os.path.join(current_dir, "..", ".."))

if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

load_dotenv(os.path.join(root_dir, ".env"), override=True)

# ─── Logging ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("VIIRSIngestion")

# ─── Configuración ────────────────────────────────────────────────────────────

# Bounding box Tenerife (WGS84 lon_min, lat_min, lon_max, lat_max)
TENERIFE_BBOX = {
    "west":  -16.92,
    "south":  27.97,
    "east":  -16.09,
    "north":  28.59,
}

START_YEAR = 2019
COVID_YEARS = {2020, 2021}

# GEE: colección VIIRS mensual
GEE_VIIRS_COLLECTION = "NOAA/VIIRS/DNB/MONTHLY_V1/VCMSLCFG"
GEE_VIIRS_BAND       = "avg_rad"          # Radianza media mensual (nW/cm²/sr)
GEE_DRIVE_FOLDER     = "TFM_Tenerife_VIIRS"
GEE_EXPORT_SCALE     = 500               # metros (~resolución nativa VIIRS)
GEE_EXPORT_CRS       = "EPSG:32628"

# NASA LAADS DAAC
NASA_LAADS_URL = "https://ladsweb.modaps.eosdis.nasa.gov/archive/allData/5000/VNP46A2"
# Tile de NASA que cubre Tenerife: h17v05 (verificado en NASA Worldview)
NASA_TILE      = "h17v05"
NASA_LAYER     = "Gap_Filled_DNB_BRDF-Corrected_NTL"  # Capa principal en VNP46A2

# Directorios locales
LOCAL_VIIRS_DIR = os.path.join(root_dir, "data", "bronce", "spatial", "satelite", "viirs")

# Azure
CONTAINER_NAME   = "bronce-raw"
AZURE_BLOB_PREFIX = "satelite/viirs"


# ─── Utilidades de fechas ─────────────────────────────────────────────────────

def get_last_complete_month(today: date = None) -> Tuple[int, int]:
    """
    Retorna (año, mes) del último mes completo disponible.
    Asume que los datos NASA VIIRS tienen ~2 meses de latencia.
    """
    if today is None:
        today = date.today()
    # Restar 2 meses por latencia de publicación NASA
    month = today.month - 2
    year  = today.year
    if month <= 0:
        month += 12
        year  -= 1
    return year, month


def build_month_list(start_year: int, end_year: int, end_month: int) -> List[Tuple[int, int]]:
    """Genera lista de (año, mes) desde start_year/01 hasta end_year/end_month."""
    months = []
    for year in range(start_year, end_year + 1):
        max_month = end_month if year == end_year else 12
        for month in range(1, max_month + 1):
            months.append((year, month))
    return months


# ─── Opción A: Exportar VIIRS via GEE ────────────────────────────────────────

class VIIRSGEEExporter:
    """Exporta composites mensuales VIIRS desde GEE a Google Drive."""

    def __init__(self, gee_project: str = None, dry_run: bool = False):
        self.dry_run     = dry_run
        self.gee_project = gee_project or os.getenv("GEE_PROJECT_ID", "")

    def _init_gee(self):
        import ee
        try:
            if self.gee_project:
                ee.Initialize(project=self.gee_project)
            else:
                ee.Initialize()
            logger.info("✅ GEE inicializado correctamente.")
        except Exception as exc:
            logger.error(f"❌ Error GEE: {exc}\n  Ejecuta: earthengine authenticate")
            raise

    def export_monthly_composites(self) -> List[str]:
        """Lanza exports mensuales VIIRS a Google Drive."""
        import ee

        self._init_gee()
        aoi = ee.Geometry.Rectangle([
            TENERIFE_BBOX["west"],  TENERIFE_BBOX["south"],
            TENERIFE_BBOX["east"],  TENERIFE_BBOX["north"],
        ])

        end_year, end_month = get_last_complete_month()
        months = build_month_list(START_YEAR, end_year, end_month)

        logger.info(
            f"\n{'='*65}\n"
            f"  VIIRS GEE EXPORT — Tenerife Luces Nocturnas\n"
            f"  Periodo: {START_YEAR}/01 → {end_year}/{end_month:02d}\n"
            f"  Total meses a exportar: {len(months)}\n"
            f"  Fuente GEE: {GEE_VIIRS_COLLECTION}\n"
            f"  Resolución: {GEE_EXPORT_SCALE}m | CRS: {GEE_EXPORT_CRS}\n"
            f"{'='*65}"
        )

        task_ids = []

        for year, month in months:
            last_day   = calendar.monthrange(year, month)[1]
            date_start = f"{year}-{month:02d}-01"
            date_end   = f"{year}-{month:02d}-{last_day}"
            desc       = f"tenerife_viirs_{year}_{month:02d}"
            covid_flag = " [COVID]" if year in COVID_YEARS else ""

            logger.info(f"\n  → {year}/{month:02d}{covid_flag}")

            if self.dry_run:
                logger.info(f"    [DRY RUN] Se omitiría: {desc}")
                continue

            try:
                # Composite mensual VIIRS (ya es mensual en GEE → tomar el primero disponible)
                collection = (
                    ee.ImageCollection(GEE_VIIRS_COLLECTION)
                    .filterBounds(aoi)
                    .filterDate(date_start, date_end)
                    .select([GEE_VIIRS_BAND])
                )

                n = collection.size().getInfo()
                if n == 0:
                    logger.warning(f"    ⚠️  Sin imágenes para {year}/{month:02d} en GEE.")
                    continue

                # Para VIIRS mensual: tomar la imagen del mes (ya es un composite)
                monthly_img = collection.first().clip(aoi)

                # Añadir metadatos como propiedades de la imagen
                monthly_img = monthly_img.set({
                    "year":          year,
                    "month":         month,
                    "date_start":    date_start,
                    "periodo_covid": 1 if year in COVID_YEARS else 0,
                    "incluir_en_modelo": 0 if year in COVID_YEARS else 1,
                    "source":        GEE_VIIRS_COLLECTION,
                    "band":          GEE_VIIRS_BAND,
                    "units":         "nW/cm²/sr",
                })

                task = ee.batch.Export.image.toDrive(
                    image=monthly_img,
                    description=desc,
                    folder=GEE_DRIVE_FOLDER,
                    fileNamePrefix=desc,
                    scale=GEE_EXPORT_SCALE,
                    region=aoi,
                    crs=GEE_EXPORT_CRS,
                    maxPixels=1e9,
                    fileFormat="GeoTIFF",
                )
                task.start()
                task_ids.append(task.id)
                logger.info(f"    ✅ Task lanzada: {task.id}")
                time.sleep(0.8)

            except Exception as exc:
                logger.error(f"    ❌ Error en {year}/{month:02d}: {exc}")
                continue

        logger.info(
            f"\n  {len(task_ids)} tasks lanzadas.\n"
            f"  Progreso: https://code.earthengine.google.com/tasks\n"
            f"  Destino Drive: {GEE_DRIVE_FOLDER}/\n"
        )
        return task_ids


# ─── Opción B: Descargar VIIRS de NASA LAADS DAAC ────────────────────────────

class VIIRSNASADownloader:
    """
    Descarga composites mensuales VNP46A2 directamente de NASA LAADS DAAC.
    Requiere token de autenticación Earthdata en EARTHDATA_TOKEN (.env).

    El producto VNP46A2 se organiza por año y día del año (DOY):
    https://ladsweb.modaps.eosdis.nasa.gov/archive/allData/5000/VNP46A2/YYYY/DOY/
    """

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.token   = os.getenv("EARTHDATA_TOKEN", "")
        if not self.token:
            logger.warning(
                "⚠️ EARTHDATA_TOKEN no configurado en .env\n"
                "   Regístrate en https://urs.earthdata.nasa.gov/ y genera un token Bearer."
            )
        os.makedirs(LOCAL_VIIRS_DIR, exist_ok=True)

    def _get_auth_headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"}

    def _month_to_doy_range(self, year: int, month: int) -> Tuple[int, int]:
        """Convierte año/mes a rango de DOY (Day of Year) para LAADS."""
        first_day = date(year, month, 1)
        last_day  = date(year, month, calendar.monthrange(year, month)[1])
        doy_start = first_day.timetuple().tm_yday
        doy_end   = last_day.timetuple().tm_yday
        return doy_start, doy_end

    def _find_hdf5_for_month(self, year: int, month: int) -> Optional[str]:
        """
        Busca el archivo HDF5 mensual VNP46A2 para el tile de Tenerife.
        Retorna la URL del primer archivo encontrado en el mes.
        """
        import requests

        doy_start, doy_end = self._month_to_doy_range(year, month)
        headers = self._get_auth_headers()

        # Iterar días del mes buscando el tile h17v05
        for doy in range(doy_start, doy_end + 1):
            url = f"{NASA_LAADS_URL}/{year}/{doy:03d}/"
            try:
                resp = requests.get(url, headers=headers, timeout=15)
                if resp.status_code != 200:
                    continue
                # Buscar archivo que contenga el tile de Tenerife
                for line in resp.text.splitlines():
                    if NASA_TILE in line and ".h5" in line:
                        # Extraer nombre de archivo del listing HTML
                        fname = line.split('"')[1] if '"' in line else None
                        if fname and fname.endswith(".h5"):
                            return f"{url}{fname}"
            except requests.RequestException:
                continue
        return None

    def _extract_tenerife_from_hdf5(self, h5_path: str, out_tif: str) -> bool:
        """
        Extrae la capa de luces nocturnas del HDF5 y la recorta a Tenerife.
        Guarda como GeoTIFF en out_tif.
        """
        try:
            import h5py
            import rasterio
            from rasterio.transform import from_bounds
            from rasterio.crs import CRS

            with h5py.File(h5_path, "r") as f:
                # Navegar por la estructura HDF5 de VNP46A2
                grp_key  = "HDFEOS/GRIDS/VNP_Grid_DNB/Data Fields"
                if grp_key not in f:
                    logger.warning(f"  Estructura HDF5 inesperada en: {h5_path}")
                    return False

                data = f[f"{grp_key}/{NASA_LAYER}"][:]
                attrs = dict(f[f"{grp_key}/{NASA_LAYER}"].attrs)

            # Aplicar factor de escala si existe
            scale  = float(attrs.get("scale_factor", 1.0))
            offset = float(attrs.get("add_offset", 0.0))
            fill   = float(attrs.get("_FillValue", 65535))

            data = data.astype(np.float32)
            data[data == fill] = np.nan
            data = data * scale + offset

            # El tile h17v05 cubre aproximadamente: lon -20 a -10, lat 20 a 30
            # Subsetting aproximado para Tenerife (ajustar si es necesario)
            # La resolución del tile es ~500m → ~2400x2400 píxeles
            with rasterio.open(
                out_tif, "w",
                driver="GTiff",
                height=data.shape[0],
                width=data.shape[1],
                count=1,
                dtype="float32",
                crs=CRS.from_epsg(4326),
                transform=from_bounds(-20, 20, -10, 30, data.shape[1], data.shape[0]),
                compress="deflate",
                nodata=np.nan,
            ) as dst:
                dst.write(data, 1)
                dst.update_tags(
                    source="VNP46A2",
                    tile=NASA_TILE,
                    layer=NASA_LAYER,
                )

            logger.info(f"    ✅ GeoTIFF creado: {out_tif}")
            return True

        except ImportError as e:
            logger.error(f"    ❌ Dependencia faltante: {e}. Instala: pip install h5py rasterio")
            return False
        except Exception as exc:
            logger.error(f"    ❌ Error extrayendo HDF5: {exc}")
            return False

    def download_all(self) -> int:
        """Descarga todos los composites VNP46A2 del periodo TFM."""
        import requests

        end_year, end_month = get_last_complete_month()
        months = build_month_list(START_YEAR, end_year, end_month)

        logger.info(
            f"\n{'='*65}\n"
            f"  VIIRS NASA LAADS DOWNLOAD — Tenerife\n"
            f"  Producto: VNP46A2 | Tile: {NASA_TILE}\n"
            f"  Periodo: {START_YEAR}/01 → {end_year}/{end_month:02d}\n"
            f"  Total meses: {len(months)}\n"
            f"{'='*65}"
        )

        ok_count = 0
        for year, month in months:
            covid_flag = " [COVID]" if year in COVID_YEARS else ""
            out_fname  = f"tenerife_viirs_{year}_{month:02d}.tif"
            out_path   = os.path.join(LOCAL_VIIRS_DIR, out_fname)
            h5_tmp     = out_path.replace(".tif", "_raw.h5")

            logger.info(f"\n  → {year}/{month:02d}{covid_flag}")

            if os.path.exists(out_path):
                logger.info(f"    ✅ Ya existe: {out_fname}")
                ok_count += 1
                continue

            if self.dry_run:
                logger.info(f"    [DRY RUN] Se omitiría la descarga de {out_fname}")
                continue

            # Buscar URL del HDF5 en LAADS
            url = self._find_hdf5_for_month(year, month)
            if not url:
                logger.warning(f"    ⚠️ No se encontró HDF5 para {year}/{month:02d} en LAADS.")
                continue

            # Descargar HDF5
            try:
                logger.info(f"    📥 Descargando: {url.split('/')[-1]}")
                resp = requests.get(url, headers=self._get_auth_headers(), stream=True, timeout=120)
                resp.raise_for_status()
                with open(h5_tmp, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        f.write(chunk)
            except Exception as exc:
                logger.error(f"    ❌ Error descargando: {exc}")
                continue

            # Extraer y convertir a GeoTIFF
            success = self._extract_tenerife_from_hdf5(h5_tmp, out_path)
            if success:
                os.remove(h5_tmp)   # Borrar HDF5 crudo tras convertir
                ok_count += 1
            time.sleep(1.0)

        logger.info(f"\n  ✅ {ok_count}/{len(months)} meses VIIRS descargados en: {LOCAL_VIIRS_DIR}")
        return ok_count


# ─── Upload a Azure Blob ──────────────────────────────────────────────────────

class VIIRSAzureUploader:
    """Sube los GeoTIFFs VIIRS locales a Azure Blob Storage."""

    def __init__(self):
        self.blob_client = None
        conn_str = os.getenv("AZURE_STORAGE_CONNECTION_STRING", "").strip().strip('"').strip("'")
        if conn_str:
            try:
                from azure.storage.blob import BlobServiceClient
                if "AccountName=" not in conn_str and "DefaultEndpointsProtocol=" not in conn_str:
                    conn_str = (
                        f"DefaultEndpointsProtocol=https;"
                        f"AccountName=datalaketfmtenerife;"
                        f"AccountKey={conn_str};"
                        f"EndpointSuffix=core.windows.net"
                    )
                self.blob_client = BlobServiceClient.from_connection_string(conn_str)
                logger.info("✅ Conectado a Azure Blob Storage.")
            except Exception as exc:
                logger.warning(f"⚠️ No se pudo conectar a Azure: {exc}")
        else:
            logger.warning("⚠️ AZURE_STORAGE_CONNECTION_STRING no configurada.")

    def upload_all(self, local_dir: str = LOCAL_VIIRS_DIR):
        """Sube todos los GeoTIFFs VIIRS a Azure Blob."""
        if not self.blob_client:
            logger.error("❌ Azure Blob no disponible.")
            return

        geotiffs = sorted(f for f in os.listdir(local_dir) if f.endswith(".tif"))
        if not geotiffs:
            logger.warning(f"⚠️ No hay GeoTIFFs en: {local_dir}")
            return

        logger.info(f"\n{'='*55}")
        logger.info(f"  UPLOAD VIIRS A AZURE — {len(geotiffs)} GeoTIFFs")
        logger.info(f"{'='*55}")

        ok_count = 0
        for fname in geotiffs:
            # Parsear año y mes del nombre: tenerife_viirs_2023_07.tif
            try:
                parts = fname.replace(".tif", "").split("_")
                year  = parts[-2]
                month = parts[-1]
            except (IndexError, ValueError):
                year, month = "unknown", "unknown"

            blob_name  = f"{AZURE_BLOB_PREFIX}/year={year}/month={month}/{fname}"
            local_path = os.path.join(local_dir, fname)

            try:
                blob = self.blob_client.get_blob_client(container=CONTAINER_NAME, blob=blob_name)
                with open(local_path, "rb") as f:
                    blob.upload_blob(f, overwrite=True)
                size_mb = os.path.getsize(local_path) / 1024 / 1024
                covid_flag = " [COVID]" if year in {"2020", "2021"} else ""
                logger.info(f"  ☁️  {blob_name} ({size_mb:.1f} MB){covid_flag}")
                ok_count += 1
            except Exception as exc:
                logger.error(f"  ❌ Error subiendo {fname}: {exc}")

        logger.info(f"\n  ✅ {ok_count}/{len(geotiffs)} GeoTIFFs VIIRS subidos a Azure.")


# ─── Inventario ───────────────────────────────────────────────────────────────

def list_local_viirs(local_dir: str = LOCAL_VIIRS_DIR):
    """Lista los archivos VIIRS disponibles localmente."""
    os.makedirs(local_dir, exist_ok=True)
    geotiffs = sorted(f for f in os.listdir(local_dir) if f.endswith(".tif"))

    end_year, end_month = get_last_complete_month()
    expected = build_month_list(START_YEAR, end_year, end_month)

    logger.info(f"\n{'='*55}")
    logger.info(f"  INVENTARIO LOCAL — VIIRS Luces Nocturnas")
    logger.info(f"  Directorio: {local_dir}")
    logger.info(f"  Esperados: {len(expected)} | Disponibles: {len(geotiffs)}")
    logger.info(f"{'='*55}")

    downloaded = set()
    for fname in geotiffs:
        try:
            parts  = fname.replace(".tif", "").split("_")
            year   = int(parts[-2])
            month  = int(parts[-1])
            downloaded.add((year, month))
            covid  = " [COVID — excluir modelo]" if year in COVID_YEARS else ""
            logger.info(f"  ✅ {year}/{month:02d}{covid} — {fname}")
        except (IndexError, ValueError):
            logger.info(f"  ❓ {fname}")

    missing = [(y, m) for y, m in expected if (y, m) not in downloaded]
    if missing:
        logger.warning(f"\n  ⚠️  Meses faltantes ({len(missing)}):")
        for y, m in missing:
            covid = " [COVID]" if y in COVID_YEARS else ""
            logger.warning(f"    - {y}/{m:02d}{covid}")


# ─── CLI ─────────────────────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description="Pipeline de descarga VIIRS Luces Nocturnas — Tenerife TFM.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  # Exportar via GEE (recomendado — más sencillo)
  python download_viirs.py --source gee --export

  # Descargar directamente de NASA LAADS
  python download_viirs.py --source nasa --download

  # Subir GeoTIFFs locales a Azure
  python download_viirs.py --upload-azure

  # Ver inventario local
  python download_viirs.py --list

  # Dry run para verificar qué se haría
  python download_viirs.py --source gee --export --dry-run
        """,
    )
    parser.add_argument("--source",       choices=["gee", "nasa"], default="gee",
                        help="Fuente de descarga: GEE (recomendado) o NASA LAADS DAAC")
    parser.add_argument("--export",       action="store_true", help="Exportar a Google Drive (--source gee)")
    parser.add_argument("--download",     action="store_true", help="Descargar de NASA LAADS (--source nasa)")
    parser.add_argument("--upload-azure", action="store_true", help="Subir GeoTIFFs locales a Azure Blob")
    parser.add_argument("--list",         action="store_true", help="Listar archivos disponibles localmente")
    parser.add_argument("--gee-project",  type=str, default=None, help="ID del proyecto GEE")
    parser.add_argument("--dry-run",      action="store_true", help="Simular sin ejecutar")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    end_year, end_month = get_last_complete_month()
    months = build_month_list(START_YEAR, end_year, end_month)
    logger.info(
        f"\n  Tenerife VIIRS Luces Nocturnas Pipeline\n"
        f"  Periodo: {START_YEAR}/01 → {end_year}/{end_month:02d} ({len(months)} meses)\n"
        f"  COVID years: 2020-2021 (etiquetar, NO usar en regresión)\n"
        f"  Fuente preferida: GEE ({GEE_VIIRS_COLLECTION})\n"
    )

    if not any([args.export, args.download, args.upload_azure, args.list]):
        args.list = True

    if args.list:
        list_local_viirs()

    if args.export and args.source == "gee":
        exporter = VIIRSGEEExporter(gee_project=args.gee_project, dry_run=args.dry_run)
        exporter.export_monthly_composites()

    if args.download and args.source == "nasa":
        downloader = VIIRSNASADownloader(dry_run=args.dry_run)
        downloader.download_all()

    if args.upload_azure:
        uploader = VIIRSAzureUploader()
        uploader.upload_all()
