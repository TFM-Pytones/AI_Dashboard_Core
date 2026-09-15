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

NOTA SOBRE `confianza_ptna` (diagnostico de estabilidad de coeficientes,
sesion aparte sobre el .pkl ya generado): con kernel adaptativo, un
bandwidth chico + ubicacion geografica periferica (pocos vecinos reales,
todos concentrados de un lado) puede producir coeficientes locales
extremos e inestables. Se diagnosticaron los 4 coeficientes con rangos
min/max mas amplios; de esos, 2 (`dist_costa_km`, `n_paradas_bus_500m`)
mostraron sus extremos (percentil 1/99) concentrados en zonas
geograficamente perifericas (borde 5% del rango lon/lat del dataset) --
las otras 2 (`n_pois_turisticos`, `viirs_medio`) mostraron sus extremos en
zonas de alta actividad real (Puerto de la Cruz/La Orotava), no
inestabilidad, y se descartaron de este criterio a proposito. `ptna_score`
NO cambia por esto -- `confianza_ptna` es puramente informativa, para que
quien lea el top-10 sepa si algun "mejor candidato" tiene esta salvedad
antes de reportarlo como hallazgo solido sin más contexto.

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

# Variables cuyos coeficientes extremos (percentil 1/99), SI ADEMAS caen en
# zona periferica, marcan el hexagono como confianza_ptna='baja'. Ver nota
# extensa arriba -- n_pois_turisticos y viirs_medio quedaron fuera a
# proposito (sus extremos son zonas de alta actividad real, no inestabilidad
# numerica).
CONFIANZA_BAJA_VARIABLES = ["dist_costa_km", "n_paradas_bus_500m"]
CONFIANZA_BAJA_PERCENTILES = (1, 99)
CONFIANZA_BAJA_MARGEN_PERIFERICO = 0.05  # 5% del rango lon/lat del dataset


def _es_periferico(lon, lat, lon_min, lon_max, lat_min, lat_max, margen_pct):
    """Un punto es 'periferico' si esta a <= margen_pct del rango total de
    lon o de lat del dataset -- mismo criterio usado en el diagnostico de
    estabilidad de coeficientes (sesion previa, sobre el mismo .pkl)."""
    rango_lon = lon_max - lon_min
    rango_lat = lat_max - lat_min
    cerca_borde_lon = (lon - lon_min) <= rango_lon * margen_pct or (lon_max - lon) <= rango_lon * margen_pct
    cerca_borde_lat = (lat - lat_min) <= rango_lat * margen_pct or (lat_max - lat) <= rango_lat * margen_pct
    return bool(cerca_borde_lon or cerca_borde_lat)


def calcular_h3_confianza_baja(df, model):
    """
    Recalcula (no hardcodea por h3_index) el conjunto de hexagonos con
    confianza_ptna='baja': union, sobre CONFIANZA_BAJA_VARIABLES, de los
    hexagonos cuyo coeficiente local esta en percentil 1 o 99 Y ADEMAS estan
    en zona periferica del dataset. Si el modelo se vuelve a correr con datos
    nuevos, este calculo se rehace solo -- no depende de una lista fija.
    """
    feature_names = model["feature_names"]
    params = model["params"]
    h3_model = model["h3_index"]

    faltantes = [v for v in CONFIANZA_BAJA_VARIABLES if v not in feature_names]
    if faltantes:
        raise RuntimeError(
            f"Las variables {faltantes} (usadas para confianza_ptna) no estan en "
            f"feature_names del modelo: {feature_names}."
        )

    coef_df = pd.DataFrame(params, columns=feature_names)
    coef_df["h3_index"] = h3_model

    lon_min, lon_max = df["centroide_lon"].min(), df["centroide_lon"].max()
    lat_min, lat_max = df["centroide_lat"].min(), df["centroide_lat"].max()
    periferico_by_h3 = {
        row.h3_index: _es_periferico(
            row.centroide_lon, row.centroide_lat, lon_min, lon_max, lat_min, lat_max,
            CONFIANZA_BAJA_MARGEN_PERIFERICO,
        )
        for row in df.itertuples()
    }

    p_bajo, p_alto = CONFIANZA_BAJA_PERCENTILES
    h3_confianza_baja = set()
    detalle_por_variable = {}
    for var in CONFIANZA_BAJA_VARIABLES:
        coef = coef_df[var].values
        p1 = np.percentile(coef, p_bajo)
        p99 = np.percentile(coef, p_alto)
        extremos = coef_df.loc[(coef <= p1) | (coef >= p99), "h3_index"]
        extremos_perifericos = [h for h in extremos if periferico_by_h3.get(h, False)]
        detalle_por_variable[var] = len(extremos_perifericos)
        h3_confianza_baja.update(extremos_perifericos)

    return h3_confianza_baja, detalle_por_variable


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

        logger.info(
            "Calculando confianza_ptna (variables=%s, percentiles=%s, margen periferico=%.0f%%)...",
            CONFIANZA_BAJA_VARIABLES, CONFIANZA_BAJA_PERCENTILES, CONFIANZA_BAJA_MARGEN_PERIFERICO * 100,
        )
        h3_confianza_baja, detalle_confianza = calcular_h3_confianza_baja(df, model)
        for var, n in detalle_confianza.items():
            logger.info("  %s: %d hexagonos extremos (p1/p99) Y perifericos", var, n)
        logger.info(
            "Total hexagonos marcados confianza_ptna='baja' (union, sin doble conteo): %d",
            len(h3_confianza_baja),
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
        result_df["confianza_ptna"] = np.where(
            result_df["h3_index"].isin(h3_confianza_baja), "baja", "normal"
        )
        n_confianza_baja = int((result_df["confianza_ptna"] == "baja").sum())

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
        top_cols = ["h3_index"] + (["municipio"] if has_municipio else []) + ["ptna_score", "confianza_ptna"]
        top10 = result_df.sort_values("ptna_score", ascending=False).head(TOP_N)[top_cols]
        n_top10_confianza_baja = int((top10["confianza_ptna"] == "baja").sum())
        logger.info("Top %d hexagonos por ptna_score:\n%s", TOP_N, top10.to_string(index=False))
        if n_top10_confianza_baja:
            logger.warning(
                "%d de los top %d hexagonos tienen confianza_ptna='baja' -- ver detalle.",
                n_top10_confianza_baja, TOP_N,
            )
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
    print(
        f"Hexagonos con confianza_ptna='baja' (bandwidth chico + zona periferica en "
        f"dist_costa_km y/o n_paradas_bus_500m): {n_confianza_baja} / {len(result_df)} "
        f"({n_confianza_baja / len(result_df) * 100:.1f}%)"
    )
    for var, n in detalle_confianza.items():
        print(f"  - {var}: {n} hexagonos")
    if n_missing_score:
        print(f"AVISO: {n_missing_score} filas sin match de h3_index entre dataset y modelo.")
    print("Percentiles de ptna_score:")
    print(pct_values.round(4).to_string())
    if not has_municipio:
        print("(municipio no disponible en el dataset -- top 10 solo con h3_index, ver detalle en el log)")
    print(f"\nTop {TOP_N} hexagonos por ptna_score:")
    print(top10.round(4).to_string(index=False))
    if n_top10_confianza_baja:
        print(
            f"\n*** AVISO: {n_top10_confianza_baja} de los top {TOP_N} tienen confianza_ptna='baja' "
            f"-- ver columna arriba antes de reportar estos como hallazgo solido. ***"
        )
    else:
        print(f"\nNinguno de los top {TOP_N} tiene confianza_ptna='baja'.")
    print(f"\nGuardado en: {output_path}")
    print(f"Tiempo total: {elapsed:.1f} s")
    print("=" * 60)


if __name__ == "__main__":
    main()
