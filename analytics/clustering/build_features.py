"""
build_features.py
------------------
Issue #25 -- Preparacion de Datos Geometricos (Features para Clustering).

Construye la tabla de features geoespaciales consolidadas por hexagono H3
que sirve como input al clustering HDBSCAN (Issue #26) y a la deteccion de
brechas de mercado / MGWR (Issues #27, #32).

Fuentes reales (no las tablas oro.*/plata.* sueltas que describe el plan
original, que nunca llegaron a construirse asi): casi todo ya vive
consolidado en gold.gold_h3_master (alojamiento, paradas de bus, MDT,
NDVI/NDBI/VIIRS -- ver Issues #22/#23/#24), asi que este script solo necesita
unir esa tabla con gold.gold_sentimiento_h3 (Issue #20), en vez de repetir
joins espaciales que gold_h3_master ya resuelve.

Salida: gold.gold_features_h3 (equivalente a "oro.features_h3" del plan;
se usa el prefijo gold_ para ser consistente con el resto de tablas del
proyecto, que usan bronze/silver/gold en vez de bronce/plata/oro).

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

# Columnas de gold_h3_master + gold_sentimiento_h3 que entran al clustering.
# Ver Issue #25: sentimiento_h3, ndvi_h3, ndbi_h3, viirs_h3, mdt_stats
# (altitud/pendiente/orientacion), alojamientos (count+capacidad), paradas_transporte (count).
FEATURE_COLUMNS = [
    "sentimiento_medio",
    "ndvi_medio",
    "ndbi_medio",
    "viirs_medio",
    "elevation_mean",
    "slope_mean",
    "aspect_mean",
    "n_establecimientos_registro",
    "n_plazas_registro",
    "n_paradas_bus",
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
            m.cod_municipio,
            m.municipio,
            s.sentimiento_medio,
            m.ndvi_medio,
            m.ndbi_medio,
            m.viirs_medio,
            m.elevation_mean,
            m.slope_mean,
            m.aspect_mean,
            m.n_establecimientos_registro,
            m.n_plazas_registro,
            m.n_paradas_bus
        FROM gold.gold_h3_master m
        LEFT JOIN gold.gold_sentimiento_h3 s ON s.h3_index = m.h3_index
    """
    return pd.read_sql(query, engine)


def drop_sparse_hexagons(df: pd.DataFrame, feature_cols: list[str], max_nan_ratio: float) -> pd.DataFrame:
    nan_ratio = df[feature_cols].isna().mean(axis=1)
    n_excluidos = int((nan_ratio > max_nan_ratio).sum())
    logging.info(
        f"Hexagonos con > {max_nan_ratio:.0%} de features nulas (excluidos): {n_excluidos} / {len(df)}"
    )
    return df.loc[nan_ratio <= max_nan_ratio].copy()


def build_features(scaler_name: str = "standard") -> pd.DataFrame:
    engine = get_pg_engine()

    logging.info("Cargando features crudas desde gold_h3_master + gold_sentimiento_h3...")
    df = load_raw_features(engine)
    logging.info(f"Hexagonos cargados: {len(df)}")

    logging.info("Estadisticas descriptivas (pre-normalizacion):")
    logging.info("\n%s", df[FEATURE_COLUMNS].describe().transpose())

    df = drop_sparse_hexagons(df, FEATURE_COLUMNS, MAX_NAN_RATIO)

    # Para las columnas restantes, imputamos con la mediana de la propia
    # columna: HDBSCAN (Issue #26) no admite NaN, y sustituir por 0 falsearia
    # variables donde 0 tiene significado propio (p.ej. NDVI=0 es suelo desnudo).
    imputed = df[FEATURE_COLUMNS].fillna(df[FEATURE_COLUMNS].median())

    scaler = MinMaxScaler() if scaler_name == "minmax" else StandardScaler()
    scaled_values = scaler.fit_transform(imputed)
    scaled_cols = [f"{c}_norm" for c in FEATURE_COLUMNS]
    df_scaled = pd.DataFrame(scaled_values, columns=scaled_cols, index=df.index)

    result = pd.concat(
        [df[["h3_index", "cod_municipio", "municipio"] + FEATURE_COLUMNS], df_scaled],
        axis=1,
    )
    return result


def save_features(df: pd.DataFrame, engine) -> None:
    schema = "gold"
    table_name = "gold_features_h3"
    logging.info(f"Guardando {len(df)} filas en {schema}.{table_name}...")
    df.to_sql(table_name, con=engine, schema=schema, if_exists="replace", index=False)
    logging.info("¡Listo!")


def parse_args():
    parser = argparse.ArgumentParser(description="Issue #25 -- Construye oro.features_h3 para clustering HDBSCAN")
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
