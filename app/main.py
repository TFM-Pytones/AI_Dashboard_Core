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
    load_municipio_mensual,
    load_nlp_chunks,
    load_sentimiento,
    load_topicos_municipio,
    load_turismo_hotelero_anual,
    load_turismo_hotelero_mensual,
    merge_accesibilidad,
    merge_h3_data,
)
from app.detail_panel import render_detail_panel
from app.map_layers import (
    DEFAULT_HEXAGON_OPACITY,
    METRICS,
    build_deck,
    build_isocronas_layer,
    legend_html,
    list_destinos,
)
from app.municipios import render_municipios_tab
from app.rankings import RANKINGS, render_rankings_tab
from app.summary import compute_summary_stats, restriction_counts_dataframe
from app.table_view import build_table_column_config, filter_table, prepare_table_view
from app.temas import render_temas_tab
from app.turismo import render_turismo_tab
from app.ui_helpers import add_chart_motion, format_metric, render_footer

st.set_page_config(page_title="AI-Dashboard Tenerife", page_icon="🌋", layout="wide")

st.markdown(
    """
    <style>
    .block-container {
        padding-top: 1rem;
        max-width: 100%;
    }

    @keyframes fadeInUp {
        from { opacity: 0; transform: translateY(14px); }
        to { opacity: 1; transform: translateY(0); }
    }

    .hero-banner {
        position: relative;
        height: 260px;
        margin: -1rem -1rem 1.5rem -1rem;
        width: calc(100% + 2rem);
        background-size: cover;
        background-position: center 50%;
        display: flex;
        flex-direction: column;
        justify-content: center;
        padding: 0 clamp(1.5rem, 5vw, 4rem);
        border-bottom: 5px solid #1e3a8a;
        animation: fadeInUp 0.6s ease-out;
    }
    .hero-banner--main {
        height: 420px;
    }
    .hero-banner h1 {
        color: white;
        font-size: clamp(1.6rem, 3vw, 2.6rem);
        margin: 0 0 0.4rem 0;
        text-shadow: 0 2px 12px rgba(0,0,0,0.35);
    }
    .hero-banner--main h1 {
        font-size: clamp(1.8rem, 3.2vw, 2.9rem);
    }
    .hero-banner p {
        color: #e8eefc;
        font-size: clamp(0.95rem, 1.3vw, 1.2rem);
        margin: 0;
        max-width: 46ch;
        text-shadow: 0 1px 8px rgba(0,0,0,0.35);
    }

    /* KPI cards (st.container(border=True) wrapping a st.metric): fade in on
       render, subtle resting shadow for depth, lift further on hover. */
    [data-testid="stVerticalBlock"]:has(> [data-testid="stElementContainer"] [data-testid="stMetric"]) {
        animation: fadeInUp 0.5s ease-out;
        box-shadow: 0 1px 3px rgba(15, 23, 42, 0.06);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    [data-testid="stVerticalBlock"]:has(> [data-testid="stElementContainer"] [data-testid="stMetric"]):hover {
        transform: translateY(-3px);
        box-shadow: 0 10px 24px rgba(30, 58, 138, 0.16);
    }

    /* Very subtle gradient instead of flat white, for a bit of depth. */
    [data-testid="stMain"] {
        background: linear-gradient(180deg, #fefefe 0%, #f4f6fb 100%);
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def render_page_banner(image_filename: str, title: str, subtitle: str, main: bool = False) -> None:
    image_b64 = base64.b64encode((Path(__file__).parent / "assets" / image_filename).read_bytes()).decode(
        "utf-8"
    )
    css_class = "hero-banner hero-banner--main" if main else "hero-banner"
    st.markdown(
        f"""
        <div class="{css_class}" style="background-image:
            linear-gradient(100deg, rgba(10,10,8,0.55) 0%, rgba(10,10,8,0.20) 50%, rgba(10,10,8,0.0) 80%),
            url(data:image/jpeg;base64,{image_b64});">
            <h1>{title}</h1>
            <p>{subtitle}</p>
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
    municipio_mensual = load_municipio_mensual(engine)
    topicos_municipio = load_topicos_municipio(engine)
    nlp_chunks = load_nlp_chunks(engine)
    turismo_hotelero_anual = load_turismo_hotelero_anual(engine)
    turismo_hotelero_mensual = load_turismo_hotelero_mensual(engine)
    aena_pasajeros = load_aena_pasajeros(engine)

    full_gdf = merge_h3_data(h3_master, sentimiento)
    full_gdf = merge_accesibilidad(full_gdf, accesibilidad)


def page_resumen() -> None:
    render_page_banner(
        "hero_puerto_cruz.jpg",
        "AI-Dashboard — Oferta turística de Tenerife",
        "Analítica geoespacial por hexágono H3: alojamiento, clima, satélite y economía municipal",
        main=True,
    )
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
    add_chart_motion(fig_restriction)
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

    st.subheader("Explora el dashboard")
    overview_cards = [
        (
            nav_mapa,
            "🗺️",
            "Mapa",
            "Colorea Tenerife hexágono a hexágono: densidad hotelera, sentimiento, accesibilidad y más.",
            f"{len(METRICS)} capas de color",
        ),
        (
            nav_tabla,
            "📋",
            "Tabla",
            "Consulta y descarga todos los datos en una tabla filtrable.",
            f"{format_metric(len(full_gdf), 'entero')} hexágonos",
        ),
        (
            nav_rankings,
            "🏆",
            "Rankings",
            "Compara municipios: más vegetación, mejor valorados, más turísticos, más calurosos.",
            f"{len(RANKINGS)} rankings",
        ),
        (
            nav_clima,
            "🌡️",
            "Clima",
            "Temperatura, lluvia, viento y humedad por trimestre y municipio.",
            "4 variables climáticas",
        ),
        (
            nav_municipios,
            "🏛️",
            "Municipios",
            "Economía, empleo y turismo por municipio, con evolución anual y mensual.",
            f"{municipio_master['municipio'].nunique()} municipios",
        ),
        (
            nav_alojamiento,
            "🏨",
            "Alojamiento",
            "Reputación y tipo de alojamiento: hoteles, viviendas vacacionales y extrahoteleros.",
            f"{format_metric(int(full_gdf['n_reviews_booking'].sum()), 'entero')} reseñas Booking",
        ),
        (
            nav_temas,
            "💬",
            "Temas y Opinión",
            "Qué opinan los visitantes de verdad, extraído con NLP de miles de reseñas.",
            f"{format_metric(len(nlp_chunks), 'entero')} opiniones analizadas",
        ),
        (
            nav_turismo,
            "✈️",
            "Turismo",
            "Ocupación hotelera y tráfico aéreo por polo turístico, con estacionalidad mensual.",
            f"{aena_pasajeros['aeropuerto_nombre'].nunique()} aeropuertos monitorizados",
        ),
    ]
    overview_cols = st.columns(4)
    for i, (page_obj, icon, title, description, highlight) in enumerate(overview_cards):
        with overview_cols[i % 4].container(border=True):
            st.markdown(f"#### {icon} {title}")
            st.caption(description)
            st.markdown(f"**{highlight}**")
            st.page_link(page_obj, label="Explorar →", use_container_width=True)

    render_footer("gold.gold_h3_master, gold.gold_h3_accesibilidad, gold.gold_sentimiento_h3")


def page_mapa() -> None:
    with st.sidebar:
        st.subheader("Filtros del mapa")
        show_hexagons = st.checkbox("Mostrar capa de hexágonos", value=False)
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

    if show_hexagons:
        st.caption(f"Leyenda — {metric_key}")
        st.markdown(legend_html(metric_key, filtered_gdf), unsafe_allow_html=True)

    deck = build_deck(filtered_gdf, metric_key, show_hexagons=show_hexagons, opacity=hex_opacity)
    if show_isocronas and isocrona_destino:
        deck.layers.append(build_isocronas_layer(isocronas, isocrona_destino))
    st.pydeck_chart(deck, on_select="rerun", selection_mode="single-object", key="h3_map", height=650)

    selected_h3_index = None
    event = st.session_state.get("h3_map")
    if event is not None:
        picked = event.get("selection", {}).get("objects", {}).get("h3_index", [])
        if picked:
            selected_h3_index = picked[0].get("h3_index")

    st.divider()
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
    render_page_banner(
        "clima_montana.jpg", "Clima", "Temperatura, lluvia, viento y humedad por municipio"
    )
    clima_municipio = st.selectbox(
        "Municipio", ["Todos"] + list_municipios(full_gdf), key="clima_municipio"
    )
    if clima_municipio != "Todos":
        st.caption(f"🔍 Filtrando por municipio: **{clima_municipio}**")
    render_clima_tab(filter_by_municipio(full_gdf, clima_municipio))


def page_municipios() -> None:
    render_municipios_tab(municipio_master, municipio_anual, municipio_empleo, municipio_mensual)


def page_alojamiento() -> None:
    render_page_banner(
        "alojamiento_hotel.jpg",
        "Alojamiento",
        "Reputación y distribución de la oferta de alojamiento turístico",
    )
    alojamiento_municipio = st.selectbox(
        "Municipio", ["Todos"] + list_municipios(full_gdf), key="alojamiento_municipio"
    )
    if alojamiento_municipio != "Todos":
        st.caption(f"🔍 Filtrando por municipio: **{alojamiento_municipio}**")
    render_alojamiento_tab(filter_by_municipio(full_gdf, alojamiento_municipio))


def page_temas() -> None:
    render_page_banner(
        "temas_cafe.jpg",
        "Temas y Opinión",
        "Qué dicen realmente los visitantes, extraído con NLP de miles de reseñas",
    )
    render_temas_tab(topicos_municipio, nlp_chunks)


def page_turismo() -> None:
    render_page_banner(
        "turismo_playa.jpg",
        "Turismo",
        "Ocupación hotelera, tráfico aéreo y estacionalidad por polo turístico",
    )
    render_turismo_tab(turismo_hotelero_anual, turismo_hotelero_mensual, aena_pasajeros)


nav_resumen = st.Page(page_resumen, title="Resumen", icon="📊", default=True)
nav_mapa = st.Page(page_mapa, title="Mapa", icon="🗺️")
nav_tabla = st.Page(page_tabla, title="Tabla", icon="📋")
nav_rankings = st.Page(page_rankings, title="Rankings", icon="🏆")
nav_clima = st.Page(page_clima, title="Clima", icon="🌡️")
nav_municipios = st.Page(page_municipios, title="Municipios", icon="🏛️")
nav_alojamiento = st.Page(page_alojamiento, title="Alojamiento", icon="🏨")
nav_temas = st.Page(page_temas, title="Temas", icon="💬")
nav_turismo = st.Page(page_turismo, title="Turismo", icon="✈️")

pages = [
    nav_resumen,
    nav_mapa,
    nav_tabla,
    nav_rankings,
    nav_clima,
    nav_municipios,
    nav_alojamiento,
    nav_temas,
    nav_turismo,
]

pg = st.navigation(pages)
pg.run()
