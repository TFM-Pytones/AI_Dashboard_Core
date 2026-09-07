import pandas as pd

from app.detail_panel import format_kpi_value, municipio_aspect_comparison


def test_format_kpi_value_none_returns_dash():
    assert format_kpi_value(None) == "—"


def test_format_kpi_value_nan_returns_dash():
    assert format_kpi_value(float("nan")) == "—"


def test_format_kpi_value_float_formats_with_one_decimal_by_default():
    assert format_kpi_value(4.567) == "4.6"


def test_format_kpi_value_int_returns_plain_string():
    assert format_kpi_value(7) == "7"


def _peer_gdf():
    return pd.DataFrame(
        {
            "h3_index": ["a", "b", "c", "d"],
            "municipio": ["Adeje", "Adeje", "Adeje", "Arona"],
            "queja_principal": ["ruido", "precio", "ruido", "limpieza"],
        }
    )


def test_municipio_aspect_comparison_counts_peers_in_same_municipio():
    result = municipio_aspect_comparison(_peer_gdf(), "a")
    counts = dict(zip(result["aspecto"], result["n_hexagonos"]))
    assert counts == {"ruido": 2, "precio": 1}


def test_municipio_aspect_comparison_marks_selected_hexagon_aspect():
    result = municipio_aspect_comparison(_peer_gdf(), "b")
    row = result.loc[result["aspecto"] == "precio"].iloc[0]
    assert bool(row["es_seleccionado"]) is True


def test_municipio_aspect_comparison_returns_none_for_unknown_hexagon():
    assert municipio_aspect_comparison(_peer_gdf(), "unknown") is None


def test_municipio_aspect_comparison_drops_null_quejas():
    gdf = _peer_gdf()
    gdf.loc[gdf["h3_index"] == "c", "queja_principal"] = None
    result = municipio_aspect_comparison(gdf, "a")
    assert result["aspecto"].tolist() == ["ruido", "precio"]
    assert result.loc[result["aspecto"] == "ruido", "n_hexagonos"].iloc[0] == 1
