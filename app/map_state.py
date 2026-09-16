import streamlit as st


def get_selected_h3_index() -> str | None:
    """Hexágono H3 actualmente seleccionado en el mapa (page_mapa), leído del
    evento de selección de pydeck guardado en session_state bajo la key
    "h3_map". Vive en su propio módulo (no en app/main.py) para que también
    lo pueda leer app/asistente.py sin crear un import circular."""
    event = st.session_state.get("h3_map")
    if event is None:
        return None
    picked_hex = event.get("selection", {}).get("objects", {}).get("h3_index", [])
    if not picked_hex:
        return None
    return picked_hex[0].get("h3_index")
