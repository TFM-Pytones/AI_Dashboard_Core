import os

import geopandas as gpd
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

# override=True is required: Streamlit's own bootstrap pre-seeds
# os.environ["MAPBOX_API_KEY"] = "" (from its unset `mapbox.token` config
# option, to silence an internal pydeck warning) *before* this module runs.
# python-dotenv's default override=False then refuses to replace that
# already-present empty value with the real one from .env.
load_dotenv(override=True)

H3_MASTER_QUERY = "SELECT * FROM gold.gold_h3_master"
SENTIMIENTO_QUERY = "SELECT * FROM gold.gold_sentimiento_h3"
ACCESIBILIDAD_QUERY = "SELECT * FROM gold.gold_h3_accesibilidad"
ISOCRONAS_QUERY = "SELECT * FROM gold.isocronas_visuales"

# gold_h3_accesibilidad usa 999 como centinela de "destino inalcanzable" en
# vez de NULL en las columnas tiempo_*_min (confirmado por auditoría directa
# de la tabla) -- sin esto, un hexágono remoto parecería estar a 999 min.
TIEMPO_SENTINEL = 999.0


@st.cache_resource
def get_engine() -> Engine:
    return create_engine(os.environ["AZURE_DB_URL"])


@st.cache_data
def load_h3_master(_engine: Engine) -> gpd.GeoDataFrame:
    return gpd.read_postgis(H3_MASTER_QUERY, _engine, geom_col="geometry")


@st.cache_data
def load_sentimiento(_engine: Engine) -> pd.DataFrame:
    return pd.read_sql(SENTIMIENTO_QUERY, _engine)


@st.cache_data
def load_accesibilidad(_engine: Engine) -> pd.DataFrame:
    return pd.read_sql(ACCESIBILIDAD_QUERY, _engine)


@st.cache_data
def load_isocronas(_engine: Engine) -> gpd.GeoDataFrame:
    return gpd.read_postgis(ISOCRONAS_QUERY, _engine, geom_col="geometry")


def compute_density_metric(gdf: pd.DataFrame) -> pd.DataFrame:
    gdf = gdf.copy()
    gdf["densidad_metric"] = gdf["n_plazas_registro"].where(
        gdf["n_plazas_registro"] > 0, gdf["n_establecimientos_registro"]
    )
    return gdf


def compute_restriction_category(gdf: pd.DataFrame) -> pd.DataFrame:
    gdf = gdf.copy()
    gdf["restriction_category"] = "Sin restricción"
    gdf.loc[gdf["es_zona_turistica_oficial"] == True, "restriction_category"] = (  # noqa: E712
        "Zona turística oficial"
    )
    gdf.loc[gdf["es_enp"] == True, "restriction_category"] = "ENP"  # noqa: E712
    return gdf


def merge_h3_data(h3_gdf: gpd.GeoDataFrame, sentimiento_df: pd.DataFrame) -> gpd.GeoDataFrame:
    merged = h3_gdf.merge(sentimiento_df, on="h3_index", how="left")
    merged = compute_density_metric(merged)
    return compute_restriction_category(merged)


def clean_accesibilidad_sentinel(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    tiempo_cols = [c for c in df.columns if c.startswith("tiempo_")]
    for c in tiempo_cols:
        df.loc[df[c] >= TIEMPO_SENTINEL, c] = None
    return df


def merge_accesibilidad(gdf: pd.DataFrame, accesibilidad_df: pd.DataFrame) -> pd.DataFrame:
    cleaned = clean_accesibilidad_sentinel(accesibilidad_df)
    return gdf.merge(cleaned, on="h3_index", how="left")


def list_municipios(gdf: pd.DataFrame) -> list[str]:
    return sorted(gdf["municipio"].dropna().unique().tolist())


def filter_by_municipio(gdf: pd.DataFrame, municipio: str | None) -> pd.DataFrame:
    if municipio is None or municipio == "Todos":
        return gdf
    return gdf[gdf["municipio"] == municipio]
