import pandas as pd

from app.municipios import (
    get_istac_anual_row,
    get_istac_mensual_row_for_year,
    get_municipio_row,
    list_available_years,
)


def _municipio_master_df():
    return pd.DataFrame(
        {
            "municipio": ["Adeje", "Arona"],
            "n_hexagonos": [50, 80],
        }
    )


def test_get_municipio_row_returns_matching_row():
    row = get_municipio_row(_municipio_master_df(), "Adeje")
    assert row["n_hexagonos"] == 50


def test_get_municipio_row_returns_none_for_unknown_municipio():
    assert get_municipio_row(_municipio_master_df(), "No Existe") is None


def _istac_anual_df():
    return pd.DataFrame(
        {
            "municipio": ["Adeje", "Adeje", "Arona"],
            "anio": [2024, 2025, 2025],
            "poblacion_total": [50000, 51000, 80000],
        }
    )


def test_list_available_years_returns_sorted_unique_years():
    assert list_available_years(_istac_anual_df()) == [2024, 2025]


def test_get_istac_anual_row_returns_matching_municipio_and_year():
    row = get_istac_anual_row(_istac_anual_df(), "Adeje", 2024)
    assert row["poblacion_total"] == 50000


def test_get_istac_anual_row_returns_none_when_year_not_available():
    assert get_istac_anual_row(_istac_anual_df(), "Arona", 2024) is None


def _istac_mensual_df():
    return pd.DataFrame(
        {
            "municipio": ["Adeje", "Adeje", "Adeje", "Arona"],
            "periodo_codigo": ["2024-11", "2024-12", "2025-01", "2024-12"],
            "paro_registrado": [100, 110, 120, 200],
        }
    )


def test_get_istac_mensual_row_for_year_picks_latest_month_in_that_year():
    row = get_istac_mensual_row_for_year(_istac_mensual_df(), "Adeje", 2024)
    assert row["periodo_codigo"] == "2024-12"
    assert row["paro_registrado"] == 110


def test_get_istac_mensual_row_for_year_returns_none_when_no_months_in_year():
    assert get_istac_mensual_row_for_year(_istac_mensual_df(), "Adeje", 2026) is None
