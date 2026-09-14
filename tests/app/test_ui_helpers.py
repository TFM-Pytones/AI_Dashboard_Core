import pandas as pd

from app.ui_helpers import format_as_of, latest_value


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
