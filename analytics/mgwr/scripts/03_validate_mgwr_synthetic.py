"""
03_validate_mgwr_synthetic.py
------------------------------
Bloque 5 (MGWR/PTNA) -- validacion MECANICA de que Sel_BW + MGWR corren en
este entorno, usando datos 100% sinteticos (numpy.random).

IMPORTANTE: este script NUNCA debe importar _db.py, leer nada de
analytics/mgwr/data/, ni conectarse a Postgres. Es deliberado (ver
docs/contexto_maestro_proyecto_ptna.md, seccion 6, Hallazgo 3): mientras el
dataset real no tiene sentimiento_medio, no se quiere correr el riesgo de
mezclar datos ficticios con el dataset de produccion por error. Los
resultados de este script NO se interpretan -- solo confirman que la
libreria/entorno funcionan.

Uso:
    python 03_validate_mgwr_synthetic.py
    python 03_validate_mgwr_synthetic.py --n-rows 1000 --seed 42
"""

import argparse
import logging
import sys
import time
from pathlib import Path

import numpy as np

LOGS_DIR = Path(__file__).resolve().parent.parent / "logs"
SCRIPT_NAME = "03_validate_mgwr_synthetic"
N_VARS_X = 9  # mismo numero de variables X que tendria el dataset real filtrado


def setup_local_logging() -> logging.Logger:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(SCRIPT_NAME)
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.propagate = False

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    file_handler = logging.FileHandler(LOGS_DIR / f"{SCRIPT_NAME}.log", mode="w", encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(fmt)
    logger.addHandler(console_handler)

    return logger


def parse_args():
    parser = argparse.ArgumentParser(
        description="Valida mecanicamente que Sel_BW + MGWR corren, con datos sinteticos (no toca Postgres)."
    )
    parser.add_argument("--n-rows", type=int, default=800, help="Filas sinteticas a generar (default: 800)")
    parser.add_argument("--seed", type=int, default=42, help="Semilla de numpy.random (default: 42)")
    parser.add_argument(
        "--max-iter-multi",
        type=int,
        default=100,
        help="Iteraciones maximas de backfitting multiescala (default: 100; la version real v1 usa 30-50)",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    logger = setup_local_logging()
    t0 = time.perf_counter()

    try:
        # Import diferido: si mgwr/libpysal no estan instalados, el error de
        # import queda en el log/stdout con contexto claro en vez de un
        # traceback crudo al importar el modulo.
        from mgwr.gwr import MGWR
        from mgwr.sel_bw import Sel_BW

        rng = np.random.default_rng(args.seed)
        n = args.n_rows

        logger.info("Generando datos sinteticos: n=%d filas, %d variables X.", n, N_VARS_X)
        coords = list(zip(rng.uniform(-16.9, -16.1, n), rng.uniform(28.0, 28.6, n)))  # bbox aprox Tenerife, sin significado real
        X = rng.standard_normal((n, N_VARS_X))
        y = rng.standard_normal((n, 1))

        logger.info(
            "Corriendo Sel_BW(multi=True, fixed=True).search(max_iter_multi=%d)...",
            args.max_iter_multi,
        )
        t_bw0 = time.perf_counter()
        selector = Sel_BW(coords, y, X, multi=True, fixed=True)
        bw = selector.search(max_iter_multi=args.max_iter_multi)
        bw_elapsed = time.perf_counter() - t_bw0
        logger.info("Sel_BW.search() OK en %.1f s. Bandwidths: %s", bw_elapsed, np.asarray(bw).tolist())

        logger.info("Corriendo MGWR(...).fit()...")
        t_fit0 = time.perf_counter()
        model = MGWR(coords, y, X, selector, fixed=True).fit()
        fit_elapsed = time.perf_counter() - t_fit0
        logger.info("MGWR.fit() OK en %.1f s. predy shape: %s, params shape: %s", fit_elapsed, model.predy.shape, model.params.shape)

        total_elapsed = time.perf_counter() - t0
        logger.info("Script finalizado OK en %.1f s.", total_elapsed)

    except Exception:
        logger.exception("Fallo en %s", SCRIPT_NAME)
        print(f"\nERROR en {SCRIPT_NAME} -- ver analytics/mgwr/logs/{SCRIPT_NAME}.log para el detalle.")
        sys.exit(1)

    print("\n" + "=" * 60)
    print(f"RESUMEN -- {SCRIPT_NAME} (100% sintetico, no interpretar valores)")
    print("=" * 60)
    print(f"Corrio sin errores: SI")
    print(f"Filas sinteticas: {n} | Variables X: {N_VARS_X}")
    print(f"Tiempo Sel_BW.search(): {bw_elapsed:.1f} s")
    print(f"Tiempo MGWR.fit(): {fit_elapsed:.1f} s")
    print(f"Bandwidths encontrados (uno por variable, incl. intercepto): {np.asarray(bw).round(4).tolist()}")
    print(f"Tiempo total: {total_elapsed:.1f} s")
    print("=" * 60)


if __name__ == "__main__":
    main()
