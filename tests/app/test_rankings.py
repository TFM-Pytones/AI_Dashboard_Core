import pandas as pd

from app.rankings import RANKINGS, top_n_by_ranking


def _gdf():
    return pd.DataFrame(
        {
            "h3_index": ["a", "b", "c", "d"],
            "municipio": ["Adeje", "Arona", "Adeje", "Arona"],
            "ndvi_medio": [0.8, None, 0.2, 0.5],
            "temp_media_anual": [22.0, 25.0, 19.0, 24.0],
            "n_establecimientos_booking": [10, 3, 0, 7],
            "rating_booking_medio": [4.5, 3.0, None, 4.8],
        }
    )


def test_top_n_by_ranking_sorts_descending_and_drops_nulls():
    result = top_n_by_ranking(_gdf(), "Más vegetación (NDVI)", n=10)
    assert result["h3_index"].tolist() == ["a", "d", "c"]  # b dropped (NaN)


def test_top_n_by_ranking_respects_n():
    result = top_n_by_ranking(_gdf(), "Más vegetación (NDVI)", n=2)
    assert len(result) == 2


def test_top_n_by_ranking_more_turistica_uses_booking_count():
    result = top_n_by_ranking(_gdf(), "Más turística (nº establecimientos Booking)", n=1)
    assert result["h3_index"].tolist() == ["a"]


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
