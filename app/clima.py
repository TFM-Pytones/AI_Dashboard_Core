import pandas as pd
import plotly.express as px
import streamlit as st

CLIMATE_VARIABLES = {
    "Temperatura": "temp_media",
    "Lluvia": "lluvia_mm",
    "Viento": "vel_viento_media",
    "Humedad": "humedad_media",
}

TRIMESTRES = ["Q1", "Q2", "Q3", "Q4"]


def climate_by_trimestre(gdf: pd.DataFrame, variable_prefix: str) -> pd.DataFrame:
    rows = []
    for i, trimestre in enumerate(TRIMESTRES, start=1):
        column = f"{variable_prefix}_q{i}"
        rows.append({"trimestre": trimestre, "valor": gdf[column].mean()})
    return pd.DataFrame(rows)


def render_clima_tab(gdf: pd.DataFrame) -> None:
    variable_label = st.selectbox("Variable climática", list(CLIMATE_VARIABLES.keys()))
    prefix = CLIMATE_VARIABLES[variable_label]

    result = climate_by_trimestre(gdf, prefix)
    fig = px.line(
        result,
        x="trimestre",
        y="valor",
        markers=True,
        title=f"{variable_label} media por trimestre",
    )
    fig.update_traces(line_color="#2a78d6")
    st.plotly_chart(fig, use_container_width=True)
