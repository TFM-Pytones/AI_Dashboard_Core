import math

import pandas as pd
import plotly.express as px
import streamlit as st

from app.detail_panel import format_kpi_value

# (value_column, yoy_delta_column | None, label)
HOTELERO_KPI_COLUMNS = [
    ("viajeros_entrados_total", "crec_viajeros_yoy_pct", "Viajeros entrados"),
    ("pernoctaciones_total", "crec_pernoctaciones_yoy_pct", "Pernoctaciones"),
    ("ocupacion_media_plazas", None, "Ocupación media plazas (%)"),
    ("estancia_media_hotel_dias", None, "Estancia media (días)"),
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
    ("pasajeros", "Pasajeros"),
    ("operaciones", "Operaciones"),
    ("pasajeros_por_operacion", "Pasajeros por operación"),
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
        for i, (column, delta_column, label) in enumerate(HOTELERO_KPI_COLUMNS):
            delta = format_yoy_delta(anual_row.get(delta_column)) if delta_column else None
            cols[i % 4].metric(label, format_kpi_value(anual_row.get(column)), delta=delta)

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
    fig.update_traces(marker_color="#2a78d6")
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Tráfico aéreo")
    aeropuertos = sorted(aena_df["aeropuerto_nombre"].dropna().unique().tolist())
    aeropuerto_nombre = st.selectbox("Aeropuerto", aeropuertos, key="turismo_aeropuerto")
    codigo = aena_df.loc[aena_df["aeropuerto_nombre"] == aeropuerto_nombre, "aeropuerto_codigo"].iloc[0]

    latest_row = get_latest_aena_row(aena_df, codigo)
    if latest_row is not None:
        st.caption(f"Último dato: {latest_row['periodo']}")
        cols = st.columns(3)
        for i, (column, label) in enumerate(AENA_KPI_COLUMNS):
            cols[i].metric(label, format_kpi_value(latest_row.get(column)))

    serie_aena = aena_series(aena_df, codigo)
    fig_aena = px.line(
        serie_aena, x="periodo", y="pasajeros", title=f"Pasajeros mensuales — {aeropuerto_nombre}"
    )
    fig_aena.update_traces(line_color="#eb6834")
    st.plotly_chart(fig_aena, use_container_width=True)
