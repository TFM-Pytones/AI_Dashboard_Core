import pytest

from analytics.aspects.batch_inference import (
    ANIO_MINIMO_RESENAS,
    RUTA_DDL_SILVER,
    SQL_PENDIENTES_RESENAS,
    SQL_PENDIENTES_YOUTUBE,
    fetch_pending_resenas,
    fuentes_de_resenas,
    parse_args,
    parsear_resultado,
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


def test_el_ddl_que_faltaba_existe_de_verdad():
    # Punto 14 de la revision: ensure_schema() leia este fichero, que no estaba
    # en el repo, y el script petaba al correr en limpio.
    assert RUTA_DDL_SILVER.exists(), f"falta {RUTA_DDL_SILVER}"
    ddl = RUTA_DDL_SILVER.read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS silver.aspect_results" in ddl


def test_el_ddl_no_pone_unique_en_source_id():
    # Un comentario genera varias filas (una por aspecto): un UNIQUE(source,
    # source_id) haria fallar el INSERT del segundo aspecto de cada texto.
    ddl = RUTA_DDL_SILVER.read_text(encoding="utf-8")
    assert "UNIQUE (source, source_id)" not in ddl


def test_youtube_lee_la_tabla_que_declara_dbt():
    # Antes leia bronze.youtube_comments, de la migracion antigua desde Neon.
    assert "bronze.bronze_youtube_comments" in SQL_PENDIENTES_YOUTUBE
    assert "FROM bronze.youtube_comments" not in SQL_PENDIENTES_YOUTUBE


def test_source_resenas_agrupa_booking_y_tripadvisor():
    assert fuentes_de_resenas("resenas") == ["tripadvisor", "booking"]
    assert fuentes_de_resenas("youtube") == []


def test_parse_args_rechaza_fuente_desconocida():
    with pytest.raises(SystemExit):
        parse_args(["--source", "instagram"])


def test_las_consultas_de_resenas_son_incrementales():
    for sql in SQL_PENDIENTES_RESENAS.values():
        assert "NOT EXISTS" in sql
        assert "gold.nlp_aspectos_resenas" in sql


def test_fetch_pending_resenas_pasa_un_anio_por_cada_consulta_unida():
    conn = _ConnFalsa()
    fetch_pending_resenas(conn, ["tripadvisor", "booking"])
    assert conn.cur.params == (ANIO_MINIMO_RESENAS, ANIO_MINIMO_RESENAS)


def test_una_resena_sin_aspectos_se_marca_igualmente_como_procesada():
    # Si no se guardara nada, el NOT EXISTS la volveria a traer en cada
    # ejecucion y se reprocesaria para siempre.
    filas = parsear_resultado("booking", "r1", "h1", {"aspect": [], "sentiment": [], "confidence": []})
    assert filas == [("r1", "h1", None, None, None, "booking")]


def test_una_resena_con_varios_aspectos_genera_una_fila_por_aspecto():
    pred = {
        "aspect": ["habitacion", "ruido"],
        "sentiment": ["Positive", "Negative"],
        "confidence": [0.98, 0.91],
    }
    filas = parsear_resultado("booking", "r1", "h1", pred)
    assert len(filas) == 2
    assert [f[2] for f in filas] == ["habitacion", "ruido"]
    assert filas[1] == ("r1", "h1", "ruido", "Negative", 0.91, "booking")


def test_parsear_resultado_tolera_que_pyabsa_devuelva_none():
    # pyabsa es menos estable que transformers y su salida varia entre
    # versiones; con None en vez de lista no debe reventar.
    filas = parsear_resultado("tripadvisor", "r2", "h2", {"aspect": None})
    assert filas == [("r2", "h2", None, None, None, "tripadvisor")]
