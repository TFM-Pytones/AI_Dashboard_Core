import streamlit as st

from app.data import (
    filter_by_municipio,
    get_engine,
    list_municipios,
    load_accesibilidad,
    load_h3_master,
    load_isocronas,
    load_sentimiento,
    merge_accesibilidad,
    merge_h3_data,
)
from app.detail_panel import render_detail_panel
from app.clima import render_clima_tab
from app.map_layers import DEFAULT_HEXAGON_OPACITY, METRICS, build_deck, build_isocronas_layer, list_destinos
from app.rankings import render_rankings_tab
from app.summary import compute_summary_stats
from app.table_view import filter_table, prepare_table_view

st.set_page_config(page_title="AI-Dashboard Tenerife", layout="wide")
st.markdown(
    """
    <style>
    .stTabs [data-baseweb="tab-list"] { gap: 4px; }
    .stTabs [data-baseweb="tab"] {
        background-color: #f0efe8;
        border-radius: 8px 8px 0 0;
        padding: 8px 16px;
    }
    .stTabs [aria-selected="true"] {
        background-color: #2a78d6;
        color: white;
    }
    </style>
    """,
    unsafe_allow_html=True,
)
st.title("AI-Dashboard — Oferta turística de Tenerife")

engine = get_engine()
h3_master = load_h3_master(engine)
sentimiento = load_sentimiento(engine)
accesibilidad = load_accesibilidad(engine)
isocronas = load_isocronas(engine)

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

tab_resumen, tab_mapa, tab_tabla, tab_rankings, tab_clima = st.tabs(
    ["Resumen", "Mapa", "Tabla", "Rankings", "Clima"]
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
