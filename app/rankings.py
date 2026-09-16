import pandas as pd
import plotly.express as px
import streamlit as st

from app.color_scales import (
    ACCENT_RANKING_ALOJAMIENTOS,
    ACCENT_RANKING_CALUROSAS,
    ACCENT_RANKING_NDVI,
    ACCENT_RANKING_PLAZAS,
    ACCENT_RANKING_VALORADAS,
)
from app.ui_helpers import add_chart_motion, format_metric, render_footer

# "agg" controls how each metric is rolled up from hexagon-level rows to one
# value per municipio -- "mean" for rates/scores, "sum" for counts. "color"
# matches what's measured (green=vegetation, amber=establishments, blue=capacity,
# purple=rating, red=heat) instead of every ranking looking the same in navy.
RANKINGS = {
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
    st.markdown("<div style='margin-top: 1.5rem;'></div>", unsafe_allow_html=True)
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
        st.plotly_chart(fig, use_container_width=True)

        display = result.copy()
        display[column] = display[column].map(lambda v: format_metric(v, spec["kind"]))
        display = display.rename(columns={"municipio": "Municipio", column: label})
        st.dataframe(display, width="stretch", hide_index=True)

    render_footer("gold.gold_h3_master, gold.gold_sentimiento_h3")

