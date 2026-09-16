import pandas as pd
import plotly.express as px
import streamlit as st

from app.color_scales import SEQUENTIAL_TEAL
from app.ui_helpers import add_chart_motion, format_metric

# (column, label, kind, help) -- kind drives number formatting (see
# format_metric); help is shown as an (i) tooltip on the metric tile so the
# raw numbers aren't left unexplained.
KPI_COLUMNS = [
    ("n_hoteles", "🏨 Nº hoteles", "entero", "Hoteles registrados en este hexágono."),
    (
        "n_establecimientos_registro",
        "🛏️ Nº alojamientos registrados",
        "entero",
        "Alojamientos turísticos con registro oficial en este hexágono.",
    ),
    (
        "ndvi_medio",
        "🌿 NDVI medio",
        "decimal2",
        "Índice de vegetación por satélite, de 0 (sin vegetación) a 1 (vegetación densa).",
    ),
    (
        "sentimiento_medio",
        "😊 Sentimiento medio",
        "decimal2",
        "Sentimiento medio de las reseñas analizadas por NLP, de -1 (muy negativo) a 1 (muy positivo).",
    ),
    ("rating_booking_medio", "⭐ Rating Booking", "decimal", "Valoración media en Booking, escala 0-10."),
    (
        "rating_tripadvisor_medio",
        "⭐ Rating TripAdvisor",
        "decimal",
        "Valoración media en TripAdvisor, escala 0-5.",
    ),
]

# gold_h3_accesibilidad has 19 tiempo_*_min columns (one per named destino) plus
# distance/transit columns -- only 3 of them are used as map color layers today
# (see METRICS in map_layers.py). This surfaces the rest as readable text/chart
# in the hex detail panel.
ACCESIBILIDAD_KPI_COLUMNS = [
    (
        "aeropuerto_mas_cercano",
        "✈️ Aeropuerto más cercano",
        "texto",
        "Aeropuerto de Tenerife más cercano por tiempo en coche (TFS = Sur, TFN = Norte).",
    ),
    (
        "tiempo_aeropuerto_min",
        "🕐 Min. al aeropuerto",
        "entero",
        "Minutos estimados en coche hasta el aeropuerto más cercano.",
    ),
    ("dist_hospital_km", "🏥 Km al hospital", "decimal", "Distancia en línea recta al hospital más cercano."),
    ("dist_costa_km", "🌊 Km a la costa", "decimal", "Distancia en línea recta a la costa."),
    (
        "n_paradas_bus_500m",
        "🚌 Paradas de bus (500 m)",
        "entero",
        "Número de paradas de guagua a menos de 500 metros.",
    ),
]

TIEMPO_DESTINOS = [
    ("tiempo_capital_min", "Santa Cruz de Tenerife"),
    ("tiempo_la_laguna_min", "La Laguna"),
    ("tiempo_teide_min", "El Teide"),
    ("tiempo_los_gigantes_min", "Los Gigantes"),
    ("tiempo_el_medano_min", "El Médano"),
    ("tiempo_garachico_min", "Garachico"),
    ("tiempo_anaga_min", "Anaga"),
    ("tiempo_masca_min", "Masca"),
    ("tiempo_vilaflor_min", "Vilaflor"),
    ("tiempo_la_orotava_min", "La Orotava"),
    ("tiempo_guimar_min", "Güímar"),
    ("tiempo_buenavista_min", "Buenavista del Norte"),
    ("tiempo_arico_min", "Arico"),
    ("tiempo_candelaria_min", "Candelaria"),
]


def _has_overlap(value) -> bool:
    if value is None or pd.isna(value):
        return False
    return value > 0


# gold_h3_master dropped its old boolean es_enp/es_zona_turistica_oficial
# columns (confirmed by direct schema audit 2026-09-14) in favor of
# pct_area_enp/pct_area_zona_turistica -- the fraction of the hexagon's area
# overlapping that polygon type. Any overlap at all (> 0) reproduces the old
# boolean's semantics.
def restriction_badges(row) -> list[str]:
    badges = []
    if _has_overlap(row.get("pct_area_enp")):
        badges.append("⚠️ Espacio Natural Protegido")
    if _has_overlap(row.get("pct_area_zona_turistica")):
        badges.append("🏖️ Zona turística oficial")
    return badges


def nearest_destinos(row, n: int = 5) -> pd.DataFrame:
    pairs = [{"destino": label, "minutos": row.get(column)} for column, label in TIEMPO_DESTINOS]
    df = pd.DataFrame(pairs).dropna(subset=["minutos"])
    return df.sort_values("minutos").head(n)


def municipio_aspect_comparison(gdf: pd.DataFrame, h3_index: str) -> pd.DataFrame | None:
    if h3_index not in gdf["h3_index"].values:
        return None
    row = gdf.loc[gdf["h3_index"] == h3_index].iloc[0]
    peers = gdf[gdf["municipio"] == row["municipio"]]
    counts = peers["queja_principal"].dropna().value_counts().reset_index()
    counts.columns = ["aspecto", "n_hexagonos"]
    counts["es_seleccionado"] = counts["aspecto"] == row["queja_principal"]
    return counts


def render_detail_panel(gdf: pd.DataFrame, selected_h3_index: str | None) -> None:
    if selected_h3_index is None:
        st.info("Haz clic en un hexágono del mapa para ver su detalle.")
        return
    matches = gdf.loc[gdf["h3_index"] == selected_h3_index]
    if matches.empty:
        st.warning("No hay datos para el hexágono seleccionado.")
        return
    row = matches.iloc[0]
    st.subheader(f"Hexágono {selected_h3_index}")
    for badge in restriction_badges(row):
        st.caption(badge)
    cols = st.columns(3)
    for i, (column, label, kind, help_text) in enumerate(KPI_COLUMNS):
        with cols[i % 3].container(border=True):
            st.metric(label, format_metric(row.get(column), kind), help=help_text)

    st.subheader("Accesibilidad")
    acc_cols = st.columns(3)
    for i, (column, label, kind, help_text) in enumerate(ACCESIBILIDAD_KPI_COLUMNS):
        with acc_cols[i % 3].container(border=True):
            st.metric(label, format_metric(row.get(column), kind), help=help_text)

    destinos = nearest_destinos(row)
    if not destinos.empty:
        fig_dest = px.bar(
            destinos.sort_values("minutos"),
            x="minutos",
            y="destino",
            orientation="h",
            color="minutos",
            color_continuous_scale=list(SEQUENTIAL_TEAL),
            title="Destinos más cercanos (min. en coche)",
        )
        fig_dest.update_layout(coloraxis_showscale=False)
        add_chart_motion(fig_dest)
        st.plotly_chart(fig_dest, width="stretch")

    comparison = municipio_aspect_comparison(gdf, selected_h3_index)
    if comparison is None or comparison.empty:
        st.caption("Sin aspectos NLP registrados para este municipio.")
    else:
        fig = px.bar(
            comparison,
            x="aspecto",
            y="n_hexagonos",
            color="es_seleccionado",
            color_discrete_map={True: "#1e3a8a", False: "#d1d5db"},
            title=f"Aspectos más mencionados en {row['municipio']}",
        )
        add_chart_motion(fig)
        st.plotly_chart(fig, width="stretch")
