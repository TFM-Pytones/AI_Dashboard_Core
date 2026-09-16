import pandas as pd
import pytest

from app.detail_panel import (
    municipio_aspect_comparison,
    municipio_metric_comparison,
    nearest_destinos,
    restriction_badges,
)


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


def _metric_gdf():
    return pd.DataFrame(
        {
            "h3_index": ["a", "b", "c", "d"],
            "municipio": ["Adeje", "Adeje", "Adeje", "Arona"],
            "ndvi_medio": [0.2, 0.4, 0.6, 0.8],
            "altitud_media_m": [10.0, 20.0, 30.0, 900.0],
            "n_plazas_registro": [100, 200, 300, 5],
        }
    )


def test_municipio_metric_comparison_returns_none_for_unknown_hexagon():
    assert municipio_metric_comparison(_metric_gdf(), "no-existe") is None


def test_municipio_metric_comparison_compares_hexagono_vs_media_de_sus_pares():
    result = municipio_metric_comparison(_metric_gdf(), "a")
    fila_hex = result[(result["metrica"] == "NDVI medio") & (result["serie"] == "Este hexágono")]
    fila_media = result[(result["metrica"] == "NDVI medio") & (result["serie"] == "Media del municipio")]
    assert fila_hex["valor"].iloc[0] == 0.2
    assert fila_media["valor"].iloc[0] == pytest.approx((0.2 + 0.4 + 0.6) / 3)


def test_municipio_metric_comparison_no_mezcla_hexagonos_de_otro_municipio():
    result = municipio_metric_comparison(_metric_gdf(), "a")
    fila_media = result[(result["metrica"] == "NDVI medio") & (result["serie"] == "Media del municipio")]
    # Arona (0.8) no debe entrar en la media -- solo los 3 hexagonos de Adeje.
    assert fila_media["valor"].iloc[0] == pytest.approx(0.4)


def test_municipio_metric_comparison_omite_metrica_sin_dato():
    gdf = _metric_gdf()
    gdf["ndvi_medio"] = None
    result = municipio_metric_comparison(gdf, "a")
    assert "NDVI medio" not in result["metrica"].values
    assert "Altitud media (m)" in result["metrica"].values


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
