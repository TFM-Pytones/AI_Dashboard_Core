import pandas as pd
import pydeck as pdk

from app.map_layers import build_deck, build_fill_color_column, build_layer


def _gdf():
    return pd.DataFrame(
        {
            "h3_index": ["a", "b", "c"],
            "densidad_metric": [0, 10, 20],
            "sentimiento_medio": [1.0, 3.0, 5.0],
            "ndvi_medio": [None, 0.5, 1.0],
        }
    )


def test_build_fill_color_column_sequential_scales_min_to_max():
    colors = build_fill_color_column(_gdf(), "Densidad hotelera")
    assert colors.iloc[0] == [205, 226, 251]  # light end of the blue ramp
    assert colors.iloc[2] == [13, 54, 107]  # dark end of the blue ramp


def test_build_fill_color_column_diverging_uses_fixed_domain():
    colors = build_fill_color_column(_gdf(), "Sentimiento")
    assert colors.tolist() == [[227, 73, 72], [240, 239, 236], [42, 120, 214]]


def test_build_fill_color_column_handles_null_values():
    colors = build_fill_color_column(_gdf(), "Naturaleza (NDVI)")
    assert colors.iloc[0] == [137, 135, 129]  # NO_DATA_COLOR


def test_build_layer_returns_pickable_h3_layer():
    layer = build_layer(_gdf(), "Densidad hotelera")
    assert isinstance(layer, pdk.Layer)
    assert layer.id == "h3_index"
    assert layer.pickable is True
    assert layer.get_hexagon == "@@=h3_index"  # pydeck prefixes column accessors with "@@="
    assert layer.get_fill_color == "@@=fill_color"


def test_build_deck_has_one_layer_centered_on_tenerife():
    deck = build_deck(_gdf(), "Sentimiento")
    assert isinstance(deck, pdk.Deck)
    assert len(deck.layers) == 1
    assert round(deck.initial_view_state.latitude, 2) == 28.29
    assert round(deck.initial_view_state.longitude, 2) == -16.62
