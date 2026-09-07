import os

import geopandas as gpd
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

load_dotenv()

H3_MASTER_QUERY = "SELECT * FROM gold.gold_h3_master"
SENTIMIENTO_QUERY = "SELECT * FROM gold.gold_sentimiento_h3"


@st.cache_resource
def get_engine() -> Engine:
    return create_engine(os.environ["AZURE_DB_URL"])


@st.cache_data
def load_h3_master(_engine: Engine) -> gpd.GeoDataFrame:
    return gpd.read_postgis(H3_MASTER_QUERY, _engine, geom_col="geometry")


@st.cache_data
def load_sentimiento(_engine: Engine) -> pd.DataFrame:
    return pd.read_sql(SENTIMIENTO_QUERY, _engine)


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


def list_municipios(gdf: pd.DataFrame) -> list[str]:
    return sorted(gdf["municipio"].dropna().unique().tolist())


def filter_by_municipio(gdf: pd.DataFrame, municipio: str | None) -> pd.DataFrame:
    if municipio is None or municipio == "Todos":
        return gdf
    return gdf[gdf["municipio"] == municipio]
