import pandas as pd
import streamlit as st


def format_as_of(value) -> str | None:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def latest_value(series: pd.Series) -> str | None:
    if series.empty:
        return None
    return format_as_of(series.max())


def render_footer(source: str, as_of: str | None = None) -> None:
    text = f"📊 Fuente: {source}"
    if as_of:
        text += f" · Datos hasta: {as_of}"
    st.caption(text)
