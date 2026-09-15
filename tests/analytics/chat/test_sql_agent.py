import pandas as pd
import pytest

from analytics.chat.sql_agent import (
    ESQUEMA_GOLD,
    LIMIT_POR_DEFECTO,
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
    es_valido, motivo = validar_sql("SELECT * FROM gold.gold_h3_master")
    assert es_valido is False
    assert "gold.gold_h3_master" in motivo


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


def test_esquema_gold_solo_incluye_tablas_curadas_a_nivel_municipio():
    # gold_h3_master (nivel hexágono, ~80 columnas técnicas) se excluye a
    # propósito -- ver decisión 3 de la spec.
    assert "gold.gold_h3_master" not in ESQUEMA_GOLD
    assert "gold.gold_municipio_master" in ESQUEMA_GOLD
    assert "gold.gold_aena_pasajeros" in ESQUEMA_GOLD


def test_describir_esquema_incluye_todas_las_tablas_y_columnas():
    texto = describir_esquema()
    for tabla, columnas in ESQUEMA_GOLD.items():
        assert tabla in texto
        for columna, _descripcion in columnas:
            assert columna in texto
