import math

import pandas as pd
import plotly.express as px
import streamlit as st

KPI_COLUMNS = [
    ("n_hoteles", "Nº hoteles"),
    ("n_establecimientos_registro", "Nº alojamientos registrados"),
    ("ndvi_medio", "NDVI medio"),
    ("sentimiento_medio", "Sentimiento medio"),
    ("rating_booking_medio", "Rating Booking"),
    ("rating_tripadvisor_medio", "Rating TripAdvisor"),
]


def format_kpi_value(value, decimals: int = 1) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "—"
    if isinstance(value, float):
        return f"{value:.{decimals}f}"
    return str(value)


def _has_overlap(value) -> bool:
    if value is None:
        return False
    if isinstance(value, float) and math.isnan(value):
        return False
    return value > 0


# gold_h3_master dropped its old boolean es_enp/es_zona_turistica_oficial
# columns (confirmed by direct schema audit 2026-09-14) in favor of
# pct_area_enp/pct_area_zona_turistica -- the fraction of the hexagon's area
# overlapping that polygon type. Any overlap at all (> 0) reproduces the old
# boolean's semantics.
def restriction_badges(row) -> list[str]:
    badges = []
    if _has_overlap(row.get("pct_area_enp")):
        badges.append("⚠️ Espacio Natural Protegido")
    if _has_overlap(row.get("pct_area_zona_turistica")):
        badges.append("🏖️ Zona turística oficial")
    return badges


def municipio_aspect_comparison(gdf: pd.DataFrame, h3_index: str) -> pd.DataFrame | None:
    if h3_index not in gdf["h3_index"].values:
        return None
    row = gdf.loc[gdf["h3_index"] == h3_index].iloc[0]
    peers = gdf[gdf["municipio"] == row["municipio"]]
    counts = peers["queja_principal"].dropna().value_counts().reset_index()
    counts.columns = ["aspecto", "n_hexagonos"]
    counts["es_seleccionado"] = counts["aspecto"] == row["queja_principal"]
    return counts


def render_detail_panel(gdf: pd.DataFrame, selected_h3_index: str | None) -> None:
    if selected_h3_index is None:
        st.info("Haz clic en un hexágono del mapa para ver su detalle.")
        return
    matches = gdf.loc[gdf["h3_index"] == selected_h3_index]
    if matches.empty:
        st.warning("No hay datos para el hexágono seleccionado.")
        return
    row = matches.iloc[0]
    st.subheader(f"Hexágono {selected_h3_index}")
    for badge in restriction_badges(row):
        st.caption(badge)
    cols = st.columns(3)
    for i, (column, label) in enumerate(KPI_COLUMNS):
        cols[i % 3].metric(label, format_kpi_value(row.get(column)))
    comparison = municipio_aspect_comparison(gdf, selected_h3_index)
    if comparison is None or comparison.empty:
        st.caption("Sin aspectos NLP registrados para este municipio.")
        return
    fig = px.bar(
        comparison,
        x="aspecto",
        y="n_hexagonos",
        color="es_seleccionado",
        color_discrete_map={True: "#2a78d6", False: "#c3c2b7"},
        title=f"Aspectos más mencionados en {row['municipio']}",
    )
    st.plotly_chart(fig, width="stretch")
