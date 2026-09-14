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
MUNICIPIO_ANUAL_QUERY = "SELECT * FROM gold.gold_municipio_anual"
MUNICIPIO_EMPLEO_QUERY = "SELECT * FROM gold.gold_municipio_empleo"
MUNICIPIO_MENSUAL_QUERY = "SELECT * FROM gold.gold_municipio_mensual"
TURISMO_HOTELERO_ANUAL_QUERY = "SELECT * FROM gold.gold_turismo_hotelero_anual"
TURISMO_HOTELERO_MENSUAL_QUERY = "SELECT * FROM gold.gold_turismo_hotelero_mensual"
AENA_PASAJEROS_QUERY = "SELECT * FROM gold.gold_aena_pasajeros"
TOPICOS_MUNICIPIO_QUERY = "SELECT * FROM gold.gold_topicos_municipio"
NLP_CHUNKS_QUERY = """
    SELECT chunk_id, source, source_id, chunk_index, text, topic_id, topic_label,
           municipio, zona, h3_index, fecha, pais_resenante, rating, processed_at
    FROM gold.nlp_chunks
"""

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

# gold_topicos_municipio has 37 rows for Tenerife's 31 real municipios -- 6
# are alias rows using an accented/official-long-form spelling that doesn't
# match the spelling gold_h3_master (and the rest of this app) uses, e.g.
# "Guía de Isora" alongside the canonical "Guia de Isora" (confirmed by
# direct audit 2026-09-14: every alias carries a small minority of that
# municipio's opinions, worst case "San Cristobal de La Laguna" 189 +
# "San Cristóbal de La Laguna" 7 vs. canonical "La Laguna" 3679). Dropped
# outright rather than merged into the canonical row: merging would require
# recomputing topicos_top3's ranking from scratch for a <5% correction.
MUNICIPIO_ALIAS_DROP = {
    "Guía de Isora",
    "Güímar",
    "San Cristobal de La Laguna",
    "San Cristóbal de La Laguna",
    "Santa Úrsula",
    "Vilaflor de Chasna",
}


def drop_municipio_alias_rows(df: pd.DataFrame) -> pd.DataFrame:
    return df.loc[~df["municipio"].isin(MUNICIPIO_ALIAS_DROP)].reset_index(drop=True)


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
def load_municipio_anual(_engine: Engine) -> pd.DataFrame:
    return pd.read_sql(MUNICIPIO_ANUAL_QUERY, _engine)


@st.cache_data
def load_municipio_empleo(_engine: Engine) -> pd.DataFrame:
    return pd.read_sql(MUNICIPIO_EMPLEO_QUERY, _engine)


@st.cache_data
def load_municipio_mensual(_engine: Engine) -> pd.DataFrame:
    return pd.read_sql(MUNICIPIO_MENSUAL_QUERY, _engine)


@st.cache_data
def load_turismo_hotelero_anual(_engine: Engine) -> pd.DataFrame:
    return pd.read_sql(TURISMO_HOTELERO_ANUAL_QUERY, _engine)


@st.cache_data
def load_turismo_hotelero_mensual(_engine: Engine) -> pd.DataFrame:
    return pd.read_sql(TURISMO_HOTELERO_MENSUAL_QUERY, _engine)


@st.cache_data
def load_aena_pasajeros(_engine: Engine) -> pd.DataFrame:
    return pd.read_sql(AENA_PASAJEROS_QUERY, _engine)


@st.cache_data
def load_topicos_municipio(_engine: Engine) -> pd.DataFrame:
    return drop_municipio_alias_rows(pd.read_sql(TOPICOS_MUNICIPIO_QUERY, _engine))


@st.cache_data
def load_nlp_chunks(_engine: Engine) -> pd.DataFrame:
    return pd.read_sql(NLP_CHUNKS_QUERY, _engine)


def compute_density_metric(gdf: pd.DataFrame) -> pd.DataFrame:
    gdf = gdf.copy()
    gdf["densidad_metric"] = gdf["n_plazas_registro"].where(
        gdf["n_plazas_registro"] > 0, gdf["n_establecimientos_registro"]
    )
    return gdf


# gold_h3_master dropped its old boolean es_zona_turistica_oficial/es_enp
# columns at some point after this dashboard was last verified against the
# live DB (confirmed by direct schema audit 2026-09-14 -- gold_h3_master now
# has pct_area_zona_turistica/pct_area_enp, the fraction of the hexagon's
# area overlapping that polygon type, instead of a plain boolean). Any
# overlap at all (> 0) reproduces the old boolean's semantics.
def compute_restriction_category(gdf: pd.DataFrame) -> pd.DataFrame:
    gdf = gdf.copy()
    gdf["restriction_category"] = "Sin restricción"
    gdf.loc[gdf["pct_area_zona_turistica"] > 0, "restriction_category"] = "Zona turística oficial"
    gdf.loc[gdf["pct_area_enp"] > 0, "restriction_category"] = "ENP"
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
