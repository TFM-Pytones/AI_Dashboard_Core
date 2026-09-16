"""
01_build_dataset.py -- v2
--------------------------
Bloque 5 (MGWR/PTNA) -- Subtarea 5.1, paso 1: construye el dataset crudo de
regresion uniendo gold.gold_h3_master, gold.gold_h3_accesibilidad y
gold.gold_h3_sentimiento (ver 00_create_sentimiento_table.py -- correr ese
script primero si la tabla no existe todavia).

Ver analytics/mgwr/docs/contexto_maestro_proyecto_ptna.md (seccion 3 y
Hallazgos 4-7) para el contexto completo del cambio v1 -> v2.

Cambios respecto al v1 (15-sep-2026, alineando con plan_final_mejorado.md
Bloque 5 Subtarea 5.1, no con el resumen de la sesion del 12-sep):
- ELIMINADAS ndbi_medio y viirs_medio (el plan las excluye explicitamente por
  riesgo de colinealidad/proxy directo de la variable Y).
- n_pois_turisticos (suma de 4 subcategorias) DEJA DE USARSE. El plan lista
  n_restaurantes, n_naturaleza y n_cultura como 3 variables X INDEPENDIENTES
  en la tabla de la Subtarea 5.1 -- la suma fue una decision de la sesion del
  12-sep documentada solo en este script y en el doc de contexto (Hallazgo 1),
  no algo que pida el plan real. Se revierte esa decision aca. n_pois_institucionales
  queda fuera del todo (tampoco aparece en la tabla del plan).
- n_paradas_bus_500m (conteo discreto) -> dist_parada_cercana_m (distancia
  continua): evita el exceso de ceros en zonas rurales.
- tiempo_tfs_min -> tiempo_aeropuerto_min: columna YA PRECALCULADA en
  gold_h3_accesibilidad, verificada igual a LEAST(tiempo_tfs_min,
  tiempo_tfn_min) en las 2583 filas (0 discrepancias) -- no hace falta
  calcularla a mano.
- NUEVA tiempo_polo_turistico_min = LEAST(tiempo_extremo_sur_min,
  tiempo_extremo_norte_min) -- a diferencia de tiempo_aeropuerto_min, esta NO
  viene precalculada, se computa aca.
- NUEVAS dist_hospital_km, pct_area_enp, temp_media_anual, lluvia_mm_anual,
  tiempo_teide_min (todas confirmadas contra information_schema.columns con
  el nombre exacto del plan).
- NUEVA sentimiento_medio (+ n_resenas_sentimiento, informativa) via LEFT JOIN
  a gold.gold_h3_sentimiento -- 84.1% de los hexagonos quedan con
  sentimiento_medio NULL (solo 410/2579 tienen reseñas geolocalizadas), ver
  Hallazgo 5. Por eso sentimiento_medio NO cuenta para el filtro de >50% NaN
  de 02_filter_nan.py (PTNA_NAN_FILTER_COLUMNS en _db.py), aunque si se usa
  como variable X del modelo en 04 (imputada con mediana).
- NUEVA columna municipio, solo para que los reportes de top-N sean legibles
  (no es variable X del modelo).

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

# Query v2, acordada en el documento de contexto (seccion 3) y en
# plan_final_mejorado.md (Bloque 5, Subtarea 5.1). No modificar sin
# actualizar tambien el documento -- 02/04/05 asumen estos nombres de columna.
QUERY = """
SELECT
    m.h3_index,
    m.municipio,
    m.centroide_lon,
    m.centroide_lat,
    m.n_plazas_registro / NULLIF(m.area_km2, 0) AS densidad_plazas_km2,
    m.ndvi_medio,
    m.altitud_media_m,
    m.slope_mean,
    m.n_restaurantes,
    m.n_naturaleza,
    m.n_cultura,
    a.dist_hospital_km,
    m.pct_area_enp,
    m.temp_media_anual,
    m.lluvia_mm_anual,
    a.tiempo_teide_min,
    a.dist_parada_cercana_m,
    a.tiempo_aeropuerto_min,
    LEAST(a.tiempo_extremo_sur_min, a.tiempo_extremo_norte_min) AS tiempo_polo_turistico_min,
    a.dist_costa_km,
    sent.sentimiento_medio,
    sent.n_resenas_sentimiento
FROM gold.gold_h3_master m
LEFT JOIN gold.gold_h3_accesibilidad a ON a.h3_index = m.h3_index
LEFT JOIN gold.gold_h3_sentimiento sent ON sent.h3_index = m.h3_index;
"""

EXPECTED_COLUMNS = [
    "h3_index", "municipio", "centroide_lon", "centroide_lat", "densidad_plazas_km2",
    "ndvi_medio", "altitud_media_m", "slope_mean",
    "n_restaurantes", "n_naturaleza", "n_cultura",
    "dist_hospital_km", "pct_area_enp", "temp_media_anual", "lluvia_mm_anual",
    "tiempo_teide_min", "dist_parada_cercana_m", "tiempo_aeropuerto_min",
    "tiempo_polo_turistico_min", "dist_costa_km",
    "sentimiento_medio", "n_resenas_sentimiento",
]


def parse_args():
    parser = argparse.ArgumentParser(description="Construye el dataset crudo del Bloque 5 (MGWR/PTNA)")
    parser.add_argument(
        "--output",
        default=str(DATA_INTERIM_DIR / "ptna_dataset_raw_v3.parquet"),
        help="Ruta de salida del parquet (default: analytics/mgwr/data/interim/ptna_dataset_raw_v3.parquet -- "
             "sufijo _v3 a proposito, ver Hallazgo 10 (misma query que v2, el cambio de version es solo "
             "por consistencia con 02/04 -- no pisa ptna_dataset_raw_v2.parquet ni el v1)",
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
