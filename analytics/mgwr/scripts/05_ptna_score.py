"""
05_ptna_score.py
-----------------
Bloque 5 (MGWR/PTNA) -- Subtarea 5.2, cierre: calcula el indice PTNA a partir
del modelo MGWR ya ajustado (04_run_model.py) y produce el dataset final.

PTNA = Valor_esperado_por_MGWR - Valor_observado_real
     = modelo.predy - y

ptna_score > 0 -> el hexagono "deberia" tener mas plazas hoteleras segun sus
                  condiciones -> oportunidad de inversion.
ptna_score < 0 -> zona sobre-explotada -> riesgo de overtourism.

Uso:
    python 05_ptna_score.py
"""

import argparse
import pickle
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _db import DATA_INTERIM_DIR, DATA_PROCESSED_DIR, setup_logging

SCRIPT_NAME = "05_ptna_score"
TOP_N = 10


def parse_args():
    parser = argparse.ArgumentParser(description="Calcula ptna_score y produce el dataset final del Bloque 5")
    parser.add_argument(
        "--model",
        default=str(DATA_INTERIM_DIR / "ptna_mgwr_model.pkl"),
        help="Pickle del modelo (default: analytics/mgwr/data/interim/ptna_mgwr_model.pkl)",
    )
    parser.add_argument(
        "--dataset",
        default=str(DATA_INTERIM_DIR / "ptna_dataset_filtered.parquet"),
        help="Dataset filtrado (default: analytics/mgwr/data/interim/ptna_dataset_filtered.parquet)",
    )
    parser.add_argument(
        "--output",
        default=str(DATA_PROCESSED_DIR / "gold_h3_ptna_v1.parquet"),
        help="Parquet final de salida (default: analytics/mgwr/data/processed/gold_h3_ptna_v1.parquet)",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    logger = setup_logging(SCRIPT_NAME)
    t0 = time.perf_counter()

    try:
        model_path = Path(args.model)
        dataset_path = Path(args.dataset)
        if not model_path.exists():
            raise FileNotFoundError(f"No existe {model_path}. Correr primero 04_run_model.py.")
        if not dataset_path.exists():
            raise FileNotFoundError(f"No existe {dataset_path}. Correr primero 02_filter_nan.py.")

        logger.info("Leyendo modelo %s", model_path)
        with open(model_path, "rb") as f:
            model = pickle.load(f)

        logger.info("Leyendo dataset filtrado %s", dataset_path)
        df = pd.read_parquet(dataset_path)

        required_keys = ["h3_index", "y", "predy"]
        missing_keys = [k for k in required_keys if k not in model]
        if missing_keys:
            raise RuntimeError(f"El pickle del modelo no tiene las claves esperadas: {missing_keys}.")

        if len(model["h3_index"]) != len(df):
            raise RuntimeError(
                f"El modelo tiene {len(model['h3_index'])} filas pero el dataset filtrado tiene {len(df)}. "
                f"Probablemente 02_filter_nan.py o 04_run_model.py corrieron sobre datos distintos -- "
                f"volver a correr el pipeline en orden (01 -> 02 -> 04 -> 05)."
            )

        y = np.asarray(model["y"]).flatten()
        predy = np.asarray(model["predy"]).flatten()
        ptna_score = predy - y
        logger.info(
            "ptna_score calculado: %d valores, media=%.4f, std=%.4f",
            len(ptna_score), ptna_score.mean(), ptna_score.std(),
        )

        scores_by_h3 = pd.DataFrame({"h3_index": model["h3_index"], "ptna_score": ptna_score})
        result_df = df.merge(scores_by_h3, on="h3_index", how="left", validate="one_to_one")

        n_missing_score = int(result_df["ptna_score"].isna().sum())
        if n_missing_score > 0:
            logger.warning(
                "%d filas del dataset filtrado no encontraron match de h3_index en el modelo.",
                n_missing_score,
            )

        n_positive = int((result_df["ptna_score"] > 0).sum())
        n_negative = int((result_df["ptna_score"] < 0).sum())

        percentiles = [5, 10, 25, 50, 75, 90, 95]
        pct_values = result_df["ptna_score"].quantile([p / 100 for p in percentiles])
        logger.info("Percentiles de ptna_score:\n%s", pct_values.to_string())

        has_municipio = "municipio" in result_df.columns
        top_cols = ["h3_index"] + (["municipio"] if has_municipio else []) + ["ptna_score"]
        top10 = result_df.sort_values("ptna_score", ascending=False).head(TOP_N)[top_cols]
        logger.info("Top %d hexagonos por ptna_score:\n%s", TOP_N, top10.to_string(index=False))
        if not has_municipio:
            logger.info(
                "Columna 'municipio' no esta presente en el dataset filtrado -- la query de "
                "01_build_dataset.py no la selecciona (no estaba en el pedido original). "
                "Top 10 reportado solo con h3_index."
            )

        DATA_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        result_df.to_parquet(output_path, index=False)
        logger.info("Dataset final guardado en %s", output_path)

        elapsed = time.perf_counter() - t0
        logger.info("Script finalizado OK en %.1f s.", elapsed)

    except Exception:
        logger.exception("Fallo en %s", SCRIPT_NAME)
        print(f"\nERROR en {SCRIPT_NAME} -- ver analytics/mgwr/logs/{SCRIPT_NAME}.log para el detalle.")
        sys.exit(1)

    print("\n" + "=" * 60)
    print(f"RESUMEN -- {SCRIPT_NAME}")
    print("=" * 60)
    print(f"Hexagonos con ptna_score > 0 (oportunidad): {n_positive}")
    print(f"Hexagonos con ptna_score < 0 (sobre-explotado): {n_negative}")
    if n_missing_score:
        print(f"AVISO: {n_missing_score} filas sin match de h3_index entre dataset y modelo.")
    print("Percentiles de ptna_score:")
    print(pct_values.round(4).to_string())
    if not has_municipio:
        print("(municipio no disponible en el dataset -- top 10 solo con h3_index, ver detalle en el log)")
    print(f"\nTop {TOP_N} hexagonos por ptna_score:")
    print(top10.round(4).to_string(index=False))
    print(f"\nGuardado en: {output_path}")
    print(f"Tiempo total: {elapsed:.1f} s")
    print("=" * 60)


if __name__ == "__main__":
    main()
