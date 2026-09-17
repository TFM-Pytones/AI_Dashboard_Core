import pandas as pd
import plotly.express as px
import streamlit as st

from app.color_scales import ACCENT_ALOJAMIENTO
from app.ui_helpers import add_chart_motion, format_metric

ACCOMMODATION_TYPES = [
    ("n_hoteles", "Hoteles"),
    ("n_vv", "Viviendas vacacionales"),
    ("n_extrahoteleros", "Extrahoteleros"),
]


def accommodation_breakdown(gdf: pd.DataFrame) -> pd.DataFrame:
    rows = [{"tipo": label, "cantidad": int(gdf[column].sum())} for column, label in ACCOMMODATION_TYPES]
    return pd.DataFrame(rows)


def reputation_summary(gdf: pd.DataFrame) -> dict:
    total_reviews_booking = int(gdf["n_reviews_booking"].sum()) if "n_reviews_booking" in gdf.columns else 0
    total_reviews_ta = int(gdf["n_reviews_tripadvisor"].sum()) if "n_reviews_tripadvisor" in gdf.columns else 0
    total_reviews = (
        int(gdf["n_reviews_total"].sum())
        if "n_reviews_total" in gdf.columns
        else (total_reviews_booking + total_reviews_ta)
    )
    return {
        "rating_booking_medio": round(gdf["rating_booking_medio"].mean(), 2) if "rating_booking_medio" in gdf.columns else 0.0,
        "rating_tripadvisor_medio": round(gdf["rating_tripadvisor_medio"].mean(), 2) if "rating_tripadvisor_medio" in gdf.columns else 0.0,
        "total_reviews_booking": total_reviews_booking,
        "total_reviews": total_reviews,
    }


def render_alojamiento_tab(
    gdf: pd.DataFrame,
    alojamiento_breakdown_df: pd.DataFrame | None = None,
    municipio: str = "Todos",
) -> None:
    breakdown = accommodation_breakdown(gdf)
    summary = reputation_summary(gdf)

    col1, col2, col3 = st.columns(3)
    with col1.container(border=True):
        st.metric(
            "⭐ Rating medio Booking",
            format_metric(summary["rating_booking_medio"], "decimal"),
            help="Valoración media en Booking, escala 0-10.",
        )
    with col2.container(border=True):
        st.metric(
            "⭐ Rating medio TripAdvisor",
            format_metric(summary["rating_tripadvisor_medio"], "decimal"),
            help="Valoración media en TripAdvisor, escala 0-5.",
        )
    with col3.container(border=True):
        st.metric(
            "📝 Reseñas totales",
            format_metric(summary["total_reviews"], "entero"),
            help="Número total de reseñas recopiladas (Booking y TripAdvisor).",
        )

    col_d1, _ = st.columns([2, 1])
    dist_mode = col_d1.radio(
        "Distribución por",
        ["Plazas turísticas", "Nº de alojamientos"],
        horizontal=True,
        help="Elige si quieres visualizar el peso de cada modalidad alojativa por capacidad en plazas o por número de establecimientos.",
    )

    nombre_ambito = f" — {municipio}" if municipio != "Todos" else " — Total insular"

    if dist_mode == "Plazas turísticas":
        if alojamiento_breakdown_df is not None and not alojamiento_breakdown_df.empty:
            df_sub = alojamiento_breakdown_df.copy()
            if municipio != "Todos":
                df_sub = df_sub[df_sub["municipio"] == municipio]
            if not df_sub.empty:
                plazas_data = df_sub.groupby("tipo", as_index=False)["plazas"].sum()
                fig = px.pie(
                    plazas_data,
                    names="tipo",
                    values="plazas",
                    title=f"Distribución por plazas turísticas{nombre_ambito}",
                    hole=0.45,
                    color="tipo",
                    color_discrete_map={
                        "Hoteles": ACCENT_ALOJAMIENTO,
                        "Viviendas vacacionales": "#1e3a8a",
                        "Extrahoteleros": "#6b7280",
                    },
                )
            else:
                fig = px.pie(
                    breakdown,
                    names="tipo",
                    values="cantidad",
                    title=f"Distribución del tipo de alojamiento{nombre_ambito}",
                    hole=0.45,
                    color_discrete_sequence=[ACCENT_ALOJAMIENTO, "#1e3a8a", "#6b7280"],
                )
        else:
            # Fallback en caso de que no esté cargada la tabla
            fig = px.pie(
                breakdown,
                names="tipo",
                values="cantidad",
                title=f"Distribución del tipo de alojamiento{nombre_ambito}",
                hole=0.45,
                color_discrete_sequence=[ACCENT_ALOJAMIENTO, "#1e3a8a", "#6b7280"],
            )
    else:
        fig = px.pie(
            breakdown,
            names="tipo",
            values="cantidad",
            title=f"Distribución del tipo de alojamiento (establecimientos){nombre_ambito}",
            hole=0.45,
            color="tipo",
            color_discrete_map={
                "Hoteles": ACCENT_ALOJAMIENTO,
                "Viviendas vacacionales": "#1e3a8a",
                "Extrahoteleros": "#6b7280",
            },
        )

    add_chart_motion(fig)
    st.plotly_chart(fig, width="stretch")
