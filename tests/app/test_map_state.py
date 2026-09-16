import streamlit as st

from app.map_state import get_selected_h3_index


def test_get_selected_h3_index_devuelve_none_sin_evento_de_mapa(monkeypatch):
    monkeypatch.setattr(st, "session_state", {})
    assert get_selected_h3_index() is None


def test_get_selected_h3_index_devuelve_none_sin_objetos_seleccionados(monkeypatch):
    monkeypatch.setattr(st, "session_state", {"h3_map": {"selection": {"objects": {}}}})
    assert get_selected_h3_index() is None


def test_get_selected_h3_index_extrae_el_hexagono_seleccionado(monkeypatch):
    evento = {"selection": {"objects": {"h3_index": [{"h3_index": "8839f8a449fffff"}]}}}
    monkeypatch.setattr(st, "session_state", {"h3_map": evento})
    assert get_selected_h3_index() == "8839f8a449fffff"
