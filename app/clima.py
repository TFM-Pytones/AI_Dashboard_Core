import pandas as pd
import plotly.express as px
import streamlit as st

from app.color_scales import (
    ACCENT_CLIMA_HUMEDAD,
    ACCENT_CLIMA_LLUVIA,
    ACCENT_CLIMA_TEMPERATURA,
    ACCENT_CLIMA_VIENTO,
    hex_to_rgba,
)
from app.ui_helpers import add_chart_motion

# prefix: column prefix in gold_h3_master (suffixed _q1.._q4 per trimestre).
# unidad/help: shown next to the chart so the numbers aren't left unexplained.
# color: each variable gets its own hue (heat=red, water=blue, air=teal,
# moisture=purple) instead of every climate chart being the same navy.
CLIMATE_VARIABLES = {
    "Temperatura": {
        "prefix": "temp_media",
        "unidad": "°C",
        "help": "Temperatura media del aire, en grados Celsius.",
        "color": ACCENT_CLIMA_TEMPERATURA,
    },
    "Lluvia": {
        "prefix": "lluvia_mm",
        "unidad": "mm",
        "help": "Precipitación acumulada media, en milímetros (litros por metro cuadrado).",
        "color": ACCENT_CLIMA_LLUVIA,
    },
    "Viento": {
        "prefix": "vel_viento_media",
        "unidad": "m/s",
        "help": "Velocidad media del viento, en metros por segundo.",
        "color": ACCENT_CLIMA_VIENTO,
    },
    "Humedad": {
        "prefix": "humedad_media",
        "unidad": "%",
        "help": "Humedad relativa media del aire, en porcentaje.",
        "color": ACCENT_CLIMA_HUMEDAD,
    },
}

TRIMESTRES = ["Q1", "Q2", "Q3", "Q4"]


def climate_by_trimestre(gdf: pd.DataFrame, variable_prefix: str) -> pd.DataFrame:
    rows = []
    for i, trimestre in enumerate(TRIMESTRES, start=1):
        column = f"{variable_prefix}_q{i}"
        rows.append({"trimestre": trimestre, "valor": gdf[column].mean()})
    return pd.DataFrame(rows)


def climate_value_anual(gdf: pd.DataFrame, variable_prefix: str) -> float:
    return gdf[f"{variable_prefix}_anual"].mean()


def render_clima_tab(gdf: pd.DataFrame) -> None:
    variable_label = st.selectbox("Variable climática", list(CLIMATE_VARIABLES.keys()))
    variable = CLIMATE_VARIABLES[variable_label]
    unidad = variable["unidad"]

    st.caption(f"📏 Unidad: **{unidad}** — {variable['help']}")

    color = variable["color"]
    result = climate_by_trimestre(gdf, variable["prefix"])
    fig = px.area(
        result,
        x="trimestre",
        y="valor",
        markers=True,
        title=f"{variable_label} media por trimestre ({unidad})",
        labels={"trimestre": "Trimestre", "valor": f"{variable_label} ({unidad})"},
    )
    fig.update_traces(line_color=color, line_shape="spline", fillcolor=hex_to_rgba(color, 0.15))
    add_chart_motion(fig)
    st.plotly_chart(fig, width="stretch")

    valor_anual = climate_value_anual(gdf, variable["prefix"])
    st.caption(f"📅 La {variable_label.lower()} media anual es **{valor_anual:.1f} {unidad}**.")
