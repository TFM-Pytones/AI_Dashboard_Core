import numpy as np
import os

import geopandas as gpd
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine

# override=True is required: Streamlit's own bootstrap pre-seeds
# os.environ["MAPBOX_API_KEY"] = "" (from its unset `mapbox.token` config
# option, to silence an internal pydeck warning) *before* this module runs.
# python-dotenv's default override=False then refuses to replace that
# already-present empty value with the real one from .env.
load_dotenv(override=True)

H3_MASTER_QUERY = "SELECT * FROM gold.gold_h3_master"
SENTIMIENTO_QUERY = """
    SELECT h3_index, sentimiento_medio, n_resenas_sentimiento AS n_resenas,
           n_resenas_booking, n_resenas_tripadvisor, queja_principal
    FROM gold.gold_h3_sentimiento
"""
ACCESIBILIDAD_QUERY = "SELECT * FROM gold.gold_h3_accesibilidad"
ISOCRONAS_QUERY = "SELECT * FROM gold.gold_isocronas_visuales"
GTFS_RUTAS_QUERY = """
SELECT r.shape_id,
       r.route_short_name,
       r.route_long_name,
       r.operador,
       COALESCE(string_agg(DISTINCT m.municipio, ', '), '') AS municipios,
       ST_Simplify(r.geometry, 0.0002) AS geometry
FROM silver.silver_gtfs_rutas r
LEFT JOIN gold.gold_municipio_master m
  ON ST_Intersects(r.geometry, m.geometry)
GROUP BY r.shape_id, r.route_short_name, r.route_long_name, r.operador, r.geometry
"""
BIENES_CULTURALES_QUERY = "SELECT id, nombre, tipo, municipio, geometry FROM silver.silver_bienes_interes_culturales"
ESTACIONES_AGROCABILDO_QUERY = "SELECT id_estacion, nombre_estacion, municipio, altitud_m, geometry FROM silver.silver_estaciones_agrocabildo"
MUNICIPIO_MASTER_QUERY = "SELECT * FROM gold.gold_municipio_master"
MUNICIPIO_ANUAL_QUERY = "SELECT * FROM gold.gold_municipio_anual"
MUNICIPIO_EMPLEO_QUERY = "SELECT * FROM gold.gold_municipio_empleo"
MUNICIPIO_MENSUAL_QUERY = "SELECT * FROM gold.gold_municipio_mensual"
TURISMO_HOTELERO_ANUAL_QUERY = "SELECT * FROM gold.gold_turismo_hotelero_anual"
TURISMO_HOTELERO_MENSUAL_QUERY = "SELECT * FROM gold.gold_turismo_hotelero_mensual"
AENA_PASAJEROS_QUERY = "SELECT * FROM gold.gold_aena_pasajeros"
CLIMA_ANUAL_QUERY = "SELECT * FROM gold.gold_clima_anual"
ALOJAMIENTO_BREAKDOWN_QUERY = "SELECT * FROM gold.gold_alojamiento_breakdown"
TOPICOS_MUNICIPIO_QUERY = "SELECT * FROM gold.gold_topicos_municipio"
NLP_CHUNKS_QUERY = """
    SELECT chunk_id, source, source_id, chunk_index, text, topic_id, topic_label,
           municipio, zona, h3_index, fecha, pais_resenante, rating, processed_at
    FROM gold.nlp_chunks
"""
H3_CLUSTERS_QUERY = "SELECT h3_index, tipo_zona FROM gold.h3_clusters"
H3_PTNA_QUERY = "SELECT h3_index, ptna_score, confianza_ptna FROM gold.gold_h3_ptna_v3"
H3_ESG_QUERY = "SELECT h3_index, e_score, s_score, g_score, esg_h3_score FROM gold.gold_h3_esg_v1"
H3_OPORTUNIDAD_QUERY = "SELECT h3_index, es_oportunidad_ideal FROM gold.gold_bloque5_h3_oportunidad_v1"

# gold_h3_accesibilidad usa 999 como centinela de "destino inalcanzable" en
# vez de NULL en las columnas tiempo_*_min (confirmado por auditoría directa
# de la tabla) -- sin esto, un hexágono remoto parecería estar a 999 min.
TIEMPO_SENTINEL = 999.0

# El modelo dbt original (dbt_project/models/gold/gold_sentimiento_h3.sql,
# Issue #20) nunca se materializo -- lee de un esquema `gold_nlp` que no
# existe en la BD real (auditoria directa: 0 tablas). Por separado, en la
# rama feature/gold-h3-ptna (Bloque 5/PTNA, sin mergear a main) se creo
# gold.gold_h3_sentimiento a mano via script (00_create_sentimiento_table.py)
# con el nombre al reves y una columna distinta (n_resenas_sentimiento en vez
# de n_resenas) -- esa si esta poblada de verdad (410 hexagonos, confirmado
# por auditoria directa 2026-09-16) porque las reseñas no siempre tienen
# coordenadas para geolocalizar al hexagono. load_sentimiento() sigue
# devolviendo un DataFrame vacio si la tabla no existe, por si esa rama
# renombra/quita gold_h3_sentimiento antes de mergear -- las capas/paneles
# que lo consumen ya tratan NULL/ausente como "sin datos".
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


# Longitud aproximada de la arista para celdas H3 Res 8 (~461 m / 0.461 km).
# Al calcularse dist_costa_km desde el centroide del hexágono hacia la costa,
# los hexágonos que tocan físicamente el mar presentaban una distancia artificial
# de entre 0.01 y 0.46 km. Restando la arista y acotando a 0.0 km, las celdas
# de primera línea / litoral muestran 0.0 km en el Dashboard sin alterar la
# pureza continua de gold.gold_h3_master en PostgreSQL para el modelo MGWR.
H3_RES8_EDGE_KM = 0.461


def adjust_coastal_distance(gdf: pd.DataFrame, edge_km: float = H3_RES8_EDGE_KM) -> pd.DataFrame:
    gdf = gdf.copy()
    if "dist_costa_km" in gdf.columns:
        gdf["dist_costa_km"] = (gdf["dist_costa_km"] - edge_km).clip(lower=0.0).round(2)
    return gdf


@st.cache_resource
def get_engine() -> Engine:
    return create_engine(
        os.environ["AZURE_DB_URL"],
        pool_pre_ping=True,
        pool_recycle=300,
        connect_args={
            "connect_timeout": 15,
            "keepalives": 1,
            "keepalives_idle": 30,
            "keepalives_interval": 10,
            "keepalives_count": 5,
        },
    )


@st.cache_data
def load_h3_master(_engine: Engine) -> gpd.GeoDataFrame:
    gdf = gpd.read_postgis(H3_MASTER_QUERY, _engine, geom_col="geometry")
    return adjust_coastal_distance(gdf)


@st.cache_data
def load_sentimiento(_engine: Engine) -> pd.DataFrame:
    if not inspect(_engine).has_table("gold_h3_sentimiento", schema="gold"):
        return pd.DataFrame(columns=SENTIMIENTO_COLUMNS)
    return pd.read_sql(SENTIMIENTO_QUERY, _engine)


@st.cache_data
def load_accesibilidad(_engine: Engine) -> pd.DataFrame:
    return pd.read_sql(ACCESIBILIDAD_QUERY, _engine)


@st.cache_data
def load_isocronas(_engine: Engine) -> gpd.GeoDataFrame:
    return gpd.read_postgis(ISOCRONAS_QUERY, _engine, geom_col="geometry")


@st.cache_data
def load_gtfs_rutas(_engine: Engine) -> gpd.GeoDataFrame:
    return gpd.read_postgis(GTFS_RUTAS_QUERY, _engine, geom_col="geometry")


@st.cache_data
def load_bienes_culturales(_engine: Engine) -> gpd.GeoDataFrame:
    return gpd.read_postgis(BIENES_CULTURALES_QUERY, _engine, geom_col="geometry")


@st.cache_data
def load_estaciones_agrocabildo(_engine: Engine) -> gpd.GeoDataFrame:
    return gpd.read_postgis(ESTACIONES_AGROCABILDO_QUERY, _engine, geom_col="geometry")


@st.cache_data
def load_municipio_master(_engine: Engine) -> gpd.GeoDataFrame:
    return gpd.read_postgis(MUNICIPIO_MASTER_QUERY, _engine, geom_col="geometry")


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
def load_clima_anual(_engine: Engine) -> pd.DataFrame:
    if not inspect(_engine).has_table("gold_clima_anual", schema="gold"):
        return pd.DataFrame(columns=["municipio", "variable_nombre", "anio", "valor"])
    return pd.read_sql(CLIMA_ANUAL_QUERY, _engine)


@st.cache_data
def load_alojamiento_breakdown(_engine: Engine) -> pd.DataFrame:
    if not inspect(_engine).has_table("gold_alojamiento_breakdown", schema="gold"):
        return pd.DataFrame(columns=["tipo", "municipio", "cantidad_alojamientos", "plazas"])
    return pd.read_sql(ALOJAMIENTO_BREAKDOWN_QUERY, _engine)


@st.cache_data
def load_topicos_municipio(_engine: Engine) -> pd.DataFrame:
    return drop_municipio_alias_rows(pd.read_sql(TOPICOS_MUNICIPIO_QUERY, _engine))


@st.cache_data
def load_nlp_chunks(_engine: Engine) -> pd.DataFrame:
    return pd.read_sql(NLP_CHUNKS_QUERY, _engine)


@st.cache_data
def load_nlp_chunks_count(_engine: Engine) -> int:
    with _engine.connect() as con:
        val = con.execute(text("SELECT count(*) FROM gold.nlp_chunks")).scalar()
        return int(val or 87981)


@st.cache_data
def load_h3_clusters(_engine: Engine) -> pd.DataFrame:
    if not inspect(_engine).has_table("h3_clusters", schema="gold"):
        return pd.DataFrame(columns=["h3_index", "tipo_zona"])
    df = pd.read_sql(H3_CLUSTERS_QUERY, _engine)
    df["tipo_zona"] = df["tipo_zona"].astype(str).str.replace("Transicin", "Transición")
    return df


@st.cache_data
def load_ptna(_engine: Engine) -> pd.DataFrame:
    if not inspect(_engine).has_table("gold_h3_ptna_v3", schema="gold"):
        return pd.DataFrame(columns=["h3_index", "ptna_score", "confianza_ptna"])
    return pd.read_sql(H3_PTNA_QUERY, _engine)


@st.cache_data
def load_esg(_engine: Engine) -> pd.DataFrame:
    if not inspect(_engine).has_table("gold_h3_esg_v1", schema="gold"):
        return pd.DataFrame(columns=["h3_index", "e_score", "s_score", "g_score", "esg_h3_score"])
    return pd.read_sql(H3_ESG_QUERY, _engine)


@st.cache_data
def load_oportunidad(_engine: Engine) -> pd.DataFrame:
    if not inspect(_engine).has_table("gold_bloque5_h3_oportunidad_v1", schema="gold"):
        return pd.DataFrame(columns=["h3_index", "es_oportunidad_ideal"])
    return pd.read_sql(H3_OPORTUNIDAD_QUERY, _engine)


def _normalize_series(series: pd.Series) -> pd.Series:
    s = pd.to_numeric(series, errors="coerce").fillna(0.0)
    mn, mx = s.min(), s.max()
    if mx > mn:
        return (s - mn) / (mx - mn)
    return pd.Series(0.0, index=series.index)


def compute_strategic_axes_and_archetypes(gdf: pd.DataFrame) -> pd.DataFrame:
    gdf = gdf.copy()

    # Normalizaciones base para scoring
    p_norm = _normalize_series(np.log1p(gdf["n_plazas_registro"].fillna(0).clip(lower=0)))
    v_norm = _normalize_series(np.log1p(gdf["viirs_medio"].fillna(0).clip(lower=0)))
    costa_prox = (1.0 - (gdf["dist_costa_km"].fillna(10.0) / 10.0)).clip(0.0, 1.0)
    establ_norm = _normalize_series(np.log1p(gdf["n_establecimientos_registro"].fillna(0).clip(lower=0)))

    ndvi_norm = _normalize_series(gdf["ndvi_medio"].fillna(0))
    ndbi_norm = _normalize_series(gdf["ndbi_medio"].fillna(0))
    ndbi_inv = (1.0 - ndbi_norm).clip(0.0, 1.0)

    slope_norm = _normalize_series(gdf["slope_mean"].fillna(0))
    alt_norm = _normalize_series(gdf["altitud_media_m"].fillna(0).clip(lower=0))

    ptna_val = gdf["ptna_score"] if "ptna_score" in gdf.columns else pd.Series(0.0, index=gdf.index)
    ptna_norm = _normalize_series(ptna_val)

    esg_val = gdf["esg_h3_score"] if "esg_h3_score" in gdf.columns else pd.Series(50.0, index=gdf.index)
    esg_norm = (pd.to_numeric(esg_val, errors="coerce").fillna(50.0) / 100.0).clip(0.0, 1.0)

    cultura_norm = _normalize_series(np.log1p(gdf["n_cultura"].fillna(0)))
    rest_norm = _normalize_series(np.log1p(gdf["n_restaurantes"].fillna(0)))
    pois_norm = _normalize_series(np.log1p(gdf["n_pois_total"].fillna(0)))
    nat_norm = _normalize_series(np.log1p(gdf.get("n_naturaleza", pd.Series(0.0, index=gdf.index)).fillna(0)))
    rating_val = gdf["rating_booking_medio"].fillna(gdf["rating_booking_medio"].mean())
    rating_norm = _normalize_series(rating_val)

    # -------------------------------------------------------------
    # Eje 1 (HDBSCAN, silhouette 0.808): Saturado <-> Transición [continuo]
    # Mide la presión turística continua en el gradiente de masificación.
    # -------------------------------------------------------------
    eje1_raw = 0.45 * p_norm + 0.25 * v_norm + 0.15 * costa_prox + 0.15 * establ_norm
    gdf["eje_1_saturacion"] = _normalize_series(eje1_raw).round(4)

    # -------------------------------------------------------------
    # Eje 2 (score compuesto): Rural Infrautilizado [0-1]
    # Mide el potencial rural y ambiental sostenible actualmente desaprovechado.
    # -------------------------------------------------------------
    no_masificacion = (1.0 - p_norm).clip(0.0, 1.0)
    eje2_raw = (
        0.25 * ndvi_norm +
        0.25 * ptna_norm +
        0.20 * no_masificacion +
        0.15 * ndbi_inv +
        0.15 * esg_norm
    )
    gdf["eje_2_rural_infrautilizado"] = _normalize_series(eje2_raw).round(4)

    # -------------------------------------------------------------
    # Scores de los 5 Arquetipos de Producto Turístico TUI
    # -------------------------------------------------------------
    # 1. Sol y Playa Premium
    gdf["score_sol_playa"] = _normalize_series(
        0.40 * p_norm + 0.30 * costa_prox + 0.15 * v_norm + 0.15 * rating_norm
    ).round(4)

    # 2. Ecoturismo Rural y Medianías
    gdf["score_ecoturismo"] = _normalize_series(
        0.30 * ndvi_norm + 0.25 * ptna_norm + 0.25 * no_masificacion + 0.20 * esg_norm
    ).round(4)

    # 3. Cultural y Patrimonial
    gdf["score_cultural"] = _normalize_series(
        0.35 * cultura_norm + 0.25 * rest_norm + 0.20 * pois_norm + 0.20 * ptna_norm
    ).round(4)

    # 4. Aventura y Activo
    gdf["score_aventura"] = _normalize_series(
        0.35 * slope_norm + 0.30 * alt_norm + 0.20 * ndvi_norm + 0.15 * nat_norm
    ).round(4)

    # 5. Bienestar y Salud (temperatura constante ~21°C, baja estacionalidad y calma)
    temp = gdf["temp_media_anual"].fillna(21.0)
    temp_opt = (1.0 - (np.abs(temp - 21.0) / 10.0)).clip(0.0, 1.0)
    gdf["score_bienestar"] = _normalize_series(
        0.35 * temp_opt + 0.25 * no_masificacion + 0.20 * ndvi_norm + 0.20 * esg_norm
    ).round(4)

    # Arquetipo Dominante
    arch_cols = ["score_sol_playa", "score_ecoturismo", "score_cultural", "score_aventura", "score_bienestar"]
    arch_names = {
        "score_sol_playa": "Sol y playa",
        "score_ecoturismo": "Ecoturismo rural",
        "score_cultural": "Cultural y patrimonial",
        "score_aventura": "Aventura y activo",
        "score_bienestar": "Bienestar y salud",
    }
    gdf["arquetipo_principal"] = gdf[arch_cols].idxmax(axis=1).map(arch_names)

    return gdf


def merge_clusters_and_analytics(
    gdf: pd.DataFrame,
    clusters_df: pd.DataFrame,
    ptna_df: pd.DataFrame,
    esg_df: pd.DataFrame,
    oportunidad_df: pd.DataFrame,
) -> pd.DataFrame:
    merged = gdf.copy()
    if not clusters_df.empty and "tipo_zona" in clusters_df.columns:
        merged = merged.merge(clusters_df[["h3_index", "tipo_zona"]], on="h3_index", how="left")
    if not ptna_df.empty:
        ptna_cols = [c for c in ["h3_index", "ptna_score", "confianza_ptna"] if c in ptna_df.columns]
        merged = merged.merge(ptna_df[ptna_cols], on="h3_index", how="left")
    if not esg_df.empty:
        esg_cols = [c for c in ["h3_index", "e_score", "s_score", "g_score", "esg_h3_score"] if c in esg_df.columns]
        merged = merged.merge(esg_df[esg_cols], on="h3_index", how="left")
    if not oportunidad_df.empty and "es_oportunidad_ideal" in oportunidad_df.columns:
        merged = merged.merge(oportunidad_df[["h3_index", "es_oportunidad_ideal"]], on="h3_index", how="left")
        merged["es_oportunidad_ideal"] = merged["es_oportunidad_ideal"].fillna(False)

    return compute_strategic_axes_and_archetypes(merged)


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
    gdf.loc[gdf["pct_area_enp"] > 0, "restriction_category"] = "Espacio Natural Protegido"
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
    # gold_h3_master already carries its own dist_costa_km (identical values,
    # confirmed by direct comparison against gold_h3_accesibilidad's copy).
    # Without dropping it here, the merge silently renames both copies to
    # dist_costa_km_x/_y, which broke every downstream reference to the
    # plain "dist_costa_km" column name (detail panel showed "-", the map's
    # "Distancia a la costa" layer raised a KeyError).
    cleaned = cleaned.drop(columns=["dist_costa_km"], errors="ignore")
    return gdf.merge(cleaned, on="h3_index", how="left")


def list_municipios(gdf: pd.DataFrame) -> list[str]:
    return sorted(gdf["municipio"].dropna().unique().tolist())


def filter_by_municipio(gdf: pd.DataFrame, municipio: str | None) -> pd.DataFrame:
    if municipio is None or municipio == "Todos":
        return gdf
    return gdf[gdf["municipio"] == municipio]
