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

# Las 9 variables X de referencia del filtro de calidad y del modelo MGWR
# (ver docs/contexto_maestro_proyecto_ptna.md, seccion 3). Compartidas entre
# 02_filter_nan.py y 04_run_model.py para no repetir la lista dos veces.
PTNA_QUALITY_COLUMNS = [
    "ndvi_medio",
    "ndbi_medio",
    "viirs_medio",
    "altitud_media_m",
    "slope_mean",
    "n_pois_turisticos",
    "tiempo_tfs_min",
    "n_paradas_bus_500m",
    "dist_costa_km",
]


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
