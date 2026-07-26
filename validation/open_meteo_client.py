"""
open_meteo_client.py
--------------------
Cliente para la API de Open-Meteo con dos niveles de validación:

  NIVEL 1 — ERA5 (reanálisis):
    URL: archive-api.open-meteo.com/v1/archive
    → "Mejor estimado del pasado" con asimilación de observaciones.
    → Sirve para validar bias de terreno y representación espacial.
    → NO es un forecast real: es artificialmente preciso.

  NIVEL 2 — Historical Forecast (NWP real):
    URL: historical-forecast-api.open-meteo.com/v1/forecast
    → Outputs reales de los modelos NWP tal como corrieron en su momento.
    → Misma fuente que se usa en producción (IFS/GFS/AROME).
    → Permite medir el error real del forecast a distintos horizontes.

  PRODUCCIÓN — Best Match Forecast (predicción futura):
    URL: api.open-meteo.com/v1/forecast
    → Predicción de hasta 16 días (mismos modelos que Nivel 2).

  ANÁLISIS LEAD-TIME — Previous Model Runs:
    URL: previous-runs-api.open-meteo.com/v1/forecast
    → Obtiene la serie completa histórica con lead-time en días.
    → Permite construir la curva de degradación del error vs horizonte.

Autor: TFM - AI Dashboard Core
"""

import logging
import time
from pathlib import Path
from typing import Optional

import pandas as pd
import requests_cache
from retry_requests import retry

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("OpenMeteoClient")

# ──────────────────────────────────────────────
# Configuración de caché HTTP (evita descargas repetidas)
# ──────────────────────────────────────────────
CACHE_DIR = Path(__file__).parent / ".cache"
CACHE_DIR.mkdir(exist_ok=True)

_cache_session = requests_cache.CachedSession(
    cache_name=str(CACHE_DIR / "openmeteo_cache"),
    expire_after=3600 * 24 * 7,   # 7 días: datos históricos no cambian
    backend="sqlite",
)
_retry_session = retry(_cache_session, retries=5, backoff_factor=0.4)

# Caché más corta para datos de forecast (se actualizan con frecuencia)
_forecast_session = requests_cache.CachedSession(
    cache_name=str(CACHE_DIR / "openmeteo_forecast_cache"),
    expire_after=3600,   # 1 h
    backend="sqlite",
)
_forecast_retry_session = retry(_forecast_session, retries=5, backoff_factor=0.4)

# ──────────────────────────────────────────────
# Variables y mapeo de alias
# ──────────────────────────────────────────────
HOURLY_VARS = [
    "temperature_2m",
    "relative_humidity_2m",
    "precipitation",
    "wind_speed_10m",
    "wind_direction_10m",
    "shortwave_radiation",
]

OPENMETEO_TO_ALIAS = {
    "temperature_2m":       "TEMP",
    "relative_humidity_2m": "HUM",
    "precipitation":        "RAIN",
    "wind_speed_10m":       "WSP",
    "wind_direction_10m":   "WDR",
    "shortwave_radiation":  "RAD",
}

# Horizontes de predicción a analizar (en horas)
# D+1=24h, D+3=72h, D+7=168h, D+14=336h
LEAD_TIME_HOURS = [24, 72, 168, 336]
LEAD_TIME_LABELS = {24: "D+1", 72: "D+3", 168: "D+7", 336: "D+14"}


# ──────────────────────────────────────────────
# Función auxiliar común de parseo de respuesta
# ──────────────────────────────────────────────
def _parse_hourly_response(data: dict, source_label: str = "") -> pd.DataFrame:
    """Parsea la respuesta JSON de Open-Meteo y devuelve un DataFrame limpio."""
    hourly = data.get("hourly", {})
    if not hourly:
        logger.warning(f"Respuesta vacía de Open-Meteo [{source_label}].")
        return pd.DataFrame()

    df = pd.DataFrame(hourly)
    df = df.rename(columns={"time": "timestamp_utc"})
    df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True)
    df = df.rename(columns=OPENMETEO_TO_ALIAS)

    # Seleccionar solo las columnas de variables (las que estén disponibles)
    alias_cols = [a for a in OPENMETEO_TO_ALIAS.values() if a in df.columns]
    df = df[["timestamp_utc"] + alias_cols].set_index("timestamp_utc")
    return df


def _common_params(lat: float, lon: float) -> dict:
    """Parámetros comunes a todas las llamadas."""
    return {
        "latitude": lat,
        "longitude": lon,
        "hourly": ",".join(HOURLY_VARS),
        "timezone": "UTC",
        "wind_speed_unit": "ms",
        "precipitation_unit": "mm",
    }


# ──────────────────────────────────────────────
# NIVEL 1 — ERA5-Land (reanálisis)
# ──────────────────────────────────────────────
def _get_era5land(lat: float, lon: float, start_date: str, end_date: str) -> pd.DataFrame:
    """
    Datos ERA5 (reanálisis ECMWF). Resolución ~25 km, 6 variables completas.

    Nota: se usa ERA5 sin forzar 'era5_land' porque este último solo devuelve
    temperatura y humedad en el endpoint archive. ERA5 completo proporciona
    las 6 variables requeridas (TEMP, HUM, RAIN, WSP, WDR, RAD) y sigue
    siendo un reanálisis válido para Nivel 1.

    Uso: benchmark de bias de terreno (Nivel 1 de validación).
    """
    url = "https://archive-api.open-meteo.com/v1/archive"
    # Sin especificar 'models' se usa ERA5 por defecto con todas las variables
    params = {**_common_params(lat, lon),
              "start_date": start_date, "end_date": end_date}

    logger.info(f"[ERA5] [{lat},{lon}] {start_date} → {end_date}")
    resp = _retry_session.get(url, params=params, timeout=60)
    resp.raise_for_status()
    df = _parse_hourly_response(resp.json(), "ERA5")
    logger.info(f"  → {len(df):,} registros. Columnas: {list(df.columns)}")
    return df


# ──────────────────────────────────────────────
# NIVEL 2 — Historical Forecast (NWP real)
# ──────────────────────────────────────────────
def _get_historical_forecast(
    lat: float,
    lon: float,
    start_date: str,
    end_date: str,
    model: str = "best_match",
) -> pd.DataFrame:
    """
    Outputs reales de los modelos NWP (IFS, GFS, AROME...) tal como
    corrieron operacionalmente. NO es reanálisis.

    Es el mismo modelo que se usa en producción para predicción futura,
    por lo que es la fuente correcta para validar la calidad real del forecast
    a ~0-12h de lead time (el output más reciente de cada hora).

    Uso: Nivel 2 de validación (calidad operacional del modelo).
    """
    url = "https://historical-forecast-api.open-meteo.com/v1/forecast"
    params = {**_common_params(lat, lon),
              "start_date": start_date, "end_date": end_date,
              "models": model}

    logger.info(f"[HistForecast/{model}] [{lat},{lon}] {start_date} → {end_date}")
    resp = _retry_session.get(url, params=params, timeout=60)
    resp.raise_for_status()
    df = _parse_hourly_response(resp.json(), f"HistForecast/{model}")
    logger.info(f"  → {len(df):,} registros.")
    return df


# ──────────────────────────────────────────────
# ANÁLISIS LEAD-TIME — Previous Model Runs
# ──────────────────────────────────────────────
def _get_historical_previous_runs(
    lat: float,
    lon: float,
    start_date: str,
    end_date: str,
    lead_times_days: list[int] = [1, 3, 7],
    model: str = "best_match",
) -> pd.DataFrame:
    """
    Obtiene la serie temporal completa de predicciones pasadas (2022-2024)
    para múltiples horizontes temporales (lead times en días).

    Usa las variables de sufijo _previous_dayX (ej: temperature_2m_previous_day1).
    Retorna un DataFrame indexado por timestamp_utc con columnas:
      TEMP_d1, TEMP_d3, TEMP_d7, HUM_d1...
    """
    url = "https://previous-runs-api.open-meteo.com/v1/forecast"

    # Construir lista de variables con sufijos
    target_vars = []
    for var in HOURLY_VARS:
        for day in lead_times_days:
            target_vars.append(f"{var}_previous_day{day}")

    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start_date,
        "end_date": end_date,
        "hourly": ",".join(target_vars),
        "models": model,
        "timezone": "UTC",
        "wind_speed_unit": "ms",
        "precipitation_unit": "mm",
    }

    logger.info(f"[PrevRuns/NWP] [{lat},{lon}] {start_date} → {end_date} (D+1, D+3, D+7)")
    resp = _retry_session.get(url, params=params, timeout=120)
    resp.raise_for_status()
    data = resp.json()

    hourly = data.get("hourly", {})
    if not hourly:
        logger.warning("Respuesta Previous Runs vacía.")
        return pd.DataFrame()

    df = pd.DataFrame(hourly)
    df = df.rename(columns={"time": "timestamp_utc"})
    df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True)
    df = df.set_index("timestamp_utc")

    # Renombrar columnas a formato alias_dX (ej: TEMP_d1)
    rename_map = {}
    for om_var, alias in OPENMETEO_TO_ALIAS.items():
        for day in lead_times_days:
            rename_map[f"{om_var}_previous_day{day}"] = f"{alias}_d{day}"

    df = df.rename(columns=rename_map)
    # Dejar solo las columnas mapeadas
    df = df[[col for col in rename_map.values() if col in df.columns]]

    logger.info(f"  → {len(df):,} registros de lead-time extraídos.")
    return df


# ──────────────────────────────────────────────
# PRODUCCIÓN — Best Match Forecast (futuro)
# ──────────────────────────────────────────────
def _get_forecast(
    lat: float,
    lon: float,
    forecast_days: int = 16,
    past_days: int = 0,
) -> pd.DataFrame:
    """
    Predicción Best Match hasta 16 días futuros.
    Selección automática: ECMWF IFS + GFS + AROME para Canarias.
    """
    url = "https://api.open-meteo.com/v1/forecast"
    params = {**_common_params(lat, lon),
              "forecast_days": forecast_days, "past_days": past_days}

    logger.info(f"[Forecast] [{lat},{lon}] +{forecast_days}d, -{past_days}d")
    resp = _forecast_retry_session.get(url, params=params, timeout=60)
    resp.raise_for_status()
    df = _parse_hourly_response(resp.json(), "Forecast")
    logger.info(f"  → {len(df):,} registros.")
    return df


# ──────────────────────────────────────────────
# Funciones de descarga por lote (con caché parquet)
# ──────────────────────────────────────────────

def _download_for_stations(
    stations: list[dict],
    fetch_fn,
    cache_prefix: str,
    output_dir: Path,
    **fetch_kwargs,
) -> dict[int, pd.DataFrame]:
    """Función genérica de descarga por lote con caché en parquet."""
    output_dir.mkdir(parents=True, exist_ok=True)
    results = {}

    for st in stations:
        sid    = st["id"]
        nombre = st["nombre"]
        lat    = st["latitud"]
        lon    = st["longitud"]

        cache_file = output_dir / f"{cache_prefix}_{sid}.parquet"
        if cache_file.exists():
            logger.info(f"[{sid} {nombre}] Caché: {cache_file.name}")
            results[sid] = pd.read_parquet(cache_file)
            continue

        try:
            df = fetch_fn(lat, lon, **fetch_kwargs)
            if not df.empty:
                df["id_estacion"] = sid
                df["nombre"]      = nombre
                df.to_parquet(cache_file)
                logger.info(f"  → Guardado: {cache_file.name}")
                results[sid] = df
        except Exception as e:
            logger.error(f"Error estación {sid} ({nombre}): {e}")

        time.sleep(1.2)   # Respetar rate limit Open-Meteo

    return results


def download_era5land_for_stations(
    stations: list[dict],
    start_date: str = "2022-01-01",
    end_date: str   = "2024-12-31",
    output_dir: Optional[Path] = None,
) -> dict[int, pd.DataFrame]:
    """Nivel 1: Descarga ERA5 (reanálisis) para las estaciones de validación."""
    out = output_dir or Path(__file__).parent / "results" / "era5land"
    return _download_for_stations(
        stations, _get_era5land, "era5land",
        Path(out), start_date=start_date, end_date=end_date,
    )


def download_historical_forecast_for_stations(
    stations: list[dict],
    start_date: str = "2022-01-01",
    end_date: str   = "2024-12-31",
    model: str      = "best_match",
    output_dir: Optional[Path] = None,
) -> dict[int, pd.DataFrame]:
    """
    Nivel 2: Descarga el Historical Forecast (NWP real operacional)
    para las estaciones de validación.
    Mismo modelo que se usará en producción para predicciones futuras.
    """
    out = output_dir or Path(__file__).parent / "results" / "hist_forecast"
    return _download_for_stations(
        stations, _get_historical_forecast, f"hist_forecast_{model}",
        Path(out), start_date=start_date, end_date=end_date, model=model,
    )


def download_leadtime_samples(
    stations: list[dict],
    start_date: str = "2022-01-01",
    end_date: str   = "2024-12-31",
    lead_times_days: list[int] = [1, 3, 7],
    model: str = "best_match",
    output_dir: Optional[Path] = None,
) -> dict[int, pd.DataFrame]:
    """
    Análisis de lead-time: obtiene la serie histórica completa de predicciones
    con lead-time de D+1, D+3 y D+7 para las estaciones.

    Retorna: dict {station_id: DataFrame}
    """
    out = output_dir or Path(__file__).parent / "results" / "leadtime"
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)

    results: dict[int, pd.DataFrame] = {}

    for st in stations:
        sid    = st["id"]
        nombre = st["nombre"]
        lat    = st["latitud"]
        lon    = st["longitud"]

        cache_f = out / f"leadtime_historical_{sid}.parquet"

        if cache_f.exists():
            logger.info(f"[{sid} {nombre}] Lead-Time: cargando caché → {cache_f.name}")
            results[sid] = pd.read_parquet(cache_f)
            continue

        try:
            df = _get_historical_previous_runs(
                lat, lon, start_date, end_date,
                lead_times_days=lead_times_days, model=model
            )
            if not df.empty:
                df["id_estacion"] = sid
                df["nombre"]      = nombre
                df.to_parquet(cache_f)
                logger.info(f"  → Guardado: {cache_f.name}")
                results[sid] = df
        except Exception as e:
            logger.error(f"Error descargando previous runs históricos para estación {sid}: {e}")

        time.sleep(1.5)

    return results


def download_forecast_for_stations(
    stations: list[dict],
    forecast_days: int = 16,
    output_dir: Optional[Path] = None,
) -> dict[int, pd.DataFrame]:
    """Producción: Descarga predicción Best Match para las estaciones."""
    results = {}
    for st in stations:
        sid    = st["id"]
        nombre = st["nombre"]
        try:
            df = _get_forecast(st["latitud"], st["longitud"],
                               forecast_days=forecast_days)
            if not df.empty:
                df["id_estacion"] = sid
                df["nombre"]      = nombre
                results[sid]      = df
        except Exception as e:
            logger.error(f"Error forecast estación {sid}: {e}")
        time.sleep(0.5)

    if output_dir:
        p = Path(output_dir)
        p.mkdir(parents=True, exist_ok=True)
        for sid, df in results.items():
            df.to_parquet(p / f"forecast_{sid}.parquet")

    return results


# ──────────────────────────────────────────────
# Estaciones de validación
# ──────────────────────────────────────────────
VALIDATION_STATIONS = [
    {"id": 2,  "nombre": "GALLETAS",  "latitud": 28.0406, "longitud": -16.6532},
    {"id": 7,  "nombre": "OROTAV01",  "latitud": 28.4066, "longitud": -16.5143},
    {"id": 11, "nombre": "TEJINA01",  "latitud": 28.5324, "longitud": -16.3955},
    {"id": 13, "nombre": "VILAFLOR",  "latitud": 28.1442, "longitud": -16.6281},
]

if __name__ == "__main__":
    # Test rápido (1 semana) para las 4 estaciones
    from pathlib import Path
    test_period = {"start_date": "2023-07-01", "end_date": "2023-07-07"}

    print("=== Test ERA5-Land (Nivel 1) ===")
    dfs_l1 = download_era5land_for_stations(
        VALIDATION_STATIONS, **test_period,
        output_dir=Path("results/era5land"))
    for sid, df in dfs_l1.items():
        print(f"  Estación {sid}: {df.shape}")

    print("\n=== Test Historical Forecast (Nivel 2) ===")
    dfs_l2 = download_historical_forecast_for_stations(
        VALIDATION_STATIONS, **test_period,
        output_dir=Path("results/hist_forecast"))
    for sid, df in dfs_l2.items():
        print(f"  Estación {sid}: {df.shape}")

    print("\n=== Test Lead-Time (Previous Runs) ===")
    lt = download_leadtime_samples(
        VALIDATION_STATIONS[:1],   # Solo 1 estación en test
        lead_times_days=[1, 3, 7],
        output_dir=Path("results/leadtime"))
    for sid, df in lt.items():
        print(f"  Estación {sid}: {df.shape} (columnas: {list(df.columns)})")
