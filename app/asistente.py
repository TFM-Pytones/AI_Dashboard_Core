import pandas as pd
import streamlit as st

from analytics.chat.router import clasificar
from analytics.chat.sql_agent import responder_sql
from analytics.rag.rag_answer import responder as responder_rag
from app.data import get_engine, load_accesibilidad, load_h3_master, load_sentimiento, merge_accesibilidad, merge_h3_data
from app.detail_panel import ACCESIBILIDAD_KPI_COLUMNS, KPI_COLUMNS, restriction_badges
from app.map_state import get_selected_h3_index
from app.ui_helpers import format_metric

AVISO = (
    "Este asistente combina dos motores: uno consulta cifras oficiales (población, paro, "
    "turismo, tráfico aéreo) con SQL generado automáticamente; el otro busca opiniones reales "
    "de viajeros. Cada respuesta muestra la consulta SQL usada (si aplica). El motor de "
    "opiniones nunca inventa cifras ni compara cantidades a partir de una muestra de reseñas."
)


def resumen_contexto_hexagono(row: pd.Series) -> str:
    partes = [f"Hexágono H3 en {row.get('municipio') or 'municipio desconocido'}."]
    for columna, etiqueta, tipo, _ayuda in KPI_COLUMNS + ACCESIBILIDAD_KPI_COLUMNS:
        valor = format_metric(row.get(columna), tipo)
        if valor != "—":
            partes.append(f"{etiqueta}: {valor}.")
    badges = restriction_badges(row)
    if badges:
        partes.append("Restricciones: " + ", ".join(badges) + ".")
    return " ".join(partes)


def _construir_pregunta_con_contexto(pregunta: str, contexto_hexagono: str | None) -> str:
    if not contexto_hexagono:
        return pregunta
    return f"Contexto del hexágono seleccionado en el mapa: {contexto_hexagono}\n\nPregunta del usuario: {pregunta}"


def _generar_respuesta(pregunta: str) -> dict:
    try:
        tipo = clasificar(pregunta)
    except Exception:
        tipo = "rag"

    if tipo == "sql":
        try:
            respuesta = responder_sql(pregunta, get_engine())
            return {
                "role": "assistant",
                "content": respuesta.texto,
                "sql": respuesta.sql,
                "filas": respuesta.filas,
            }
        except Exception:
            return {
                "role": "assistant",
                "content": "No se ha podido consultar la base de datos en este momento.",
            }

    try:
        respuesta = responder_rag(pregunta)
        return {"role": "assistant", "content": respuesta.texto}
    except Exception:
        return {
            "role": "assistant",
            "content": "No se ha podido generar una respuesta en este momento.",
        }


def _cargar_fila_hexagono(h3_index: str) -> pd.Series | None:
    engine = get_engine()
    full_gdf = merge_accesibilidad(
        merge_h3_data(load_h3_master(engine), load_sentimiento(engine)), load_accesibilidad(engine)
    )
    coincidencias = full_gdf.loc[full_gdf["h3_index"] == h3_index]
    if coincidencias.empty:
        return None
    return coincidencias.iloc[0]


def _render_mensaje(mensaje: dict) -> None:
    with st.chat_message(mensaje["role"]):
        st.markdown(mensaje["content"])
        if mensaje.get("sql"):
            with st.expander("Ver SQL generado"):
                st.code(mensaje["sql"], language="sql")
        if mensaje.get("filas"):
            st.dataframe(mensaje["filas"], hide_index=True)


def page_asistente() -> None:
    st.title("🤖 Asistente IA")
    st.info(AVISO)

    contexto_hexagono = None
    selected_h3_index = get_selected_h3_index()
    if selected_h3_index:
        fila = _cargar_fila_hexagono(selected_h3_index)
        if fila is not None:
            contexto_hexagono = resumen_contexto_hexagono(fila)
            st.caption(
                f"📍 Contexto activo: hexágono en **{fila.get('municipio') or 'municipio desconocido'}** "
                "(el seleccionado en la página Mapa) -- tus preguntas se responderán teniendo esto en cuenta."
            )

    if "chat_historial" not in st.session_state:
        st.session_state["chat_historial"] = []

    for mensaje in st.session_state["chat_historial"]:
        _render_mensaje(mensaje)

    pregunta = st.chat_input("Pregunta algo sobre el turismo en Tenerife...")
    if pregunta:
        pregunta_con_contexto = _construir_pregunta_con_contexto(pregunta, contexto_hexagono)
        st.session_state["chat_historial"].append({"role": "user", "content": pregunta})
        with st.spinner("Pensando..."):
            st.session_state["chat_historial"].append(_generar_respuesta(pregunta_con_contexto))
        st.rerun()
