import pandas as pd
import streamlit as st

from app.data import filter_by_municipio

# (column, label, format) -- the default table view. h3_index, coordinates,
# and the dozens of satellite/climate sub-columns are hidden here and only
# shown when the user opts into the technical view (see show_technical).
CURATED_COLUMNS = [
    ("municipio", "Municipio", None),
    ("restriction_category", "Restricción legal", None),
    ("area_km2", "Área (km²)", "%.2f"),
    ("n_establecimientos_registro", "Alojamientos registrados", "%d"),
    ("n_plazas_registro", "Plazas registradas", "%d"),
    ("n_hoteles", "Hoteles", "%d"),
    ("n_vv", "Viviendas vacacionales", "%d"),
    ("rating_booking_medio", "Rating Booking", "%.1f"),
    ("rating_tripadvisor_medio", "Rating TripAdvisor", "%.1f"),
    ("sentimiento_medio", "Sentimiento medio", "%.2f"),
    ("ndvi_medio", "NDVI medio", "%.2f"),
    ("temp_media_anual", "Temp. media anual (°C)", "%.1f"),
    ("n_pois_total", "Puntos de interés", "%d"),
    ("queja_principal", "Aspecto más mencionado", None),
]


def filter_table(gdf: pd.DataFrame, municipio: str | None, restriction: str | None) -> pd.DataFrame:
    result = filter_by_municipio(gdf, municipio)
    if restriction and restriction != "Todas":
        result = result[result["restriction_category"] == restriction]
    return result


def prepare_table_view(gdf: pd.DataFrame, show_technical: bool = False) -> pd.DataFrame:
    dropped = gdf.drop(columns=["geometry"], errors="ignore")
    if show_technical:
        return dropped
    columns = [column for column, _, _ in CURATED_COLUMNS if column in dropped.columns]
    return dropped[columns]


def build_table_column_config(show_technical: bool = False) -> dict:
    if show_technical:
        return {}
    return {
        column: st.column_config.NumberColumn(label, format=fmt)
        if fmt
        else st.column_config.TextColumn(label)
        for column, label, fmt in CURATED_COLUMNS
    }
