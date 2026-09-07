from app.color_scales import (
    NO_DATA_COLOR,
    diverging_color,
    interpolate_hex,
    sequential_color,
)


def test_interpolate_hex_at_light_endpoint():
    assert interpolate_hex(0.0, "#000000", "#ffffff") == [0, 0, 0]


def test_interpolate_hex_at_dark_endpoint():
    assert interpolate_hex(1.0, "#000000", "#ffffff") == [255, 255, 255]


def test_interpolate_hex_midpoint():
    assert interpolate_hex(0.5, "#000000", "#ffffff") == [128, 128, 128]


def test_interpolate_hex_clamps_t_above_one():
    assert interpolate_hex(1.5, "#000000", "#ffffff") == [255, 255, 255]


def test_interpolate_hex_clamps_t_below_zero():
    assert interpolate_hex(-0.5, "#000000", "#ffffff") == [0, 0, 0]


def test_sequential_color_scales_between_bounds():
    assert sequential_color(5, 0, 10, "#000000", "#ffffff") == [128, 128, 128]


def test_sequential_color_none_returns_no_data():
    assert sequential_color(None, 0, 10, "#000000", "#ffffff") == NO_DATA_COLOR


def test_sequential_color_nan_returns_no_data():
    assert sequential_color(float("nan"), 0, 10, "#000000", "#ffffff") == NO_DATA_COLOR


def test_diverging_color_at_min_returns_low_pole():
    assert diverging_color(1.0, 1.0, 3.0, 5.0) == [227, 73, 72]


def test_diverging_color_at_mid_returns_neutral_gray():
    assert diverging_color(3.0, 1.0, 3.0, 5.0) == [240, 239, 236]


def test_diverging_color_at_max_returns_high_pole():
    assert diverging_color(5.0, 1.0, 3.0, 5.0) == [42, 120, 214]


def test_diverging_color_none_returns_no_data():
    assert diverging_color(None, 1.0, 3.0, 5.0) == NO_DATA_COLOR


def test_diverging_color_nan_returns_no_data():
    assert diverging_color(float("nan"), 1.0, 3.0, 5.0) == NO_DATA_COLOR
