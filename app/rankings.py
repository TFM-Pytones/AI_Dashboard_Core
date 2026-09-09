import pandas as pd
import plotly.express as px
import streamlit as st

RANKINGS = {
    "Más vegetación (NDVI)": {"column": "ndvi_medio"},
    "Más turística (nº establecimientos Booking)": {"column": "n_establecimientos_booking"},
    "Mejor valoradas (rating Booking)": {"column": "rating_booking_medio"},
    "Más calurosas": {"column": "temp_media_anual"},
}

DISPLAY_COLUMNS = ["h3_index", "municipio"]


def top_n_by_ranking(gdf: pd.DataFrame, ranking_key: str, n: int = 10) -> pd.DataFrame:
    column = RANKINGS[ranking_key]["column"]
    ranked = gdf.dropna(subset=[column]).sort_values(column, ascending=False)
    return ranked[DISPLAY_COLUMNS + [column]].head(n)


def render_rankings_tab(gdf: pd.DataFrame) -> None:
    col1, col2 = st.columns([3, 1])
    ranking_key = col1.selectbox("Ranking", list(RANKINGS.keys()))
    n = col2.slider("Nº de hexágonos", min_value=5, max_value=30, value=10)

    result = top_n_by_ranking(gdf, ranking_key, n)
    column = RANKINGS[ranking_key]["column"]

    if result.empty:
        st.info("No hay hexágonos con datos para este ranking.")
        return

    fig = px.bar(
        result.sort_values(column),
        x=column,
        y="h3_index",
        color="municipio",
        orientation="h",
        title=ranking_key,
    )
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(result, width="stretch")
