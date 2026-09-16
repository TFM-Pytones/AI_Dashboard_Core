import pandas as pd

from app.asistente import _construir_pregunta_con_contexto, _responder_desde_contexto, resumen_contexto_hexagono


class _LLMFalso:
    def __init__(self, respuesta: str):
        self.respuesta = respuesta
        self.prompts_recibidos = []

    def complete(self, prompt: str, temperature: float = 0.4, max_tokens: int = 1200) -> str:
        self.prompts_recibidos.append(prompt)
        return self.respuesta


def test_resumen_contexto_hexagono_incluye_el_h3_index():
    # Bug real: preguntar "cual es el h3_index en el que estoy" caia a SQL,
    # que intentaba reconstruir el hexagono buscando una coincidencia EXACTA
    # de todos los valores redondeados del contexto (ej. ndvi_medio = 0.19),
    # que casi nunca coincide con el valor real de la base de datos -- "La
    # consulta no devolvio resultados". El contexto nunca incluia el propio
    # h3_index, el dato mas basico de "el hexagono en el que estoy".
    row = pd.Series({"h3_index": "88344ccb0dfffff", "municipio": "La Orotava"})
    resumen = resumen_contexto_hexagono(row)
    assert "88344ccb0dfffff" in resumen


def test_resumen_contexto_hexagono_incluye_municipio_y_metricas_disponibles():
    row = pd.Series(
        {
            "municipio": "Adeje",
            "n_hoteles": 12,
            "n_establecimientos_registro": 45,
            "ndvi_medio": 0.42,
            "sentimiento_medio": None,
            "rating_booking_medio": 8.1,
            "rating_tripadvisor_medio": None,
            "pct_area_enp": 0,
            "pct_area_zona_turistica": 0.8,
            "aeropuerto_mas_cercano": "TFS",
            "tiempo_aeropuerto_min": 18,
            "dist_hospital_km": 3.2,
            "dist_costa_km": 0.5,
            "n_paradas_bus_500m": 4,
        }
    )
    resumen = resumen_contexto_hexagono(row)
    assert "Adeje" in resumen
    assert "8,1" in resumen
    assert "Zona turística oficial" in resumen


def test_resumen_contexto_hexagono_omite_metricas_sin_dato_no_pone_none_ni_nan():
    row = pd.Series({"municipio": "Vilaflor", "sentimiento_medio": None, "rating_booking_medio": None})
    resumen = resumen_contexto_hexagono(row)
    assert "None" not in resumen
    assert "nan" not in resumen.lower()


def test_resumen_contexto_hexagono_sin_restricciones_no_menciona_restriccion():
    row = pd.Series({"municipio": "Adeje", "pct_area_enp": 0, "pct_area_zona_turistica": 0})
    resumen = resumen_contexto_hexagono(row)
    assert "Restricciones" not in resumen


def test_construir_pregunta_con_contexto_devuelve_la_pregunta_igual_sin_contexto():
    assert _construir_pregunta_con_contexto("¿qué tal el clima?", None) == "¿qué tal el clima?"


def test_construir_pregunta_con_contexto_antepone_el_resumen_del_hexagono():
    resultado = _construir_pregunta_con_contexto("¿qué puedo hacer aquí?", "Hexágono en Adeje.")
    assert "Hexágono en Adeje." in resultado
    assert "¿qué puedo hacer aquí?" in resultado


def test_responder_desde_contexto_devuelve_la_respuesta_si_el_llm_puede_contestar():
    # Bug real: "qué me puedes decir del hexágono que tengo seleccionado"
    # caía a RAG y fallaba, aunque toda la respuesta ya estaba en el
    # contexto inyectado (KPIs del hexágono) -- ni el agente SQL ni el RAG
    # saben "resumir el contexto ya dado", solo generar SQL nuevo o buscar
    # reseñas. Esta vía nueva contesta directamente desde el contexto cuando
    # puede, sin pasar por el router.
    llm = _LLMFalso("Este hexágono tiene 12 hoteles y un NDVI medio de 0,42.")
    resultado = _responder_desde_contexto(
        "qué me puedes decir de este hexágono", "Hexágono en Adeje. 🏨 Nº hoteles: 12.", llm
    )
    assert resultado == "Este hexágono tiene 12 hoteles y un NDVI medio de 0,42."
    assert "Hexágono en Adeje" in llm.prompts_recibidos[0]


def test_responder_desde_contexto_devuelve_none_si_el_llm_deriva():
    llm = _LLMFalso("DERIVAR")
    resultado = _responder_desde_contexto("qué opinan los viajeros de este sitio", "Hexágono en Adeje.", llm)
    assert resultado is None


def test_responder_desde_contexto_devuelve_none_si_el_llm_no_responde():
    llm = _LLMFalso("")
    resultado = _responder_desde_contexto("pregunta", "contexto", llm)
    assert resultado is None
