import pandas as pd

from app.municipios import (
    empleo_breakdown,
    evolucion_mensual_series,
    evolucion_series,
    format_yoy_delta,
    get_anual_row,
    get_latest_empleo_row,
    get_municipio_row,
    list_available_years,
)


def _municipio_master_df():
    return pd.DataFrame(
        {
            "municipio": ["Adeje", "Arona"],
            "n_hexagonos": [50, 40],
        }
    )


def test_get_municipio_row_returns_matching_row():
    row = get_municipio_row(_municipio_master_df(), "Adeje")
    assert row["n_hexagonos"] == 50


def test_get_municipio_row_returns_none_for_unknown_municipio():
    assert get_municipio_row(_municipio_master_df(), "No Existe") is None


def _municipio_anual_df():
    return pd.DataFrame(
        [
            {
                "municipio": "Adeje", "anio": 2024, "n_meses": 12, "es_anio_completo": True,
                "poblacion": 50929.0, "paro_medio": 1996.0, "var_paro_yoy_pct": -9.9,
            },
            {
                "municipio": "Adeje", "anio": 2025, "n_meses": 12, "es_anio_completo": True,
                "poblacion": 50612.0, "paro_medio": 1925.0, "var_paro_yoy_pct": -3.6,
            },
            {
                "municipio": "Adeje", "anio": 2026, "n_meses": 8, "es_anio_completo": False,
                "poblacion": 50612.0, "paro_medio": 1902.0, "var_paro_yoy_pct": -1.2,
            },
            {
                "municipio": "Arona", "anio": 2025, "n_meses": 12, "es_anio_completo": True,
                "poblacion": 80000.0, "paro_medio": 3000.0, "var_paro_yoy_pct": 1.0,
            },
        ]
    )


def test_list_available_years_returns_sorted_unique_years():
    assert list_available_years(_municipio_anual_df()) == [2024, 2025, 2026]


def test_get_anual_row_returns_matching_municipio_and_year():
    row = get_anual_row(_municipio_anual_df(), "Adeje", 2025)
    assert row["poblacion"] == 50612.0


def test_get_anual_row_returns_none_when_year_not_available():
    assert get_anual_row(_municipio_anual_df(), "Arona", 2024) is None


def test_format_yoy_delta_formats_with_sign_and_percent():
    assert format_yoy_delta(-9.9) == "-9.9%"
    assert format_yoy_delta(7.8) == "+7.8%"


def test_format_yoy_delta_returns_none_for_missing_value():
    assert format_yoy_delta(None) is None
    assert format_yoy_delta(float("nan")) is None


def test_evolucion_series_returns_year_ordered_tidy_frame():
    result = evolucion_series(_municipio_anual_df(), "Adeje", "paro_medio")
    assert result["anio"].tolist() == [2024, 2025, 2026]
    assert result["valor"].tolist() == [1996.0, 1925.0, 1902.0]


def _municipio_mensual_df():
    return pd.DataFrame(
        [
            {"municipio": "Adeje", "periodo": "2026-01", "paro_registrado": 1876.0, "plazas_vv": 17486.0},
            {"municipio": "Adeje", "periodo": "2025-12", "paro_registrado": 1900.0, "plazas_vv": 18553.0},
            {"municipio": "Arona", "periodo": "2026-01", "paro_registrado": 3100.0, "plazas_vv": 9000.0},
        ]
    )


def test_evolucion_mensual_series_returns_period_ordered_tidy_frame():
    result = evolucion_mensual_series(_municipio_mensual_df(), "Adeje", "paro_registrado")
    assert result["periodo"].tolist() == ["2025-12", "2026-01"]
    assert result["valor"].tolist() == [1900.0, 1876.0]


def test_evolucion_mensual_series_scopes_to_municipio():
    result = evolucion_mensual_series(_municipio_mensual_df(), "Arona", "plazas_vv")
    assert result["valor"].tolist() == [9000.0]


def _municipio_empleo_df():
    return pd.DataFrame(
        [
            {
                "municipio": "Adeje", "anio": 2025, "trimestre": 3, "periodo": "2025-Q3",
                "periodo_texto": "2025 Tercer trimestre",
                "empleo_asalariados": 31969.0, "empleo_autonomos": 5402.0,
            },
            {
                "municipio": "Adeje", "anio": 2025, "trimestre": 4, "periodo": "2025-Q4",
                "periodo_texto": "2025 Cuarto trimestre",
                "empleo_asalariados": 32257.0, "empleo_autonomos": 5431.0,
            },
        ]
    )


def test_get_latest_empleo_row_picks_latest_quarter_in_year():
    row = get_latest_empleo_row(_municipio_empleo_df(), "Adeje", 2025)
    assert row["periodo"] == "2025-Q4"


def test_get_latest_empleo_row_returns_none_when_no_data_for_year():
    assert get_latest_empleo_row(_municipio_empleo_df(), "Adeje", 2026) is None


def test_empleo_breakdown_returns_tidy_frame():
    row = get_latest_empleo_row(_municipio_empleo_df(), "Adeje", 2025)
    result = empleo_breakdown(row)
    counts = dict(zip(result["tipo"], result["cantidad"]))
    assert counts == {"Asalariados": 32257.0, "Autónomos": 5431.0}
