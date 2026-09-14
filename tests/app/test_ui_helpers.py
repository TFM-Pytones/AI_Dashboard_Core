import pandas as pd

from app.ui_helpers import format_as_of, format_metric, latest_value


def test_format_metric_none_returns_dash():
    assert format_metric(None) == "—"


def test_format_metric_nan_returns_dash():
    assert format_metric(float("nan")) == "—"


def test_format_metric_entero_uses_spanish_thousands_separator():
    assert format_metric(50612, "entero") == "50.612"


def test_format_metric_entero_rounds_floats_to_whole_number():
    assert format_metric(5827.0, "entero") == "5.827"


def test_format_metric_decimal_uses_comma_and_one_place():
    assert format_metric(4.567, "decimal") == "4,6"


def test_format_metric_decimal2_uses_two_places():
    assert format_metric(0.1234, "decimal2") == "0,12"


def test_format_metric_pct_appends_percent_sign():
    assert format_metric(79.5, "pct") == "79,5%"


def test_format_metric_euro_appends_euro_sign_with_thousands_separator():
    assert format_metric(1052093, "euro") == "1.052.093 €"


def test_format_metric_texto_passes_strings_through():
    assert format_metric("TFS", "texto") == "TFS"


def test_format_as_of_none_returns_none():
    assert format_as_of(None) is None


def test_format_as_of_nan_returns_none():
    assert format_as_of(float("nan")) is None


def test_format_as_of_integer_float_strips_decimal():
    assert format_as_of(2024.0) == "2024"


def test_format_as_of_string_passthrough():
    assert format_as_of("2024-03") == "2024-03"


def test_format_as_of_timestamp_formats_as_date():
    assert format_as_of(pd.Timestamp("2024-03-15")) == "2024-03-15"


def test_latest_value_returns_max_formatted():
    assert latest_value(pd.Series([2021, 2023, 2022])) == "2023"


def test_latest_value_empty_series_returns_none():
    assert latest_value(pd.Series([], dtype=float)) is None


def test_latest_value_drops_none_before_comparing_mixed_object_dtype():
    import datetime

    series = pd.Series([datetime.date(2025, 1, 1), None, datetime.date(2025, 6, 1), None], dtype=object)
    assert latest_value(series) == "2025-06-01"


def test_latest_value_all_none_returns_none():
    series = pd.Series([None, None], dtype=object)
    assert latest_value(series) is None
