from pathlib import Path

import pytest

from analytics.sentiment import batch_inference
from analytics.sentiment.batch_inference import (
    ANIO_MINIMO_RESENAS,
    MODEL_NAME_RESENAS,
    MODEL_NAME_YOUTUBE,
    SQL_PENDIENTES_BOOKING,
    SQL_PENDIENTES_RESENAS,
    SQL_PENDIENTES_TRIPADVISOR,
    SQL_PENDIENTES_YOUTUBE,
    build_off_topic_results,
    estrellas,
    fetch_pending_resenas,
    fuentes_de_resenas,
    parse_args,
    prepare_items,
    split_by_relevance,
)


class _CursorFalso:
    """Cursor minimo que solo recuerda la SQL y los parametros recibidos."""

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


def test_source_resenas_agrupa_booking_y_tripadvisor():
    assert fuentes_de_resenas("resenas") == ["tripadvisor", "booking"]
    assert fuentes_de_resenas("todas") == ["tripadvisor", "booking"]


def test_source_individual_solo_trae_su_fuente():
    assert fuentes_de_resenas("booking") == ["booking"]
    assert fuentes_de_resenas("tripadvisor") == ["tripadvisor"]


def test_youtube_no_entra_por_la_rama_de_resenas():
    # La rama de reseñas escribe en gold con el modelo de estrellas; YouTube
    # tiene su propio pipeline. Mezclarlos meteria etiquetas donde van notas.
    assert fuentes_de_resenas("youtube") == []


def test_parse_args_por_defecto_procesa_todo():
    assert parse_args([]).source == "todas"
    assert parse_args(["--source", "booking"]).source == "booking"


def test_parse_args_rechaza_fuente_desconocida():
    with pytest.raises(SystemExit):
        parse_args(["--source", "reddit"])


def test_youtube_lee_la_tabla_que_declara_dbt():
    # bronze.youtube_comments (sin prefijo) era el destino de la migracion
    # antigua desde Neon; la tabla viva es bronze.bronze_youtube_comments.
    assert "bronze.bronze_youtube_comments" in SQL_PENDIENTES_YOUTUBE


def test_las_consultas_de_resenas_son_incrementales():
    # Sin el NOT EXISTS se reprocesarian en cada ejecucion miles de reseñas ya
    # analizadas, duplicando filas en gold (la tabla no tiene UNIQUE).
    for sql in SQL_PENDIENTES_RESENAS.values():
        assert "NOT EXISTS" in sql
        assert "gold.nlp_sentimiento_resenas" in sql


def test_las_consultas_de_resenas_filtran_por_anio():
    assert "EXTRACT(YEAR FROM r.fecha_publicacion) > %s" in SQL_PENDIENTES_TRIPADVISOR
    assert "EXTRACT(YEAR FROM b.review_date) > %s" in SQL_PENDIENTES_BOOKING


def test_fetch_pending_resenas_pasa_un_anio_por_cada_consulta_unida():
    # Bug facil: unir dos SELECT con UNION ALL y pasar un solo parametro.
    conn = _ConnFalsa()
    fetch_pending_resenas(conn, ["tripadvisor", "booking"])
    assert conn.cur.sql.count("UNION ALL") == 1
    assert conn.cur.params == (ANIO_MINIMO_RESENAS, ANIO_MINIMO_RESENAS)


def test_fetch_pending_resenas_con_una_sola_fuente_no_une_nada():
    conn = _ConnFalsa()
    fetch_pending_resenas(conn, ["booking"])
    assert "UNION ALL" not in conn.cur.sql
    assert conn.cur.params == (ANIO_MINIMO_RESENAS,)


def test_estrellas_saca_la_nota_de_la_etiqueta_de_nlptown():
    # nlptown devuelve '1 star' / '4 stars': gold espera un entero 1-5.
    assert estrellas("4 stars") == 4
    assert estrellas("1 star") == 1
    assert "nlptown" in MODEL_NAME_RESENAS


def test_prepare_items_quita_urls_y_descarta_lo_vacio():
    items = prepare_items([("a", "https://x.com"), ("b", "  playa  limpia  "), ("c", None)])
    assert items == [("b", "playa limpia")]


def test_split_by_relevance_reparte_segun_el_zero_shot():
    items = [("a", "texto a"), ("b", "texto b")]
    relevantes, descartados = split_by_relevance(items, [(True, 0.9), (False, 0.1)])
    assert [c for c, _, _ in relevantes] == ["a"]
    assert [c for c, _, _ in descartados] == ["b"]


def test_los_descartados_se_guardan_marcados_como_no_relevantes():
    # Se guardan igualmente para no volver a clasificarlos en cada ejecucion.
    filas = build_off_topic_results([("a", "texto", 0.12)])
    assert filas[0]["is_relevant"] is False
    assert filas[0]["label"] == "off_topic"


def test_el_script_no_borra_ni_sobrescribe_nada():
    # Los comentarios de YouTube y sus resultados de relevancia son carga
    # estructural del Bloque 3: is_relevant sale por silver_sentiment_results y
    # es lo que export_general_corpus.py usa para montar el corpus de BERTopic.
    # Este script solo debe INSERTar; nada de DELETE/UPDATE/DROP/TRUNCATE.
    fuente = Path(batch_inference.__file__).read_text(encoding="utf-8")
    sql = "\n".join(
        linea for linea in fuente.splitlines()
        if not linea.strip().startswith("#")
    ).upper()
    for prohibido in ("DELETE FROM", "DROP TABLE", "TRUNCATE", "UPDATE BRONZE", "UPDATE GOLD"):
        assert prohibido not in sql, f"el script contiene {prohibido}"


def test_los_insert_de_youtube_no_pisan_lo_ya_calculado():
    fuente = Path(batch_inference.__file__).read_text(encoding="utf-8")
    assert "ON CONFLICT (source, source_id) DO NOTHING" in fuente


def test_youtube_y_resenas_no_escriben_en_la_tabla_de_la_otra():
    # Meter notas de 1-5 en bronze.ml_sentiment_results vaciaria el corpus de
    # temas en silencio; meter etiquetas en gold romperia sentimiento_medio.
    import inspect

    youtube = inspect.getsource(batch_inference.save_results)
    resenas = inspect.getsource(batch_inference.guardar_resenas)
    assert "bronze.ml_sentiment_results" in youtube
    assert "gold.nlp_sentimiento_resenas" not in youtube
    assert "gold.nlp_sentimiento_resenas" in resenas
    assert "bronze.ml_sentiment_results" not in resenas


def test_cada_rama_carga_el_modelo_que_le_toca():
    # Si la rama de YouTube acabara cargando el modelo de estrellas, sus filas
    # dejarian de traer positive/neutral/negative y silver_sentiment_results
    # (y con el, el corpus de BERTopic) se quedaria sin nada que filtrar.
    import inspect

    assert "MODEL_NAME_YOUTUBE" in inspect.getsource(batch_inference.run_sentiment)
    assert "MODEL_NAME_RESENAS" not in inspect.getsource(batch_inference.run_sentiment)
    assert "MODEL_NAME_RESENAS" in inspect.getsource(batch_inference.procesar_resenas)
    assert "MODEL_NAME_YOUTUBE" not in inspect.getsource(batch_inference.procesar_resenas)
    assert "cardiffnlp" in MODEL_NAME_YOUTUBE
    assert "nlptown" in MODEL_NAME_RESENAS
