"""
tabular_ingestion.py
--------------------
Pipeline de Ingesta a Capa Bronce para Microdatos Tabulares de Tenerife:

  1. Estadisticas Demograficas (INE - Padron Municipal)
     - Poblacion por municipio y sexo (tabla t=2892)
     - Indicadores demograficos por municipio (tabla t=31195)
     Fuente: INE (Instituto Nacional de Estadistica)
     URL: https://www.ine.es/jaxiT3/

  2. Oferta Alojativa (ISTAC - Encuesta de Alojamiento Turistico)
     - Establecimientos, plazas, habitaciones y tasas de ocupacion por municipio
     Fuente: ISTAC (Instituto Canario de Estadistica)
     URL: https://www.gobiernodecanarias.org/istac/

Los datos se filtran a municipios de la provincia de Santa Cruz de Tenerife
(codigo INE: 38xxx) y se guardan como Parquet en Azure Blob Storage
bajo bronce-raw/tabular/.

Uso:
    python ingestion/microdatos/tabular_ingestion.py

Autor: TFM - AI Dashboard Core
"""

import os
import sys
import logging
import io
from datetime import datetime, timezone
from typing import Optional

import requests
import pandas as pd
from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient

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
logger = logging.getLogger("TabularBronzeIngestion")

DEFAULT_OUTPUT_DIR = os.path.abspath(os.path.join(root_dir, "data", "bronce", "tabular"))

# ---------------------------------------------------------------------------
# Configuracion de fuentes INE
#
# La API JSON del INE permite descargar tablas completas sin navegador.
# Formato URL: https://servicios.ine.es/wstempus/js/ES/DATOS_TABLA/<id>
#
# Documentacion API INE: https://www.ine.es/dyngs/DataLab/es/manual.htm?cid=1259945948883
# ---------------------------------------------------------------------------

# INE tabla 2892: Cifras de poblacion - Municipios por sexo y provincia
# Filtramos luego por provincia 38 (Santa Cruz de Tenerife)
INE_POBLACION_URL = (
    "https://servicios.ine.es/wstempus/js/ES/DATOS_TABLA/2852"
    "?nult=10"
)
# Nota: usamos la tabla 2852 (Padron municipal por municipio/sexo)
# que incluye todos los municipios. La 2892 es similar pero multianual.

# Alternativa con descarga CSV directa (mas estable)
INE_POBLACION_CSV_URL = (
    "https://www.ine.es/jaxiT3/files/t/es/csv_bdsc/2852.csv"
)

# INE tabla 31195: Indicadores demograficos por municipio
INE_INDICADORES_CSV_URL = (
    "https://www.ine.es/jaxiT3/files/t/es/csv_bdsc/31195.csv"
)

# ---------------------------------------------------------------------------
# Configuracion de fuentes ISTAC
#
# ISTAC ofrece dos modos de acceso:
#   1. API REST de estadisticas: https://datos.canarias.es/api/estadisticas/
#   2. Descarga directa CSV: datasets de la EAT (Encuesta Alojamiento Turistico)
#
# Dataset EAT por municipios de Canarias:
# https://datos.canarias.es/api/estadisticas/statistical-resources/v1.0/
#   datasets/ISTAC/E16028A_000008/~latest/data?fields=...
# ---------------------------------------------------------------------------

ISTAC_EAT_API_URL = (
    "https://datos.canarias.es/api/estadisticas/statistical-resources/v1.0/"
    "datasets/ISTAC/E16028A_000008/~latest/data"
    "?fields=id,title&lang=es&_limit=1000"
)

# Descarga directa CSV del dataset EAT (mas estable que la API)
# Codigo del dataset: "Encuesta de Alojamiento en Hoteles"
ISTAC_EAT_CSV_DIRECT = (
    "https://datos.canarias.es/api/estadisticas/statistical-resources/v1.0/"
    "datasets/ISTAC/E16028A_000008/~latest/data"
    "?_format=csv&lang=es"
)

# Codigo INE de municipios de Tenerife (provincia 38)
TENERIFE_MUNICIPIOS_PREFIJO = "38"
TENERIFE_PROVINCIA_CODE = "38"


class TabularBronzeIngestionPipeline:
    """
    Pipeline de ingesta de microdatos tabulares (demograficos y alojativos) a Capa Bronce.
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
    # Azure Blob I/O (mismo patron que open_meteo_ingestion.py)
    # ------------------------------------------------------------------

    def _write_parquet_to_blob(self, df: pd.DataFrame, blob_name: str) -> bool:
        """Escribe un DataFrame en Parquet local y en Azure Blob."""
        if df.empty:
            logger.warning(f"DataFrame vacio para {blob_name}. Omitido.")
            return False

        local_path = os.path.join(self.output_dir, blob_name.replace("/", "_"))
        try:
            df.to_parquet(local_path, index=False, compression="snappy")
            logger.info(f"  Parquet local: {local_path} ({len(df):,} filas)")
        except Exception as e:
            logger.error(f"  Error guardando {local_path}: {e}")

        if not self.blob_service_client:
            return False
        try:
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name, blob=blob_name
            )
            buffer = io.BytesIO()
            df.to_parquet(buffer, index=False, compression="snappy")
            buffer.seek(0)
            blob_client.upload_blob(buffer, overwrite=True)
            logger.info(f"  Azure: {self.container_name}/{blob_name} ({len(df):,} filas)")
            return True
        except Exception as e:
            logger.error(f"  Error subiendo {blob_name}: {e}")
            return False

    # ------------------------------------------------------------------
    # Utilidad: Descarga CSV del INE
    # ------------------------------------------------------------------

    @staticmethod
    def _download_ine_csv(url: str) -> Optional[pd.DataFrame]:
        """
        Descarga un CSV del INE y lo devuelve como DataFrame.

        Los CSV del INE usan punto y coma como separador y codificacion latin-1.
        """
        try:
            headers = {"User-Agent": "TFM-TUI-Tenerife/1.0 (academic research)"}
            resp = requests.get(url, timeout=120, headers=headers)
            resp.raise_for_status()

            # Intentar con punto y coma primero (formato INE estandar)
            try:
                df = pd.read_csv(
                    io.StringIO(resp.content.decode("latin-1")),
                    sep=";",
                    thousands=".",
                    decimal=",",
                )
            except Exception:
                df = pd.read_csv(
                    io.StringIO(resp.content.decode("utf-8")),
                    sep=";",
                    thousands=".",
                    decimal=",",
                )

            logger.info(f"  CSV INE descargado: {len(df):,} filas, {len(df.columns)} columnas")
            return df
        except Exception as e:
            logger.warning(f"  Error descargando CSV INE de {url}: {e}")
            return None

    @staticmethod
    def _filter_tenerife_ine(df: pd.DataFrame) -> pd.DataFrame:
        """
        Filtra un DataFrame del INE a los municipios de Tenerife.

        Busca columnas con codigo de municipio (empiezan por '38').
        """
        # Columnas candidatas con codigo de municipio
        mun_cols = [
            c for c in df.columns
            if any(kw in c.lower() for kw in ("municipio", "mun", "codigo", "prov", "cod"))
        ]

        for col in mun_cols:
            try:
                mask = df[col].astype(str).str.strip().str.startswith("38")
                filtered = df[mask]
                if len(filtered) > 0 and len(filtered) < len(df):
                    logger.info(
                        f"  Filtrado por columna '{col}': "
                        f"{len(filtered)} municipios de Tenerife"
                    )
                    return filtered
            except Exception:
                continue

        # Buscar en todas las columnas de texto
        for col in df.select_dtypes(include=["object"]).columns:
            try:
                mask = df[col].astype(str).str.strip().str.match(r"^38\d{3}$")
                filtered = df[mask]
                if len(filtered) > 0 and len(filtered) < len(df):
                    logger.info(
                        f"  Filtrado por patron municipio en '{col}': "
                        f"{len(filtered)} filas"
                    )
                    return filtered
            except Exception:
                continue

        logger.warning(
            "  No se encontro columna de municipio para filtrar Tenerife. "
            "Devolviendo datos sin filtrar."
        )
        return df

    # ------------------------------------------------------------------
    # 1. Estadisticas Demograficas (INE)
    # ------------------------------------------------------------------

    def run_demografia_ingestion(self) -> dict:
        """
        Descarga estadisticas demograficas del INE para municipios de Tenerife.

        Tablas descargadas:
          - Poblacion por municipio y sexo (Padron Municipal)
          - Indicadores demograficos municipales (edad media, etc.)

        Returns:
            Dict {'poblacion': df, 'indicadores': df}
        """
        logger.info("\n" + "="*60)
        logger.info("INGESTA: Estadisticas Demograficas (INE) Tenerife")
        logger.info("="*60)

        now_utc = datetime.now(timezone.utc).isoformat()
        results = {}

        # --- Tabla 1: Poblacion por municipio ---
        logger.info("\n  [INE] Padron Municipal - Poblacion por municipio y sexo")
        df_pob = self._download_ine_csv(INE_POBLACION_CSV_URL)

        if df_pob is not None:
            df_pob_tenerife = self._filter_tenerife_ine(df_pob)
            df_pob_tenerife = df_pob_tenerife.copy()
            df_pob_tenerife["ingested_at_utc"] = now_utc
            df_pob_tenerife["source"] = "INE - Padron Municipal"
            df_pob_tenerife["tabla_ine"] = "2852"

            self._write_parquet_to_blob(
                df_pob_tenerife,
                "tabular/demografia/ine_padron_municipal_tenerife.parquet",
            )
            results["poblacion"] = df_pob_tenerife
            logger.info(f"  Poblacion: {len(df_pob_tenerife):,} registros")
        else:
            logger.warning(
                "  No se pudo descargar Padron Municipal. Descarga manual:\n"
                "  -> https://www.ine.es/jaxiT3/Tabla.htm?t=2852\n"
                "  -> Seleccionar: Provincia = Santa Cruz de Tenerife\n"
                "  -> Descargar CSV (separador punto y coma)\n"
                f"  -> Guardar en: {os.path.join(DEFAULT_OUTPUT_DIR, 'raw', 'ine_padron.csv')}"
            )

        # --- Tabla 2: Indicadores demograficos ---
        logger.info("\n  [INE] Indicadores Demograficos Municipales")
        df_ind = self._download_ine_csv(INE_INDICADORES_CSV_URL)

        if df_ind is not None:
            df_ind_tenerife = self._filter_tenerife_ine(df_ind)
            df_ind_tenerife = df_ind_tenerife.copy()
            df_ind_tenerife["ingested_at_utc"] = now_utc
            df_ind_tenerife["source"] = "INE - Indicadores Demograficos"
            df_ind_tenerife["tabla_ine"] = "31195"

            self._write_parquet_to_blob(
                df_ind_tenerife,
                "tabular/demografia/ine_indicadores_demograficos_tenerife.parquet",
            )
            results["indicadores"] = df_ind_tenerife
            logger.info(f"  Indicadores: {len(df_ind_tenerife):,} registros")
        else:
            logger.warning(
                "  No se pudo descargar Indicadores Demograficos. Descarga manual:\n"
                "  -> https://www.ine.es/jaxiT3/Tabla.htm?t=31195\n"
                "  -> Filtrar por provincia 38 (Santa Cruz de Tenerife)\n"
                "  -> Descargar en formato CSV"
            )

        # --- Fallback: ficheros manuales pre-descargados ---
        raw_dir = os.path.join(self.output_dir, "raw")
        os.makedirs(raw_dir, exist_ok=True)
        import glob
        manual_csvs = glob.glob(os.path.join(raw_dir, "ine_*.csv"))
        for csv_path in manual_csvs:
            name = os.path.splitext(os.path.basename(csv_path))[0]
            logger.info(f"  Procesando CSV manual: {csv_path}")
            try:
                df_manual = pd.read_csv(
                    csv_path, sep=";", encoding="latin-1",
                    thousands=".", decimal=","
                )
                df_manual["ingested_at_utc"] = now_utc
                df_manual["source"] = f"INE Manual - {name}"
                self._write_parquet_to_blob(
                    df_manual, f"tabular/demografia/{name}.parquet"
                )
                results[name] = df_manual
            except Exception as e:
                logger.error(f"  Error procesando {csv_path}: {e}")

        return results

    # ------------------------------------------------------------------
    # 2. Oferta Alojativa (ISTAC)
    # ------------------------------------------------------------------

    def run_oferta_alojativa_ingestion(self) -> Optional[pd.DataFrame]:
        """
        Descarga estadisticas de oferta alojativa del ISTAC para Tenerife.

        Dataset: Encuesta de Alojamiento Turistico (EAT) por municipios
        Variables: establecimientos abiertos, plazas, habitaciones, ocupacion

        Returns:
            DataFrame con datos alojativos de Tenerife (o None si hay error)
        """
        logger.info("\n" + "="*60)
        logger.info("INGESTA: Oferta Alojativa (ISTAC) Tenerife")
        logger.info("="*60)

        now_utc = datetime.now(timezone.utc).isoformat()

        # --- Opcion 1: API CSV de ISTAC ---
        logger.info("  Intentando API CSV de ISTAC (EAT por municipios)...")
        df = None

        try:
            headers = {"User-Agent": "TFM-TUI-Tenerife/1.0 (academic research)"}
            resp = requests.get(
                ISTAC_EAT_CSV_DIRECT, timeout=120, headers=headers
            )
            resp.raise_for_status()

            content_type = resp.headers.get("Content-Type", "")
            if "csv" in content_type or "text" in content_type:
                df = pd.read_csv(
                    io.StringIO(resp.content.decode("utf-8")),
                    sep=";",
                    thousands=".",
                    decimal=",",
                )
                logger.info(f"  API CSV ISTAC exitosa: {len(df):,} filas")
            else:
                logger.warning(f"  API ISTAC devolvio Content-Type: {content_type}")
        except Exception as e:
            logger.warning(f"  API ISTAC fallida: {e}")

        # --- Opcion 2: Ficheros CSV manuales ---
        if df is None:
            raw_dir = os.path.join(self.output_dir, "raw")
            os.makedirs(raw_dir, exist_ok=True)
            import glob
            manual_files = (
                glob.glob(os.path.join(raw_dir, "istac_*.csv"))
                + glob.glob(os.path.join(raw_dir, "eat_*.csv"))
            )
            if manual_files:
                logger.info(f"  CSV manual encontrado: {manual_files[0]}")
                try:
                    df = pd.read_csv(
                        manual_files[0], sep=";", encoding="latin-1",
                        thousands=".", decimal=","
                    )
                    logger.info(f"  CSV manual cargado: {len(df):,} filas")
                except Exception as e:
                    logger.error(f"  Error cargando CSV manual: {e}")

        if df is None:
            logger.error(
                "  No se pudo obtener datos del ISTAC. Descarga manual:\n"
                "  -> https://www.gobiernodecanarias.org/istac/\n"
                "  -> Buscar: 'Establecimientos abiertos plazas hoteles municipios'\n"
                "  -> O directamente: https://datos.canarias.es/\n"
                "     Dataset: E16028A_000008 (EAT Hoteles por municipios)\n"
                "  -> Descargar en formato CSV (separador punto y coma)\n"
                f"  -> Guardar en: {os.path.join(DEFAULT_OUTPUT_DIR, 'raw', 'istac_eat.csv')}"
            )
            return None

        # Filtrar Tenerife
        df_tenerife = self._filter_tenerife_istac(df)
        df_tenerife = df_tenerife.copy()
        df_tenerife["ingested_at_utc"] = now_utc
        df_tenerife["source"] = "ISTAC - EAT Hoteles por Municipios"
        df_tenerife["dataset_id"] = "E16028A_000008"

        self._write_parquet_to_blob(
            df_tenerife,
            "tabular/alojamiento/istac_eat_hoteles_tenerife.parquet",
        )

        logger.info(f"  Oferta Alojativa Tenerife: {len(df_tenerife):,} registros")
        return df_tenerife

    @staticmethod
    def _filter_tenerife_istac(df: pd.DataFrame) -> pd.DataFrame:
        """
        Filtra datos del ISTAC a la isla de Tenerife.

        El ISTAC usa 'Tenerife' como nombre de isla o codigos propios.
        """
        # Estrategia 1: columna de isla/municipio con texto "Tenerife"
        for col in df.select_dtypes(include=["object"]).columns:
            if any(kw in col.lower() for kw in ("isla", "municipio", "territorio", "zona")):
                mask = df[col].astype(str).str.contains("Tenerife", case=False, na=False)
                filtered = df[mask]
                if len(filtered) > 0 and len(filtered) < len(df):
                    logger.info(
                        f"  Filtrado por '{col}' = 'Tenerife': {len(filtered)} filas"
                    )
                    return filtered

        # Estrategia 2: buscar "Tenerife" en cualquier columna de texto
        for col in df.select_dtypes(include=["object"]).columns:
            mask = df[col].astype(str).str.contains("Tenerife", case=False, na=False)
            if mask.sum() > 0 and mask.sum() < len(df):
                filtered = df[mask]
                logger.info(
                    f"  Filtrado por Tenerife en '{col}': {len(filtered)} filas"
                )
                return filtered

        logger.warning(
            "  No se encontro columna 'Tenerife' en datos ISTAC. "
            "Devolviendo datos sin filtrar."
        )
        return df

    # ------------------------------------------------------------------
    # Pipeline completo
    # ------------------------------------------------------------------

    def run_full_tabular_ingestion(self) -> dict:
        """Ejecuta la ingesta completa de microdatos tabulares."""
        logger.info("Iniciando Pipeline Microdatos Tabulares -> Capa Bronce...")
        results = {}

        demo = self.run_demografia_ingestion()
        if demo:
            results["demografia"] = demo

        aloj = self.run_oferta_alojativa_ingestion()
        if aloj is not None:
            results["oferta_alojativa"] = aloj

        logger.info(f"\nPipeline Tabular completado: {list(results.keys())} ingestados.")
        return results


if __name__ == "__main__":
    pipeline = TabularBronzeIngestionPipeline()
    pipeline.run_full_tabular_ingestion()
