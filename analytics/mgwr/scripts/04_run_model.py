"""
04_run_model.py -- v1 EXPLORATORIO
------------------------------------
Bloque 5 (MGWR/PTNA) -- Subtarea 5.2: corre MGWR sobre el dataset filtrado.

Esta es deliberadamente una version liviana: el dataset todavia no tiene
sentimiento_medio (bloqueante activo, ver docs/contexto_maestro_proyecto_ptna.md
seccion 6, Hallazgo 3), asi que no vale la pena gastar el computo completo de
precision -- esto se va a volver a correr cuando esa variable este disponible.

NOTA SOBRE LA API DE mgwr (importante, no es un detalle menor): a diferencia
del pseudocodigo de referencia (`bw = Sel_BW(...).search(); MGWR(coords, y, X,
bw)`), la clase real `MGWR` de la libreria `mgwr` 2.x NO acepta un bandwidth
escalar -- exige un objeto `selector` (un `Sel_BW` con multi=True ya resuelto
via .search()), porque MGWR es multiescala: cada variable X termina con su
propio bandwidth, no uno solo compartido. Ademas, el backfitting (los
coeficientes locales) se calcula DENTRO de `Sel_BW.search()`, no dentro de
`MGWR.fit()` -- `.fit()` solo calcula predy y diagnosticos a partir de eso.
Esto significa que no existe una forma directa en la API publica de "inyectar"
un bandwidth ya conocido (encontrado en el submuestreo) en el dataset
completo sin volver a pasar por `Sel_BW.search()`. La solucion usada aca:
correr `Sel_BW(...).search()` una segunda vez sobre el dataset completo, pero
con `multi_bw_min = multi_bw_max = bandwidth_del_submuestreo` -- esto evita
la busqueda cara del bandwidth optimo (ya se hizo, mas barato, en el
submuestreo) pero sigue ejecutando el backfitting multiescala real sobre
todas las filas, que es donde vive el costo de computo inevitable.

Uso:
    python 04_run_model.py
    python 04_run_model.py --subsample-step 4 --max-iter-multi 30
"""

import argparse
import multiprocessing
import pickle
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _db import DATA_INTERIM_DIR, PTNA_QUALITY_COLUMNS, setup_logging

SCRIPT_NAME = "04_run_model"

COORD_COLUMNS = ["centroide_lon", "centroide_lat"]
Y_COLUMN = "densidad_plazas_km2"


def spatial_subsample_indices(lon: np.ndarray, lat: np.ndarray, step: int) -> np.ndarray:
    """
    Indices de un submuestreo espacial (1 de cada `step` filas) que preserva
    dispersion geografica, ordenando por curva de Morton (Z-order) en vez de
    tomar aleatoriedad pura o las primeras N filas (que podrian quedar todas
    concentradas en una esquina del mapa).
    """
    lon = np.asarray(lon, dtype=float)
    lat = np.asarray(lat, dtype=float)

    def _to_uint16(values: np.ndarray) -> np.ndarray:
        vmin, vmax = values.min(), values.max()
        if vmax == vmin:
            return np.zeros(len(values), dtype=np.uint64)
        norm = (values - vmin) / (vmax - vmin)
        return np.clip(norm * 65535, 0, 65535).astype(np.uint64)

    def _spread_bits(x: np.ndarray) -> np.ndarray:
        x = (x | (x << 8)) & 0x00FF00FF
        x = (x | (x << 4)) & 0x0F0F0F0F
        x = (x | (x << 2)) & 0x33333333
        x = (x | (x << 1)) & 0x55555555
        return x

    morton = (_spread_bits(_to_uint16(lat)) << 1) | _spread_bits(_to_uint16(lon))
    order = np.argsort(morton, kind="stable")
    return order[::step]


def _bw_search_worker(coords, y, X, max_iter_multi, result_queue):
    """Corre en un proceso aparte para poder aplicarle un timeout duro (ver run_bw_search_with_timeout)."""
    try:
        from mgwr.sel_bw import Sel_BW

        selector = Sel_BW(coords, y, X, multi=True, fixed=True)
        bw = selector.search(max_iter_multi=max_iter_multi)
        result_queue.put(("ok", np.asarray(bw, dtype=float)))
    except Exception as exc:  # noqa: BLE001 -- se reporta al proceso padre, no se traga en silencio
        result_queue.put(("error", f"{type(exc).__name__}: {exc}"))


def run_bw_search_with_timeout(coords, y, X, max_iter_multi, timeout_seconds, logger):
    ctx = multiprocessing.get_context("spawn")
    result_queue = ctx.Queue()
    process = ctx.Process(target=_bw_search_worker, args=(coords, y, X, max_iter_multi, result_queue))

    logger.info(
        "Lanzando Sel_BW().search() sobre el submuestreo en un proceso aparte (limite: %.0f min)...",
        timeout_seconds / 60,
    )
    process.start()
    process.join(timeout=timeout_seconds)

    if process.is_alive():
        process.terminate()
        process.join()
        raise TimeoutError(
            f"Sel_BW().search() supero el limite de {timeout_seconds / 60:.0f} minutos "
            f"sobre el submuestreo ({len(coords)} filas). Proceso terminado."
        )

    if result_queue.empty():
        raise RuntimeError(
            f"El proceso de busqueda de bandwidth termino sin devolver resultado "
            f"(exit code: {process.exitcode}). Revisar el log para mas contexto."
        )

    status, payload = result_queue.get()
    if status == "error":
        raise RuntimeError(f"Sel_BW().search() fallo dentro del proceso hijo: {payload}")
    return payload


def parse_args():
    parser = argparse.ArgumentParser(description="Bloque 5 (MGWR/PTNA) -- v1 exploratorio")
    parser.add_argument(
        "--input",
        default=str(DATA_INTERIM_DIR / "ptna_dataset_filtered.parquet"),
        help="Parquet filtrado de entrada (default: analytics/mgwr/data/interim/ptna_dataset_filtered.parquet)",
    )
    parser.add_argument(
        "--output",
        default=str(DATA_INTERIM_DIR / "ptna_mgwr_model.pkl"),
        help="Ruta del pickle de salida (default: analytics/mgwr/data/interim/ptna_mgwr_model.pkl)",
    )
    parser.add_argument(
        "--subsample-step", type=int, default=3,
        help="1 de cada N filas (orden Morton) para la busqueda de bandwidth (default: 3)",
    )
    parser.add_argument(
        "--max-iter-multi", type=int, default=50,
        help="Iteraciones maximas de backfitting MGWR, submuestreo y dataset completo (default: 50)",
    )
    parser.add_argument(
        "--bw-search-timeout-min", type=float, default=15.0,
        help="Limite de tiempo para Sel_BW().search() sobre el submuestreo, en minutos (default: 15)",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    logger = setup_logging(SCRIPT_NAME)
    t0 = time.perf_counter()

    try:
        from mgwr.gwr import MGWR
        from mgwr.sel_bw import Sel_BW

        input_path = Path(args.input)
        if not input_path.exists():
            raise FileNotFoundError(f"No existe {input_path}. Correr primero 02_filter_nan.py.")

        logger.info("Leyendo %s", input_path)
        df = pd.read_parquet(input_path)
        n_total = len(df)
        logger.info("Filas cargadas: %d", n_total)

        required_cols = PTNA_QUALITY_COLUMNS + COORD_COLUMNS + [Y_COLUMN]
        missing_cols = [c for c in required_cols if c not in df.columns]
        if missing_cols:
            raise RuntimeError(f"Faltan columnas esperadas en el dataset filtrado: {missing_cols}.")

        logger.info("Imputando NaN restantes en las 9 variables X con la mediana de cada columna...")
        X_raw = df[PTNA_QUALITY_COLUMNS].copy()
        medians = X_raw.median()
        n_imputed = int(X_raw.isna().sum().sum())
        X_imputed = X_raw.fillna(medians)
        logger.info("Valores imputados por mediana: %d. Medianas usadas: %s", n_imputed, medians.to_dict())

        logger.info("Normalizando las 9 variables X con StandardScaler...")
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X_imputed.values)

        y = df[[Y_COLUMN]].values.astype(float)
        lon = df["centroide_lon"].values
        lat = df["centroide_lat"].values
        coords_full = list(zip(lon, lat))

        logger.info(
            "Submuestreo espacial (orden Morton/Z): 1 de cada %d filas.", args.subsample_step
        )
        sub_idx = spatial_subsample_indices(lon, lat, args.subsample_step)
        coords_sub = [coords_full[i] for i in sub_idx]
        X_sub = X_scaled[sub_idx]
        y_sub = y[sub_idx]
        logger.info("Filas en el submuestreo: %d / %d", len(sub_idx), n_total)

        timeout_seconds = args.bw_search_timeout_min * 60
        t_bw0 = time.perf_counter()
        bw_sub = run_bw_search_with_timeout(
            coords_sub, y_sub, X_sub, args.max_iter_multi, timeout_seconds, logger
        )
        bw_search_elapsed = time.perf_counter() - t_bw0
        logger.info("Bandwidth encontrado sobre el submuestreo en %.1f s: %s", bw_search_elapsed, bw_sub.tolist())

        logger.info(
            "Aplicando ese bandwidth (fijo, multi_bw_min=multi_bw_max) sobre el DATASET COMPLETO filtrado (%d filas)...",
            n_total,
        )
        t_fit0 = time.perf_counter()
        bw_bounds = [float(b) for b in bw_sub]
        selector_full = Sel_BW(coords_full, y, X_scaled, multi=True, fixed=True)
        selector_full.search(multi_bw_min=bw_bounds, multi_bw_max=bw_bounds, max_iter_multi=args.max_iter_multi)
        model = MGWR(coords_full, y, X_scaled, selector_full, fixed=True, name_x=PTNA_QUALITY_COLUMNS).fit()
        fit_elapsed = time.perf_counter() - t_fit0
        logger.info("Fit sobre el dataset completo OK en %.1f s.", fit_elapsed)

        feature_names = ["intercept"] + PTNA_QUALITY_COLUMNS
        params = model.params
        coef_stats = pd.DataFrame(
            {"media": params.mean(axis=0), "min": params.min(axis=0), "max": params.max(axis=0)},
            index=feature_names,
        )
        logger.info("Estadisticos de coeficientes por variable:\n%s", coef_stats.to_string())

        bandwidths_full = np.asarray(selector_full.bw[0], dtype=float)

        result = {
            "h3_index": df["h3_index"].values,
            "y": y,
            "predy": model.predy,
            "params": params,
            "feature_names": feature_names,
            "bandwidths_full": bandwidths_full,
            "bandwidths_subsample": bw_sub,
            "subsample_step": args.subsample_step,
            "max_iter_multi": args.max_iter_multi,
            "n_obs_full": n_total,
            "n_obs_subsample": len(sub_idx),
            "quality_columns": PTNA_QUALITY_COLUMNS,
            "scaler_mean_": scaler.mean_,
            "scaler_scale_": scaler.scale_,
            "median_imputation": medians.to_dict(),
            "timing_sec": {"bw_search_subsample": bw_search_elapsed, "full_fit": fit_elapsed},
        }

        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as f:
            pickle.dump(result, f)
        logger.info("Modelo guardado en %s", output_path)

        total_elapsed = time.perf_counter() - t0
        logger.info("Script finalizado OK en %.1f s.", total_elapsed)

    except Exception:
        logger.exception("Fallo en %s", SCRIPT_NAME)
        print(f"\nERROR en {SCRIPT_NAME} -- ver analytics/mgwr/logs/{SCRIPT_NAME}.log para el detalle.")
        sys.exit(1)

    print("\n" + "=" * 60)
    print(f"RESUMEN -- {SCRIPT_NAME} (v1 EXPLORATORIO, sin sentimiento_medio)")
    print("=" * 60)
    print(f"Filas dataset completo: {n_total} | Filas submuestreo (bandwidth search): {len(sub_idx)}")
    print(f"Bandwidth submuestreo:      {bw_sub.round(4).tolist()}")
    print(f"Bandwidth dataset completo: {bandwidths_full.round(4).tolist()}")
    print(f"Tiempo Sel_BW.search() (submuestreo): {bw_search_elapsed:.1f} s")
    print(f"Tiempo fit dataset completo: {fit_elapsed:.1f} s")
    print("Estadisticos de coeficientes por variable (media / min / max):")
    print(coef_stats.round(4).to_string())
    print(f"Guardado en: {output_path}")
    print(f"Tiempo total: {total_elapsed:.1f} s")
    print("=" * 60)


if __name__ == "__main__":
    main()
