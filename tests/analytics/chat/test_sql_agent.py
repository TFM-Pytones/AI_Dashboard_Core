import pandas as pd
import pytest

from analytics.chat.sql_agent import (
    ESQUEMA_GOLD,
    GRANULARIDAD_TABLA,
    LIMIT_POR_DEFECTO,
    PROMPT_NARRACION,
    PROMPT_SQL,
    RespuestaSQL,
    _narrar_resultado,
    asegurar_limit,
    describir_esquema,
    responder_sql,
    validar_sql,
)


class _LLMSecuencial:
    """Fake LLM que devuelve una respuesta distinta por llamada, en orden --
    para probar la logica de reintento sin depender de la API real."""

    def __init__(self, respuestas: list[str]):
        self.respuestas = respuestas
        self.llamadas = 0
        self.prompts_recibidos = []

    def complete(self, prompt: str, temperature: float = 0.4, max_tokens: int = 1200) -> str:
        self.prompts_recibidos.append(prompt)
        respuesta = self.respuestas[min(self.llamadas, len(self.respuestas) - 1)]
        self.llamadas += 1
        return respuesta


def test_validar_sql_acepta_select_simple_sobre_tabla_permitida():
    es_valido, motivo = validar_sql("SELECT municipio, paro_actual FROM gold.gold_municipio_master")
    assert es_valido is True
    assert motivo is None


@pytest.mark.parametrize(
    "palabra",
    ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE", "GRANT", "CREATE"],
)
def test_validar_sql_rechaza_sentencia_que_no_es_select(palabra):
    # Cualquier sentencia de escritura por sí sola ya falla el primer
    # requisito (debe empezar por SELECT), antes de llegar a la lista de
    # palabras prohibidas -- se comprueba aquí explícitamente.
    es_valido, motivo = validar_sql(f"{palabra} INTO gold.gold_municipio_master VALUES (1)")
    assert es_valido is False
    assert "SELECT" in motivo


@pytest.mark.parametrize(
    "palabra",
    ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE", "GRANT", "CREATE"],
)
def test_validar_sql_rechaza_palabras_prohibidas_dentro_de_un_select(palabra):
    # La lista de palabras prohibidas es una segunda capa de defensa (por si
    # el SQL generado por el LLM, aunque empiece por SELECT y sea una única
    # sentencia, intentara colar una de estas palabras en cualquier parte de
    # la consulta).
    es_valido, motivo = validar_sql(
        f"SELECT municipio FROM gold.gold_municipio_master WHERE municipio = '{palabra}'"
    )
    assert es_valido is False
    assert palabra in motivo


def test_validar_sql_rechaza_multiples_sentencias():
    es_valido, motivo = validar_sql(
        "SELECT 1 FROM gold.gold_municipio_master; DROP TABLE gold.gold_municipio_master"
    )
    assert es_valido is False
    assert "única sentencia" in motivo


def test_validar_sql_rechaza_tablas_fuera_de_la_lista_curada():
    # gold.nlp_chunks es la tabla del corpus del RAG -- nunca debe ser
    # alcanzable por el agente SQL, esas preguntas van al RAG.
    es_valido, motivo = validar_sql("SELECT * FROM gold.nlp_chunks")
    assert es_valido is False
    assert "gold.nlp_chunks" in motivo


def test_validar_sql_acepta_join_entre_tablas_permitidas():
    es_valido, motivo = validar_sql(
        "SELECT a.municipio, b.anio FROM gold.gold_municipio_master a "
        "JOIN gold.gold_municipio_anual b ON a.cod_municipio = b.cod_municipio"
    )
    assert es_valido is True
    assert motivo is None


def test_asegurar_limit_anade_limit_por_defecto_cuando_falta():
    resultado = asegurar_limit("SELECT * FROM gold.gold_municipio_master")
    assert "LIMIT 200" in resultado


def test_asegurar_limit_respeta_limit_explicito_menor():
    resultado = asegurar_limit("SELECT * FROM gold.gold_municipio_master LIMIT 5")
    assert resultado.count("LIMIT") == 1
    assert "LIMIT 5" in resultado


def test_esquema_gold_incluye_las_tablas_curadas():
    # gold_h3_master se incluye con una selección curada de ~24 columnas (no
    # las ~80 originales) -- amplía la cobertura a nivel hexágono (relieve,
    # restricciones legales, distancia a costa) sin arrastrar las columnas
    # técnicas de satélite/clima por año y trimestre que no aportan a
    # preguntas en lenguaje natural.
    assert "gold.gold_h3_master" in ESQUEMA_GOLD
    assert "gold.gold_municipio_master" in ESQUEMA_GOLD
    assert "gold.gold_aena_pasajeros" in ESQUEMA_GOLD
    # Las tablas del propio RAG nunca deben ser alcanzables por el agente SQL.
    assert "gold.nlp_chunks" not in ESQUEMA_GOLD
    assert "gold.nlp_sentimiento_resenas" not in ESQUEMA_GOLD


def test_esquema_gold_h3_master_incluye_columnas_de_restricciones_y_costa():
    columnas_h3 = dict(ESQUEMA_GOLD["gold.gold_h3_master"])
    assert "pct_area_enp" in columnas_h3
    assert "pct_area_zona_turistica" in columnas_h3
    assert "dist_costa_km" in columnas_h3
    # La semántica de "sin restricción" (ambos en 0) tiene que quedar clara
    # en la propia descripción -- si no, el LLM no sabe cómo escribir el
    # WHERE para "municipios sin restricciones".
    assert "0" in columnas_h3["pct_area_enp"]


def test_esquema_gold_incluye_h3_sentimiento():
    # gold_h3_sentimiento se conecto al dashboard el 2026-09-16 (antes
    # devolvia vacio -- ver app/data.py). Sin esto, preguntas de sentimiento
    # por municipio ("municipios con menor sentimiento") no eran respondibles
    # ni por SQL ni por RAG (probado: el router las manda a RAG, que no tiene
    # el agregado numerico).
    assert "gold.gold_h3_sentimiento" in ESQUEMA_GOLD
    columnas = dict(ESQUEMA_GOLD["gold.gold_h3_sentimiento"])
    assert "sentimiento_medio" in columnas
    assert "h3_index" in columnas
    # No tiene columna de municipio -- el LLM tiene que saber que hace falta
    # un JOIN con gold_h3_master por h3_index para agrupar por municipio.
    assert "municipio" not in columnas
    assert "gold_h3_master" in columnas["h3_index"] or "h3_master" in GRANULARIDAD_TABLA["gold.gold_h3_sentimiento"]


def test_granularidad_h3_sentimiento_indica_cobertura_parcial():
    # Solo 410 de 2.579 hexagonos tienen reseñas geolocalizadas -- si el LLM
    # no lo sabe, puede presentar un AVG sobre 410 filas como si fuera
    # representativo de toda la isla sin avisar de la cobertura parcial.
    granularidad = GRANULARIDAD_TABLA["gold.gold_h3_sentimiento"]
    assert "410" in granularidad


def test_describir_esquema_incluye_todas_las_tablas_y_columnas():
    texto = describir_esquema()
    for tabla, columnas in ESQUEMA_GOLD.items():
        assert tabla in texto
        for columna, _descripcion in columnas:
            assert columna in texto


def test_esquema_distingue_n_hoteles_de_plazas_registro():
    # Bug real detectado en pruebas manuales: ante "plazas hoteleras por cada
    # 1000 habitantes" el LLM generó SQL usando n_hoteles (número de
    # establecimientos) en vez de n_plazas_registro (capacidad real). Las
    # descripciones deben dejar la diferencia inequívoca para las dos tablas
    # que tienen ambas columnas.
    for tabla in ("gold.gold_municipio_master", "gold.gold_h3_master"):
        columnas = dict(ESQUEMA_GOLD[tabla])
        assert "plazas" in columnas["n_hoteles"].lower()
        assert "n_plazas_registro" in columnas["n_hoteles"]


def test_describir_esquema_indica_granularidad_de_gold_h3_master():
    # gold_h3_master tiene ~2.579 filas (una por hexágono) frente a 1 fila
    # por municipio en las tablas *_anual/*_mensual -- si el LLM no sabe
    # esto, genera JOINs entre ambos niveles que duplican cada hexágono una
    # vez por cada fila coincidente de la otra tabla, sesgando AVG/SUM. La
    # cabecera de cada tabla (antes de la lista de columnas) debe dejar
    # explícita la granularidad, no basta con que la palabra aparezca en
    # alguna descripción de columna.
    texto = describir_esquema()
    cabecera_h3 = texto[texto.index("Tabla gold.gold_h3_master") : texto.index("\n  - h3_index")]
    assert "fila" in cabecera_h3.lower()
    assert "hexágono" in cabecera_h3.lower()

    cabecera_anual = texto[
        texto.index("Tabla gold.gold_municipio_anual") : texto.index("\n  - cod_municipio", texto.index("Tabla gold.gold_municipio_anual"))
    ]
    assert "fila" in cabecera_anual.lower()


def test_prompt_sql_advierte_sobre_join_entre_niveles_distintos():
    assert "JOIN" in PROMPT_SQL
    assert "IN (SELECT DISTINCT" in PROMPT_SQL


def test_prompt_sql_pide_incluir_columnas_usadas_en_el_select():
    assert "SELECT" in PROMPT_SQL
    texto_minusculas = PROMPT_SQL.lower()
    assert "verificable" in texto_minusculas or "verificar" in texto_minusculas


def test_prompt_sql_exige_nombre_legible_de_municipio_no_solo_codigo():
    # Bug real: preguntas que devuelven varios municipios (ej. "los 10
    # municipios con menor sentimiento") generaban SQL con GROUP BY/SELECT
    # cod_municipio sin incluir la columna municipio -- la narracion final
    # listaba codigos INE tecnicos ("38023") en vez de nombres ("Adeje").
    # No basta con que la palabra "municipio" aparezca en el prompt (ya
    # aparece en otras reglas) -- tiene que haber una instruccion explicita
    # de incluir la columna `municipio` legible, no solo cod_municipio.
    texto_minusculas = PROMPT_SQL.lower()
    assert "columna `municipio`" in texto_minusculas or "columna municipio" in texto_minusculas
    assert "cod_municipio` no es legible" in texto_minusculas or "codigo ine" in texto_minusculas


def test_prompt_narracion_prefiere_nombre_de_municipio_sobre_codigo():
    # Bug real detectado en pruebas manuales (con trampa): aunque el SQL ya
    # incluye la columna `municipio`, la narracion puede elegir citar
    # cod_municipio en su lugar si la propia pregunta del usuario usa la
    # palabra "codigo" (ej. "agrupa los hexagonos por codigo de municipio").
    # Repeticion del bug de test_prompt_sql_exige_nombre_legible... pero en
    # el segundo paso (narracion), no en la generacion de SQL.
    texto_minusculas = PROMPT_NARRACION.lower()
    assert "cod_municipio" in texto_minusculas
    assert "nunca el código" in texto_minusculas or "no el código" in texto_minusculas


def test_prompt_narracion_incluye_ejemplo_concreto_nombre_vs_codigo():
    # La instruccion abstracta (test anterior) no bastaba en la practica --
    # confirmado en pruebas manuales: la pregunta "agrupa por codigo de
    # municipio" seguia generando narracion con codigos (38026, 38005...)
    # pese a la regla explicita. Un ejemplo concreto de entrada/salida es
    # mas efectivo para fijar el formato que una regla abstracta.
    assert "38001" in PROMPT_NARRACION
    assert "Adeje" in PROMPT_NARRACION


def test_narrar_resultado_devuelve_texto_si_el_llm_responde_a_la_primera():
    llm = _LLMSecuencial(["Los municipios son Adeje y Arona."])
    texto = _narrar_resultado("pregunta", [{"municipio": "Adeje"}], llm)
    assert texto == "Los municipios son Adeje y Arona."
    assert llm.llamadas == 1


def test_narrar_resultado_reintenta_si_el_llm_devuelve_vacio():
    # Bug real: reproducido contra la API de Groq con el caso de 31
    # municipios agrupados -- el modelo (openai/gpt-oss-120b) gasta a veces
    # todo max_tokens en razonamiento interno y devuelve "" (2 de 4 intentos
    # vacios incluso con max_tokens=1500). Un reintento normalmente basta.
    llm = _LLMSecuencial(["", "Los municipios son Adeje y Arona."])
    texto = _narrar_resultado("pregunta", [{"municipio": "Adeje"}], llm)
    assert texto == "Los municipios son Adeje y Arona."
    assert llm.llamadas == 2


def test_narrar_resultado_da_mensaje_de_fallback_si_sigue_vacio_tras_reintentar():
    llm = _LLMSecuencial(["", ""])
    texto = _narrar_resultado("pregunta", [{"municipio": "Adeje"}], llm)
    assert texto != ""
    assert "tabla" in texto.lower()
    assert llm.llamadas == 2


def test_narrar_resultado_incluye_el_aviso_de_cobertura_parcial_en_el_prompt():
    # Bug real: "cuantos hexagonos han sido analizados" generaba SQL contra
    # gold_h3_sentimiento (410 filas) y la narracion respondia "Se han
    # analizado 410 hexagonos" sin avisar de que son solo 410 de 2.579 --
    # aunque GRANULARIDAD_TABLA ya tiene esa nota, _narrar_resultado nunca
    # recibia que tabla se habia consultado para poder usarla.
    llm = _LLMSecuencial(["Se han analizado 410 hexágonos (cobertura parcial)."])
    _narrar_resultado(
        "cuantos hexagonos han sido analizados",
        [{"total_hexagonos": 410}],
        llm,
        sql="SELECT COUNT(*) AS total_hexagonos FROM gold.gold_h3_sentimiento LIMIT 200",
    )
    assert "410" in llm.prompts_recibidos[0]
    assert "2.579" in llm.prompts_recibidos[0]


def test_narrar_resultado_no_incluye_aviso_para_tablas_sin_nota_de_cobertura():
    llm = _LLMSecuencial(["Adeje tiene 134 hexágonos."])
    _narrar_resultado(
        "cuantos hexagonos tiene adeje",
        [{"n": 134}],
        llm,
        sql="SELECT COUNT(*) AS n FROM gold.gold_h3_master WHERE municipio = 'Adeje'",
    )
    assert "cobertura parcial" not in llm.prompts_recibidos[0].lower()
