import pandas as pd
import pytest

from app.rankings import RANKINGS, top_n_by_ranking


def _gdf():
    return pd.DataFrame(
        {
            "h3_index": ["a", "b", "c", "d", "e"],
            "municipio": ["Adeje", "Adeje", "Arona", "Arona", "Arona"],
            "ndvi_medio": [0.8, 0.4, None, 0.2, 0.5],
            "temp_media_anual": [22.0, 24.0, 25.0, 19.0, 24.0],
            "n_establecimientos_registro": [100, 50, 30, 0, 70],
            "n_plazas_registro": [1000, 500, 200, 0, 800],
            "rating_booking_medio": [4.5, 3.5, 3.0, None, 4.8],
        }
    )


def test_top_n_by_ranking_aggregates_by_municipio_and_sorts_descending():
    result = top_n_by_ranking(_gdf(), "Más vegetación (NDVI)", n=10)
    # Adeje mean = (0.8+0.4)/2 = 0.6, Arona mean = (0.2+0.5)/2 = 0.35 (b's NaN dropped before grouping)
    assert result["municipio"].tolist() == ["Adeje", "Arona"]
    assert result["ndvi_medio"].tolist() == pytest.approx([0.6, 0.35])


def test_top_n_by_ranking_respects_n():
    result = top_n_by_ranking(_gdf(), "Más vegetación (NDVI)", n=1)
    assert len(result) == 1


def test_top_n_by_ranking_establecimientos_sums_official_count_per_municipio():
    result = top_n_by_ranking(_gdf(), "Mayor oferta alojativa (nº alojamientos)", n=10)
    counts = dict(zip(result["municipio"], result["n_establecimientos_registro"]))
    assert counts == {"Adeje": 150, "Arona": 100}


def test_top_n_by_ranking_plazas_sums_official_capacity_per_municipio():
    result = top_n_by_ranking(_gdf(), "Mayor capacidad alojativa (nº plazas)", n=10)
    counts = dict(zip(result["municipio"], result["n_plazas_registro"]))
    assert counts == {"Adeje": 1500, "Arona": 1000}


def test_top_n_by_ranking_unknown_key_raises():
    try:
        top_n_by_ranking(_gdf(), "no existe", n=1)
        assert False, "expected KeyError"
    except KeyError:
        pass


def test_rankings_dict_covers_expected_labels():
    assert set(RANKINGS.keys()) == {
        "Mayor oferta alojativa (nº alojamientos)",
        "Mayor capacidad alojativa (nº plazas)",
        "Más vegetación (NDVI)",
        "Mejor valoradas (rating Booking)",
        "Más calurosas",
    }
