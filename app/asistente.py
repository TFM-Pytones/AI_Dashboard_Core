import pandas as pd
import streamlit as st

from analytics.chat.router import clasificar
from analytics.chat.sql_agent import responder_sql
from analytics.llm.llm_client import LLMClient
from analytics.rag.rag_answer import responder as responder_rag
from app.data import get_engine, load_accesibilidad, load_h3_master, load_sentimiento, merge_accesibilidad, merge_h3_data
from app.detail_panel import ACCESIBILIDAD_KPI_COLUMNS, KPI_COLUMNS, restriction_badges
from app.map_state import get_selected_h3_index
from app.ui_helpers import format_metric

PROMPT_CONTEXTO_HEXAGONO = """Eres un asistente turístico. Tienes estos datos del hexágono
actualmente seleccionado en el mapa:

{contexto_hexagono}

Pregunta del usuario: {pregunta}

Si puedes responder a esta pregunta usando SOLO estos datos, hazlo en 1-3 frases en español.
Si la pregunta pide algo que NO está en estos datos (opiniones de otros viajeros, comparación
con otro municipio, series temporales, un ranking de toda la isla...), responde EXACTAMENTE con
la palabra: DERIVAR

RESPUESTA:"""

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


def _responder_desde_contexto(pregunta: str, contexto_hexagono: str, llm: LLMClient) -> str | None:
    prompt = PROMPT_CONTEXTO_HEXAGONO.format(contexto_hexagono=contexto_hexagono, pregunta=pregunta)
    texto = llm.complete(prompt, temperature=0.2, max_tokens=1200).strip()
    if not texto or texto.upper().startswith("DERIVAR"):
        return None
    return texto


def _generar_respuesta(pregunta: str, contexto_hexagono: str | None = None) -> dict:
    # Bug real: preguntas abiertas tipo "qué me puedes decir de este
    # hexágono" caían a RAG y fallaban, aunque la respuesta ya estaba en el
    # contexto inyectado -- ni el agente SQL (genera SQL NUEVO a partir de
    # la pregunta, no resume datos ya dados) ni el RAG (busca reseñas, no
    # tiene los KPIs del hexágono) saben usar el contexto directamente.
    if contexto_hexagono:
        try:
            respuesta_directa = _responder_desde_contexto(pregunta, contexto_hexagono, LLMClient())
        except Exception:
            respuesta_directa = None
        if respuesta_directa:
            return {"role": "assistant", "content": respuesta_directa}

    pregunta = _construir_pregunta_con_contexto(pregunta, contexto_hexagono)

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


# Solo hay un st.popover en toda la app, así que basta con dirigirse a
# stPopover a secas -- no hace falta una clase/key propia para no chocar con
# otros popovers.
#
# Streamlit pone width:100% al contenedor del popover por defecto (para que
# ocupe la columna donde vive) -- con position:fixed eso lo estira por toda
# la pantalla en vez de dejarlo como un botón pequeño en la esquina.
# width:fit-content lo reduce al tamaño real del botón. El selector del
# botón es descendiente (no hijo directo) porque Streamlit anida el botón
# dentro de un wrapper del tooltip del `help=`.
_FLOATING_CSS = """
<style>
div[data-testid="stPopover"] {
    position: fixed;
    bottom: 24px;
    right: 24px;
    z-index: 9999;
    width: fit-content !important;
}
div[data-testid="stPopover"] button[data-testid="stPopoverButton"] {
    border-radius: 50%;
    width: 60px;
    height: 60px;
    font-size: 1.6rem;
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.3);
}
div[data-testid="stPopoverBody"] {
    width: 420px;
    max-height: 70vh;
    overflow-y: auto;
}
</style>
"""


def render_floating_assistant() -> None:
    st.markdown(_FLOATING_CSS, unsafe_allow_html=True)

    with st.popover("🤖", help="Asistente IA -- pregunta sobre el turismo en Tenerife"):
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

        pregunta = st.chat_input("Pregunta algo sobre el turismo en Tenerife...", key="asistente_chat_input")
        if pregunta:
            st.session_state["chat_historial"].append({"role": "user", "content": pregunta})
            with st.spinner("Pensando..."):
                st.session_state["chat_historial"].append(_generar_respuesta(pregunta, contexto_hexagono))
            st.rerun()
