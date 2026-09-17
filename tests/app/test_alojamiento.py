import pandas as pd

from app.alojamiento import accommodation_breakdown, reputation_summary


def _gdf():
    return pd.DataFrame(
        {
            "n_hoteles": [2, 1],
            "n_vv": [5, 3],
            "n_extrahoteleros": [0, 1],
            "rating_booking_medio": [4.5, 3.5],
            "rating_tripadvisor_medio": [4.0, None],
            "n_reviews_booking": [100, 50],
        }
    )


def test_accommodation_breakdown_sums_each_type():
    result = accommodation_breakdown(_gdf())
    counts = dict(zip(result["tipo"], result["cantidad"]))
    assert counts == {"Hoteles": 3, "Viviendas vacacionales": 8, "Extrahoteleros": 1}


def test_reputation_summary_averages_ratings_ignoring_nulls():
    summary = reputation_summary(_gdf())
    assert summary["rating_booking_medio"] == 4.0
    assert summary["rating_tripadvisor_medio"] == 4.0
    assert summary["total_reviews_booking"] == 150
    assert summary["total_reviews"] == 150
