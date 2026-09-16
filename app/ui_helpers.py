import pandas as pd

# Metric kinds understood by format_metric, each mapped to (decimal_places, suffix).
# "texto" passes strings through unchanged instead of formatting a number.
_METRIC_KIND_SPECS = {
    "entero": (0, ""),
    "decimal": (1, ""),
    "decimal2": (2, ""),
    "pct": (1, "%"),
    "euro": (0, " €"),
}


def _thousands_es(value: float, decimals: int) -> str:
    # Python's default grouping uses "," for thousands and "." for decimals
    # (e.g. "50,612.0"); Spanish convention swaps them ("50.612,0").
    formatted = f"{value:,.{decimals}f}"
    return formatted.replace(",", "§").replace(".", ",").replace("§", ".")


def format_metric(value, kind: str = "entero") -> str:
    if value is None or pd.isna(value):
        return "—"
    if isinstance(value, str):
        return value
    decimals, suffix = _METRIC_KIND_SPECS[kind]
    return _thousands_es(value, decimals) + suffix


def add_chart_motion(fig):
    # Streamlit's plotly component updates the existing chart in place (not a
    # full remount) when its data changes, e.g. via a filter -- this makes
    # that redraw animate instead of jumping straight to the new values.
    fig.update_layout(transition={"duration": 400, "easing": "cubic-in-out"})
    return fig
