import pandas as pd
import pytest

from analytics.chat.sql_agent import (
    ESQUEMA_GOLD,
    GRANULARIDAD_TABLA,
    LIMIT_POR_DEFECTO,
    PROMPT_SQL,
    RespuestaSQL,
    asegurar_limit,
    describir_esquema,
    responder_sql,
    validar_sql,
)


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
