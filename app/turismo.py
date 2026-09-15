import math

import pandas as pd
import plotly.express as px
import streamlit as st

from app.color_scales import ACCENT_TURISMO, ACCENT_TURISMO_AEREO, hex_to_rgba
from app.ui_helpers import add_chart_motion, format_metric, latest_value, render_footer

# (value_column, yoy_delta_column | None, label, kind, help)
HOTELERO_KPI_COLUMNS = [
    (
        "viajeros_entrados_total",
        "crec_viajeros_yoy_pct",
        "🧳 Viajeros entrados",
        "entero",
        "Viajeros alojados en establecimientos hoteleros durante el año.",
    ),
    (
        "pernoctaciones_total",
        "crec_pernoctaciones_yoy_pct",
        "🛌 Pernoctaciones",
        "entero",
        "Noches pernoctadas en establecimientos hoteleros durante el año.",
    ),
    (
        "ocupacion_media_plazas",
        None,
        "📊 Ocupación media plazas",
        "pct",
        "Porcentaje medio de ocupación de plazas hoteleras.",
    ),
    (
        "estancia_media_hotel_dias",
        None,
        "🕐 Estancia media",
        "decimal",
        "Duración media de la estancia en establecimientos hoteleros, en días.",
    ),
]

ESTACIONALIDAD_METRICS = {
    "Pernoctaciones": "pernoctaciones",
    "Viajeros entrados": "viajeros_entrados",
    "Ocupación plazas (%)": "tasa_ocupacion_plazas",
    "Estancia media (días)": "estancia_media_hotel_dias",
}

MES_LABELS = {
    1: "Ene", 2: "Feb", 3: "Mar", 4: "Abr", 5: "May", 6: "Jun",
    7: "Jul", 8: "Ago", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dic",
}
MES_ORDER = [MES_LABELS[m] for m in range(1, 13)]

AENA_KPI_COLUMNS = [
    ("pasajeros", "✈️ Pasajeros", "entero", "Pasajeros totales del aeropuerto en el mes."),
    (
        "operaciones",
        "🛫 Operaciones",
        "entero",
        "Operaciones (despegues + aterrizajes) del aeropuerto en el mes.",
    ),
    (
        "pasajeros_por_operacion",
        "👥 Pasajeros por operación",
        "decimal",
        "Pasajeros medios transportados por cada operación.",
    ),
]


def format_yoy_delta(value) -> str | None:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    return f"{value:+.1f}%"


def get_hotelero_anual_row(df: pd.DataFrame, municipio: str, anio: int) -> pd.Series | None:
    matches = df.loc[(df["municipio"] == municipio) & (df["anio"] == anio)]
    if matches.empty:
        return None
    return matches.iloc[0]


def estacionalidad_by_mes(df: pd.DataFrame, municipio: str, column: str) -> pd.DataFrame:
    subset = df.loc[df["municipio"] == municipio, ["mes", column]]
    result = subset.groupby("mes", as_index=False)[column].mean()
    result = result.rename(columns={column: "valor"}).sort_values("mes")
    result["mes_label"] = result["mes"].map(MES_LABELS)
    return result


def aena_estacionalidad_comparativa(df: pd.DataFrame, column: str = "pasajeros") -> pd.DataFrame:
    grouped = df.groupby(["aeropuerto_nombre", "mes"], as_index=False)[column].mean()
    grouped = grouped.rename(columns={column: "valor"}).sort_values(["aeropuerto_nombre", "mes"])
    grouped["mes_label"] = grouped["mes"].map(MES_LABELS)
    return grouped.reset_index(drop=True)


def get_latest_aena_row(df: pd.DataFrame, aeropuerto_codigo: str) -> pd.Series | None:
    matches = df.loc[df["aeropuerto_codigo"] == aeropuerto_codigo]
    if matches.empty:
        return None
    return matches.sort_values("periodo").iloc[-1]


def aena_series(df: pd.DataFrame, aeropuerto_codigo: str) -> pd.DataFrame:
    return df.loc[df["aeropuerto_codigo"] == aeropuerto_codigo].sort_values("periodo")


def render_turismo_tab(
    hotelero_anual_df: pd.DataFrame,
    hotelero_mensual_df: pd.DataFrame,
    aena_df: pd.DataFrame,
) -> None:
    st.subheader("Turismo hotelero por polo turístico")
    municipios = sorted(hotelero_anual_df["municipio"].dropna().unique().tolist())
    col1, col2 = st.columns([2, 1])
    municipio = col1.selectbox("Municipio", municipios, key="turismo_municipio")
    years = sorted(
        hotelero_anual_df.loc[hotelero_anual_df["municipio"] == municipio, "anio"].unique().tolist()
    )
    anio = col2.selectbox("Año", years, index=len(years) - 1, key="turismo_anio")

    anual_row = get_hotelero_anual_row(hotelero_anual_df, municipio, anio)
    if anual_row is None:
        st.info("No hay datos hoteleros para este municipio en el año seleccionado.")
    else:
        st.caption(anual_row["polo_turistico"])
        cols = st.columns(4)
        for i, (column, delta_column, label, kind, help_text) in enumerate(HOTELERO_KPI_COLUMNS):
            delta = format_yoy_delta(anual_row.get(delta_column)) if delta_column else None
            with cols[i % 4].container(border=True):
                st.metric(label, format_metric(anual_row.get(column), kind), delta=delta, help=help_text)

    st.subheader("Estacionalidad")
    metrica_label = st.selectbox(
        "Métrica", list(ESTACIONALIDAD_METRICS.keys()), key="turismo_estacionalidad_metrica"
    )
    serie = estacionalidad_by_mes(hotelero_mensual_df, municipio, ESTACIONALIDAD_METRICS[metrica_label])
    fig = px.bar(
        serie,
        x="mes_label",
        y="valor",
        category_orders={"mes_label": MES_ORDER},
        title=f"{metrica_label} media por mes — {municipio}",
    )
    fig.update_traces(marker_color=ACCENT_TURISMO)
    add_chart_motion(fig)
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Tráfico aéreo")
    aeropuertos = sorted(aena_df["aeropuerto_nombre"].dropna().unique().tolist())
    aeropuerto_nombre = st.selectbox("Aeropuerto", aeropuertos, key="turismo_aeropuerto")
    codigo = aena_df.loc[aena_df["aeropuerto_nombre"] == aeropuerto_nombre, "aeropuerto_codigo"].iloc[0]

    latest_row = get_latest_aena_row(aena_df, codigo)
    if latest_row is not None:
        st.caption(f"Último dato: {latest_row['periodo']}")
        cols = st.columns(3)
        for i, (column, label, kind, help_text) in enumerate(AENA_KPI_COLUMNS):
            with cols[i].container(border=True):
                st.metric(label, format_metric(latest_row.get(column), kind), help=help_text)

    serie_aena = aena_series(aena_df, codigo)
    fig_aena = px.area(
        serie_aena, x="periodo", y="pasajeros", title=f"Pasajeros mensuales — {aeropuerto_nombre}"
    )
    fig_aena.update_traces(
        line_color=ACCENT_TURISMO_AEREO, line_shape="spline", fillcolor=hex_to_rgba(ACCENT_TURISMO_AEREO, 0.15)
    )
    add_chart_motion(fig_aena)
    st.plotly_chart(fig_aena, use_container_width=True)

    st.subheader("Estacionalidad comparada: TFS vs. TFN")
    st.caption(
        "Tenerife Sur (tráfico internacional predominante, pico en invierno) frente a "
        "Tenerife Norte (tráfico nacional e interinsular, pico en verano)."
    )
    serie_comparativa = aena_estacionalidad_comparativa(aena_df, "pasajeros")
    fig_comparativa = px.line(
        serie_comparativa,
        x="mes_label",
        y="valor",
        color="aeropuerto_nombre",
        category_orders={"mes_label": MES_ORDER},
        markers=True,
        color_discrete_map={
            "Tenerife Sur - Reina Sofía": ACCENT_TURISMO,
            "Tenerife Norte - Ciudad de La Laguna": ACCENT_TURISMO_AEREO,
        },
        title="Pasajeros medios por mes — TFS vs. TFN",
    )
    add_chart_motion(fig_comparativa)
    st.plotly_chart(fig_comparativa, use_container_width=True)

    render_footer(
        "gold.gold_turismo_hotelero_anual, gold.gold_turismo_hotelero_mensual, gold.gold_aena_pasajeros",
        as_of=latest_value(hotelero_anual_df["anio"]),
    )
