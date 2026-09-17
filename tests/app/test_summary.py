import pandas as pd

from app.summary import compute_summary_stats, restriction_counts_dataframe


def _gdf():
    return pd.DataFrame(
        {
            "h3_index": ["a", "b", "c", "d"],
            "municipio": ["Adeje", "Adeje", "Arona", None],
            "restriction_category": ["Sin restricción", "ENP", "Zona turística oficial", "ENP"],
            "n_establecimientos_registro": [10, 0, 2, 0],
            "sentimiento_medio": [4.1, None, None, None],
        }
    )


def test_compute_summary_stats_total_hexagonos():
    stats = compute_summary_stats(_gdf())
    assert stats["total_hexagonos"] == 4


def test_compute_summary_stats_pct_sin_restriccion():
    stats = compute_summary_stats(_gdf())
    assert stats["pct_sin_restriccion"] == 25.0


def test_compute_summary_stats_pct_con_sentimiento():
    stats = compute_summary_stats(_gdf())
    assert stats["pct_con_sentimiento"] == 25.0


def test_compute_summary_stats_restriction_counts():
    stats = compute_summary_stats(_gdf())
    assert stats["restriction_counts"] == {"Espacio Natural Protegido": 2, "Sin restricción": 1, "Zona turística oficial": 1}


def test_compute_summary_stats_n_municipios_excludes_null():
    stats = compute_summary_stats(_gdf())
    assert stats["n_municipios"] == 2


def test_compute_summary_stats_municipio_mas_y_menos_oferta():
    stats = compute_summary_stats(_gdf())
    assert stats["municipio_mas_oferta"] == "Adeje"
    assert stats["municipio_menos_oferta"] == "Arona"


def test_restriction_counts_dataframe_sorts_descending():
    result = restriction_counts_dataframe({"ENP": 2, "Sin restricción": 1, "Zona turística oficial": 1})
    assert result["restriction_category"].tolist()[0] == "ENP"
    assert result["n_hexagonos"].tolist()[0] == 2


def test_restriction_counts_dataframe_has_expected_columns():
    result = restriction_counts_dataframe({"ENP": 2})
    assert list(result.columns) == ["restriction_category", "n_hexagonos"]
