"""
02_filter_nan.py -- v3
------------------------
Bloque 5 (MGWR/PTNA) -- Subtarea 5.1, paso 2: filtro de calidad sobre el
dataset crudo generado por 01_build_dataset.py.

Excluye hexagonos con mas del 50% de NULL entre las 13 variables X de
PTNA_NAN_FILTER_COLUMNS (ver docs/contexto_maestro_proyecto_ptna.md,
seccion 3 y Hallazgo 5). No toca Postgres -- opera solo sobre el parquet local.

NOTA v3 (ver Hallazgo 10): PTNA_QUALITY_COLUMNS paso de 16 a 14 variables --
tiempo_teide_min y tiempo_polo_turistico_min se sacaron del modelo por
multicolinealidad severa con tiempo_aeropuerto_min. Este script no cambia de
logica, solo hereda la lista mas corta desde _db.py.

IMPORTANTE (Hallazgo 5): sentimiento_medio queda deliberadamente AFUERA de
este filtro (PTNA_NAN_FILTER_COLUMNS en _db.py = PTNA_QUALITY_COLUMNS sin
sentimiento_medio). Solo el 15.9% de los hexagonos (410/2579) tiene reseñas
geolocalizadas -- si sentimiento_medio contara aca, el filtro excluiria de
forma incorrecta la mayoria del dataset por una variable que simplemente no
tiene cobertura geografica completa, no porque el resto del hexagono sea de
mala calidad. sentimiento_medio si se usa como variable X del modelo en
04_run_model.py, imputada con la mediana como las demas.

Uso:
    python 02_filter_nan.py
    python 02_filter_nan.py --input otra_ruta.parquet --output otra_salida.parquet
"""

import argparse
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _db import DATA_INTERIM_DIR, PTNA_NAN_FILTER_COLUMNS, PTNA_QUALITY_COLUMNS, setup_logging

SCRIPT_NAME = "02_filter_nan"
MAX_NAN_RATIO = 0.5


def parse_args():
    parser = argparse.ArgumentParser(
        description="Filtra hexagonos con > 50% de NaN en las 13 variables X de calidad del Bloque 5 "
                     "(todas las X salvo sentimiento_medio, ver Hallazgo 5)"
    )
    parser.add_argument(
        "--input",
        default=str(DATA_INTERIM_DIR / "ptna_dataset_raw_v3.parquet"),
        help="Parquet de entrada (default: analytics/mgwr/data/interim/ptna_dataset_raw_v3.parquet)",
    )
    parser.add_argument(
        "--output",
        default=str(DATA_INTERIM_DIR / "ptna_dataset_filtered_v3.parquet"),
        help="Parquet de salida (default: analytics/mgwr/data/interim/ptna_dataset_filtered_v3.parquet -- "
             "sufijo _v3 a proposito (Hallazgo 10), para no pisar el ptna_dataset_filtered_v2.parquet "
             "que sirvio para diagnosticar la multicolinealidad, ni el del v1)",
    )
    parser.add_argument(
        "--max-nan-ratio",
        type=float,
        default=MAX_NAN_RATIO,
        help=f"Umbral de exclusion, como fraccion (default: {MAX_NAN_RATIO} = 50%%)",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    logger = setup_logging(SCRIPT_NAME)
    t0 = time.perf_counter()

    try:
        input_path = Path(args.input)
        if not input_path.exists():
            raise FileNotFoundError(
                f"No existe {input_path}. Correr primero 01_build_dataset.py."
            )

        logger.info("Leyendo %s", input_path)
        df = pd.read_parquet(input_path)
        logger.info("Filas cargadas: %d", len(df))

        missing_quality_cols = [c for c in PTNA_NAN_FILTER_COLUMNS if c not in df.columns]
        if missing_quality_cols:
            raise RuntimeError(
                f"Faltan columnas de calidad esperadas en el dataset: {missing_quality_cols}. "
                f"Columnas disponibles: {list(df.columns)}."
            )

        nan_ratio = df[PTNA_NAN_FILTER_COLUMNS].isna().mean(axis=1)
        excluded_mask = nan_ratio > args.max_nan_ratio
        n_excluded = int(excluded_mask.sum())
        n_kept = len(df) - n_excluded

        logger.info(
            "Umbral de exclusion: > %.0f%% de NULL entre %d variables de calidad (sentimiento_medio "
            "excluida a proposito de este conteo, ver Hallazgo 5).",
            args.max_nan_ratio * 100, len(PTNA_NAN_FILTER_COLUMNS),
        )
        logger.info("Filas excluidas: %d / %d", n_excluded, len(df))
        logger.info("Filas conservadas: %d", n_kept)

        excluded_df = df.loc[excluded_mask, PTNA_NAN_FILTER_COLUMNS]
        missing_ranking = excluded_df.isna().sum().sort_values(ascending=False)
        logger.info(
            "Ranking de variables mas ausentes entre las filas excluidas:\n%s",
            missing_ranking.to_string(),
        )

        # Reporte informativo sobre las 14 variables (incluye sentimiento_medio,
        # aunque no participe del calculo de exclusion de arriba) -- para tener
        # visibilidad completa de cobertura antes del paso de imputacion en 04.
        logger.info(
            "NaNs por columna, dataset completo (antes de excluir; incluye sentimiento_medio "
            "a modo informativo, no participa de la exclusion):\n%s",
            df[PTNA_QUALITY_COLUMNS].isna().sum().to_string(),
        )

        filtered_df = df.loc[~excluded_mask].reset_index(drop=True)

        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        filtered_df.to_parquet(output_path, index=False)
        logger.info("Dataset filtrado guardado en %s", output_path)

        elapsed = time.perf_counter() - t0
        logger.info("Script finalizado OK en %.1f s.", elapsed)

    except Exception:
        logger.exception("Fallo en %s", SCRIPT_NAME)
        print(f"\nERROR en {SCRIPT_NAME} -- ver analytics/mgwr/logs/{SCRIPT_NAME}.log para el detalle.")
        sys.exit(1)

    ranking_str = ", ".join(f"{col}={int(n)}" for col, n in missing_ranking.items() if n > 0) or "ninguna"
    print("\n" + "=" * 60)
    print(f"RESUMEN -- {SCRIPT_NAME}")
    print("=" * 60)
    print(f"Filas totales: {len(df)}")
    print(f"Excluidas (> {args.max_nan_ratio:.0%} NaN en las {len(PTNA_NAN_FILTER_COLUMNS)} vars de calidad, sentimiento_medio no cuenta): {n_excluded}")
    print(f"Conservadas: {n_kept}")
    print(f"Ranking de variables mas ausentes entre las excluidas: {ranking_str}")
    print(f"Guardado en: {output_path}")
    print(f"Tiempo total: {elapsed:.1f} s")
    print("=" * 60)


if __name__ == "__main__":
    main()
