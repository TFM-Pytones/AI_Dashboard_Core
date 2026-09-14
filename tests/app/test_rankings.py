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
            "n_establecimientos_booking": [10, 5, 3, 0, 7],
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


def test_top_n_by_ranking_more_turistica_sums_booking_count_per_municipio():
    result = top_n_by_ranking(_gdf(), "Más turística (nº establecimientos Booking)", n=10)
    counts = dict(zip(result["municipio"], result["n_establecimientos_booking"]))
    assert counts == {"Adeje": 15, "Arona": 10}


def test_top_n_by_ranking_unknown_key_raises():
    try:
        top_n_by_ranking(_gdf(), "no existe", n=1)
        assert False, "expected KeyError"
    except KeyError:
        pass


def test_rankings_dict_covers_expected_labels():
    assert set(RANKINGS.keys()) == {
        "Más vegetación (NDVI)",
        "Más turística (nº establecimientos Booking)",
        "Mejor valoradas (rating Booking)",
        "Más calurosas",
    }
