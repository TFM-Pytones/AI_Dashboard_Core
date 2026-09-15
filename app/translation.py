import streamlit as st

from analytics.llm.llm_client import LLMClient

TRANSLATION_PROMPT_TEMPLATE = (
    "Traduce el siguiente texto de una reseña turística al español. "
    "Responde UNICAMENTE con la traduccion, sin comentarios ni texto adicional.\n\n"
    "Texto: {text}"
)


def build_translation_prompt(text: str) -> str:
    return TRANSLATION_PROMPT_TEMPLATE.format(text=text)


# Cached by input text so re-clicking "Traducir" (or another button triggering
# a rerun) never re-calls the LLM for a review already translated this session.
@st.cache_data(show_spinner=False, ttl=3600)
def translate_to_spanish(text: str) -> str:
    client = LLMClient()
    return client.complete(build_translation_prompt(text), temperature=0.2, max_tokens=500).strip()
