import pandas as pd

from app.turismo import (
    aena_series,
    estacionalidad_by_mes,
    format_yoy_delta,
    get_hotelero_anual_row,
    get_latest_aena_row,
)


def _hotelero_anual_df():
    return pd.DataFrame(
        [
            {
                "municipio": "Adeje", "polo_turistico": "Polo Sur", "anio": 2024,
                "viajeros_entrados_total": 1938929.0, "crec_viajeros_yoy_pct": 2.7,
                "pernoctaciones_total": 13840017.0, "crec_pernoctaciones_yoy_pct": 1.8,
                "ocupacion_media_plazas": 81.3, "estancia_media_hotel_dias": 7.14,
            },
            {
                "municipio": "Adeje", "polo_turistico": "Polo Sur", "anio": 2025,
                "viajeros_entrados_total": 1858237.0, "crec_viajeros_yoy_pct": -4.2,
                "pernoctaciones_total": 13113733.0, "crec_pernoctaciones_yoy_pct": -5.2,
                "ocupacion_media_plazas": 79.5, "estancia_media_hotel_dias": 7.06,
            },
        ]
    )


def test_get_hotelero_anual_row_returns_matching_row():
    row = get_hotelero_anual_row(_hotelero_anual_df(), "Adeje", 2025)
    assert row["pernoctaciones_total"] == 13113733.0


def test_get_hotelero_anual_row_returns_none_when_year_missing():
    assert get_hotelero_anual_row(_hotelero_anual_df(), "Adeje", 2020) is None


def test_format_yoy_delta_formats_with_sign_and_percent():
    assert format_yoy_delta(-4.2) == "-4.2%"
    assert format_yoy_delta(2.7) == "+2.7%"


def test_format_yoy_delta_returns_none_for_missing_value():
    assert format_yoy_delta(None) is None
    assert format_yoy_delta(float("nan")) is None


def _hotelero_mensual_df():
    return pd.DataFrame(
        [
            {"municipio": "Adeje", "mes": 1, "pernoctaciones": 900000.0},
            {"municipio": "Adeje", "mes": 1, "pernoctaciones": 1000000.0},
            {"municipio": "Adeje", "mes": 7, "pernoctaciones": 1200000.0},
            {"municipio": "Arona", "mes": 1, "pernoctaciones": 500000.0},
        ]
    )


def test_estacionalidad_by_mes_averages_across_years():
    result = estacionalidad_by_mes(_hotelero_mensual_df(), "Adeje", "pernoctaciones")
    row = result.loc[result["mes"] == 1].iloc[0]
    assert row["valor"] == 950000.0


def test_estacionalidad_by_mes_sorts_by_month_and_labels_in_spanish():
    result = estacionalidad_by_mes(_hotelero_mensual_df(), "Adeje", "pernoctaciones")
    assert result["mes"].tolist() == [1, 7]
    assert result["mes_label"].tolist() == ["Ene", "Jul"]


def _aena_df():
    return pd.DataFrame(
        [
            {"aeropuerto_codigo": "TFS", "periodo": "2026-05", "pasajeros": 938372.0, "operaciones": 6429.0},
            {"aeropuerto_codigo": "TFS", "periodo": "2026-06", "pasajeros": 935707.0, "operaciones": 6325.0},
            {"aeropuerto_codigo": "TFN", "periodo": "2026-06", "pasajeros": 300000.0, "operaciones": 3000.0},
        ]
    )


def test_get_latest_aena_row_picks_latest_period_for_airport():
    row = get_latest_aena_row(_aena_df(), "TFS")
    assert row["periodo"] == "2026-06"


def test_get_latest_aena_row_returns_none_for_unknown_airport():
    assert get_latest_aena_row(_aena_df(), "XXX") is None


def test_aena_series_filters_and_sorts_by_periodo():
    result = aena_series(_aena_df(), "TFS")
    assert result["periodo"].tolist() == ["2026-05", "2026-06"]
