import base64
from pathlib import Path

import plotly.express as px
import streamlit as st

from app.alojamiento import render_alojamiento_tab
from app.clima import render_clima_tab
from app.data import (
    filter_by_municipio,
    get_engine,
    list_municipios,
    load_accesibilidad,
    load_aena_pasajeros,
    load_h3_master,
    load_isocronas,
    load_municipio_anual,
    load_municipio_empleo,
    load_municipio_master,
    load_nlp_chunks,
    load_sentimiento,
    load_topicos_municipio,
    load_turismo_hotelero_anual,
    load_turismo_hotelero_mensual,
    merge_accesibilidad,
    merge_h3_data,
)
from app.detail_panel import render_detail_panel
from app.map_layers import DEFAULT_HEXAGON_OPACITY, METRICS, build_deck, build_isocronas_layer, list_destinos
from app.municipios import render_municipios_tab
from app.rankings import render_rankings_tab
from app.summary import compute_summary_stats, restriction_counts_dataframe
from app.table_view import build_table_column_config, filter_table, prepare_table_view
from app.temas import render_temas_tab
from app.turismo import render_turismo_tab
from app.ui_helpers import format_metric, render_footer

st.set_page_config(page_title="AI-Dashboard Tenerife", page_icon="🌋", layout="wide")

HERO_IMAGE_B64 = base64.b64encode(
    (Path(__file__).parent / "assets" / "hero_puerto_cruz.jpg").read_bytes()
).decode("utf-8")

st.markdown(
    f"""
    <style>
    .block-container {{
        padding-top: 1rem;
        max-width: 100%;
    }}
    .hero-banner {{
        position: relative;
        height: 420px;
        margin: -1rem -1rem 1.5rem -1rem;
        width: calc(100% + 2rem);
        background-image:
            linear-gradient(100deg, rgba(10,10,8,0.55) 0%, rgba(10,10,8,0.20) 50%, rgba(10,10,8,0.0) 80%),
            url(data:image/jpeg;base64,{HERO_IMAGE_B64});
        background-size: cover;
        background-position: center 50%;
        display: flex;
        flex-direction: column;
        justify-content: center;
        padding: 0 clamp(1.5rem, 5vw, 4rem);
        border-bottom: 5px solid #1e3a8a;
    }}
    .hero-banner h1 {{
        color: white;
        font-size: clamp(1.8rem, 3.2vw, 2.9rem);
        margin: 0 0 0.5rem 0;
        text-shadow: 0 2px 12px rgba(0,0,0,0.35);
    }}
    .hero-banner p {{
        color: #e8eefc;
        font-size: clamp(1rem, 1.4vw, 1.3rem);
        margin: 0;
        max-width: 46ch;
        text-shadow: 0 1px 8px rgba(0,0,0,0.35);
    }}
    </style>
    <div class="hero-banner">
        <h1>AI-Dashboard — Oferta turística de Tenerife</h1>
        <p>Analítica geoespacial por hexágono H3: alojamiento, clima, satélite y economía municipal</p>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.spinner("Cargando datos del dashboard..."):
    engine = get_engine()
    h3_master = load_h3_master(engine)
    sentimiento = load_sentimiento(engine)
    accesibilidad = load_accesibilidad(engine)
    isocronas = load_isocronas(engine)
    municipio_master = load_municipio_master(engine)
    municipio_anual = load_municipio_anual(engine)
    municipio_empleo = load_municipio_empleo(engine)
    topicos_municipio = load_topicos_municipio(engine)
    nlp_chunks = load_nlp_chunks(engine)
    turismo_hotelero_anual = load_turismo_hotelero_anual(engine)
    turismo_hotelero_mensual = load_turismo_hotelero_mensual(engine)
    aena_pasajeros = load_aena_pasajeros(engine)

    full_gdf = merge_h3_data(h3_master, sentimiento)
    full_gdf = merge_accesibilidad(full_gdf, accesibilidad)


def page_resumen() -> None:
    stats = compute_summary_stats(full_gdf)

    col1, col2, col3, col4 = st.columns(4)
    with col1.container(border=True):
        st.metric(
            "🔷 Hexágonos analizados",
            format_metric(stats["total_hexagonos"], "entero"),
            help="Total de hexágonos H3 con datos disponibles en el dashboard.",
        )
    with col2.container(border=True):
        st.metric(
            "✅ Sin restricción legal",
            format_metric(stats["pct_sin_restriccion"], "pct"),
            help="Porcentaje de hexágonos sin solape con un Espacio Natural Protegido ni zona turística oficial.",
        )
    with col3.container(border=True):
        st.metric(
            "😊 Con datos de sentimiento",
            format_metric(stats["pct_con_sentimiento"], "pct"),
            help="Porcentaje de hexágonos con al menos una reseña analizada por NLP.",
        )
    with col4.container(border=True):
        st.metric(
            "🏛️ Municipios",
            format_metric(stats["n_municipios"], "entero"),
            help="Municipios de Tenerife representados en los datos.",
        )

    st.subheader("Reparto de restricciones legales")
    restriction_df = restriction_counts_dataframe(stats["restriction_counts"])
    fig_restriction = px.bar(restriction_df, x="restriction_category", y="n_hexagonos")
    fig_restriction.update_traces(marker_color="#1e3a8a")
    fig_restriction.update_layout(xaxis_title=None, yaxis_title="Nº de hexágonos")
    st.plotly_chart(fig_restriction, use_container_width=True)

    col5, col6 = st.columns(2)
    with col5.container(border=True):
        st.metric(
            "📈 Municipio con más oferta registrada",
            stats["municipio_mas_oferta"],
            help="Municipio con más alojamientos turísticos registrados.",
        )
    with col6.container(border=True):
        st.metric(
            "📉 Municipio con menos oferta registrada",
            stats["municipio_menos_oferta"],
            help="Municipio con menos alojamientos turísticos registrados.",
        )

    render_footer("gold.gold_h3_master, gold.gold_h3_accesibilidad, gold.gold_sentimiento_h3")


def page_mapa() -> None:
    with st.sidebar:
        st.subheader("Filtros del mapa")
        show_hexagons = st.checkbox("Mostrar capa de hexágonos", value=True)
        metric_key = st.selectbox("Capa del mapa", list(METRICS.keys()), disabled=not show_hexagons)
        hex_opacity = st.slider(
            "Opacidad de hexágonos",
            min_value=0.05,
            max_value=1.0,
            value=DEFAULT_HEXAGON_OPACITY,
            step=0.05,
            disabled=not show_hexagons,
            help="Más bajo = se ve más el satélite de fondo. Más alto = se ve más el color de los hexágonos.",
        )
        map_municipio = st.selectbox("Municipio", ["Todos"] + list_municipios(full_gdf), key="map_municipio")
        show_isocronas = st.checkbox("Mostrar isócronas")
        isocrona_destino = None
        if show_isocronas:
            isocrona_destino = st.selectbox("Destino de referencia", list_destinos(isocronas))

    filtered_gdf = filter_by_municipio(full_gdf, map_municipio)

    if map_municipio != "Todos":
        st.caption(f"🔍 Filtrando por municipio: **{map_municipio}**")

    map_col, detail_col = st.columns([3, 2])

    with map_col:
        deck = build_deck(filtered_gdf, metric_key, show_hexagons=show_hexagons, opacity=hex_opacity)
        if show_isocronas and isocrona_destino:
            deck.layers.append(build_isocronas_layer(isocronas, isocrona_destino))
        st.pydeck_chart(deck, on_select="rerun", selection_mode="single-object", key="h3_map")

    selected_h3_index = None
    event = st.session_state.get("h3_map")
    if event is not None:
        picked = event.get("selection", {}).get("objects", {}).get("h3_index", [])
        if picked:
            selected_h3_index = picked[0].get("h3_index")

    with detail_col:
        render_detail_panel(full_gdf, selected_h3_index)


def page_tabla() -> None:
    col1, col2 = st.columns(2)
    tabla_municipio = col1.selectbox(
        "Municipio", ["Todos"] + list_municipios(full_gdf), key="tabla_municipio"
    )
    tabla_restriccion = col2.selectbox(
        "Restricción legal",
        ["Todas"] + sorted(full_gdf["restriction_category"].dropna().unique().tolist()),
        key="tabla_restriccion",
    )

    active_filters = []
    if tabla_municipio != "Todos":
        active_filters.append(f"Municipio: **{tabla_municipio}**")
    if tabla_restriccion != "Todas":
        active_filters.append(f"Restricción: **{tabla_restriccion}**")
    if active_filters:
        st.caption("🔍 Filtrando por " + " · ".join(active_filters))

    show_technical = st.checkbox(
        "Mostrar columnas técnicas (ID de hexágono, coordenadas, satélite...)", value=False
    )

    tabla_filtrada = filter_table(full_gdf, tabla_municipio, tabla_restriccion)
    tabla_mostrable = prepare_table_view(tabla_filtrada, show_technical=show_technical)

    st.dataframe(
        tabla_mostrable,
        width="stretch",
        hide_index=True,
        column_config=build_table_column_config(show_technical=show_technical),
    )
    st.download_button(
        "Descargar CSV",
        data=tabla_mostrable.to_csv(index=False).encode("utf-8"),
        file_name="hexagonos_tenerife.csv",
        mime="text/csv",
    )

    render_footer("gold.gold_h3_master, gold.gold_h3_accesibilidad, gold.gold_sentimiento_h3")


def page_rankings() -> None:
    render_rankings_tab(full_gdf)


def page_clima() -> None:
    clima_municipio = st.selectbox(
        "Municipio", ["Todos"] + list_municipios(full_gdf), key="clima_municipio"
    )
    if clima_municipio != "Todos":
        st.caption(f"🔍 Filtrando por municipio: **{clima_municipio}**")
    render_clima_tab(filter_by_municipio(full_gdf, clima_municipio))


def page_municipios() -> None:
    render_municipios_tab(municipio_master, municipio_anual, municipio_empleo)


def page_alojamiento() -> None:
    alojamiento_municipio = st.selectbox(
        "Municipio", ["Todos"] + list_municipios(full_gdf), key="alojamiento_municipio"
    )
    if alojamiento_municipio != "Todos":
        st.caption(f"🔍 Filtrando por municipio: **{alojamiento_municipio}**")
    render_alojamiento_tab(filter_by_municipio(full_gdf, alojamiento_municipio))


def page_temas() -> None:
    render_temas_tab(topicos_municipio, nlp_chunks)


def page_turismo() -> None:
    render_turismo_tab(turismo_hotelero_anual, turismo_hotelero_mensual, aena_pasajeros)


pages = [
    st.Page(page_resumen, title="Resumen", icon="📊", default=True),
    st.Page(page_mapa, title="Mapa", icon="🗺️"),
    st.Page(page_tabla, title="Tabla", icon="📋"),
    st.Page(page_rankings, title="Rankings", icon="🏆"),
    st.Page(page_clima, title="Clima", icon="🌡️"),
    st.Page(page_municipios, title="Municipios", icon="🏛️"),
    st.Page(page_alojamiento, title="Alojamiento", icon="🏨"),
    st.Page(page_temas, title="Temas", icon="💬"),
    st.Page(page_turismo, title="Turismo", icon="✈️"),
]

pg = st.navigation(pages)
pg.run()
