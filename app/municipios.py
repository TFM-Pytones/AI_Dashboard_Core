import pandas as pd
import streamlit as st

from app.detail_panel import format_kpi_value

HEX_KPI_COLUMNS = [
    ("n_hexagonos", "Hexágonos analizados"),
    ("n_establecimientos_registro", "Alojamientos registrados"),
    ("n_plazas_registro", "Plazas registradas"),
    ("rating_booking_medio", "Rating Booking"),
    ("rating_tripadvisor_medio", "Rating TripAdvisor"),
    ("ndvi_medio", "NDVI medio"),
]

# NOTA: silver_istac_anual tiene un bug de ingesta confirmado (auditado
# 2026-09-09) -- poblacion_15_64, poblacion_65_mas y edad_media traen
# exactamente el mismo valor que poblacion_total en todas las filas (p.ej.
# Adeje 2025: las 4 columnas valen 50612). Es un problema del pipeline de
# ingestion/istac/, no de este dashboard -- reportado al equipo. Mientras
# tanto solo se muestra poblacion_total, la unica columna de esta tabla en
# la que se puede confiar.
ISTAC_ANUAL_KPI_COLUMNS = [
    ("poblacion_total", "Población"),
]

# NOTA: el esquema real de silver_istac_mensual ya no coincide con
# dbt_project/models/silver/istac/silver_istac_mensual.sql (auditado
# 2026-09-09) -- las columnas que trae hoy son de vivienda vacacional
# (*_vv), no las genericas pernoctaciones/plazas_ofertadas/tasa_ocupacion_plazas
# que describe ese archivo. Se usan las columnas reales.
ISTAC_MENSUAL_KPI_COLUMNS = [
    ("paro_registrado", "Paro registrado"),
    ("tasa_ocupacion_vv", "Ocupación viviendas vacacionales (%)"),
    ("plazas_vv", "Plazas de vivienda vacacional"),
]


def get_municipio_row(df: pd.DataFrame, municipio: str) -> pd.Series | None:
    matches = df.loc[df["municipio"] == municipio]
    if matches.empty:
        return None
    return matches.iloc[0]


def list_available_years(istac_anual_df: pd.DataFrame) -> list[int]:
    return sorted(istac_anual_df["anio"].dropna().unique().tolist())


def get_istac_anual_row(istac_anual_df: pd.DataFrame, municipio: str, anio: int) -> pd.Series | None:
    matches = istac_anual_df.loc[
        (istac_anual_df["municipio"] == municipio) & (istac_anual_df["anio"] == anio)
    ]
    if matches.empty:
        return None
    return matches.iloc[0]


def get_istac_mensual_row_for_year(
    istac_mensual_df: pd.DataFrame, municipio: str, anio: int
) -> pd.Series | None:
    matches = istac_mensual_df.loc[
        (istac_mensual_df["municipio"] == municipio)
        & (istac_mensual_df["periodo_codigo"].str.startswith(str(anio)))
    ]
    if matches.empty:
        return None
    return matches.sort_values("periodo_codigo").iloc[-1]


def render_municipios_tab(
    municipio_master_df: pd.DataFrame,
    istac_anual_df: pd.DataFrame,
    istac_mensual_df: pd.DataFrame,
) -> None:
    col1, col2 = st.columns([2, 1])
    municipio = col1.selectbox(
        "Municipio", sorted(municipio_master_df["municipio"].dropna().unique().tolist())
    )
    years = list_available_years(istac_anual_df)
    anio = col2.selectbox("Año", years, index=len(years) - 1)

    hex_row = get_municipio_row(municipio_master_df, municipio)
    if hex_row is None:
        st.warning("No hay datos para este municipio.")
        return

    anual_row = get_istac_anual_row(istac_anual_df, municipio, anio)
    mensual_row = get_istac_mensual_row_for_year(istac_mensual_df, municipio, anio)

    periodo_caption = mensual_row["periodo_codigo"] if mensual_row is not None else "sin datos"
    st.caption(f"Población de {anio} · Ocupación/paro de {periodo_caption}")

    st.subheader("Oferta turística (hexágonos)")
    cols = st.columns(3)
    for i, (column, label) in enumerate(HEX_KPI_COLUMNS):
        cols[i % 3].metric(label, format_kpi_value(hex_row.get(column)))

    st.subheader(f"Población y economía ({anio})")
    cols = st.columns(2)
    for i, (column, label) in enumerate(ISTAC_ANUAL_KPI_COLUMNS):
        value = anual_row.get(column) if anual_row is not None else None
        cols[i % 2].metric(label, format_kpi_value(value))

    st.subheader("Turismo y empleo (último mes disponible del año)")
    cols = st.columns(3)
    for i, (column, label) in enumerate(ISTAC_MENSUAL_KPI_COLUMNS):
        value = mensual_row.get(column) if mensual_row is not None else None
        cols[i % 3].metric(label, format_kpi_value(value))
