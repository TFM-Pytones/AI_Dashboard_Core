import inspect

import pydeck
import plotly
import streamlit as st


def test_pydeck_and_plotly_are_importable():
    assert pydeck.__version__
    assert plotly.__version__


def test_streamlit_pydeck_chart_supports_click_selection():
    signature = inspect.signature(st.pydeck_chart)
    assert "on_select" in signature.parameters
    assert "selection_mode" in signature.parameters
