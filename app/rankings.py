import pandas as pd
import plotly.express as px
import streamlit as st

from app.color_scales import (
    ACCENT_OPORTUNIDADES,
    ACCENT_RANKING_ALOJAMIENTOS,
    ACCENT_RANKING_CALUROSAS,
    ACCENT_RANKING_NDVI,
    ACCENT_RANKING_PLAZAS,
    ACCENT_RANKING_VALORADAS,
    ACCENT_TURISMO,
)
from app.ui_helpers import add_chart_motion, format_metric

# "agg" controls how each metric is rolled up from hexagon-level rows to one
# value per municipio -- "mean" for rates/scores, "sum" for counts. "color"
# matches what's measured (green=vegetation, amber=establishments, blue=capacity,
# purple=rating, red=heat) instead of every ranking looking the same in navy.
RANKINGS = {
    "Mayor potencial turístico (PTNA)": {
        "column": "ptna_score",
        "agg": "mean",
        "kind": "decimal",
        "color": ACCENT_OPORTUNIDADES,
        "label": "Score PTNA medio",
    },
    "Mayor sostenibilidad territorial (ESG)": {
        "column": "esg_h3_score",
        "agg": "mean",
        "kind": "decimal",
        "color": ACCENT_RANKING_NDVI,
        "label": "Score ESG medio (0-100)",
    },
    "Mayor potencial rural y sostenible (Eje 2)": {
        "column": "eje_2_rural_infrautilizado",
        "agg": "mean",
        "kind": "decimal2",
        "color": ACCENT_RANKING_NDVI,
        "label": "Eje 2 medio (0-1)",
    },
    "Mayor saturación turística (Eje 1)": {
        "column": "eje_1_saturacion",
        "agg": "mean",
        "kind": "decimal2",
        "color": ACCENT_RANKING_CALUROSAS,
        "label": "Eje 1 medio (0-1)",
    },
    "Mayor oferta alojativa (nº alojamientos)": {
        "column": "n_establecimientos_registro",
        "agg": "sum",
        "kind": "entero",
        "color": ACCENT_RANKING_ALOJAMIENTOS,
        "label": "Nº de alojamientos",
    },
    "Mayor capacidad alojativa (nº plazas)": {
        "column": "n_plazas_registro",
        "agg": "sum",
        "kind": "entero",
        "color": ACCENT_RANKING_PLAZAS,
        "label": "Nº de plazas",
    },
    "Más vegetación (NDVI)": {
        "column": "ndvi_medio",
        "agg": "mean",
        "kind": "decimal2",
        "color": ACCENT_RANKING_NDVI,
        "label": "NDVI medio",
    },
    "Mejor valoradas (rating Booking)": {
        "column": "rating_booking_medio",
        "agg": "mean",
        "kind": "decimal",
        "color": ACCENT_RANKING_VALORADAS,
        "label": "Rating medio",
    },
    "Más calurosas": {
        "column": "temp_media_anual",
        "agg": "mean",
        "kind": "decimal",
        "color": ACCENT_RANKING_CALUROSAS,
        "label": "Temperatura media (°C)",
    },
}


def top_n_by_ranking(gdf: pd.DataFrame, ranking_key: str, n: int = 10) -> pd.DataFrame:
    spec = RANKINGS[ranking_key]
    column = spec["column"]
    grouped = gdf.dropna(subset=[column]).groupby("municipio", as_index=False)[column].agg(spec["agg"])
    return grouped.sort_values(column, ascending=False).head(n)


def render_rankings_tab(gdf: pd.DataFrame) -> None:
    col1, col2 = st.columns([3, 1])
    ranking_key = col1.selectbox("Ranking", list(RANKINGS.keys()))
    n = col2.slider("Nº de municipios", min_value=5, max_value=31, value=10)

    result = top_n_by_ranking(gdf, ranking_key, n)
    spec = RANKINGS[ranking_key]
    column = spec["column"]
    label = spec.get("label", column)

    if result.empty:
        st.info("No hay municipios con datos para este ranking.")
    else:
        fig = px.bar(
            result.sort_values(column),
            x=column,
            y="municipio",
            orientation="h",
            title=ranking_key,
            labels={column: label, "municipio": "Municipio"},
        )
        fig.update_traces(marker_color=spec["color"])
        add_chart_motion(fig)
        st.plotly_chart(fig, width="stretch")

        display = result.copy()
        display[column] = display[column].map(lambda v: format_metric(v, spec["kind"]))
        display = display.rename(columns={"municipio": "Municipio", column: label})
        st.dataframe(display, width="stretch", hide_index=True)

