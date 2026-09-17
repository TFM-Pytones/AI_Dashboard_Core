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
        "db_nombre": "Temperatura",
    },
    "Precipitación": {
        "prefix": "lluvia_mm",
        "unidad": "mm",
        "help": "Precipitación acumulada media, en milímetros (litros por metro cuadrado).",
        "color": ACCENT_CLIMA_LLUVIA,
        "db_nombre": "Precipitación",
    },
    "Velocidad viento": {
        "prefix": "vel_viento_media",
        "unidad": "m/s",
        "help": "Velocidad media del viento, en metros por segundo.",
        "color": ACCENT_CLIMA_VIENTO,
        "db_nombre": "Velocidad del viento",
    },
    "Humedad relativa": {
        "prefix": "humedad_media",
        "unidad": "%",
        "help": "Humedad relativa media del aire, en porcentaje.",
        "color": ACCENT_CLIMA_HUMEDAD,
        "db_nombre": "Humedad relativa",
    },
}

# Alias de compatibilidad para llamadas previas
CLIMATE_VARIABLES["Lluvia"] = CLIMATE_VARIABLES["Precipitación"]
CLIMATE_VARIABLES["Viento"] = CLIMATE_VARIABLES["Velocidad viento"]
CLIMATE_VARIABLES["Humedad"] = CLIMATE_VARIABLES["Humedad relativa"]

TRIMESTRES = ["Q1", "Q2", "Q3", "Q4"]


def climate_by_trimestre(gdf: pd.DataFrame, variable_prefix: str) -> pd.DataFrame:
    rows = []
    for i, trimestre in enumerate(TRIMESTRES, start=1):
        column = f"{variable_prefix}_q{i}"
        rows.append({"trimestre": trimestre, "valor": gdf[column].mean()})
    return pd.DataFrame(rows)


def climate_value_anual(gdf: pd.DataFrame, variable_prefix: str) -> float:
    return gdf[f"{variable_prefix}_anual"].mean()


def render_clima_tab(
    gdf: pd.DataFrame,
    clima_anual_df: pd.DataFrame | None = None,
    municipio: str = "Todos",
) -> None:
    col_v1, col_v2 = st.columns([1, 1])
    vista = col_v1.radio(
        "Tipo de visualización",
        ["Media por trimestre (Q)", "Evolución anual (2022–2026)"],
        horizontal=True,
        help="Elige entre el patrón estacional por trimestres (Q1 a Q4) o la evolución histórica anual (2022–2026).",
    )

    selector_keys = ["Temperatura", "Precipitación", "Velocidad viento", "Humedad relativa"]
    variable_label = col_v2.selectbox("Variable climática", selector_keys)
    variable = CLIMATE_VARIABLES[variable_label]
    unidad = variable["unidad"]
    color = variable["color"]

    st.caption(f"📏 Unidad: **{unidad}** — {variable['help']}")

    nombre_ambito = f" — {municipio}" if municipio != "Todos" else " — Media insular"

    if vista == "Media por trimestre (Q)":
        result = climate_by_trimestre(gdf, variable["prefix"])
        fig = px.area(
            result,
            x="trimestre",
            y="valor",
            markers=True,
            title=f"{variable_label} media por trimestre ({unidad}){nombre_ambito}",
            labels={"trimestre": "Trimestre", "valor": f"{variable_label} ({unidad})"},
        )
        fig.update_traces(line_color=color, line_shape="spline", fillcolor=hex_to_rgba(color, 0.15))
        add_chart_motion(fig)
        st.plotly_chart(fig, width="stretch")

        valor_anual = climate_value_anual(gdf, variable["prefix"])
        st.caption(f"📅 La {variable_label.lower()} media anual es **{valor_anual:.1f} {unidad}**.")
    else:
        # Evolución anual histórica (2022–2026)
        db_var = variable.get("db_nombre", variable_label)
        if clima_anual_df is not None and not clima_anual_df.empty:
            sub = clima_anual_df[
                clima_anual_df["variable_nombre"].str.lower().str.startswith(db_var[:5].lower())
            ].copy()
            if municipio != "Todos":
                sub = sub[sub["municipio"] == municipio]

            if not sub.empty:
                serie_anual = sub.groupby("anio", as_index=False)["valor"].mean().sort_values("anio")
                fig = px.area(
                    serie_anual,
                    x="anio",
                    y="valor",
                    markers=True,
                    title=f"Evolución anual de {variable_label.lower()} ({unidad}){nombre_ambito}",
                    labels={"anio": "Año", "valor": f"{variable_label} ({unidad})"},
                )
                fig.update_traces(
                    line_color=color,
                    line_shape="spline",
                    fillcolor=hex_to_rgba(color, 0.15),
                    marker=dict(size=8, color=color),
                )
                fig.update_xaxes(type="category")
                add_chart_motion(fig)
                st.plotly_chart(fig, width="stretch")
                st.caption(f"📊 Evolución histórica anual registrada por la red agroclimática de Agrocabildo (2022–2026).")
            else:
                st.info(f"No hay registros anuales de {variable_label} para el municipio seleccionado.")
        else:
            st.info(f"Cargando serie temporal anual de {variable_label}...")
