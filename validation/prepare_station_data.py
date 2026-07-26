"""
prepare_station_data.py
-----------------------
Extrae y prepara los datos históricos de las 4 estaciones de validación
desde el fichero principal clima_horario_agrocabildo.parquet.

El parquet principal tiene esquema:
  id_estacion | id_sensor | timestamp (UTC) | valor_observado | valor_validado | es_validado

Este script:
1. Lee el parquet en chunks (es muy grande, ~235 MB)
2. Filtra las 4 estaciones y sus 6 sensores de interés
3. Hace un pivot: una columna por alias (TEMP, HUM, RAIN, WSP, WDR, RAD)
4. Resamplea a 1H (media, excepto RAIN que es suma)
5. Filtra el rango 2022-2024
6. Exporta un parquet por estación en validation/results/station/

Autor: TFM - AI Dashboard Core
"""

import logging
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("PrepareStationData")

# ──────────────────────────────────────────────
# Configuración
# ──────────────────────────────────────────────
BASE_DIR     = Path(__file__).parent.parent
PARQUET_PATH = BASE_DIR / "data" / "clima_horario_agrocabildo.parquet"
OUTPUT_DIR   = BASE_DIR / "validation" / "results" / "station"

VALIDATION_START = "2022-01-01"
VALIDATION_END   = "2024-12-31"

# Mapa: id_estacion → {alias: id_sensor}
STATION_SENSOR_MAP: dict[int, dict[str, int]] = {
    2: {   # GALLETAS – Arona 95m
        "TEMP": 352,
        "HUM":  353,
        "RAIN": 355,
        "WSP":  350,
        "WDR":  351,
        "RAD":  358,
    },
    7: {   # OROTAV01 – La Orotava 214m
        "TEMP": 668,
        "HUM":  669,
        "RAIN": 671,
        "WSP":  666,
        "WDR":  667,
        "RAD":  674,
    },
    11: {  # TEJINA01 – S.C. La Laguna 69m
        "TEMP": 789,
        "HUM":  790,
        "RAIN": 792,
        "WSP":  787,
        "WDR":  788,
        "RAD":  795,
    },
    13: {  # VILAFLOR – Vilaflor 1258m
        "TEMP": 307,
        "HUM":  308,
        "RAIN": 310,
        "WSP":  305,
        "WDR":  306,
        "RAD":  313,
    },
}

STATION_NAMES = {2: "GALLETAS", 7: "OROTAV01", 11: "TEJINA01", 13: "VILAFLOR"}

# Todos los sensor IDs que nos interesan (para filtrado eficiente)
ALL_SENSOR_IDS = set()
SENSOR_TO_ALIAS: dict[int, str] = {}
SENSOR_TO_STATION: dict[int, int] = {}

for station_id, sensors in STATION_SENSOR_MAP.items():
    for alias, sensor_id in sensors.items():
        ALL_SENSOR_IDS.add(sensor_id)
        SENSOR_TO_ALIAS[sensor_id] = alias
        SENSOR_TO_STATION[sensor_id] = station_id

ALL_STATION_IDS = list(STATION_SENSOR_MAP.keys())


def _circular_mean(series: pd.Series) -> float:
    """Media circular para dirección del viento (grados)."""
    import numpy as np
    rad = np.deg2rad(series.dropna())
    if len(rad) == 0:
        return float("nan")
    sin_mean = rad.apply(np.sin).mean()
    cos_mean = rad.apply(np.cos).mean()
    angle = np.rad2deg(np.arctan2(sin_mean, cos_mean))
    return float(angle % 360)


def load_and_filter_parquet() -> pd.DataFrame:
    """
    Lee el parquet grande en chunks usando PyArrow con filtros push-down
    (mucho más eficiente que leer todo en pandas).
    """
    logger.info(f"Leyendo {PARQUET_PATH} con filtros push-down...")

    ts_start = pd.Timestamp(VALIDATION_START, tz="UTC")
    ts_end   = pd.Timestamp(VALIDATION_END + " 23:59:59", tz="UTC")

    # Filtros de PyArrow (predicate pushdown → solo lee las filas necesarias)
    filters = [
        ("id_estacion", "in", ALL_STATION_IDS),
        ("id_sensor",   "in", list(ALL_SENSOR_IDS)),
        ("timestamp",   ">=", ts_start),
        ("timestamp",   "<=", ts_end),
    ]

    table = pq.read_table(
        PARQUET_PATH,
        filters=filters,
        columns=["id_estacion", "id_sensor", "timestamp",
                 "valor_observado", "valor_validado", "es_validado"],
    )
    df = table.to_pandas()
    logger.info(f"  → {len(df):,} registros tras filtrado.")
    return df


def build_station_hourly(df: pd.DataFrame, station_id: int) -> pd.DataFrame:
    """
    Para una estación, hace el pivot sensor → columna alias
    y resamplea a 1H.
    """
    sensors = STATION_SENSOR_MAP[station_id]
    sensor_ids = list(sensors.values())

    st_df = df[df["id_estacion"] == station_id].copy()
    st_df = st_df[st_df["id_sensor"].isin(sensor_ids)].copy()

    if st_df.empty:
        logger.warning(f"Estación {station_id}: sin datos en el rango.")
        return pd.DataFrame()

    # Usar valor_validado si disponible, si no valor_observado
    st_df["valor"] = st_df["valor_validado"].fillna(st_df["valor_observado"])

    # Añadir columna alias
    st_df["alias"] = st_df["id_sensor"].map(SENSOR_TO_ALIAS)

    # Pivot: timestamp × alias → valor
    # (puede haber sub-lecturas por minuto → agrupar primero)
    st_df = st_df.set_index("timestamp")
    st_df.index = pd.DatetimeIndex(st_df.index).tz_convert("UTC")

    # Resampleo a 1H: media para todo excepto RAIN (suma acumulada)
    pivoted_parts = []
    for alias, sid in sensors.items():
        sensor_df = st_df[st_df["id_sensor"] == sid]["valor"].rename(alias)
        if alias == "RAIN":
            resampled = sensor_df.resample("1h").sum(min_count=1)
        elif alias == "WDR":
            # Media circular para dirección de viento
            def circ_resample(s):
                import numpy as np
                rad = s.dropna().map(lambda x: x * 3.14159265 / 180)
                if len(rad) == 0:
                    return float("nan")
                sin_m = rad.map(lambda r: __import__("numpy").sin(r)).mean()
                cos_m = rad.map(lambda r: __import__("numpy").cos(r)).mean()
                angle = __import__("numpy").arctan2(sin_m, cos_m) * 180 / 3.14159265
                return float(angle % 360)

            resampled = sensor_df.resample("1h").apply(circ_resample)
        else:
            resampled = sensor_df.resample("1h").mean()

        pivoted_parts.append(resampled)

    hourly = pd.concat(pivoted_parts, axis=1)
    hourly.index.name = "timestamp_utc"

    # Añadir metadatos
    hourly["id_estacion"] = station_id
    hourly["nombre"]      = STATION_NAMES[station_id]

    logger.info(f"  Estación {station_id} ({STATION_NAMES[station_id]}): "
                f"{len(hourly):,} horas, {hourly.isna().mean().to_dict()}")
    return hourly


def prepare_all_stations(
    start_date: str = VALIDATION_START,
    end_date: str   = VALIDATION_END,
    output_dir: Path = OUTPUT_DIR,
) -> dict[int, pd.DataFrame]:
    """Ejecuta el pipeline completo y guarda los resultados."""
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("=== Inicio preparación datos de estaciones ===")
    raw_df = load_and_filter_parquet()

    results = {}
    for station_id in ALL_STATION_IDS:
        out_file = output_dir / f"station_{station_id}_hourly.parquet"

        if out_file.exists():
            logger.info(f"Estación {station_id}: cargando desde caché {out_file.name}")
            results[station_id] = pd.read_parquet(out_file)
            continue

        logger.info(f"\nProcesando estación {station_id} ({STATION_NAMES[station_id]})...")
        hourly = build_station_hourly(raw_df, station_id)

        if not hourly.empty:
            hourly.to_parquet(out_file)
            logger.info(f"  → Guardado: {out_file.name}")
            results[station_id] = hourly

    logger.info("\n=== Preparación completada ===")
    for sid, df in results.items():
        pct_nan = df[["TEMP","HUM","RAIN","WSP","WDR","RAD"]].isna().mean().mean()
        logger.info(f"  Estación {sid} ({STATION_NAMES[sid]}): "
                    f"{len(df):,} horas | NaN medio: {pct_nan:.1%}")

    return results


if __name__ == "__main__":
    dfs = prepare_all_stations()
    for sid, df in dfs.items():
        print(f"\n--- Estación {sid} ({STATION_NAMES[sid]}) ---")
        print(df[["TEMP","HUM","RAIN","WSP","WDR","RAD"]].describe().round(2))
