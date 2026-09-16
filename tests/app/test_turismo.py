import pandas as pd

from app.turismo import (
    aena_estacionalidad_comparativa,
    aena_series,
    compute_aena_kpis,
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


def test_aena_series_total_aggregates_both_airports_per_period():
    result = aena_series(_aena_df(), "TOTAL")
    assert result["periodo"].tolist() == ["2026-05", "2026-06"]
    # 2026-05: only TFS (938372.0)
    assert result.loc[result["periodo"] == "2026-05", "pasajeros"].iloc[0] == 938372.0
    # 2026-06: TFS (935707.0) + TFN (300000.0) = 1235707.0
    assert result.loc[result["periodo"] == "2026-06", "pasajeros"].iloc[0] == 1235707.0
    assert result.loc[result["periodo"] == "2026-06", "operaciones"].iloc[0] == 9325.0


def test_get_latest_aena_row_total_returns_combined_latest_period():
    row = get_latest_aena_row(_aena_df(), "TOTAL")
    assert row is not None
    assert row["periodo"] == "2026-06"
    assert row["pasajeros"] == 1235707.0
    assert row["operaciones"] == 9325.0
    assert row["pasajeros_por_operacion"] == round(1235707.0 / 9325.0, 1)


def test_get_latest_aena_row_total_returns_none_on_empty_df():
    empty_df = pd.DataFrame(columns=["aeropuerto_codigo", "periodo", "pasajeros", "operaciones"])
    assert get_latest_aena_row(empty_df, "TOTAL") is None


def test_compute_aena_kpis_returns_expected_kpis_with_yoy_and_trailing():
    df = pd.DataFrame(
        [
            {"aeropuerto_codigo": "TFS", "periodo": "2025-06", "pasajeros": 800000.0, "operaciones": 5000.0},
            {"aeropuerto_codigo": "TFS", "periodo": "2026-06", "pasajeros": 900000.0, "operaciones": 6000.0},
        ]
    )
    serie = aena_series(df, "TFS")
    kpis = compute_aena_kpis(serie)
    assert len(kpis) == 3
    assert kpis[0]["label"] == "✈️ Pasajeros (último mes)"
    assert kpis[0]["value"] == 900000.0
    assert kpis[0]["delta"] == "+12.5%"
    assert kpis[1]["label"] == "📅 Acumulado anual (12 meses)"
    assert kpis[1]["value"] == 1700000.0
    assert kpis[2]["label"] == "📊 Media mensual histórica"
    assert kpis[2]["value"] == 850000.0


def test_compute_aena_kpis_returns_empty_list_for_empty_df():
    assert compute_aena_kpis(pd.DataFrame()) == []


def _aena_estacionalidad_df():
    return pd.DataFrame(
        [
            {"aeropuerto_codigo": "TFS", "aeropuerto_nombre": "Tenerife Sur - Reina Sofía", "mes": 1, "pasajeros": 900000.0},
            {"aeropuerto_codigo": "TFS", "aeropuerto_nombre": "Tenerife Sur - Reina Sofía", "mes": 1, "pasajeros": 1000000.0},
            {"aeropuerto_codigo": "TFS", "aeropuerto_nombre": "Tenerife Sur - Reina Sofía", "mes": 7, "pasajeros": 500000.0},
            {"aeropuerto_codigo": "TFN", "aeropuerto_nombre": "Tenerife Norte - Ciudad de La Laguna", "mes": 1, "pasajeros": 200000.0},
            {"aeropuerto_codigo": "TFN", "aeropuerto_nombre": "Tenerife Norte - Ciudad de La Laguna", "mes": 7, "pasajeros": 400000.0},
        ]
    )


def test_aena_estacionalidad_comparativa_averages_across_years_per_airport():
    result = aena_estacionalidad_comparativa(_aena_estacionalidad_df(), "pasajeros")
    tfs_enero = result.loc[
        (result["aeropuerto_nombre"] == "Tenerife Sur - Reina Sofía") & (result["mes"] == 1)
    ].iloc[0]
    assert tfs_enero["valor"] == 950000.0


def test_aena_estacionalidad_comparativa_keeps_both_airports_separate():
    result = aena_estacionalidad_comparativa(_aena_estacionalidad_df(), "pasajeros")
    assert sorted(result["aeropuerto_nombre"].unique().tolist()) == [
        "Tenerife Norte - Ciudad de La Laguna",
        "Tenerife Sur - Reina Sofía",
    ]


def test_aena_estacionalidad_comparativa_sorts_by_month_and_labels_in_spanish():
    result = aena_estacionalidad_comparativa(_aena_estacionalidad_df(), "pasajeros")
    tfn = result.loc[result["aeropuerto_nombre"] == "Tenerife Norte - Ciudad de La Laguna"]
    assert tfn["mes"].tolist() == [1, 7]
    assert tfn["mes_label"].tolist() == ["Ene", "Jul"]
