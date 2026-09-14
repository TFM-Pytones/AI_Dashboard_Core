"""
sentinel2_upload_blob.py
-------------------------
Pipeline de Extracción Satelital Sentinel-2 (Copernicus) para la Capa Bronce.
Issue #10 — Extracción Satelital (Copernicus / Sentinel).

Arquitectura Medallón - Capa Bronce (Raw):
- Genera composites trimestrales de mediana NDVI+NDBI libres de nubes y calima.
- Aplica triple filtrado: nubes SCL + calima AOT + calima banda azul B02.
- Calcula NDVI y NDBI directamente en GEE antes de exportar (ahorra espacio).
- Exporta GeoTIFFs a Google Drive → descargar manualmente a data/bronce/spatial/satelite/sentinel2/
- Opcionalmente sube los GeoTIFFs a Azure Blob Storage (bronce-raw/satelite/sentinel2/).

Periodo: 2019-01-01 → último trimestre completo disponible (auto-calculado).
Resolución: 20m (equilibrio calidad/tamaño para el extent de Tenerife).
CRS: EPSG:32628 (WGS 84 / UTM zone 28N) — sistema oficial de Canarias.

Requisitos previos:
  1. Cuenta en Google Earth Engine: https://earthengine.google.com/
  2. Proyecto GEE creado y aprobado (puede tardar 24-48h).
  3. Autenticación: ejecutar `earthengine authenticate` en terminal UNA VEZ.
  4. pip install earthengine-api azure-storage-blob python-dotenv

Uso:
  # Paso 1: autenticar (solo la primera vez)
  earthengine authenticate

  # Paso 2: exportar composites a Google Drive
  python ingestion/satelite/sentinel2_upload_blob.py --export

  # Paso 3 (opcional): verificar estado de tasks en GEE
  python ingestion/satelite/sentinel2_upload_blob.py --status

  # Paso 4 (tras descargar de Drive): subir GeoTIFFs locales a Azure
  python ingestion/satelite/sentinel2_upload_blob.py --upload-azure

Autor: TFM — AI Dashboard Core
"""

import os
import sys
import math
import time
import logging
import argparse
import io
from datetime import date, datetime, timezone
from typing import List, Tuple, Optional

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
logger = logging.getLogger("Sentinel2GEEIngestion")

# ─── Configuración general ───────────────────────────────────────────────────

# Bounding box de Tenerife (WGS84 EPSG:4326)
# Márgenes ligeramente ampliados para capturar la costa completa
TENERIFE_BBOX = [-16.95, 27.97, -16.09, 28.59]

# GEE: colección Sentinel-2 Surface Reflectance (armonizada entre procesadores)
GEE_COLLECTION = "COPERNICUS/S2_SR_HARMONIZED"

# Periodo de inicio (Sentinel-2 disponible desde jun 2015; 2019 = línea base TFM en Bronze)
START_YEAR = 2019


# Directorio local de destino para los GeoTIFFs descargados de Google Drive
LOCAL_SENTINEL_DIR = os.path.join(root_dir, "data", "bronce", "spatial", "satelite", "sentinel2")

# Azure Blob Storage
CONTAINER_NAME   = "bronce-raw"
AZURE_BLOB_PREFIX = "satelite/sentinel2"

# GEE Export settings
GEE_DRIVE_FOLDER = "TFM_Tenerife_Sentinel2"
EXPORT_SCALE     = 20      # metros (resolución de exportación; 10m = Sentinel nativo, 20m ahorra espacio)
EXPORT_CRS       = "EPSG:32628"
MAX_PIXELS       = 1e10

# Umbrales de filtrado de calima (empíricos para Canarias/Tenerife)
AOT_THRESHOLD_DN = 300     # AOT < 0.3 → atmósfera sin calima significativa
B02_THRESHOLD_DN = 1800    # Reflectancia azul < 0.18 → sin aerosol excesivo

# Percentaje de nubosidad máxima para pre-filtro de escenas (amplio; la máscara SCL hace el trabajo fino)
CLOUD_PREFILTER_PCT = 90


# ─── Cálculo automático del último trimestre cerrado ─────────────────────────

def get_last_complete_quarter(today: date = None) -> Tuple[int, int]:
    """
    Retorna (año, trimestre) del último trimestre completo disponible.
    Ejemplo: si hoy es 2026-07-30, el último trimestre cerrado es 2026 Q2 (abr-jun).
    """
    if today is None:
        today = date.today()
    current_q = math.ceil(today.month / 3)
    last_q    = current_q - 1
    if last_q == 0:
        return today.year - 1, 4
    return today.year, last_q


def build_quarter_list(start_year: int, end_year: int, end_quarter: int) -> List[Tuple[int, int]]:
    """Genera lista de (año, trimestre) desde start_year Q1 hasta end_year Q{end_quarter}."""
    combos = []
    for year in range(start_year, end_year + 1):
        max_q = end_quarter if year == end_year else 4
        for q in range(1, max_q + 1):
            combos.append((year, q))
    return combos


def quarter_dates(year: int, quarter: int) -> Tuple[str, str]:
    """Devuelve (fecha_inicio, fecha_fin) de un trimestre en formato 'YYYY-MM-DD'."""
    month_start = (quarter - 1) * 3 + 1
    month_end   = month_start + 2
    # Último día del mes de fin de trimestre
    if month_end == 3:
        day_end = 31
    elif month_end == 6:
        day_end = 30
    elif month_end == 9:
        day_end = 30
    else:  # 12
        day_end = 31
    return (
        f"{year}-{month_start:02d}-01",
        f"{year}-{month_end:02d}-{day_end}",
    )


# ─── Funciones GEE ───────────────────────────────────────────────────────────

def mask_clouds_scl(image):
    """
    Enmascara nubes y sombras usando la banda SCL (Scene Classification Layer).
    Valores SCL excluidos:
      1 = Saturado/Defectuoso
      3 = Sombra de nube
      8 = Nubes media probabilidad
      9 = Nubes alta probabilidad
      10 = Cirrus
    """
    import ee
    scl = image.select("SCL")
    valid = (scl.neq(1)
               .And(scl.neq(3))
               .And(scl.neq(8))
               .And(scl.neq(9))
               .And(scl.neq(10)))
    return image.updateMask(valid)


def mask_calima_aot(image):
    """
    Filtra calima sahariana usando la banda AOT (Aerosol Optical Thickness).
    AOT > 0.3 indica aerosol significativo (calima moderada-alta).
    La banda AOT en Sentinel-2 L2A se almacena como DN: dividir / 1000 = valor físico.
    """
    import ee
    aot = image.select("AOT")
    return image.updateMask(aot.lt(AOT_THRESHOLD_DN))


def mask_calima_blue(image):
    """
    Refuerzo de detección de calima usando la banda azul B02 (490 nm).
    El polvo sahariano eleva la reflectancia azul en superficies oscuras.
    DN L2A: dividir / 10000 = reflectancia de superficie.
    """
    import ee
    blue = image.select("B2")
    return image.updateMask(blue.lt(B02_THRESHOLD_DN))


def mask_all_artifacts(image):
    """
    Máscara combinada: nubes (SCL) + calima AOT + calima B02.
    Diseñada para Tenerife donde coexisten panza de burro y calima sahariana.
    """
    return mask_calima_blue(mask_calima_aot(mask_clouds_scl(image)))


def get_quarterly_composite(year: int, quarter: int, aoi):
    """
    Construye un composite de mediana NDVI+NDBI+B02 libre de nubes y calima
    para un trimestre dado sobre el AOI de Tenerife.

    Retorna una ee.Image con las bandas: ['NDVI', 'NDBI', 'B02_blue']
    y propiedades de metadatos.
    """
    import ee

    date_start, date_end = quarter_dates(year, quarter)

    # Colección filtrada por AOI, fechas y pre-filtro de nubosidad
    collection = (
        ee.ImageCollection(GEE_COLLECTION)
        .filterBounds(aoi)
        .filterDate(date_start, date_end)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", CLOUD_PREFILTER_PCT))
        .map(mask_all_artifacts)
    )

    # Composite de mediana (robusto frente a valores extremos residuales)
    composite = (
        collection
        .select(["B4", "B8", "B11", "B2"])
        .median()
        .clip(aoi)
    )

    # Calcular índices directamente en GEE antes de exportar
    ndvi = composite.normalizedDifference(["B8", "B4"]).rename("NDVI")
    ndbi = composite.normalizedDifference(["B11", "B8"]).rename("NDBI")
    blue = composite.select("B2").rename("B02_blue")   # Conservar para QC visual

    n_images = collection.size()

    return (
        ee.Image.cat([ndvi, ndbi, blue]).toFloat()
        .set({
            "year":               year,
            "quarter":            quarter,
            "date_start":         date_start,
            "date_end":           date_end,
            "n_source_images":    n_images,
            "aot_threshold":      AOT_THRESHOLD_DN / 1000,
            "b02_threshold":      B02_THRESHOLD_DN / 10000,
            "cloud_prefilter_pct": CLOUD_PREFILTER_PCT,
            "export_scale_m":     EXPORT_SCALE,
            "export_crs":         EXPORT_CRS,
            "generated_at_utc":   datetime.now(timezone.utc).isoformat(),
            "source":             "COPERNICUS/S2_SR_HARMONIZED via GEE",
        })
    )


# ─── Pipeline principal ───────────────────────────────────────────────────────

class Sentinel2GEEPipeline:
    """
    Pipeline GEE para exportar composites trimestrales Sentinel-2 de Tenerife.

    Flujo:
      1. Calcula el último trimestre completo disponible.
      2. Para cada (año, trimestre) desde 2019: genera composite mediana.
      3. Lanza export a Google Drive (procesamiento asíncrono en GEE).
      4. (Opcional) Sube GeoTIFFs ya descargados de Drive a Azure Blob Storage.
    """

    def __init__(self, gee_project: str = None, dry_run: bool = False):
        self.dry_run    = dry_run
        self.gee_project = gee_project or os.getenv("GEE_PROJECT_ID", "")
        os.makedirs(LOCAL_SENTINEL_DIR, exist_ok=True)

        # Inicializar Azure Blob (opcional — puede fallar sin romper el flujo GEE)
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
                logger.info("Conectado a Azure Blob Storage.")
            except Exception as exc:
                logger.warning(f"No se pudo conectar a Azure Blob: {exc}")
        else:
            logger.warning("AZURE_STORAGE_CONNECTION_STRING no configurada. Solo export a Drive.")

    # ── GEE init ──────────────────────────────────────────────────────────────

    def _init_gee(self):
        """Inicializa la API de Google Earth Engine."""
        import ee
        try:
            if self.gee_project:
                ee.Initialize(project=self.gee_project)
                logger.info(f"GEE inicializado con proyecto: {self.gee_project}")
            else:
                ee.Initialize()
                logger.info("GEE inicializado (proyecto por defecto).")
        except Exception as exc:
            logger.error(
                f"Error al inicializar GEE: {exc}\n"
                "   NOTA: Los tokens de Google Earth Engine caducan a los pocos días por seguridad.\n"
                "   Si estabas autenticado y de repente falla, renueva el token ejecutando:\n"
                "   earthengine authenticate --force"
            )
            raise

    # ── Export a Google Drive ─────────────────────────────────────────────────

    def run_export(self, resume_from: Tuple[int, int] = None) -> List[str]:
        """
        Lanza los exports de todos los composites trimestrales a Google Drive.

        Args:
            resume_from: (año, trimestre) desde donde retomar si se interrumpió.

        Returns:
            Lista de task IDs lanzadas.
        """
        import ee

        self._init_gee()
        aoi = ee.Geometry.Rectangle(TENERIFE_BBOX)

        end_year, end_quarter = get_last_complete_quarter()
        combos = build_quarter_list(START_YEAR, end_year, end_quarter)

        if resume_from:
            resume_idx = next(
                (i for i, c in enumerate(combos) if c >= resume_from), 0
            )
            combos = combos[resume_idx:]
            logger.info(f"Retomando desde {resume_from[0]} Q{resume_from[1]}")

        logger.info(
            f"\n{'='*65}\n"
            f"  SENTINEL-2 GEE EXPORT — Tenerife NDVI/NDBI\n"
            f"  Periodo: {START_YEAR} Q1 → {end_year} Q{end_quarter}\n"
            f"  Total composites a exportar: {len(combos)}\n"
            f"  Resolución: {EXPORT_SCALE}m | CRS: {EXPORT_CRS}\n"
            f"  Destino Drive: {GEE_DRIVE_FOLDER}/\n"
            f"{'='*65}"
        )

        task_ids = []

        for year, q in combos:
            date_start, date_end = quarter_dates(year, q)
            desc = f"tenerife_ndvi_ndbi_{year}_Q{q}"

            logger.info(f"\n  → {year} Q{q} ({date_start} … {date_end})")

            if self.dry_run:
                logger.info(f"    [DRY RUN] Se omitiría el export de: {desc}")
                continue

            try:
                composite = get_quarterly_composite(year, q, aoi)

                # Verificar si hay imágenes disponibles (sincrónico, puede ser lento)
                n = composite.get("n_source_images").getInfo()
                if n == 0:
                    logger.warning(
                        f"    Sin imágenes disponibles para {year} Q{q}. "
                        "Puede ser que el periodo no tenga datos en COPERNICUS/S2_SR_HARMONIZED."
                    )
                    continue
                logger.info(f"    {n} escenas en colección fuente")

                task = ee.batch.Export.image.toDrive(
                    image=composite,
                    description=desc,
                    folder=GEE_DRIVE_FOLDER,
                    fileNamePrefix=desc,
                    scale=EXPORT_SCALE,
                    region=aoi,
                    crs=EXPORT_CRS,
                    maxPixels=MAX_PIXELS,
                    fileFormat="GeoTIFF",
                )
                task.start()
                task_ids.append(task.id)
                logger.info(f"  Task lanzada: {task.id}")

                # Pausa corta para no saturar la API de GEE
                time.sleep(1.5)

            except Exception as exc:
                logger.error(f"  Error al lanzar {desc}: {exc}")
                continue

        logger.info(
            f"\n{'='*65}\n"
            f"  {len(task_ids)} tasks lanzadas en GEE.\n"
            f"  Revisa el progreso en: https://code.earthengine.google.com/tasks\n"
            f"  Cuando terminen, descarga los GeoTIFFs de Google Drive y\n"
            f"  colócalos en: {LOCAL_SENTINEL_DIR}/\n"
            f"{'='*65}"
        )

        return task_ids

    # ── Estado de tasks ───────────────────────────────────────────────────────

    def check_status(self):
        """Muestra el estado de todas las tasks GEE activas relacionadas con el TFM."""
        import ee

        self._init_gee()

        tasks = ee.data.getTaskList()
        tfm_tasks = [t for t in tasks if "tenerife_ndvi_ndbi" in t.get("description", "")]

        if not tfm_tasks:
            logger.info("No se encontraron tasks GEE del TFM en la lista activa.")
            return

        status_summary = {}
        for task in tfm_tasks:
            state = task.get("state", "UNKNOWN")
            status_summary[state] = status_summary.get(state, 0) + 1

        logger.info(f"\n{'='*55}")
        logger.info(f"  ESTADO DE TASKS GEE — TFM Tenerife Sentinel-2")
        logger.info(f"{'='*55}")
        for state, count in status_summary.items():
            icon = {"COMPLETED": "[OK]", "RUNNING": "[RUNNING]", "READY": "[READY]", "FAILED": "[FAILED]"}.get(state, "[?]")
            logger.info(f"  {icon} {state}: {count} tasks")

        failed = [t for t in tfm_tasks if t.get("state") == "FAILED"]
        if failed:
            logger.warning(f"\n  Tasks fallidas ({len(failed)}):")
            for t in failed:
                logger.warning(f"    - {t['description']}: {t.get('error_message', 'Sin mensaje')}")

    # ── Upload a Azure Blob ───────────────────────────────────────────────────

    def upload_to_azure(self, local_dir: str = LOCAL_SENTINEL_DIR):
        """
        Sube todos los GeoTIFFs descargados de Google Drive a Azure Blob Storage.
        Estructura en Blob: bronce-raw/satelite/sentinel2/year=XXXX/quarter=QN/filename.tif

        INSTRUCCIONES PREVIAS:
          1. Ir a Google Drive → carpeta 'TFM_Tenerife_Sentinel2'
          2. Descargar todos los GeoTIFFs
          3. Colocarlos en: data/bronce/spatial/satelite/sentinel2/
          4. Ejecutar: python ingestion/copernicus/download_sentinel2_gee.py --upload-azure
        """
        if not self.blob_client:
            logger.error("Azure Blob no configurado. Añade AZURE_STORAGE_CONNECTION_STRING al .env")
            return

        geotiffs = [f for f in os.listdir(local_dir) if f.endswith(".tif")]

        if not geotiffs:
            logger.warning(f"No se encontraron GeoTIFFs en: {local_dir}")
            logger.info(
                "  Descarga los archivos de Google Drive (carpeta TFM_Tenerife_Sentinel2)\n"
                f"  y colócalos en: {local_dir}"
            )
            return

        logger.info(f"\n{'='*55}")
        logger.info(f"  UPLOAD A AZURE BLOB — {len(geotiffs)} GeoTIFFs")
        logger.info(f"{'='*55}")

        ok_count = 0
        for fname in sorted(geotiffs):
            # Parsear año y trimestre del nombre: tenerife_ndvi_ndbi_2023_Q2.tif
            try:
                parts   = fname.replace(".tif", "").split("_")
                year    = parts[-2]   # e.g. "2023"
                quarter = parts[-1]   # e.g. "Q2"
            except (IndexError, ValueError):
                year, quarter = "unknown", "unknown"

            blob_name  = f"{AZURE_BLOB_PREFIX}/year={year}/quarter={quarter}/{fname}"
            local_path = os.path.join(local_dir, fname)

            try:
                blob = self.blob_client.get_blob_client(container=CONTAINER_NAME, blob=blob_name)
                with open(local_path, "rb") as f:
                    blob.upload_blob(f, overwrite=True)
                size_mb = os.path.getsize(local_path) / 1024 / 1024
                logger.info(f"    Subido: {blob_name} ({size_mb:.1f} MB)")
                ok_count += 1
            except Exception as exc:
                logger.error(f"Error subiendo {fname}: {exc}")

        logger.info(f"\n{ok_count}/{len(geotiffs)} GeoTIFFs subidos a Azure Blob Storage.")

    # ── Inventario local ──────────────────────────────────────────────────────

    def list_local_composites(self, local_dir: str = LOCAL_SENTINEL_DIR):
        """Lista los composites GeoTIFF disponibles localmente."""
        if not os.path.exists(local_dir):
            logger.info(f"Directorio no encontrado: {local_dir}")
            return

        geotiffs = sorted(f for f in os.listdir(local_dir) if f.endswith(".tif"))

        end_year, end_quarter = get_last_complete_quarter()
        expected = build_quarter_list(START_YEAR, end_year, end_quarter)

        logger.info(f"\n{'='*55}")
        logger.info(f"  INVENTARIO LOCAL — Composites Sentinel-2")
        logger.info(f"  Directorio: {local_dir}")
        logger.info(f"  Esperados: {len(expected)} | Disponibles: {len(geotiffs)}")
        logger.info(f"{'='*55}")

        downloaded = set()
        for fname in geotiffs:
            try:
                parts = fname.replace(".tif", "").split("_")
                year  = int(parts[-2])
                qnum  = int(parts[-1].replace("Q", ""))
                downloaded.add((year, qnum))
                logger.info(f"{year} Q{qnum} — {fname}")
            except (IndexError, ValueError):
                logger.info(f"  ? {fname} (nombre inesperado)")

        missing = [(y, q) for y, q in expected if (y, q) not in downloaded]
        if missing:
            logger.warning(f"\n  Composites faltantes ({len(missing)}):")
            for y, q in missing:
                logger.warning(f"    - {y} Q{q}")
        else:
            logger.info("\n  Todos los composites esperados están disponibles localmente.")


# ─── CLI ─────────────────────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description="Pipeline GEE: Exportar composites Sentinel-2 NDVI/NDBI de Tenerife.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  # Exportar todos los composites a Google Drive
  python download_sentinel2_gee.py --export

  # Exportar solo desde 2023 Q1 (resumir descarga interrumpida)
  python download_sentinel2_gee.py --export --resume-year 2023 --resume-quarter 1

  # Verificar estado de tasks en GEE
  python download_sentinel2_gee.py --status

  # Subir GeoTIFFs locales a Azure Blob
  python download_sentinel2_gee.py --upload-azure

  # Ver inventario local
  python download_sentinel2_gee.py --list

  # Simular sin ejecutar nada (dry run)
  python download_sentinel2_gee.py --export --dry-run
        """,
    )
    parser.add_argument("--export",          action="store_true", help="Lanzar exports GEE a Google Drive")
    parser.add_argument("--status",          action="store_true", help="Verificar estado de tasks GEE")
    parser.add_argument("--upload-azure",    action="store_true", help="Subir GeoTIFFs locales a Azure Blob")
    parser.add_argument("--list",            action="store_true", help="Listar composites disponibles localmente")
    parser.add_argument("--gee-project",     type=str, default=None, help="ID del proyecto GEE (o usar GEE_PROJECT_ID en .env)")
    parser.add_argument("--resume-year",     type=int, default=None, help="Año desde donde retomar (con --export)")
    parser.add_argument("--resume-quarter",  type=int, default=None, choices=[1, 2, 3, 4], help="Trimestre desde donde retomar")
    parser.add_argument("--dry-run",         action="store_true", help="Simular sin ejecutar exports reales")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    end_year, end_quarter = get_last_complete_quarter()
    combos = build_quarter_list(START_YEAR, end_year, end_quarter)

    logger.info(
        f"\n  Tenerife Sentinel-2 GEE Pipeline\n"
        f"  Periodo: {START_YEAR} Q1 → {end_year} Q{end_quarter} ({len(combos)} composites)\n"
        f"  Calima: AOT < {AOT_THRESHOLD_DN/1000} | B02 < {B02_THRESHOLD_DN/10000}\n"
    )

    pipeline = Sentinel2GEEPipeline(
        gee_project=args.gee_project,
        dry_run=args.dry_run,
    )

    if not any([args.export, args.status, args.upload_azure, args.list]):
        # Sin argumentos → mostrar inventario como acción por defecto
        args.list = True

    if args.list:
        pipeline.list_local_composites()

    if args.export:
        resume = None
        if args.resume_year and args.resume_quarter:
            resume = (args.resume_year, args.resume_quarter)
        pipeline.run_export(resume_from=resume)

    if args.status:
        pipeline.check_status()

    if args.upload_azure:
        pipeline.upload_to_azure()
