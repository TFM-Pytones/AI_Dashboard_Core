import pytest

from analytics.llm.report_generator import (
    AMBITOS,
    FECHA_MINIMA,
    MODEL_NAME_A,
    MODEL_NAME_B,
    build_prompt,
    fetch_topic_summary,
    parse_args,
)


class _CursorFalso:
    def __init__(self, filas):
        self.filas = filas
        self.sql = None
        self.params = None

    def execute(self, sql, params=None):
        self.sql = sql
        self.params = params

    def fetchall(self):
        return self.filas

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class _ConnFalsa:
    def __init__(self, filas=()):
        self.cur = _CursorFalso(list(filas))

    def cursor(self):
        return self.cur


def test_los_dos_ambitos_siguen_existiendo_tras_la_fusion():
    assert sorted(AMBITOS) == ["alojamiento", "general"]


def test_cada_ambito_apunta_a_su_modelo_de_topicos():
    assert AMBITOS["general"]["model_name"] == MODEL_NAME_A
    assert AMBITOS["alojamiento"]["model_name"] == MODEL_NAME_B
    assert MODEL_NAME_A != MODEL_NAME_B


def test_parse_args_por_defecto_es_general():
    assert parse_args([]).ambito == "general"
    assert parse_args(["--ambito", "alojamiento"]).ambito == "alojamiento"


def test_parse_args_rechaza_un_ambito_inventado():
    with pytest.raises(SystemExit):
        parse_args(["--ambito", "restauracion"])


def test_solo_el_ambito_general_filtra_youtube_por_fecha():
    # LosViajeros no tiene fecha real del mensaje: filtrar las tres fuentes por
    # una fecha que no es la suya seria inventar un dato.
    assert AMBITOS["general"]["params"] == (MODEL_NAME_A, FECHA_MINIMA)
    assert AMBITOS["alojamiento"]["params"] == (MODEL_NAME_B,)
    assert "published_at" in AMBITOS["general"]["query"]
    assert "published_at" not in AMBITOS["alojamiento"]["query"]


def test_los_dos_ambitos_excluyen_los_outliers():
    for conf in AMBITOS.values():
        assert "topic_id != -1" in conf["query"]


def test_cada_ambito_usa_su_propio_prompt():
    counts = [("playas", 10)]
    general = build_prompt(counts, "general")
    alojamiento = build_prompt(counts, "alojamiento")
    assert general != alojamiento
    assert "Tenerife como destino" in general
    assert "experiencia de alojamiento" in alojamiento
    assert "- playas (10 comentarios)" in general


def test_fetch_topic_summary_suma_el_total_y_usa_los_params_del_ambito():
    conn = _ConnFalsa([("playas", 10), ("ruido", 5)])
    filas, total = fetch_topic_summary(conn, "alojamiento")
    assert total == 15
    assert filas == [("playas", 10), ("ruido", 5)]
    assert conn.cur.params == (MODEL_NAME_B,)
