"""
10_diagnosticos_ajuste.py
--------------------------
Bloque 5 (MGWR/PTNA) -- diagnosticos de bondad de ajuste ADICIONALES sobre el
resultado v3 ya cerrado y entregado (gold.gold_h3_ptna_v3,
gold.gold_bloque5_h3_oportunidad_v1). Este script es ESTRICTAMENTE DE SOLO
LECTURA: no re-corre MGWR, no llama a `.fit()`, no escribe en el checkpoint
v3 ni en ninguna tabla de Postgres. Solo lee dos artefactos ya existentes:

  - analytics/mgwr/data/interim/ptna_mgwr_model_v3_checkpoint.pkl (params/
    predy/y/h3_index/feature_names/bandwidths_full, sin ENP_j/CCT -- ver
    Hallazgo 9 en contexto_maestro_proyecto_ptna.md)
  - analytics/mgwr/data/interim/ptna_dataset_filtered_v3.parquet (dataset
    filtrado que alimento a 04_run_model.py)

Motivo (decision explicita, no autonoma): el checkpoint v3 NO contiene R²,
AICc ni residuales -- solo lo minimo que usa 05_ptna_score.py. Un AICc/R²
"oficial" de MGWR (ENP_j/CCT via `MGWR.fit()`) exigiria re-correr
04_run_model.py --con-diagnosticos-enp desde cero (28.5 min de
busqueda+backfitting ya conocidos + un paso de .fit() que en el unico
intento real registrado (v2, Hallazgo 9) hizo timeout a los 40.1 min SIN
terminar) -- eso quedo fuera de alcance de este script a proposito, es una
decision aparte pendiente de autorizacion explicita si se necesita en el
futuro.

Lo que SI se calcula aqui (autorizado explicitamente, opciones A+B+C1 del
plan del 17-sep-2026):

  A. R² global del MGWR, directo de `y`/`predy` ya guardados en el
     checkpoint (1 - SS_res/SS_tot). NO es el R² ajustado por grados de
     libertad efectivos (ENP) que devolveria `MGWR.fit()` -- se etiqueta
     como "global, no ajustado" en todo el output para no confundirlo con
     ese numero.
  B. OLS de referencia: mismas 14 variables X y el mismo Y
     (`densidad_plazas_km2`) del dataset v3, imputacion por mediana IDENTICA
     a la que aplica 04_run_model.py (mismo criterio, mismas columnas,
     PTNA_QUALITY_COLUMNS de _db.py), ajustado con
     sklearn.linear_model.LinearRegression (statsmodels no esta instalado,
     no hace falta -- R²/AICc se calculan con formula cerrada). El StandardScaler
     que usa 04_run_model.py NO se replica aca a proposito: R²/AICc de un OLS
     son invariantes a un reescalado lineal de X (mismos residuales, mismos
     valores predichos), asi que ajustar sobre X sin escalar da exactamente
     el mismo resultado sin ese paso.
  C1. I de Moran de los residuales del MGWR (y - predy, ya en el checkpoint)
      Y de los residuales del OLS de referencia (para comparar, igual que
      pedia el parrafo original que se estaba verificando). Matriz de pesos
      espaciales W: `libpysal.weights.KNN` sobre centroide_lon/centroide_lat
      (ya en el dataset), k=6 (aproxima la vecindad hexagonal con 6 vecinos
      mas cercanos euclidianos -- libpysal ya esta instalado, dependencia de
      mgwr, no hizo falta instalar nada nuevo). `esda` NO esta instalado --
      el estadistico de Moran's I se implementa a mano (formula estandar) y
      la significancia se estima por permutacion (999 permutaciones, semilla
      fija para reproducibilidad), sin depender de esa libreria.

Alineacion de datos: el checkpoint y el dataset filtrado pueden no compartir
el mismo orden de filas (05_ptna_score.py ya hace un merge explicito por
h3_index en vez de asumir orden identico -- mismo criterio aca). Todo se
une por `h3_index` con `validate="one_to_one"` antes de calcular nada.

Uso:
    python 10_diagnosticos_ajuste.py
"""

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from libpysal.weights import KNN
from sklearn.linear_model import LinearRegression

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _db import DATA_INTERIM_DIR, PTNA_QUALITY_COLUMNS, setup_logging

SCRIPT_NAME = "10_diagnosticos_ajuste"
MORAN_KNN_K = 6
MORAN_N_PERMUTATIONS = 999
MORAN_RANDOM_SEED = 42


def calcular_r2_global(y, predy):
    """R² global no ajustado por ENP: 1 - SS_res/SS_tot. Ver nota del modulo
    sobre por que esto NO es el R² oficial de MGWR.fit()."""
    y = np.asarray(y).flatten()
    predy = np.asarray(predy).flatten()
    ss_res = float(np.sum((y - predy) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r2 = 1.0 - ss_res / ss_tot
    return r2, ss_res, ss_tot


def ajustar_ols_referencia(df_joined):
    """OLS de referencia con las mismas 14 variables X y el mismo Y del v3,
    imputacion por mediana identica a 04_run_model.py. Devuelve R², AICc y
    los residuales (para el Moran's I de referencia)."""
    X_raw = df_joined[PTNA_QUALITY_COLUMNS].copy()
    medians = X_raw.median()
    n_imputed = int(X_raw.isna().sum().sum())
    X_imputed = X_raw.fillna(medians)

    y = df_joined["densidad_plazas_km2"].values.astype(float)

    model = LinearRegression()
    model.fit(X_imputed.values, y)
    pred = model.predict(X_imputed.values)
    resid = y - pred

    n = len(y)
    k = X_imputed.shape[1] + 1  # +1 por el intercepto, igual que feature_names del MGWR
    ss_res = float(np.sum(resid ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r2 = 1.0 - ss_res / ss_tot

    # AICc para regresion Gaussiana, formula cerrada (no requiere statsmodels):
    # AIC = n*ln(SS_res/n) + 2k ; AICc = AIC + 2k(k+1)/(n-k-1)
    aic = n * np.log(ss_res / n) + 2 * k
    aicc = aic + (2 * k * (k + 1)) / (n - k - 1)

    return {
        "r2": r2,
        "aic": float(aic),
        "aicc": float(aicc),
        "n": n,
        "k": k,
        "n_imputados": n_imputed,
        "medianas": {c: float(m) for c, m in medians.items()},
    }, resid


def moran_i_manual(resid, coords, k=MORAN_KNN_K, n_perm=MORAN_N_PERMUTATIONS, seed=MORAN_RANDOM_SEED):
    """
    I de Moran calculada a mano (esda no esta instalado -- ver nota del
    modulo). Formula estandar (Moran 1950):

        I = (n / S0) * (e' W e) / (e' e)

    con e = residuales centrados en su media, W = matriz de pesos espaciales
    (KNN, row-standardized), S0 = suma de todos los pesos (= n si W esta
    row-standardized, cada fila suma 1).

    Significancia: NO se asume normalidad -- se estima por permutacion
    (n_perm reasignaciones aleatorias de los residuales sobre las mismas
    posiciones geograficas, semilla fija para reproducibilidad), reportando
    el percentil del I real dentro de la distribucion nula empirica.
    """
    w = KNN.from_array(coords, k=k)
    w.transform = "r"  # row-standardized, como es estandar para Moran's I

    e = np.asarray(resid).flatten()
    e = e - e.mean()
    n = len(e)

    # e' W e = suma_i e_i * suma_j w_ij * e_j
    we = np.zeros(n)
    for i, neighbors in w.neighbors.items():
        weights_i = w.weights[i]
        we[i] = sum(wij * e[j] for wij, j in zip(weights_i, neighbors))

    numerador = float(np.sum(e * we))
    denominador = float(np.sum(e ** 2))
    s0 = float(sum(sum(w.weights[i]) for i in w.weights))

    I_obs = (n / s0) * (numerador / denominador)
    I_esperado = -1.0 / (n - 1)

    rng = np.random.default_rng(seed)
    I_perm = np.empty(n_perm)
    for p in range(n_perm):
        e_perm = rng.permutation(e)
        we_perm = np.zeros(n)
        for i, neighbors in w.neighbors.items():
            weights_i = w.weights[i]
            we_perm[i] = sum(wij * e_perm[j] for wij, j in zip(weights_i, neighbors))
        I_perm[p] = (n / s0) * (float(np.sum(e_perm * we_perm)) / denominador)

    p_value = float((np.sum(np.abs(I_perm) >= abs(I_obs)) + 1) / (n_perm + 1))

    return {
        "I": float(I_obs),
        "I_esperado_bajo_h0": float(I_esperado),
        "p_value_permutacion": p_value,
        "n_permutaciones": n_perm,
        "knn_k": k,
    }


def main():
    logger = setup_logging(SCRIPT_NAME)
    t0 = time.perf_counter()

    checkpoint_path = DATA_INTERIM_DIR / "ptna_mgwr_model_v3_checkpoint.pkl"
    dataset_path = DATA_INTERIM_DIR / "ptna_dataset_filtered_v3.parquet"

    if not checkpoint_path.exists():
        raise FileNotFoundError(f"No existe {checkpoint_path}.")
    if not dataset_path.exists():
        raise FileNotFoundError(f"No existe {dataset_path}.")

    logger.info("Leyendo checkpoint (solo lectura) %s", checkpoint_path)
    import pickle
    with open(checkpoint_path, "rb") as f:
        model = pickle.load(f)

    logger.info("Leyendo dataset filtrado (solo lectura) %s", dataset_path)
    df = pd.read_parquet(dataset_path)

    # --- Alineacion por h3_index (mismo criterio que 05_ptna_score.py) ---
    mgwr_df = pd.DataFrame({
        "h3_index": model["h3_index"],
        "y_mgwr": np.asarray(model["y"]).flatten(),
        "predy_mgwr": np.asarray(model["predy"]).flatten(),
    })
    df_joined = df.merge(mgwr_df, on="h3_index", how="inner", validate="one_to_one")
    if len(df_joined) != len(df) or len(df_joined) != len(mgwr_df):
        raise RuntimeError(
            f"Join por h3_index incompleto: dataset={len(df)}, checkpoint={len(mgwr_df)}, "
            f"join={len(df_joined)}. No deberia perderse ninguna fila -- revisar antes de confiar "
            f"en los resultados."
        )
    diff_y = np.abs(df_joined["densidad_plazas_km2"].values - df_joined["y_mgwr"].values).max()
    logger.info(
        "Join OK: %d filas. Diferencia maxima entre 'densidad_plazas_km2' (dataset) y 'y' "
        "(checkpoint) tras el join: %.10f (deberia ser 0 -- son la misma columna origen).",
        len(df_joined), diff_y,
    )

    # --- A. R² global MGWR (desde checkpoint, sin re-fit) ---
    logger.info("Calculando R² global del MGWR (desde y/predy del checkpoint, sin re-fit)...")
    r2_mgwr, ss_res_mgwr, ss_tot_mgwr = calcular_r2_global(
        df_joined["y_mgwr"], df_joined["predy_mgwr"]
    )
    resid_mgwr = df_joined["y_mgwr"].values - df_joined["predy_mgwr"].values

    # --- B. OLS de referencia (mismas 14 X, mismo Y) ---
    logger.info("Ajustando OLS de referencia (mismas %d variables X, mismo Y)...", len(PTNA_QUALITY_COLUMNS))
    ols_resultado, resid_ols = ajustar_ols_referencia(df_joined)

    # --- C1. Moran's I de residuales MGWR y OLS (KNN k=6, sin esda) ---
    coords = df_joined[["centroide_lon", "centroide_lat"]].values
    logger.info(
        "Calculando I de Moran de residuales MGWR (KNN k=%d, %d permutaciones, semilla=%d)...",
        MORAN_KNN_K, MORAN_N_PERMUTATIONS, MORAN_RANDOM_SEED,
    )
    moran_mgwr = moran_i_manual(resid_mgwr, coords)
    logger.info(
        "Calculando I de Moran de residuales OLS (mismo W, para comparar)...",
    )
    moran_ols = moran_i_manual(resid_ols, coords)

    resultado = {
        "n_hexagonos": len(df_joined),
        "mgwr": {
            "r2_global_no_ajustado": r2_mgwr,
            "ss_res": ss_res_mgwr,
            "ss_tot": ss_tot_mgwr,
            "moran_i_residuales": moran_mgwr,
            "nota": (
                "R2 global NO ajustado por grados de libertad efectivos (ENP). No es el R2 "
                "que devolveria MGWR.fit() (ENP_j/CCT) -- ese calculo no se corrio (ver Hallazgo 9, "
                "requeriria re-correr 04_run_model.py --con-diagnosticos-enp desde cero, ~28.5 min + "
                "un .fit() de duracion desconocida, nunca completado en ningun intento real hasta ahora)."
            ),
        },
        "ols_referencia": {**ols_resultado, "moran_i_residuales": moran_ols},
    }

    output_path = DATA_INTERIM_DIR / "diagnosticos_ajuste_v3.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(resultado, f, indent=2, ensure_ascii=False)

    elapsed = time.perf_counter() - t0

    print("\n" + "=" * 70)
    print(f"RESUMEN -- {SCRIPT_NAME} (solo lectura, no toca checkpoint v3 ni Postgres)")
    print("=" * 70)
    print(f"N hexagonos: {len(df_joined)}")
    print()
    print("MGWR (checkpoint v3 ya cerrado):")
    print(f"  R2 global (NO ajustado por ENP): {r2_mgwr:.4f}")
    print(f"  I de Moran de residuales (y-predy): I={moran_mgwr['I']:.4f}  "
          f"(esperado bajo H0={moran_mgwr['I_esperado_bajo_h0']:.4f})  "
          f"p(permutacion, {MORAN_N_PERMUTATIONS} iter)={moran_mgwr['p_value_permutacion']:.4f}")
    print()
    print(f"OLS de referencia (mismas {len(PTNA_QUALITY_COLUMNS)} variables X, mismo Y):")
    print(f"  R2: {ols_resultado['r2']:.4f}")
    print(f"  AIC: {ols_resultado['aic']:.2f}   AICc: {ols_resultado['aicc']:.2f}")
    print(f"  I de Moran de residuales: I={moran_ols['I']:.4f}  "
          f"p(permutacion, {MORAN_N_PERMUTATIONS} iter)={moran_ols['p_value_permutacion']:.4f}")
    print()
    print(f"AVISO: no se calculo AICc del MGWR (requiere ENP_j/CCT via MGWR.fit(), fuera de alcance "
          f"de este script -- ver docstring).")
    print(f"\nResultado guardado en: {output_path}")
    print(f"Tiempo total: {elapsed:.1f} s")
    print("=" * 70)


if __name__ == "__main__":
    main()
