import pandas as pd
import plotly.express as px
import streamlit as st

from app.ui_helpers import add_chart_motion, format_metric, render_footer

ACCOMMODATION_TYPES = [
    ("n_hoteles", "Hoteles"),
    ("n_vv", "Viviendas vacacionales"),
    ("n_extrahoteleros", "Extrahoteleros"),
]


def accommodation_breakdown(gdf: pd.DataFrame) -> pd.DataFrame:
    rows = [{"tipo": label, "cantidad": int(gdf[column].sum())} for column, label in ACCOMMODATION_TYPES]
    return pd.DataFrame(rows)


def reputation_summary(gdf: pd.DataFrame) -> dict:
    return {
        "rating_booking_medio": round(gdf["rating_booking_medio"].mean(), 2),
        "rating_tripadvisor_medio": round(gdf["rating_tripadvisor_medio"].mean(), 2),
        "total_reviews_booking": int(gdf["n_reviews_booking"].sum()),
    }


def render_alojamiento_tab(gdf: pd.DataFrame) -> None:
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
            "📝 Reseñas Booking totales",
            format_metric(summary["total_reviews_booking"], "entero"),
            help="Número total de reseñas recibidas en Booking.",
        )

    fig = px.pie(
        breakdown,
        names="tipo",
        values="cantidad",
        title="Distribución del tipo de alojamiento",
        color_discrete_sequence=["#1e3a8a", "#eb6834", "#6b7280"],
    )
    add_chart_motion(fig)
    st.plotly_chart(fig, use_container_width=True)

    render_footer("gold.gold_h3_master (alojamiento oficial y reputación)")
