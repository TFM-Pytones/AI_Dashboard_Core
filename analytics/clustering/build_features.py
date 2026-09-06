"""
build_features.py
------------------
Issue #25 -- Preparacion de Datos Geometricos (Features para Clustering).

Construye la tabla de features geoespaciales consolidadas por hexagono H3
que sirve como input al clustering HDBSCAN (Issue #26) y a la deteccion de
brechas de mercado / MGWR (Issues #27, #32).

IMPORTANTE: gold.features_h3 ya existia en la base de datos compartida antes
de este script (3062 filas), generada por un proceso que no esta en git.
Este script la ACTUALIZA (misma tabla, mismos nombres de columna) en vez de
crear una tabla paralela, añadiendo las dos piezas que le faltaban:
`sentimiento_medio` (Issue #20) y `viirs_mean` (Issue #24). Todo el resto de
columnas (elevation_mean, ndvi_mean, ndbi_mean, n_alojamientos,
n_paradas_transporte, is_protected_area, centroid_lon/lat...) se recalculan
igual que antes para mantener una unica fuente de verdad consistente.

Fuentes reales (no las tablas oro.*/plata.* sueltas que describe el plan
original, que nunca llegaron a construirse asi): casi todo ya vive
consolidado en gold.gold_h3_master (alojamiento, paradas de bus, MDT,
NDVI/NDBI/VIIRS -- ver Issues #22/#23/#24), asi que este script solo necesita
unir esa tabla con gold.gold_sentimiento_h3 (Issue #20), en vez de repetir
joins espaciales que gold_h3_master ya resuelve.

Uso:
    python analytics/clustering/build_features.py
    python analytics/clustering/build_features.py --scaler minmax
"""

import os
import argparse
import logging

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sklearn.preprocessing import StandardScaler, MinMaxScaler

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Columnas "pass-through" (no entran al clustering, solo identifican/describen
# el hexagono). Nombres iguales a los de la gold.features_h3 ya existente.
PASSTHROUGH_COLUMNS = ["h3_index", "centroid_lon", "centroid_lat", "is_protected_area"]

# Columnas que SI entran al clustering (se normalizan). Ver Issue #25:
# sentimiento_h3, ndvi_h3, ndbi_h3, viirs_h3, mdt_stats (altitud/pendiente/
# orientacion/hillshade), alojamientos (count), paradas_transporte (count).
# sentimiento_medio y viirs_mean son las dos columnas nuevas de este cambio;
# el resto ya existian en gold.features_h3.
FEATURE_COLUMNS = [
    "elevation_mean",
    "slope_mean",
    "aspect_mean",
    "hillshade_mean",
    "ndvi_mean",
    "ndbi_mean",
    "n_alojamientos",
    "n_paradas_transporte",
    "sentimiento_medio",
    "viirs_mean",
]

MAX_NAN_RATIO = 0.5  # Issue #25: excluir hexagonos con > 50% de features nulas


def get_pg_engine():
    load_dotenv()
    PG_USER = os.getenv("AZURE_DB_USER")
    PG_PASS = os.getenv("AZURE_DB_PASSWORD")
    PG_HOST = os.getenv("AZURE_DB_HOST")
    PG_PORT = os.getenv("AZURE_DB_PORT", "5432")
    PG_DB = os.getenv("AZURE_DB_NAME")

    if not all([PG_USER, PG_PASS, PG_HOST, PG_DB]):
        raise ValueError("Faltan variables de entorno para PostgreSQL (AZURE_DB_USER, etc.)")

    connection_string = f"postgresql://{PG_USER}:{PG_PASS}@{PG_HOST}:{PG_PORT}/{PG_DB}"
    return create_engine(connection_string, connect_args={"sslmode": "require"})


def load_raw_features(engine) -> pd.DataFrame:
    query = """
        SELECT
            m.h3_index,
            m.centroide_lon AS centroid_lon,
            m.centroide_lat AS centroid_lat,
            m.es_enp         AS is_protected_area,
            m.elevation_mean,
            m.slope_mean,
            m.aspect_mean,
            m.hillshade_mean,
            m.ndvi_medio     AS ndvi_mean,
            m.ndbi_medio     AS ndbi_mean,
            m.n_establecimientos_registro AS n_alojamientos,
            m.n_paradas_bus  AS n_paradas_transporte,
            s.sentimiento_medio,
            m.viirs_medio    AS viirs_mean
        FROM gold.gold_h3_master m
        LEFT JOIN gold.gold_sentimiento_h3 s ON s.h3_index = m.h3_index
    """
    return pd.read_sql(query, engine)


def drop_sparse_hexagons(df: pd.DataFrame, feature_cols: list[str], max_nan_ratio: float) -> pd.Series:
    """Devuelve, por fila, si el hexagono se excluye por tener demasiadas features nulas."""
    nan_ratio = df[feature_cols].isna().mean(axis=1)
    excluded = nan_ratio > max_nan_ratio
    logging.info(
        f"Hexagonos con > {max_nan_ratio:.0%} de features nulas (excluidos del clustering): "
        f"{int(excluded.sum())} / {len(df)}"
    )
    return excluded


def build_features(scaler_name: str = "standard") -> pd.DataFrame:
    engine = get_pg_engine()

    logging.info("Cargando features crudas desde gold_h3_master + gold_sentimiento_h3...")
    df = load_raw_features(engine)
    logging.info(f"Hexagonos cargados: {len(df)}")

    logging.info("Estadisticas descriptivas (pre-normalizacion):")
    logging.info("\n%s", df[FEATURE_COLUMNS].describe().transpose())

    n_features_missing = df[FEATURE_COLUMNS].isna().sum(axis=1)
    excluded_high_nan = drop_sparse_hexagons(df, FEATURE_COLUMNS, MAX_NAN_RATIO)

    # Los hexagonos excluidos se marcan (excluded_high_nan=TRUE) pero no se
    # borran de la tabla -- Issue #26 (HDBSCAN) los filtrara con
    # WHERE NOT excluded_high_nan en vez de perder la fila por completo.
    # Para el resto, imputamos con la mediana: HDBSCAN no admite NaN, y
    # sustituir por 0 falsearia variables donde 0 tiene significado propio
    # (p.ej. NDVI=0 es suelo desnudo).
    imputed = df[FEATURE_COLUMNS].fillna(df[FEATURE_COLUMNS].median())

    scaler = MinMaxScaler() if scaler_name == "minmax" else StandardScaler()
    scaled_values = scaler.fit_transform(imputed)
    scaled_cols = [f"{c}_scaled" for c in FEATURE_COLUMNS]
    df_scaled = pd.DataFrame(scaled_values, columns=scaled_cols, index=df.index)

    result = pd.concat(
        [
            df[PASSTHROUGH_COLUMNS + FEATURE_COLUMNS],
            df_scaled,
            n_features_missing.rename("n_features_missing"),
            excluded_high_nan.rename("excluded_high_nan"),
        ],
        axis=1,
    )
    result["computed_at"] = pd.Timestamp.now(tz="UTC")
    return result


def save_features(df: pd.DataFrame, engine) -> None:
    schema = "gold"
    table_name = "features_h3"
    logging.info(f"Guardando {len(df)} filas en {schema}.{table_name}...")
    df.to_sql(table_name, con=engine, schema=schema, if_exists="replace", index=False)
    logging.info("¡Listo!")


def parse_args():
    parser = argparse.ArgumentParser(description="Issue #25 -- Actualiza gold.features_h3 para clustering HDBSCAN")
    parser.add_argument(
        "--scaler",
        choices=["standard", "minmax"],
        default="standard",
        help="Metodo de normalizacion (por defecto: standard / z-score)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    features_df = build_features(scaler_name=args.scaler)
    save_features(features_df, get_pg_engine())
