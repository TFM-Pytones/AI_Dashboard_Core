import math

import pandas as pd
import plotly.express as px
import streamlit as st

from app.color_scales import ACCENT_ALOJAMIENTO, ACCENT_MUNICIPIOS, hex_to_rgba
from app.ui_helpers import add_chart_motion, format_metric, latest_value, render_footer

# (column, label, kind, help) -- kind drives number formatting (see format_metric).
HEX_KPI_COLUMNS = [
    ("n_hexagonos", "🔷 Hexágonos analizados", "entero", "Hexágonos H3 analizados en este municipio."),
    (
        "n_establecimientos_registro",
        "🏨 Alojamientos registrados",
        "entero",
        "Alojamientos turísticos con registro oficial.",
    ),
    (
        "n_plazas_registro",
        "🛏️ Plazas registradas",
        "entero",
        "Plazas turísticas registradas (capacidad total).",
    ),
    ("rating_booking_medio", "⭐ Rating Booking", "decimal", "Valoración media en Booking, escala 0-10."),
    (
        "rating_tripadvisor_medio",
        "⭐ Rating TripAdvisor",
        "decimal",
        "Valoración media en TripAdvisor, escala 0-5.",
    ),
    ("ndvi_medio", "🌿 NDVI medio", "decimal2", "Índice de vegetación por satélite, de 0 a 1."),
]

# (value_column, yoy_delta_column | None, label, kind, help)
ECONOMIA_KPI_COLUMNS = [
    ("poblacion", None, "👥 Población", "entero", "Población total del municipio (fuente: ISTAC)."),
    (
        "paro_medio",
        "var_paro_yoy_pct",
        "📉 Paro medio",
        "entero",
        "Personas en situación de paro registrado, media del año.",
    ),
    (
        "empleo_total_medio",
        "crec_empleo_total_yoy_pct",
        "💼 Empleo total medio",
        "entero",
        "Personas empleadas (asalariados + autónomos), media del año.",
    ),
    (
        "empleo_autonomos_medio",
        "crec_empleo_autonomos_yoy_pct",
        "🧑‍💼 Empleo autónomos medio",
        "entero",
        "Trabajadores autónomos, media del año.",
    ),
]

TURISMO_VV_KPI_COLUMNS = [
    (
        "plazas_vv_media",
        "crec_plazas_vv_yoy_pct",
        "🏘️ Plazas VV media",
        "entero",
        "Plazas medias registradas en vivienda vacacional (VV).",
    ),
    (
        "ingresos_vv_media_mensual",
        "crec_ingresos_mensual_yoy_pct",
        "💶 Ingresos VV media mensual",
        "euro",
        "Ingresos medios mensuales estimados por vivienda vacacional.",
    ),
    (
        "tasa_ocupacion_vv_media",
        None,
        "📊 Ocupación VV media",
        "pct",
        "Porcentaje medio de ocupación de las viviendas vacacionales.",
    ),
    (
        "estancia_media_vv",
        None,
        "🕐 Estancia media VV",
        "decimal",
        "Duración media de la estancia en vivienda vacacional, en días.",
    ),
]

EVOLUCION_METRICS = {
    "Paro medio": "paro_medio",
    "Empleo total medio": "empleo_total_medio",
    "Ingresos VV media mensual": "ingresos_vv_media_mensual",
    "Ocupación VV media (%)": "tasa_ocupacion_vv_media",
}

EVOLUCION_MENSUAL_METRICS = {
    "Paro registrado": "paro_registrado",
    "Plazas VV": "plazas_vv",
    "Ocupación VV (%)": "tasa_ocupacion_vv",
    "Estancia media VV (días)": "estancia_media_vv",
    "Ingresos VV": "ingresos_vv",
    "Alojamientos VV abiertos": "alojamientos_abiertos_vv",
}

EMPLEO_TYPES = [
    ("empleo_asalariados", "Asalariados"),
    ("empleo_autonomos", "Autónomos"),
]


def get_municipio_row(df: pd.DataFrame, municipio: str) -> pd.Series | None:
    matches = df.loc[df["municipio"] == municipio]
    if matches.empty:
        return None
    return matches.iloc[0]


def list_available_years(municipio_anual_df: pd.DataFrame) -> list[int]:
    return sorted(municipio_anual_df["anio"].dropna().unique().tolist())


def get_anual_row(df: pd.DataFrame, municipio: str, anio: int) -> pd.Series | None:
    matches = df.loc[(df["municipio"] == municipio) & (df["anio"] == anio)]
    if matches.empty:
        return None
    return matches.iloc[0]


def format_yoy_delta(value) -> str | None:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    return f"{value:+.1f}%"


def evolucion_series(df: pd.DataFrame, municipio: str, column: str) -> pd.DataFrame:
    rows = df.loc[df["municipio"] == municipio, ["anio", column]].sort_values("anio")
    return rows.rename(columns={column: "valor"})


def evolucion_mensual_series(df: pd.DataFrame, municipio: str, column: str) -> pd.DataFrame:
    rows = df.loc[df["municipio"] == municipio, ["periodo", column]].sort_values("periodo")
    return rows.rename(columns={column: "valor"})


def get_latest_empleo_row(df: pd.DataFrame, municipio: str, anio: int) -> pd.Series | None:
    matches = df.loc[(df["municipio"] == municipio) & (df["anio"] == anio)]
    if matches.empty:
        return None
    return matches.sort_values("periodo").iloc[-1]


def empleo_breakdown(row: pd.Series) -> pd.DataFrame:
    rows = [{"tipo": label, "cantidad": row[column]} for column, label in EMPLEO_TYPES]
    return pd.DataFrame(rows)


def render_municipios_tab(
    municipio_master_df: pd.DataFrame,
    municipio_anual_df: pd.DataFrame,
    municipio_empleo_df: pd.DataFrame,
    municipio_mensual_df: pd.DataFrame,
) -> None:
    st.markdown("<div style='margin-top: 1.5rem;'></div>", unsafe_allow_html=True)
    col1, col2 = st.columns([2, 1])
    municipio = col1.selectbox(
        "Municipio", sorted(municipio_master_df["municipio"].dropna().unique().tolist())
    )
    years = list_available_years(municipio_anual_df)
    anio = col2.selectbox("Año", years, index=len(years) - 1)

    hex_row = get_municipio_row(municipio_master_df, municipio)
    if hex_row is None:
        st.warning("No hay datos para este municipio.")
        return

    st.subheader("Oferta turística (hexágonos)")
    cols = st.columns(3)
    for i, (column, label, kind, help_text) in enumerate(HEX_KPI_COLUMNS):
        with cols[i % 3].container(border=True):
            st.metric(label, format_metric(hex_row.get(column), kind), help=help_text)

    anual_row = get_anual_row(municipio_anual_df, municipio, anio)

    st.subheader(f"Población y economía ({anio})")
    if anual_row is None:
        st.info("No hay datos económicos para este municipio en el año seleccionado.")
    else:
        if not bool(anual_row.get("es_anio_completo", True)):
            st.caption(f"⚠️ Año en curso: datos de solo {int(anual_row['n_meses'])} de 12 meses.")
        cols = st.columns(4)
        for i, (column, delta_column, label, kind, help_text) in enumerate(ECONOMIA_KPI_COLUMNS):
            delta = format_yoy_delta(anual_row.get(delta_column)) if delta_column else None
            with cols[i % 4].container(border=True):
                st.metric(label, format_metric(anual_row.get(column), kind), delta=delta, help=help_text)

        st.subheader("Turismo: vivienda vacacional")
        cols = st.columns(4)
        for i, (column, delta_column, label, kind, help_text) in enumerate(TURISMO_VV_KPI_COLUMNS):
            delta = format_yoy_delta(anual_row.get(delta_column)) if delta_column else None
            with cols[i % 4].container(border=True):
                st.metric(label, format_metric(anual_row.get(column), kind), delta=delta, help=help_text)

    st.subheader("Evolución")
    metrica_label = st.selectbox(
        "Métrica", list(EVOLUCION_METRICS.keys()), key="municipios_evolucion_metrica"
    )
    serie = evolucion_series(municipio_anual_df, municipio, EVOLUCION_METRICS[metrica_label])
    fig = px.area(
        serie, x="anio", y="valor", markers=True, title=f"{metrica_label} por año — {municipio}"
    )
    fig.update_traces(
        line_color=ACCENT_MUNICIPIOS, line_shape="spline", fillcolor=hex_to_rgba(ACCENT_MUNICIPIOS, 0.2)
    )
    add_chart_motion(fig)
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Evolución mensual")
    metrica_mensual_label = st.selectbox(
        "Métrica mensual", list(EVOLUCION_MENSUAL_METRICS.keys()), key="municipios_evolucion_mensual_metrica"
    )
    serie_mensual = evolucion_mensual_series(
        municipio_mensual_df, municipio, EVOLUCION_MENSUAL_METRICS[metrica_mensual_label]
    )
    if serie_mensual.empty:
        st.info("No hay datos mensuales para este municipio.")
    else:
        fig_mensual = px.area(
            serie_mensual, x="periodo", y="valor", title=f"{metrica_mensual_label} por mes — {municipio}"
        )
        fig_mensual.update_traces(
            line_color=ACCENT_MUNICIPIOS, line_shape="spline", fillcolor=hex_to_rgba(ACCENT_MUNICIPIOS, 0.15)
        )
        add_chart_motion(fig_mensual)
        st.plotly_chart(fig_mensual, use_container_width=True)

    st.subheader("Empleo: asalariados vs. autónomos")
    empleo_row = get_latest_empleo_row(municipio_empleo_df, municipio, anio)
    if empleo_row is None:
        st.info("No hay datos de empleo para este municipio en el año seleccionado.")
    else:
        st.caption(f"Datos de {empleo_row['periodo_texto']}")
        breakdown = empleo_breakdown(empleo_row)
        fig_empleo = px.pie(
            breakdown,
            names="tipo",
            values="cantidad",
            title="Reparto de empleo",
            hole=0.45,
            color_discrete_sequence=[ACCENT_MUNICIPIOS, ACCENT_ALOJAMIENTO],
        )
        add_chart_motion(fig_empleo)
        st.plotly_chart(fig_empleo, use_container_width=True)

    render_footer(
        "gold.gold_municipio_master, gold.gold_municipio_anual, gold.gold_municipio_empleo, "
        "gold.gold_municipio_mensual",
        as_of=latest_value(municipio_anual_df["anio"]),
    )
