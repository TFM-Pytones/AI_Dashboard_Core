"""
run_validation.py
-----------------
Pipeline completo de validación en DOS NIVELES + análisis de lead-time:

  NIVEL 1 — ERA5 vs Agrocabildo
    Valida el bias de terreno y la representación espacial del modelo ECMWF.
    Es la validación "optimista": ERA5 (reanálisis) asimila observaciones pasadas
    y es más preciso que un forecast real. Sirve como cota inferior del error.

  NIVEL 2 — Historical Forecast vs Agrocabildo
    Valida la calidad REAL del modelo NWP operacional (mismo que producción).
    No usa reanálisis: son los outputs que el modelo generó en tiempo real.
    Esta es la validación correcta para justificar el uso en producción.

  ANÁLISIS LEAD-TIME — Error vs Horizonte de predicción
    Usando Previous Model Runs, mide cómo crece el error al predecir más lejos:
    D+1, D+3, D+7. Clave para calibrar la confianza según el horizonte.

Uso:
  cd validation/
  python run_validation.py

Autor: TFM - AI Dashboard Core
"""

import logging
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from open_meteo_client import (
    VALIDATION_STATIONS, LEAD_TIME_HOURS, LEAD_TIME_LABELS,
    download_era5land_for_stations,
    download_historical_forecast_for_stations,
    download_leadtime_samples,
)
from prepare_station_data import prepare_all_stations, STATION_NAMES

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("Validation")

# ──────────────────────────────────────────────
# Configuración
# ──────────────────────────────────────────────
VALIDATION_START = "2022-01-01"
VALIDATION_END   = "2024-12-31"

BASE_DIR         = Path(__file__).parent.parent
RESULTS_DIR      = BASE_DIR / "validation" / "results"
STATION_DIR      = RESULTS_DIR / "station"
ERA5LAND_DIR     = RESULTS_DIR / "era5land"
HIST_FC_DIR      = RESULTS_DIR / "hist_forecast"
LEADTIME_DIR     = RESULTS_DIR / "leadtime"
ALIGNED_DIR      = RESULTS_DIR / "aligned"
METRICS_L1_FILE  = RESULTS_DIR / "metrics_level1_era5land.csv"
METRICS_L2_FILE  = RESULTS_DIR / "metrics_level2_hist_forecast.csv"
METRICS_LT_FILE  = RESULTS_DIR / "metrics_leadtime.csv"

VARIABLES = {
    "TEMP": "°C",
    "HUM":  "%",
    "RAIN": "mm/h",
    "WSP":  "m/s",
    "WDR":  "°",
    "RAD":  "W/m²",
}

ALTITUDES = {2: 95, 7: 214, 11: 69, 13: 1258}

# Criterios de aceptación del TFM
THRESHOLDS = {
    "TEMP": (2.5,  0.70),
    "HUM":  (15.0, 0.70),
    "RAIN": (0.2,  0.50),  # Tratado como categórico (MAE es 1-Accuracy, R2 es F1-Score)
    "WSP":  (2.5,  0.60),
    "WDR":  (35.0, 0.50),
    "RAD":  (50.0, 0.85),
}


# ──────────────────────────────────────────────
# Funciones de métricas
# ──────────────────────────────────────────────

def circular_mae(obs: np.ndarray, pred: np.ndarray) -> float:
    """MAE circular para dirección del viento (grados 0-360)."""
    diff = np.abs(obs - pred) % 360
    diff = np.where(diff > 180, 360 - diff, diff)
    return float(np.nanmean(diff))


def circular_rmse(obs: np.ndarray, pred: np.ndarray) -> float:
    diff = np.abs(obs - pred) % 360
    diff = np.where(diff > 180, 360 - diff, diff)
    return float(np.sqrt(np.nanmean(diff ** 2)))


def compute_metrics(obs: pd.Series, pred: pd.Series, variable: str) -> dict:
    """
    Calcula MAE, RMSE, Bias, R², MAPE para un par (observado, predicho).
    Para WDR usa métricas circulares.
    """
    aligned = pd.concat([obs.rename("obs"), pred.rename("pred")], axis=1).dropna()
    n = len(aligned)
    if n < 10:
        return {"MAE": np.nan, "RMSE": np.nan, "Bias": np.nan,
                "R2": np.nan, "MAPE": np.nan, "n_samples": n}

    o, p = aligned["obs"].values, aligned["pred"].values

    if variable == "WDR":
        mae  = circular_mae(o, p)
        rmse = circular_rmse(o, p)
        bias = float(np.nanmean(p - o))
        # Correlación circular via vectores unitarios
        o_rad, p_rad = np.deg2rad(o), np.deg2rad(p)
        dot = np.mean(np.cos(o_rad) * np.cos(p_rad) + np.sin(o_rad) * np.sin(p_rad))
        r2  = float(dot ** 2)
        mape = np.nan
    elif variable == "RAIN":
        # Evaluación categórica para eventos de lluvia (> 0.1 mm)
        threshold = 0.1
        o_bin = (o > threshold).astype(int)
        p_bin = (p > threshold).astype(int)
        
        from sklearn.metrics import accuracy_score, f1_score
        acc = float(accuracy_score(o_bin, p_bin))
        f1 = float(f1_score(o_bin, p_bin, zero_division=0))
        
        mae  = 1.0 - acc  # Mapeamos Error Rate a MAE para compatibilidad
        rmse = 0.0
        bias = float(np.mean(p_bin - o_bin))
        r2   = f1         # Mapeamos F1-Score a R2 para compatibilidad
        mape = np.nan
    else:
        mae  = float(mean_absolute_error(o, p))
        rmse = float(np.sqrt(mean_squared_error(o, p)))
        bias = float(np.mean(p - o))
        r2   = float(r2_score(o, p))
        mask = np.abs(o) > 0.01
        mape = float(np.mean(np.abs((o[mask] - p[mask]) / o[mask])) * 100) if mask.sum() > 0 else np.nan

    return {"MAE": round(mae, 4), "RMSE": round(rmse, 4),
            "Bias": round(bias, 4), "R2": round(r2, 4),
            "MAPE": round(mape, 2) if not np.isnan(mape) else np.nan,
            "n_samples": n}


def _quality_flag(variable: str, mae: float, r2: float) -> str:
    """Devuelve el semáforo de calidad."""
    if variable not in THRESHOLDS:
        return "⚪"
    max_mae, min_r2 = THRESHOLDS[variable]
    try:
        ok_mae = float(mae) <= max_mae
        ok_r2  = float(r2)  >= min_r2
    except (ValueError, TypeError):
        return "⚪"
    if ok_mae and ok_r2:   return "🟢 OK"
    if ok_mae or ok_r2:    return "🟡 LÍMITE"
    return "🔴 REVISAR"


# ──────────────────────────────────────────────
# Alineado temporal
# ──────────────────────────────────────────────

def align_datasets(station_df: pd.DataFrame, source_df: pd.DataFrame) -> pd.DataFrame:
    """
    Inner join por timestamp UTC entre datos de estación y fuente satelital.
    Devuelve columnas: VAR_obs, VAR_sat para cada variable.
    """
    def _ensure_utc_index(df):
        if not isinstance(df.index, pd.DatetimeIndex):
            df = df.set_index("timestamp_utc")
        df.index = pd.DatetimeIndex(df.index).tz_localize("UTC") \
            if df.index.tz is None else pd.DatetimeIndex(df.index).tz_convert("UTC")
        return df

    st  = _ensure_utc_index(station_df.copy())
    sat = _ensure_utc_index(source_df.copy())

    vars_list = list(VARIABLES.keys())
    st  = st[[v for v in vars_list if v in st.columns]].rename(
        columns={v: f"{v}_obs" for v in vars_list})
    sat = sat[[v for v in vars_list if v in sat.columns]].rename(
        columns={v: f"{v}_sat" for v in vars_list})

    return st.join(sat, how="inner")


# ──────────────────────────────────────────────
# Cálculo de métricas para un nivel de validación
# ──────────────────────────────────────────────

def compute_level_metrics(
    station_dfs: dict,
    source_dfs: dict,
    level_label: str,
    aligned_suffix: str,
) -> pd.DataFrame:
    """
    Compara estaciones vs fuente satelital y devuelve DataFrame de métricas.
    Guarda los alineados en ALIGNED_DIR/{aligned_suffix}_{sid}.parquet.
    """
    ALIGNED_DIR.mkdir(parents=True, exist_ok=True)
    all_metrics = []

    for st_info in VALIDATION_STATIONS:
        sid  = st_info["id"]
        name = STATION_NAMES[sid]

        if sid not in station_dfs or sid not in source_dfs:
            logger.warning(f"[{level_label}] Estación {sid}: datos incompletos.")
            continue

        logger.info(f"\n[{level_label}] Estación {sid} ({name})")
        aligned = align_datasets(station_dfs[sid], source_dfs[sid])

        # Guardar alineados
        aligned_file = ALIGNED_DIR / f"{aligned_suffix}_{sid}.parquet"
        aligned.to_parquet(aligned_file)
        logger.info(f"  Datos alineados: {len(aligned):,} horas → {aligned_file.name}")

        for var, unit in VARIABLES.items():
            obs_col, sat_col = f"{var}_obs", f"{var}_sat"
            if obs_col not in aligned.columns or sat_col not in aligned.columns:
                continue

            m = compute_metrics(aligned[obs_col], aligned[sat_col], var)
            flag = _quality_flag(var, m.get("MAE"), m.get("R2"))
            icon = "✅" if "OK" in flag else ("⚠️" if "LÍMITE" in flag else "❌")
            logger.info(
                f"  {icon} {var:4s} ({unit:5s}): MAE={m['MAE']:.3f}  "
                f"RMSE={m['RMSE']:.3f}  Bias={m['Bias']:+.3f}  R²={m['R2']:.3f}")

            m.update({
                "level":        level_label,
                "station_id":   sid,
                "station_name": name,
                "altitud_m":    ALTITUDES[sid],
                "variable":     var,
                "unit":         unit,
                "lat":          st_info["latitud"],
                "lon":          st_info["longitud"],
                "calidad":      flag,
            })
            all_metrics.append(m)

    df = pd.DataFrame(all_metrics)
    col_order = ["level", "station_id", "station_name", "altitud_m",
                 "variable", "unit", "MAE", "RMSE", "Bias", "R2",
                 "MAPE", "n_samples", "calidad"]
    return df[[c for c in col_order if c in df.columns]]


# ──────────────────────────────────────────────
# Análisis de degradación por lead-time
# ──────────────────────────────────────────────

def compute_leadtime_metrics(
    station_dfs: dict,
    leadtime_dfs: dict,
) -> pd.DataFrame:
    """
    Compara las observaciones de las estaciones con los pronósticos históricos
    para D+1, D+3 y D+7. El DataFrame de lead-time tiene columnas VAR_dX
    (ej: TEMP_d1, HUM_d3...) que se comparan directamente con la observación.
    """
    all_metrics = []
    lead_days = [1, 3, 7]

    def _ensure_utc_index(df):
        if not isinstance(df.index, pd.DatetimeIndex):
            df = df.set_index("timestamp_utc")
        df.index = pd.DatetimeIndex(df.index).tz_localize("UTC") \
            if df.index.tz is None else pd.DatetimeIndex(df.index).tz_convert("UTC")
        return df

    for st_info in VALIDATION_STATIONS:
        sid  = st_info["id"]
        name = STATION_NAMES[sid]

        if sid not in station_dfs or sid not in leadtime_dfs:
            continue

        logger.info(f"\n[Lead-Time] Estación {sid} ({name})")

        st  = _ensure_utc_index(station_dfs[sid].copy())
        lt  = _ensure_utc_index(leadtime_dfs[sid].copy())

        merged = st.join(lt, how="inner", rsuffix="_lt")
        if len(merged) < 24:
            logger.warning(f"  Lead-Time: muy pocos registros alineados ({len(merged)}h)")
            continue

        logger.info(f"  Lead-Time: {len(merged):,} horas alineadas para comparación.")

        for day in lead_days:
            label = f"D+{day}"
            n_ok = 0
            for var, unit in VARIABLES.items():
                obs_col = var          # viene de station_df: TEMP, HUM...
                fc_col  = f"{var}_d{day}"  # viene de leadtime_df: TEMP_d1, HUM_d3...

                if obs_col not in merged.columns or fc_col not in merged.columns:
                    continue

                obs = merged[obs_col]
                fc  = merged[fc_col]
                m = compute_metrics(obs, fc, var)
                m.update({
                    "lead_time_h":    day * 24,
                    "lead_time_label": label,
                    "station_id":     sid,
                    "station_name":   name,
                    "altitud_m":      ALTITUDES[sid],
                    "variable":       var,
                    "unit":           unit,
                })
                all_metrics.append(m)
                n_ok += 1
                logger.info(
                    f"  {label} {var:4s} ({unit:5s}): "
                    f"MAE={m['MAE']:.3f}  RMSE={m['RMSE']:.3f}  "
                    f"Bias={m['Bias']:+.3f}  R²={m['R2']:.3f}"
                )

    df = pd.DataFrame(all_metrics)
    col_order = ["lead_time_h", "lead_time_label", "station_id", "station_name",
                 "altitud_m", "variable", "unit", "MAE", "RMSE", "Bias", "R2", "n_samples"]
    return df[[c for c in col_order if c in df.columns]]


# ──────────────────────────────────────────────
# Pipeline principal
# ──────────────────────────────────────────────

def run_validation():
    """Ejecuta el pipeline completo de validación en dos niveles + lead-time."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    # ── Preparar datos de estaciones ─────────────────────────────────────
    logger.info("\n" + "="*65)
    logger.info("PASO 1/4: Preparar datos de estaciones (Agrocabildo)")
    logger.info("="*65)
    station_dfs = prepare_all_stations(
        start_date=VALIDATION_START,
        end_date=VALIDATION_END,
        output_dir=STATION_DIR,
    )

    # ── NIVEL 1: ERA5-Land ────────────────────────────────────────────────
    logger.info("\n" + "="*65)
    logger.info("PASO 2/4: NIVEL 1 — ERA5-Land (reanálisis)")
    logger.info("  ⚠️  Validación de terrain bias. Artificialmente preciso.")
    logger.info("="*65)
    era5land_dfs = download_era5land_for_stations(
        VALIDATION_STATIONS,
        start_date=VALIDATION_START,
        end_date=VALIDATION_END,
        output_dir=ERA5LAND_DIR,
    )
    metrics_l1 = compute_level_metrics(
        station_dfs, era5land_dfs,
        level_label="L1_ERA5Land",
        aligned_suffix="aligned_l1",
    )
    metrics_l1.to_csv(METRICS_L1_FILE, index=False, float_format="%.4f")
    logger.info(f"\n  ✅ Nivel 1 exportado: {METRICS_L1_FILE}")

    # ── NIVEL 2: Historical Forecast ──────────────────────────────────────
    logger.info("\n" + "="*65)
    logger.info("PASO 3/4: NIVEL 2 — Historical Forecast (NWP real)")
    logger.info("  ✅ Mismos modelos que producción. Validación metodológicamente correcta.")
    logger.info("="*65)
    hist_fc_dfs = download_historical_forecast_for_stations(
        VALIDATION_STATIONS,
        start_date=VALIDATION_START,
        end_date=VALIDATION_END,
        model="gfs_seamless",
        output_dir=HIST_FC_DIR,
    )
    metrics_l2 = compute_level_metrics(
        station_dfs, hist_fc_dfs,
        level_label="L2_HistForecast",
        aligned_suffix="aligned_l2",
    )
    metrics_l2.to_csv(METRICS_L2_FILE, index=False, float_format="%.4f")
    logger.info(f"\n  ✅ Nivel 2 exportado: {METRICS_L2_FILE}")

    # ── Lead-Time Analysis ────────────────────────────────────────────────
    logger.info("\n" + "="*65)
    logger.info("PASO 4/4: Análisis Lead-Time (Previous Model Runs)")
    logger.info("  D+1 | D+3 | D+7 → curva de degradación del error")
    logger.info("="*65)
    leadtime_dfs = download_leadtime_samples(
        VALIDATION_STATIONS,
        start_date=VALIDATION_START,
        end_date=VALIDATION_END,
        lead_times_days=[1, 3, 7],
        model="gfs_seamless",
        output_dir=LEADTIME_DIR,
    )
    metrics_lt = compute_leadtime_metrics(station_dfs, leadtime_dfs)
    if not metrics_lt.empty:
        metrics_lt.to_csv(METRICS_LT_FILE, index=False, float_format="%.4f")
        logger.info(f"\n  ✅ Lead-time exportado: {METRICS_LT_FILE}")

    # ── Resumen comparativo L1 vs L2 ──────────────────────────────────────
    logger.info("\n" + "="*65)
    logger.info("RESUMEN COMPARATIVO: ERA5-Land (L1) vs Historical Forecast (L2)")
    logger.info("="*65)
    if not metrics_l1.empty and not metrics_l2.empty:
        combined = pd.concat([metrics_l1, metrics_l2], ignore_index=True)
        pivot = combined.pivot_table(
            index=["variable", "station_name"],
            columns="level",
            values="MAE",
        ).round(3)
        pivot.columns = ["ERA5-Land MAE (L1)", "Hist.Forecast MAE (L2)"]
        pivot["Δ MAE (L2-L1)"] = (
            pivot["Hist.Forecast MAE (L2)"] - pivot["ERA5-Land MAE (L1)"]
        ).round(3)
        print("\n" + pivot.to_string())
        print("\n⚡ Δ MAE positivo = el forecast real es peor que el reanálisis (esperable).")
        print("   Δ MAE muy grande = el modelo tiene dificultades en esa variable/zona.")

    return metrics_l1, metrics_l2, metrics_lt


if __name__ == "__main__":
    m1, m2, mlt = run_validation()
    print("\n✅ Validación completa.")
    print(f"  Nivel 1 (ERA5-Land):        {METRICS_L1_FILE.resolve()}")
    print(f"  Nivel 2 (Hist. Forecast):   {METRICS_L2_FILE.resolve()}")
    print(f"  Lead-Time:                  {METRICS_LT_FILE.resolve()}")
