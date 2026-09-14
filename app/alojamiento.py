import pandas as pd
import plotly.express as px
import streamlit as st

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
        st.metric("Rating medio Booking", summary["rating_booking_medio"])
    with col2.container(border=True):
        st.metric("Rating medio TripAdvisor", summary["rating_tripadvisor_medio"])
    with col3.container(border=True):
        st.metric("Reseñas Booking totales", summary["total_reviews_booking"])

    fig = px.pie(
        breakdown,
        names="tipo",
        values="cantidad",
        title="Distribución del tipo de alojamiento",
        color_discrete_sequence=["#1e3a8a", "#eb6834", "#6b7280"],
    )
    st.plotly_chart(fig, use_container_width=True)
