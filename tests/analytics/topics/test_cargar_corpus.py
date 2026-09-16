import csv

import pytest

from analytics.topics.cargar_corpus import (
    MODELOS,
    SQL_INSERT,
    TOPIC_ID_SIN_ASIGNAR,
    contar_por_fuente,
    leer_corpus,
    modelos_pedidos,
    parse_args,
)


def _escribir_csv(ruta, filas, cabecera=("source", "source_id", "text")):
    with open(ruta, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(cabecera)
        w.writerows(filas)
    return ruta


def test_los_model_name_coinciden_con_los_de_entrenar_topicos():
    # Acoplamiento critico: entrenar_topicos.py decide si un documento es del
    # modelo A o del B mirando este texto ("B" if "(modelo B" in model_name).
    # Si los dos ficheros se desincronizan, el corpus entero se entrena como A.
    from analytics.topics.entrenar_topicos import MODELOS as MODELOS_ENTRENAR

    for clave, conf in MODELOS.items():
        assert conf["model_name"] == MODELOS_ENTRENAR[clave]["model_name"]


def test_el_modelo_b_se_reconoce_por_la_marca_que_busca_entrenar_topicos():
    assert "(modelo B" in MODELOS["B"]["model_name"]
    assert "(modelo B" not in MODELOS["A"]["model_name"]


def test_insertar_nunca_pisa_los_temas_ya_calculados():
    # Relanzarlo sobre la tabla poblada debe ser inofensivo: sin el ON CONFLICT
    # DO NOTHING se perderian los nombres en español que dejo volcar_topicos.py.
    assert "ON CONFLICT (source, source_id) DO NOTHING" in SQL_INSERT


def test_las_filas_entran_sin_tema_asignado():
    # topic_id es NOT NULL en el esquema; -1 es el hueco que ya usaba la tabla
    # para "sin tema", y volcar_topicos.py lo sustituye despues.
    assert TOPIC_ID_SIN_ASIGNAR == -1
    assert "topic_id" in SQL_INSERT
    assert "topic_label" not in SQL_INSERT


def test_leer_corpus_convierte_el_csv_en_filas_de_la_tabla(tmp_path):
    ruta = _escribir_csv(tmp_path / "c.csv", [("youtube_comment", "abc", "la playa estaba limpia")])
    filas = leer_corpus(ruta, "modelo-x")
    assert filas == [("youtube_comment", "abc", "la playa estaba limpia", -1, "modelo-x")]


def test_leer_corpus_descarta_textos_vacios(tmp_path):
    ruta = _escribir_csv(tmp_path / "c.csv", [
        ("youtube_comment", "a", "texto util"),
        ("youtube_comment", "b", "   "),
        ("youtube_comment", "c", ""),
    ])
    assert len(leer_corpus(ruta, "m")) == 1


def test_leer_corpus_aborta_si_la_cabecera_no_es_la_esperada(tmp_path):
    ruta = _escribir_csv(tmp_path / "c.csv", [("a", "b", "c")], cabecera=("fuente", "id", "texto"))
    with pytest.raises(SystemExit):
        leer_corpus(ruta, "m")


def test_leer_corpus_aborta_si_el_csv_no_existe(tmp_path):
    with pytest.raises(SystemExit):
        leer_corpus(tmp_path / "no_existe.csv", "m")


def test_leer_corpus_traga_textos_muy_largos(tmp_path):
    # Las reseñas de Booking pasan del limite por defecto del modulo csv.
    largo = "a" * 200_000
    ruta = _escribir_csv(tmp_path / "c.csv", [("booking_review", "r1", largo)])
    filas = leer_corpus(ruta, "m")
    assert len(filas[0][2]) == 200_000


def test_contar_por_fuente():
    filas = [("youtube_comment", "1", "t", -1, "m"), ("youtube_comment", "2", "t", -1, "m"),
             ("losviajeros_message", "3", "t", -1, "m")]
    assert contar_por_fuente(filas) == {"youtube_comment": 2, "losviajeros_message": 1}


def test_por_defecto_carga_los_dos_modelos():
    assert parse_args([]).modelo == "ambos"
    assert modelos_pedidos("ambos") == ["A", "B"]
    assert modelos_pedidos("B") == ["B"]


def test_simular_no_es_el_comportamiento_por_defecto():
    assert parse_args([]).simular is False
    assert parse_args(["--simular"]).simular is True


def test_cada_modelo_apunta_a_su_csv():
    assert MODELOS["A"]["csv"].name == "general_corpus.csv"
    assert MODELOS["B"]["csv"].name == "geo_corpus.csv"
