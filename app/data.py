import os

import geopandas as gpd
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect
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
ISOCRONAS_QUERY = "SELECT * FROM gold.gold_isocronas_visuales"
MUNICIPIO_MASTER_QUERY = "SELECT * FROM gold.gold_municipio_master"
ISTAC_ANUAL_QUERY = "SELECT * FROM silver.silver_istac_anual"
ISTAC_MENSUAL_QUERY = "SELECT * FROM silver.silver_istac_mensual"

# gold_h3_accesibilidad usa 999 como centinela de "destino inalcanzable" en
# vez de NULL en las columnas tiempo_*_min (confirmado por auditoría directa
# de la tabla) -- sin esto, un hexágono remoto parecería estar a 999 min.
TIEMPO_SENTINEL = 999.0

# gold.gold_sentimiento_h3 depende de tablas gold_nlp.* (nlp_sentimiento_resenas,
# nlp_aspectos_resenas, aspecto_traducciones) escritas a mano por notebooks
# (analytics/tarea2/*.ipynb) que todavia no se han corrido/migrado a la
# cuenta nueva de Azure -- confirmado por auditoria directa del esquema
# `gold` (solo tiene gold_h3_master, gold_h3_accesibilidad, isocronas_visuales).
# Mientras tanto, load_sentimiento() devuelve un DataFrame vacio con las
# columnas esperadas en vez de reventar la app entera: las capas/paneles que
# lo consumen ya tratan NULL/ausente como "sin datos", asi que esto solo
# apaga esa una capa, no el resto del dashboard.
SENTIMIENTO_COLUMNS = [
    "h3_index",
    "sentimiento_medio",
    "n_resenas",
    "n_resenas_booking",
    "n_resenas_tripadvisor",
    "queja_principal",
]


@st.cache_resource
def get_engine() -> Engine:
    return create_engine(os.environ["AZURE_DB_URL"])


@st.cache_data
def load_h3_master(_engine: Engine) -> gpd.GeoDataFrame:
    return gpd.read_postgis(H3_MASTER_QUERY, _engine, geom_col="geometry")


@st.cache_data
def load_sentimiento(_engine: Engine) -> pd.DataFrame:
    if not inspect(_engine).has_table("gold_sentimiento_h3", schema="gold"):
        return pd.DataFrame(columns=SENTIMIENTO_COLUMNS)
    return pd.read_sql(SENTIMIENTO_QUERY, _engine)


@st.cache_data
def load_accesibilidad(_engine: Engine) -> pd.DataFrame:
    return pd.read_sql(ACCESIBILIDAD_QUERY, _engine)


@st.cache_data
def load_isocronas(_engine: Engine) -> gpd.GeoDataFrame:
    return gpd.read_postgis(ISOCRONAS_QUERY, _engine, geom_col="geometry")


@st.cache_data
def load_municipio_master(_engine: Engine) -> pd.DataFrame:
    return pd.read_sql(MUNICIPIO_MASTER_QUERY, _engine)


@st.cache_data
def load_istac_anual(_engine: Engine) -> pd.DataFrame:
    return pd.read_sql(ISTAC_ANUAL_QUERY, _engine)


@st.cache_data
def load_istac_mensual(_engine: Engine) -> pd.DataFrame:
    return pd.read_sql(ISTAC_MENSUAL_QUERY, _engine)


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
