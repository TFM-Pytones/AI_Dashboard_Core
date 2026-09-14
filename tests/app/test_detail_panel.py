import pandas as pd

from app.detail_panel import (
    format_kpi_value,
    municipio_aspect_comparison,
    nearest_destinos,
    restriction_badges,
)


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


def test_restriction_badges_shows_enp_badge():
    row = pd.Series({"pct_area_enp": 1.0, "pct_area_zona_turistica": 0.0})
    assert restriction_badges(row) == ["⚠️ Espacio Natural Protegido"]


def test_restriction_badges_shows_zona_turistica_badge():
    row = pd.Series({"pct_area_enp": 0.0, "pct_area_zona_turistica": 0.435})
    assert restriction_badges(row) == ["🏖️ Zona turística oficial"]


def test_restriction_badges_shows_both_when_both_overlap():
    row = pd.Series({"pct_area_enp": 0.09, "pct_area_zona_turistica": 0.26})
    assert restriction_badges(row) == ["⚠️ Espacio Natural Protegido", "🏖️ Zona turística oficial"]


def test_restriction_badges_empty_when_neither_overlaps():
    row = pd.Series({"pct_area_enp": 0.0, "pct_area_zona_turistica": 0.0})
    assert restriction_badges(row) == []


def test_restriction_badges_treats_missing_values_as_no_overlap():
    row = pd.Series({"pct_area_enp": float("nan"), "pct_area_zona_turistica": None})
    assert restriction_badges(row) == []


def test_nearest_destinos_sorts_by_minutes_ascending():
    row = pd.Series({"tiempo_capital_min": 40.0, "tiempo_teide_min": 25.0, "tiempo_la_laguna_min": 35.0})
    result = nearest_destinos(row, n=5)
    assert result["destino"].tolist() == ["El Teide", "La Laguna", "Santa Cruz de Tenerife"]


def test_nearest_destinos_drops_missing_values():
    row = pd.Series({"tiempo_capital_min": None, "tiempo_teide_min": 25.0})
    result = nearest_destinos(row)
    assert result["destino"].tolist() == ["El Teide"]


def test_nearest_destinos_respects_limit():
    row = pd.Series({"tiempo_capital_min": 10.0, "tiempo_teide_min": 20.0, "tiempo_la_laguna_min": 30.0})
    result = nearest_destinos(row, n=2)
    assert len(result) == 2
