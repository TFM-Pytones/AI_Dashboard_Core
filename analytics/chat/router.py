"""Router del chatbot (Bloque 8, Subtarea 8.4): decide si una pregunta va
al agente Text-to-SQL (analytics.chat.sql_agent) o al motor RAG
(analytics.rag.rag_answer), antes de despachar.

Ver docs/superpowers/specs/2026-09-15-asistente-ia-chatbot-design.md,
decision 4, para el porqué de clasificar con el LLM en vez de con
palabras clave.
"""

from typing import Literal

from analytics.llm.llm_client import LLMClient

PROMPT_CLASIFICACION = """Eres un router que decide qué motor debe responder una pregunta sobre turismo en Tenerife.

Responde con una única palabra: SQL o RAG.

- SQL: la pregunta pide una cifra, un agregado, una comparación numérica o un ranking, calculable con una consulta SQL sobre tablas de datos oficiales (población, paro, empleo, plazas de vivienda vacacional, turismo hotelero, tráfico aéreo). Ejemplos: "¿cuántas plazas hoteleras hay en Adeje?", "¿qué municipio tiene mayor paro?", "¿cuántos pasajeros llegaron a Tenerife Sur en 2025?".
- RAG: la pregunta pide opiniones, percepciones, quejas o experiencias de viajeros, no calculables con una consulta SQL. Ejemplos: "¿por qué se quejan los turistas del transporte en el sur?", "¿qué opinan sobre las carreteras de Anaga?", "¿cómo describen la playa de Adeje?".

PREGUNTA: {pregunta}

Responde solo con SQL o RAG, sin explicación."""


def clasificar(pregunta: str, llm: LLMClient | None = None) -> Literal["sql", "rag"]:
    cliente = llm or LLMClient()
    # max_tokens=150, no 5: openai/gpt-oss-120b (el modelo de LLMClient) es un
    # modelo con razonamiento interno -- con max_tokens=5 gasta todo el
    # presupuesto en tokens de razonamiento ocultos y devuelve "" siempre,
    # lo que hacia caer cualquier pregunta al fallback RAG. Confirmado
    # empiricamente contra la API real de Groq (ver
    # docs/superpowers/plans/2026-09-15-asistente-ia-chatbot.md, Tarea 6).
    respuesta = cliente.complete(
        PROMPT_CLASIFICACION.format(pregunta=pregunta), temperature=0.0, max_tokens=150
    )
    if respuesta.strip().upper().startswith("SQL"):
        return "sql"
    return "rag"
