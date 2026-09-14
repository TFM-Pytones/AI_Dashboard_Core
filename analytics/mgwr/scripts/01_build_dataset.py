"""
01_build_dataset.py
--------------------
Bloque 5 (MGWR/PTNA) -- Subtarea 5.1, paso 1: construye el dataset crudo de
regresion uniendo gold.gold_h3_master con gold.gold_h3_accesibilidad.

Ver analytics/mgwr/docs/contexto_maestro_proyecto_ptna.md (seccion 3) para
el contexto completo: por que estas columnas puntuales, por que dist_costa_km
del Bloque 4 y no distancia_costa_metros del Bloque 1, por que n_pois_turisticos
en vez de n_pois_total, etc.

No aplica ningun filtro de calidad todavia (eso lo hace 02_filter_nan.py).

Uso:
    python 01_build_dataset.py
    python 01_build_dataset.py --output otra_ruta.parquet
"""

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _db import DATA_INTERIM_DIR, get_engine, setup_logging

SCRIPT_NAME = "01_build_dataset"

# Query exacta acordada en el documento de contexto (seccion 3). No modificar
# sin actualizar tambien el documento -- 02/04/05 asumen estos nombres de columna.
QUERY = """
SELECT
    m.h3_index, m.centroide_lon, m.centroide_lat,
    m.n_plazas_registro / NULLIF(m.area_km2, 0) AS densidad_plazas_km2,
    m.ndvi_medio, m.ndbi_medio, m.viirs_medio,
    m.altitud_media_m, m.slope_mean,
    (m.n_restaurantes + m.n_cultura + m.n_naturaleza + m.n_pois_institucionales) AS n_pois_turisticos,
    a.tiempo_tfs_min, a.n_paradas_bus_500m, a.dist_costa_km
FROM gold.gold_h3_master m
LEFT JOIN gold.gold_h3_accesibilidad a ON a.h3_index = m.h3_index;
"""

EXPECTED_COLUMNS = [
    "h3_index", "centroide_lon", "centroide_lat", "densidad_plazas_km2",
    "ndvi_medio", "ndbi_medio", "viirs_medio", "altitud_media_m", "slope_mean",
    "n_pois_turisticos", "tiempo_tfs_min", "n_paradas_bus_500m", "dist_costa_km",
]


def parse_args():
    parser = argparse.ArgumentParser(description="Construye el dataset crudo del Bloque 5 (MGWR/PTNA)")
    parser.add_argument(
        "--output",
        default=str(DATA_INTERIM_DIR / "ptna_dataset_raw.parquet"),
        help="Ruta de salida del parquet (default: analytics/mgwr/data/interim/ptna_dataset_raw.parquet)",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    logger = setup_logging(SCRIPT_NAME)
    t0 = time.perf_counter()

    try:
        logger.info("Conectando a Postgres (Azure)...")
        engine = get_engine()

        logger.info("Ejecutando query de construccion del dataset:\n%s", QUERY)
        with engine.connect() as conn:
            df = pd.read_sql(text(QUERY), conn)
        logger.info("Query ejecutada OK. Filas obtenidas: %d", len(df))

        missing_cols = [c for c in EXPECTED_COLUMNS if c not in df.columns]
        if missing_cols:
            raise RuntimeError(
                f"La query no devolvio las columnas esperadas: {missing_cols}. "
                f"Columnas reales devueltas: {list(df.columns)}. "
                f"Revisar si el schema de gold.gold_h3_master / gold.gold_h3_accesibilidad cambio "
                f"respecto a docs/contexto_maestro_proyecto_ptna.md."
            )

        if len(df) == 0:
            raise RuntimeError(
                "La query devolvio 0 filas. gold.gold_h3_master deberia tener ~2.396 hexagonos -- "
                "revisar la conexion/schema antes de continuar."
            )

        logger.info("describe() de todas las columnas:\n%s", df.describe(include="all").transpose().to_string())

        nan_counts = df.isna().sum()
        logger.info("NaNs por columna:\n%s", nan_counts.to_string())

        densidad = df["densidad_plazas_km2"]
        n_negative = int((densidad < 0).sum())
        n_inf = int(np.isinf(densidad.astype(float)).sum())
        if n_negative > 0:
            logger.warning("densidad_plazas_km2 tiene %d valores NEGATIVOS.", n_negative)
        if n_inf > 0:
            logger.warning("densidad_plazas_km2 tiene %d valores INFINITOS.", n_inf)
        if n_negative == 0 and n_inf == 0:
            logger.info("densidad_plazas_km2: sin valores negativos ni infinitos.")

        DATA_INTERIM_DIR.mkdir(parents=True, exist_ok=True)
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(output_path, index=False)
        logger.info("Dataset guardado en %s", output_path)

        elapsed = time.perf_counter() - t0
        logger.info("Script finalizado OK en %.1f s.", elapsed)

    except Exception:
        logger.exception("Fallo en %s", SCRIPT_NAME)
        print(f"\nERROR en {SCRIPT_NAME} -- ver analytics/mgwr/logs/{SCRIPT_NAME}.log para el detalle.")
        sys.exit(1)

    nan_summary = ", ".join(f"{col}={int(n)}" for col, n in nan_counts.items() if n > 0) or "ninguna"
    print("\n" + "=" * 60)
    print(f"RESUMEN -- {SCRIPT_NAME}")
    print("=" * 60)
    print(f"Filas: {len(df)}")
    print(f"Columnas: {list(df.columns)}")
    print(f"NaNs por columna (solo las que tienen > 0): {nan_summary}")
    print(f"densidad_plazas_km2 -- negativos: {n_negative} | infinitos: {n_inf}")
    print(f"Guardado en: {output_path}")
    print(f"Tiempo total: {elapsed:.1f} s")
    print("=" * 60)


if __name__ == "__main__":
    main()
