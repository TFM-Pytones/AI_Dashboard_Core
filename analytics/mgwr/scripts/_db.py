"""
_db.py
------
Modulo compartido del pipeline MGWR/PTNA (Bloque 5). Dos responsabilidades:

1. Conexion reutilizable a la base Postgres de Azure (mismas variables de
   entorno que el resto del repo: AZURE_DB_HOST/USER/PASSWORD/NAME, puerto
   5432 fijo). Usado por 01_build_dataset.py.
2. Setup de logging comun (archivo detallado en analytics/mgwr/logs/ +
   consola solo para warnings/errores) para que los 5 scripts no repitan
   la misma configuracion.

03_validate_mgwr_synthetic.py NO debe importar este modulo (no debe tocar
Postgres bajo ninguna circunstancia) -- define su propio logging local.
"""

import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

# Carpetas del pipeline, relativas a este archivo (analytics/mgwr/scripts/_db.py)
# para que los scripts sean ejecutables desde cualquier directorio de trabajo.
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_INTERIM_DIR = BASE_DIR / "data" / "interim"
DATA_PROCESSED_DIR = BASE_DIR / "data" / "processed"
LOGS_DIR = BASE_DIR / "logs"

REQUIRED_ENV_VARS = ["AZURE_DB_HOST", "AZURE_DB_USER", "AZURE_DB_PASSWORD", "AZURE_DB_NAME"]
DB_PORT = 5432

# Las 14 variables X del dataset v3 (ver docs/contexto_maestro_proyecto_ptna.md,
# seccion 3, y plan_final_mejorado.md Bloque 5 Subtarea 5.1). El v2 tenia 16 --
# ver Hallazgo 10: tiempo_teide_min y tiempo_polo_turistico_min se sacaron del
# modelo por multicolinealidad severa con tiempo_aeropuerto_min (VIF 199.4 y
# 345.8 respectivamente, r=0.99 entre las 3) -- las 3 miden esencialmente lo
# mismo ("que tan lejos del interior/costa esta este hexagono") en una isla de
# este tamanio. Se conserva solo tiempo_aeropuerto_min (columna precalculada,
# continuidad con el v1, interpretable para TUI). Las otras dos siguen
# disponibles en el parquet de 01_build_dataset.py para reporting/exploracion,
# pero no entran a esta lista ni al array X que se le pasa a Sel_BW/MGWR.
# Usada por 04_run_model.py (imputacion, escalado, ajuste del modelo) y, salvo
# sentimiento_medio, por 02_filter_nan.py (ver PTNA_NAN_FILTER_COLUMNS abajo).
PTNA_QUALITY_COLUMNS = [
    "ndvi_medio",
    "altitud_media_m",
    "slope_mean",
    "n_restaurantes",
    "n_naturaleza",
    "n_cultura",
    "dist_hospital_km",
    "pct_area_enp",
    "temp_media_anual",
    "lluvia_mm_anual",
    "dist_parada_cercana_m",
    "tiempo_aeropuerto_min",
    "dist_costa_km",
    "sentimiento_medio",
]

# Variables usadas para el filtro de >50% NaN de 02_filter_nan.py -- igual a
# PTNA_QUALITY_COLUMNS pero SIN sentimiento_medio. Motivo (ver Hallazgo 5):
# gold.gold_h3_sentimiento solo cubre 410/2579 hexagonos (15.9%) -- el 84.1%
# restante no tiene ninguna reseña geolocalizada ahi (zonas sin alojamiento
# turistico cercano), no porque el hexagono sea de mala calidad en el resto de
# sus variables. Contar sentimiento_medio en el filtro de calidad excluiria de
# forma incorrecta la mayoria del dataset. sentimiento_medio SI se imputa con
# la mediana en 04_run_model.py como las demas, solo queda afuera de esta
# decision de exclusion.
PTNA_NAN_FILTER_COLUMNS = [c for c in PTNA_QUALITY_COLUMNS if c != "sentimiento_medio"]

# Subconjunto de PTNA_QUALITY_COLUMNS para el chequeo de VIF (Variance
# Inflation Factor) en 04_run_model.py -- no las 14 variables completas (esas
# ya se chequean todas con el VIF completo del Hallazgo 10), solo estas 3 por
# ser las mas obviamente correlacionadas entre si de origen (densidad de POIs
# turisticos, antes sumadas en una sola n_pois_turisticos hasta el v2).
PTNA_VIF_CHECK_COLUMNS = ["n_restaurantes", "n_naturaleza", "n_cultura"]


def get_engine() -> Engine:
    """Crea el engine de SQLAlchemy hacia Postgres (Azure) leyendo el .env del repo."""
    load_dotenv()

    missing = [var for var in REQUIRED_ENV_VARS if not os.environ.get(var)]
    if missing:
        raise RuntimeError(
            f"Faltan variables de entorno requeridas en .env: {missing}. "
            f"Se esperan: {REQUIRED_ENV_VARS}."
        )

    host = os.environ["AZURE_DB_HOST"]
    user = os.environ["AZURE_DB_USER"]
    password = os.environ["AZURE_DB_PASSWORD"]
    dbname = os.environ["AZURE_DB_NAME"]

    conn_str = f"postgresql+psycopg2://{user}:{password}@{host}:{DB_PORT}/{dbname}"
    return create_engine(conn_str, connect_args={"sslmode": "require"})


def setup_logging(script_name: str) -> logging.Logger:
    """
    Logger que escribe el detalle completo a analytics/mgwr/logs/<script_name>.log
    y deja la consola (stdout) limpia salvo warnings/errores -- el resumen corto
    de cada script se imprime aparte con print() al final, no via logging.
    """
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(script_name)
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.propagate = False

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    file_handler = logging.FileHandler(LOGS_DIR / f"{script_name}.log", mode="w", encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(fmt)
    logger.addHandler(console_handler)

    return logger
