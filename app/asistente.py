import streamlit as st

from analytics.chat.router import clasificar
from analytics.chat.sql_agent import responder_sql
from analytics.rag.rag_answer import responder as responder_rag
from app.data import get_engine

AVISO = (
    "Este asistente combina dos motores: uno consulta cifras oficiales (población, paro, "
    "turismo, tráfico aéreo) con SQL generado automáticamente; el otro busca opiniones reales "
    "de viajeros. Cada respuesta muestra la consulta SQL usada (si aplica). El motor de "
    "opiniones nunca inventa cifras ni compara cantidades a partir de una muestra de reseñas."
)


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

    if "chat_historial" not in st.session_state:
        st.session_state["chat_historial"] = []

    for mensaje in st.session_state["chat_historial"]:
        _render_mensaje(mensaje)

    pregunta = st.chat_input("Pregunta algo sobre el turismo en Tenerife...")
    if pregunta:
        st.session_state["chat_historial"].append({"role": "user", "content": pregunta})
        with st.spinner("Pensando..."):
            st.session_state["chat_historial"].append(_generar_respuesta(pregunta))
        st.rerun()
