import pandas as pd
import plotly.express as px

from app.ui_helpers import add_chart_motion, format_metric


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


def test_add_chart_motion_sets_a_transition_and_returns_the_figure():
    fig = px.bar(pd.DataFrame({"x": ["a", "b"], "y": [1, 2]}), x="x", y="y")
    result = add_chart_motion(fig)
    assert result is fig
    assert fig.layout.transition.duration == 400
