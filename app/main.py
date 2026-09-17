import os
from dotenv import load_dotenv

load_dotenv(override=True)

# Debe fijarse antes de que se importe torch (vía sentence-transformers en el
# asistente): evita que torch._inductor compile y lance un subproceso de
# prueba para detectar el juego de instrucciones de la CPU. Ese subproceso se
# hace con fork() desde el hilo en segundo plano donde Streamlit ejecuta el
# script, y choca con el manejador atfork de libproj (cargado por geopandas
# en el Mapa), provocando un SIGSEGV. No usamos torch.compile, así que la
# comprobación no aporta nada y se puede omitir con seguridad.
os.environ.setdefault("TORCHINDUCTOR_VEC_ISA_OK", "1")

import base64
from pathlib import Path

import plotly.express as px
import streamlit as st

from app.alojamiento import render_alojamiento_tab
from app.arquetipos import render_arquetipos_tab
from app.asistente import render_floating_assistant
from app.clima import render_clima_tab
from app.color_scales import RESTRICTION_COLOR_MAP_HEX
from app.data import (
    filter_by_municipio,
    get_engine,
    list_municipios,
    load_accesibilidad,
    load_aena_pasajeros,
    load_bienes_culturales,
    load_esg,
    load_estaciones_agrocabildo,
    load_gtfs_rutas,
    load_h3_clusters,
    load_h3_master,
    load_isocronas,
    load_municipio_anual,
    load_municipio_empleo,
    load_municipio_master,
    load_municipio_mensual,
    load_nlp_chunks,
    load_nlp_chunks_count,
    load_oportunidad,
    load_ptna,
    load_sentimiento,
    load_topicos_municipio,
    load_turismo_hotelero_anual,
    load_turismo_hotelero_mensual,
    merge_accesibilidad,
    merge_clusters_and_analytics,
    merge_h3_data,
)
from app.detail_panel import render_detail_panel
from app.map_state import get_selected_h3_index
from app.map_layers import (
    DEFAULT_HEXAGON_OPACITY,
    ISOCRONAS_DESTINOS_INFO,
    METRICS,
    MUNICIPIO_METRICS,
    bic_legend_html,
    build_bic_layer,
    build_deck,
    build_estaciones_agrocabildo_layer,
    build_gtfs_rutas_layer,
    build_highlight_layer,
    build_isocronas_layer,
    build_isocronas_origen_pins_layer,
    build_isocronas_pins_labels_layer,
    build_municipio_layer,
    estaciones_legend_html,
    gtfs_legend_html,
    isocronas_legend_html,
    legend_html,
    list_destinos,
    municipio_legend_html,
)
from app.municipios import render_municipios_tab
from app.rankings import RANKINGS, render_rankings_tab
from app.summary import compute_summary_stats, restriction_counts_dataframe
from app.table_view import build_column_glossary, build_table_column_config, filter_table, prepare_table_view
from app.temas import render_temas_tab
from app.turismo import render_turismo_tab
from app.ui_helpers import add_chart_motion, format_metric

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

    /* Sliders: espacio superior suficiente para que el número flotante (stThumbValue) no se corte por arriba */
    div[data-testid="stSlider"] {
        padding-top: 0.75rem;
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
    n_opiniones = load_nlp_chunks_count(engine)
    turismo_hotelero_anual = load_turismo_hotelero_anual(engine)
    turismo_hotelero_mensual = load_turismo_hotelero_mensual(engine)
    aena_pasajeros = load_aena_pasajeros(engine)
    clusters = load_h3_clusters(engine)
    ptna = load_ptna(engine)
    esg = load_esg(engine)
    oportunidad = load_oportunidad(engine)

    full_gdf = merge_h3_data(h3_master, sentimiento)
    full_gdf = merge_accesibilidad(full_gdf, accesibilidad)
    full_gdf = merge_clusters_and_analytics(full_gdf, clusters, ptna, esg, oportunidad)


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
    medida_restriccion = st.radio(
        "Unidad de medida:",
        ["Nº de hexágonos", "Nº de km²"],
        horizontal=True,
        key="resumen_medida_restriccion",
    )
    is_km2 = medida_restriccion == "Nº de km²"
    data_dict = stats.get("restriction_areas", {}) if is_km2 else stats.get("restriction_counts", {})
    y_col = "area_km2" if is_km2 else "n_hexagonos"
    y_label = "Superficie (km²)" if is_km2 else "Nº de hexágonos"

    restriction_df = restriction_counts_dataframe(data_dict, y_col)
    fig_restriction = px.bar(restriction_df, x="restriction_category", y=y_col)
    fig_restriction.update_traces(
        marker_color=[RESTRICTION_COLOR_MAP_HEX.get(c, "#64748b") for c in restriction_df["restriction_category"]],
        width=0.4,
    )
    fig_restriction.update_layout(
        xaxis_title=None, yaxis_title=y_label, showlegend=False, height=320
    )
    add_chart_motion(fig_restriction)
    st.plotly_chart(fig_restriction, width="stretch")

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
            nav_arquetipos,
            "🎯",
            "Oportunidades TUI",
            "Matriz estratégica Eje 1 (Saturación) vs Eje 2 (Rural), clústeres territoriales y 5 arquetipos de producto.",
            "5 arquetipos de producto",
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
            nav_alojamiento_temas,
            "🏨",
            "Alojamiento y Opinión",
            "Reputación y tipo de alojamiento, y qué opinan los visitantes de verdad, extraído con NLP.",
            f"{format_metric(n_opiniones, 'entero')} opiniones analizadas",
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
            st.page_link(page_obj, label="Explorar →", width="stretch")


def page_mapa() -> None:
    st.markdown("<div style='margin-top: 1.5rem;'></div>", unsafe_allow_html=True)
    with st.sidebar:
        st.subheader("Capa activa")
        capa_activa = st.radio(
            "Selecciona una capa:",
            options=[
                "Malla de hexágonos H3",
                "Capa municipal",
                "Isócronas de transporte",
                "Líneas de guagua (GTFS)",
                "Bienes de Interés Cultural (BIC)",
                "Estaciones meteorológicas (Agrocabildo)",
                "Ninguna (solo mapa satélite)",
            ],
            index=0,
            help="Solo puede haber una capa activa a la vez para evitar solapamientos visuales.",
        )
        show_hexagons = capa_activa == "Malla de hexágonos H3"
        show_municipios = capa_activa == "Capa municipal"
        show_isocronas = capa_activa == "Isócronas de transporte"
        show_gtfs = capa_activa == "Líneas de guagua (GTFS)"
        show_bic = capa_activa == "Bienes de Interés Cultural (BIC)"
        show_estaciones = capa_activa == "Estaciones meteorológicas (Agrocabildo)"

        st.divider()
        st.subheader("Opciones de capa")
        if show_hexagons or show_municipios:
            map_municipio = st.selectbox("Municipio", ["Todos"] + list_municipios(full_gdf), key="map_municipio")
        else:
            map_municipio = "Todos"

        if show_hexagons:
            metric_key = st.selectbox("Capa del mapa (H3)", list(METRICS.keys()))
            hex_opacity = st.slider(
                "Opacidad de hexágonos",
                min_value=0.05,
                max_value=1.0,
                value=DEFAULT_HEXAGON_OPACITY,
                step=0.05,
                help="Más bajo = se ve más el satélite de fondo. Más alto = se ve más el color de los hexágonos.",
            )
        else:
            metric_key = list(METRICS.keys())[0]
            hex_opacity = DEFAULT_HEXAGON_OPACITY

        if show_municipios:
            municipio_metric_key = st.selectbox(
                "Métrica municipal", list(MUNICIPIO_METRICS.keys())
            )
        else:
            municipio_metric_key = list(MUNICIPIO_METRICS.keys())[0]

        isocronas_seleccionadas: list[str] = []
        if show_isocronas:
            isocronas_seleccionadas = st.multiselect(
                "Punto de referencia",
                options=list(ISOCRONAS_DESTINOS_INFO.keys()),
                default=["tfs", "tfn"],
                format_func=lambda k: ISOCRONAS_DESTINOS_INFO[k]["label"],
                help="Puedes seleccionar uno o varios puntos de referencia para comparar sus áreas de alcance simultáneamente.",
            )

        st.divider()
        st.subheader("Perspectiva 3D")
        enable_3d = st.toggle(
            "Relieve 3D (MDT)",
            value=False,
            disabled=not show_hexagons,
            help="Modela la orografía real de Tenerife elevando cada hexágono desde el nivel del mar hasta su cota media según el MDT.",
        )
        if not show_hexagons:
            st.caption("ℹ️ *El relieve 3D modela la orografía MDT sobre la malla de hexágonos H3.*")
        if enable_3d and show_hexagons:
            col_3d_1, col_3d_2 = st.columns(2)
            elevation_scale = col_3d_1.slider(
                "Exageración",
                min_value=0.5,
                max_value=3.0,
                value=1.0,
                step=0.1,
                help="Factor multiplicador del relieve vertical.",
            )
            pitch = col_3d_2.slider(
                "Inclinación (°)",
                min_value=20,
                max_value=70,
                value=50,
                step=5,
                help="Ángulo de inclinación de la cámara (50° es el óptimo para apreciar el relieve).",
            )
        else:
            elevation_scale = 1.0
            pitch = 0

        if not os.environ.get("MAPBOX_API_KEY", "").strip():
            st.info(
                "💡 **Mapa base CARTO activo:** Para visualizar la fotografía satelital de fondo de alta resolución, añade tu clave de Mapbox en tu archivo `.env` (`MAPBOX_API_KEY=pk...`)."
            )

    gtfs_rutas_gdf = None
    if show_gtfs:
        with st.spinner("Cargando trazado insular de guaguas (GTFS)..."):
            gtfs_rutas_gdf = load_gtfs_rutas(engine)

    bic_gdf = None
    if show_bic:
        with st.spinner("Cargando Bienes de Interés Cultural (BIC)..."):
            bic_gdf = load_bienes_culturales(engine)

    estaciones_gdf = None
    if show_estaciones:
        with st.spinner("Cargando red agroclimática de Agrocabildo..."):
            estaciones_gdf = load_estaciones_agrocabildo(engine)

    filtered_gdf = filter_by_municipio(full_gdf, map_municipio)

    if map_municipio != "Todos":
        st.caption(f"🔍 Filtrando por municipio: **{map_municipio}**")

    if show_hexagons:
        st.caption(f"Leyenda — {metric_key}")
        st.markdown(legend_html(metric_key, filtered_gdf), unsafe_allow_html=True)
        if enable_3d:
            st.caption(
                "⛰️ **Relieve 3D activo:** Hexágonos extruidos desde cota 0 según el MDT. "
                "💡 *Tip: Mantén presionado **Ctrl + arrastrar** (o botón derecho) para rotar la cámara libremente en 3D.*"
            )

    if show_municipios:
        st.caption(f"Leyenda — {municipio_metric_key} (Capa municipal)")
        st.markdown(municipio_legend_html(municipio_metric_key, municipio_master), unsafe_allow_html=True)

    if show_isocronas and isocronas_seleccionadas:
        nombres_dest = ", ".join(ISOCRONAS_DESTINOS_INFO[d]["label"] for d in isocronas_seleccionadas if d in ISOCRONAS_DESTINOS_INFO)
        st.caption(f"Leyenda — Isócronas de conducción: **{nombres_dest}**")
        st.markdown(isocronas_legend_html(), unsafe_allow_html=True)

    if show_gtfs:
        st.caption("Leyenda — Red de Transporte Insular de Guaguas (TITSA)")
        st.markdown(gtfs_legend_html(), unsafe_allow_html=True)

    if show_bic:
        st.caption("Leyenda — Bienes de Interés Cultural protegidos (BIC)")
        st.markdown(bic_legend_html(), unsafe_allow_html=True)

    if show_estaciones:
        st.caption("Leyenda — Estaciones Meteorológicas de Agrocabildo")
        st.markdown(estaciones_legend_html(), unsafe_allow_html=True)

    selected_h3_index = get_selected_h3_index()

    custom_tooltip = None
    if show_gtfs:
        custom_tooltip = {"text": "{operador}\nLínea {route_short_name}: {route_long_name}"}
    elif show_bic:
        custom_tooltip = {"text": "{nombre}\nTipo: {tipo}\nMunicipio: {municipio}"}
    elif show_estaciones:
        custom_tooltip = {"text": "{nombre_estacion} ({municipio})\nAltitud: {altitud_m} m"}
    elif show_isocronas:
        custom_tooltip = {"text": "{label}\n{destino_nombre}\nAlcance: ≤ {rango_min} min"}

    deck = build_deck(
        filtered_gdf,
        metric_key,
        show_hexagons=show_hexagons,
        opacity=hex_opacity,
        is_3d=enable_3d and show_hexagons,
        elevation_scale=elevation_scale,
        pitch=pitch,
        tooltip=custom_tooltip,
    )
    if show_municipios:
        deck.layers.append(build_municipio_layer(municipio_master, municipio_metric_key))
    if show_isocronas and isocronas_seleccionadas:
        deck.layers.append(build_isocronas_layer(isocronas, isocronas_seleccionadas))
        deck.layers.append(build_isocronas_origen_pins_layer(isocronas_seleccionadas))
        deck.layers.append(build_isocronas_pins_labels_layer(isocronas_seleccionadas))
    if show_gtfs and gtfs_rutas_gdf is not None:
        deck.layers.append(build_gtfs_rutas_layer(gtfs_rutas_gdf))
    if show_bic and bic_gdf is not None:
        deck.layers.append(build_bic_layer(bic_gdf))
    if show_estaciones and estaciones_gdf is not None:
        deck.layers.append(build_estaciones_agrocabildo_layer(estaciones_gdf))

    if selected_h3_index and show_hexagons:
        deck.layers.append(build_highlight_layer(selected_h3_index))

    st.pydeck_chart(deck, on_select="rerun", selection_mode="single-object", key="h3_map", height=650)

    st.divider()
    render_detail_panel(full_gdf, selected_h3_index)


def page_tabla() -> None:
    st.markdown("<div style='margin-top: 1.5rem;'></div>", unsafe_allow_html=True)
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
        column_config=build_table_column_config(show_technical=show_technical, gdf=tabla_filtrada),
    )
    st.download_button(
        "Descargar CSV",
        data=tabla_mostrable.to_csv(index=False).encode("utf-8"),
        file_name="hexagonos_tenerife.csv",
        mime="text/csv",
    )

    st.subheader("Leyenda de columnas")
    glosario = build_column_glossary()
    columna_buscada = st.selectbox(
        "Busca una columna para ver qué significa",
        list(glosario.keys()),
        index=None,
        placeholder="Escribe el nombre de una columna...",
        key="tabla_glosario_busqueda",
    )
    if columna_buscada:
        st.info(glosario[columna_buscada])


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


def page_alojamiento_temas() -> None:
    render_page_banner(
        "alojamiento_hotel.jpg",
        "Alojamiento y Opinión",
        "Oferta de alojamiento, reputación y qué dicen realmente los visitantes, extraído con NLP",
    )

    st.subheader("🏨 Alojamiento")
    alojamiento_municipio = st.selectbox(
        "Municipio", ["Todos"] + list_municipios(full_gdf), key="alojamiento_municipio"
    )
    if alojamiento_municipio != "Todos":
        st.caption(f"🔍 Filtrando por municipio: **{alojamiento_municipio}**")
    render_alojamiento_tab(filter_by_municipio(full_gdf, alojamiento_municipio))

    st.divider()

    st.subheader("💬 Temas y Opinión")
    with st.spinner("Cargando opiniones cualitativas..."):
        chunks = load_nlp_chunks(engine)
    render_temas_tab(topicos_municipio, chunks)


def page_turismo() -> None:
    render_page_banner(
        "turismo_playa.jpg",
        "Turismo",
        "Ocupación hotelera, tráfico aéreo y estacionalidad por polo turístico",
    )
    render_turismo_tab(turismo_hotelero_anual, turismo_hotelero_mensual, aena_pasajeros)


def page_arquetipos() -> None:
    render_page_banner(
        "hero_puerto_cruz.jpg",
        "Oportunidades TUI — Arquetipos y Clústeres",
        "Matriz Estratégica Eje 1 (Saturación continua) vs Eje 2 (Rural infrautilizado), tipología territorial y catálogo",
    )
    render_arquetipos_tab(full_gdf)


nav_resumen = st.Page(page_resumen, title="Resumen", icon="📊", default=True)
nav_mapa = st.Page(page_mapa, title="Mapa", icon="🗺️")
nav_arquetipos = st.Page(page_arquetipos, title="Oportunidades TUI", icon="🎯")
nav_tabla = st.Page(page_tabla, title="Tabla", icon="📋")
nav_rankings = st.Page(page_rankings, title="Rankings", icon="🏆")
nav_clima = st.Page(page_clima, title="Clima", icon="🌡️")
nav_municipios = st.Page(page_municipios, title="Municipios", icon="🏛️")
nav_alojamiento_temas = st.Page(page_alojamiento_temas, title="Alojamiento y Opinión", icon="🏨")
nav_turismo = st.Page(page_turismo, title="Turismo", icon="✈️")

pages = [
    nav_resumen,
    nav_mapa,
    nav_arquetipos,
    nav_tabla,
    nav_rankings,
    nav_clima,
    nav_municipios,
    nav_alojamiento_temas,
    nav_turismo,
]

pg = st.navigation(pages)
pg.run()

# Fuera de pg.run() a propósito: se ejecuta una vez por rerun sin importar
# qué página esté activa, así el botón flotante sale en todas -- ver
# app/asistente.py para el porqué del CSS (position: fixed sobre stPopover).
render_floating_assistant()
