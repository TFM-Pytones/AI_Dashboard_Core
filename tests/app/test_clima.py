import pandas as pd

from app.clima import CLIMATE_VARIABLES, climate_by_trimestre


def _gdf():
    return pd.DataFrame(
        {
            "h3_index": ["a", "b"],
            "temp_media_q1": [18.0, 20.0],
            "temp_media_q2": [20.0, 22.0],
            "temp_media_q3": [24.0, 26.0],
            "temp_media_q4": [19.0, 21.0],
        }
    )


def test_climate_by_trimestre_averages_across_hexagons():
    result = climate_by_trimestre(_gdf(), "temp_media")
    values = dict(zip(result["trimestre"], result["valor"]))
    assert values["Q1"] == 19.0
    assert values["Q2"] == 21.0
    assert values["Q3"] == 25.0
    assert values["Q4"] == 20.0


def test_climate_by_trimestre_orders_q1_to_q4():
    result = climate_by_trimestre(_gdf(), "temp_media")
    assert result["trimestre"].tolist() == ["Q1", "Q2", "Q3", "Q4"]


def test_climate_variables_covers_expected_labels():
    assert set(CLIMATE_VARIABLES.keys()) == {"Temperatura", "Lluvia", "Viento", "Humedad"}


def test_climate_variables_each_have_a_prefix_unidad_and_help():
    for variable in CLIMATE_VARIABLES.values():
        assert variable["prefix"]
        assert variable["unidad"]
        assert variable["help"]
