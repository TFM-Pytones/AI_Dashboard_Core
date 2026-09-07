import streamlit as st

from app.data import (
    filter_by_municipio,
    get_engine,
    list_municipios,
    load_h3_master,
    load_sentimiento,
    merge_h3_data,
)
from app.detail_panel import render_detail_panel
from app.map_layers import METRICS, build_deck

st.set_page_config(page_title="AI-Dashboard Tenerife", layout="wide")
st.title("AI-Dashboard — Oferta turística de Tenerife")

engine = get_engine()
h3_master = load_h3_master(engine)
sentimiento = load_sentimiento(engine)
full_gdf = merge_h3_data(h3_master, sentimiento)

with st.sidebar:
    metric_key = st.selectbox("Capa del mapa", list(METRICS.keys()))
    municipio = st.selectbox("Municipio", ["Todos"] + list_municipios(full_gdf))

filtered_gdf = filter_by_municipio(full_gdf, municipio)

map_col, detail_col = st.columns([3, 2])

with map_col:
    deck = build_deck(filtered_gdf, metric_key)
    st.pydeck_chart(deck, on_select="rerun", selection_mode="single-object", key="h3_map")

selected_h3_index = None
event = st.session_state.get("h3_map")
if event is not None:
    picked = event.get("selection", {}).get("objects", {}).get("h3_index", [])
    if picked:
        selected_h3_index = picked[0].get("h3_index")

with detail_col:
    render_detail_panel(full_gdf, selected_h3_index)
