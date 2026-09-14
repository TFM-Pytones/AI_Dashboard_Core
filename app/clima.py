import pandas as pd
import plotly.express as px
import streamlit as st

from app.ui_helpers import add_chart_motion, render_footer

# prefix: column prefix in gold_h3_master (suffixed _q1.._q4 per trimestre).
# unidad/help: shown next to the chart so the numbers aren't left unexplained.
CLIMATE_VARIABLES = {
    "Temperatura": {
        "prefix": "temp_media",
        "unidad": "°C",
        "help": "Temperatura media del aire, en grados Celsius.",
    },
    "Lluvia": {
        "prefix": "lluvia_mm",
        "unidad": "mm",
        "help": "Precipitación acumulada media, en milímetros (litros por metro cuadrado).",
    },
    "Viento": {
        "prefix": "vel_viento_media",
        "unidad": "m/s",
        "help": "Velocidad media del viento, en metros por segundo.",
    },
    "Humedad": {
        "prefix": "humedad_media",
        "unidad": "%",
        "help": "Humedad relativa media del aire, en porcentaje.",
    },
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
    variable = CLIMATE_VARIABLES[variable_label]
    unidad = variable["unidad"]

    st.caption(f"📏 Unidad: **{unidad}** — {variable['help']}")

    result = climate_by_trimestre(gdf, variable["prefix"])
    fig = px.line(
        result,
        x="trimestre",
        y="valor",
        markers=True,
        title=f"{variable_label} media por trimestre ({unidad})",
        labels={"trimestre": "Trimestre", "valor": f"{variable_label} ({unidad})"},
    )
    fig.update_traces(line_color="#1e3a8a")
    add_chart_motion(fig)
    st.plotly_chart(fig, use_container_width=True)

    render_footer("silver_clima_agrocabildo (agregado a hexágono H3)")
