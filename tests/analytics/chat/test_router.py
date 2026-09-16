from analytics.chat.router import PROMPT_CLASIFICACION, clasificar


class _LLMFalso:
    """Fake LLM client for tests -- no network call, no API key needed.
    Matches LLMClient.complete's signature so clasificar() can't tell the
    difference."""

    def __init__(self, respuesta: str):
        self.respuesta = respuesta
        self.prompts_recibidos = []

    def complete(self, prompt: str, temperature: float = 0.4, max_tokens: int = 1200) -> str:
        self.prompts_recibidos.append(prompt)
        return self.respuesta


def test_clasificar_devuelve_sql_para_pregunta_de_cifras():
    assert clasificar("¿cuántas plazas hoteleras hay en Adeje?", llm=_LLMFalso("SQL")) == "sql"


def test_clasificar_devuelve_rag_para_pregunta_de_opinion():
    assert clasificar("¿de qué se quejan los turistas en Adeje?", llm=_LLMFalso("RAG")) == "rag"


def test_clasificar_normaliza_mayusculas_y_espacios():
    assert clasificar("¿cuántos hoteles hay?", llm=_LLMFalso("  sql \n")) == "sql"


def test_clasificar_cae_a_rag_ante_respuesta_inesperada_del_llm():
    assert clasificar("pregunta ambigua", llm=_LLMFalso("No estoy seguro")) == "rag"


def test_clasificar_pasa_la_pregunta_al_prompt():
    llm = _LLMFalso("RAG")
    clasificar("¿qué opinan del ruido en Los Cristianos?", llm=llm)
    assert "¿qué opinan del ruido en Los Cristianos?" in llm.prompts_recibidos[0]


def test_prompt_clasificacion_distingue_sentimiento_agregado_de_opiniones():
    # Bug real: "sentimiento" se asociaba solo con RAG (percepciones/
    # opiniones) porque el prompt no mencionaba que sentimiento_medio es un
    # numero agregable por SQL (gold_h3_sentimiento, conectada 2026-09-16).
    # Probado empiricamente: "dime los 10 municipios con menor sentimiento
    # medio" caia a RAG con el prompt anterior pase lo que pase la redaccion.
    assert "sentimiento" in PROMPT_CLASIFICACION.lower()
