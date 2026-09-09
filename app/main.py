import base64
from pathlib import Path

import streamlit as st

from app.alojamiento import render_alojamiento_tab
from app.clima import render_clima_tab
from app.data import (
    filter_by_municipio,
    get_engine,
    list_municipios,
    load_accesibilidad,
    load_h3_master,
    load_isocronas,
    load_istac_anual,
    load_istac_mensual,
    load_municipio_master,
    load_sentimiento,
    merge_accesibilidad,
    merge_h3_data,
)
from app.detail_panel import render_detail_panel
from app.map_layers import DEFAULT_HEXAGON_OPACITY, METRICS, build_deck, build_isocronas_layer, list_destinos
from app.municipios import render_municipios_tab
from app.rankings import render_rankings_tab
from app.summary import compute_summary_stats
from app.table_view import filter_table, prepare_table_view

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
    .stTabs [data-baseweb="tab-list"] {{ gap: 4px; }}
    .stTabs [data-baseweb="tab"] {{
        background-color: #f0efe8;
        border-radius: 8px 8px 0 0;
        padding: 8px 16px;
    }}
    .stTabs [aria-selected="true"] {{
        background-color: #2a78d6;
        color: white;
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
        background-position: center 58%;
        display: flex;
        flex-direction: column;
        justify-content: center;
        padding: 0 clamp(1.5rem, 5vw, 4rem);
        border-bottom: 5px solid #2a78d6;
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
    .hero-credit {{
        position: absolute;
        bottom: 0.6rem;
        right: 1rem;
        font-size: 0.7rem;
        color: rgba(255,255,255,0.75);
        background: rgba(13,54,107,0.4);
        padding: 0.2rem 0.6rem;
        border-radius: 999px;
    }}
    </style>
    <div class="hero-banner">
        <h1>AI-Dashboard — Oferta turística de Tenerife</h1>
        <p>Analítica geoespacial por hexágono H3: alojamiento, clima, satélite y economía municipal</p>
        <span class="hero-credit">Foto: Puerto de la Cruz, Atlantic Ambience — Pexels License</span>
    </div>
    """,
    unsafe_allow_html=True,
)

engine = get_engine()
h3_master = load_h3_master(engine)
sentimiento = load_sentimiento(engine)
accesibilidad = load_accesibilidad(engine)
isocronas = load_isocronas(engine)
municipio_master = load_municipio_master(engine)
istac_anual = load_istac_anual(engine)
istac_mensual = load_istac_mensual(engine)

full_gdf = merge_h3_data(h3_master, sentimiento)
full_gdf = merge_accesibilidad(full_gdf, accesibilidad)

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

tab_resumen, tab_mapa, tab_tabla, tab_rankings, tab_clima, tab_municipios, tab_alojamiento = st.tabs(
    [
        "📊 Resumen",
        "🗺️ Mapa",
        "📋 Tabla",
        "🏆 Rankings",
        "🌡️ Clima",
        "🏛️ Municipios",
        "🏨 Alojamiento",
    ]
)

with tab_resumen:
    stats = compute_summary_stats(full_gdf)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Hexágonos analizados", stats["total_hexagonos"])
    col2.metric("Sin restricción legal", f"{stats['pct_sin_restriccion']}%")
    col3.metric("Con datos de sentimiento", f"{stats['pct_con_sentimiento']}%")
    col4.metric("Municipios", stats["n_municipios"])

    st.subheader("Reparto de restricciones legales")
    st.bar_chart(stats["restriction_counts"])

    col5, col6 = st.columns(2)
    col5.metric("Municipio con más oferta registrada", stats["municipio_mas_oferta"])
    col6.metric("Municipio con menos oferta registrada", stats["municipio_menos_oferta"])

with tab_mapa:
    filtered_gdf = filter_by_municipio(full_gdf, map_municipio)

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

with tab_tabla:
    col1, col2 = st.columns(2)
    tabla_municipio = col1.selectbox(
        "Municipio", ["Todos"] + list_municipios(full_gdf), key="tabla_municipio"
    )
    tabla_restriccion = col2.selectbox(
        "Restricción legal",
        ["Todas"] + sorted(full_gdf["restriction_category"].dropna().unique().tolist()),
        key="tabla_restriccion",
    )

    tabla_filtrada = filter_table(full_gdf, tabla_municipio, tabla_restriccion)
    tabla_mostrable = prepare_table_view(tabla_filtrada)

    st.dataframe(tabla_mostrable, width="stretch")
    st.download_button(
        "Descargar CSV",
        data=tabla_mostrable.to_csv(index=False).encode("utf-8"),
        file_name="hexagonos_tenerife.csv",
        mime="text/csv",
    )

with tab_rankings:
    render_rankings_tab(full_gdf)

with tab_clima:
    clima_municipio = st.selectbox(
        "Municipio", ["Todos"] + list_municipios(full_gdf), key="clima_municipio"
    )
    render_clima_tab(filter_by_municipio(full_gdf, clima_municipio))

with tab_municipios:
    render_municipios_tab(municipio_master, istac_anual, istac_mensual)

with tab_alojamiento:
    alojamiento_municipio = st.selectbox(
        "Municipio", ["Todos"] + list_municipios(full_gdf), key="alojamiento_municipio"
    )
    render_alojamiento_tab(filter_by_municipio(full_gdf, alojamiento_municipio))
