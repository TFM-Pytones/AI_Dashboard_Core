import geopandas as gpd
import pandas as pd
import pydeck as pdk
from shapely.geometry import MultiPolygon, box

from app.map_layers import (
    build_deck,
    build_fill_color_column,
    build_highlight_layer,
    build_isocronas_fill_color,
    build_isocronas_layer,
    build_layer,
    build_municipio_fill_color_column,
    build_municipio_layer,
    legend_html,
    list_destinos,
    municipio_legend_html,
)


def _gdf():
    return pd.DataFrame(
        {
            "h3_index": ["a", "b", "c"],
            "municipio": ["Adeje", "Arona", "Adeje"],
            "densidad_metric": [0, 10, 20],
            "sentimiento_medio": [1.0, 3.0, 5.0],
            "ndvi_medio": [None, 0.5, 1.0],
            "dist_costa_km": [0, 1000, 2000],
            "n_pois_total": [0, 5, 10],
            "slope_mean": [0, 15, 30],
            "restriction_category": ["ENP", "Zona turística oficial", "Sin restricción"],
        }
    )


def test_build_fill_color_column_sequential_scales_min_to_max():
    colors = build_fill_color_column(_gdf(), "Densidad hotelera")
    assert colors.iloc[0] == [205, 226, 251]  # light end of the blue ramp
    assert colors.iloc[2] == [13, 54, 107]  # dark end of the blue ramp


def test_build_fill_color_column_diverging_uses_fixed_domain():
    colors = build_fill_color_column(_gdf(), "Sentimiento")
    assert colors.tolist() == [[227, 73, 72], [243, 244, 246], [30, 58, 138]]


def test_build_fill_color_column_handles_null_values():
    colors = build_fill_color_column(_gdf(), "Naturaleza (NDVI)")
    assert colors.iloc[0] == [107, 114, 128]  # NO_DATA_COLOR


def test_build_fill_color_column_new_sequential_layers_scale_min_to_max():
    for metric_key, column in [
        ("Distancia a la costa", "dist_costa_km"),
        ("Puntos de interés turísticos", "n_pois_total"),
        ("Pendiente del terreno", "slope_mean"),
    ]:
        colors = build_fill_color_column(_gdf(), metric_key)
        assert colors.iloc[0] == [205, 226, 251], metric_key  # light end (row with min value)
        assert colors.iloc[2] == [13, 54, 107], metric_key  # dark end (row with max value)


def test_build_fill_color_column_categorical_maps_known_categories():
    colors = build_fill_color_column(_gdf(), "Restricciones legales")
    assert colors.tolist() == [
        [208, 59, 59],  # ENP
        [30, 58, 138],  # Zona turística oficial
        [12, 163, 12],  # Sin restricción
    ]


def test_build_fill_color_column_categorical_handles_unknown_as_no_data():
    gdf = _gdf()
    gdf.loc[0, "restriction_category"] = "Categoría desconocida"
    colors = build_fill_color_column(gdf, "Restricciones legales")
    assert colors.iloc[0] == [107, 114, 128]  # NO_DATA_COLOR


def test_build_fill_color_column_accesibilidad_layers_scale_min_to_max():
    gdf = _gdf()
    gdf["tiempo_aeropuerto_min"] = [10.0, 30.0, 50.0]
    gdf["dist_hospital_km"] = [1.0, 5.0, 9.0]
    gdf["n_paradas_bus_500m"] = [0, 2, 4]
    for metric_key in ["Tiempo al aeropuerto", "Distancia a hospital", "Paradas de bus cercanas"]:
        colors = build_fill_color_column(gdf, metric_key)
        assert colors.iloc[0] == [205, 226, 251], metric_key
        assert colors.iloc[2] == [13, 54, 107], metric_key


def _isocronas_gdf():
    return gpd.GeoDataFrame(
        {
            "destino": ["tfs", "tfs", "teide"],
            "destino_label": ["Aeropuerto Sur", "Aeropuerto Sur", "Teide"],
            "rango_min": [15.0, 60.0, 30.0],
        },
        geometry=[box(0, 0, 1, 1), box(0, 0, 2, 2), box(5, 5, 6, 6)],
    )


def test_list_destinos_returns_sorted_unique_labels():
    assert list_destinos(_isocronas_gdf()) == ["teide", "tfs"]


def test_build_isocronas_fill_color_darkest_at_shortest_range():
    colors = build_isocronas_fill_color(pd.Series([15.0, 60.0]))
    assert colors.iloc[0] == [13, 54, 107]  # closest (15 min) -> dark end
    assert colors.iloc[1] == [205, 226, 251]  # farthest (60 min) -> light end


def test_build_isocronas_layer_filters_by_destino_and_returns_geojson_layer():
    layer = build_isocronas_layer(_isocronas_gdf(), "tfs")
    assert isinstance(layer, pdk.Layer)
    assert len(layer.data["features"]) == 2
    assert layer.get_fill_color == "@@=properties.fill_color"


def test_build_layer_returns_pickable_h3_layer():
    layer = build_layer(_gdf(), "Densidad hotelera")
    assert isinstance(layer, pdk.Layer)
    assert layer.id == "h3_index"
    assert layer.pickable is True
    assert layer.get_hexagon == "@@=h3_index"  # pydeck prefixes column accessors with "@@="
    assert layer.get_fill_color == "@@=fill_color"


def test_build_layer_includes_municipio_and_formatted_tooltip_value():
    layer = build_layer(_gdf(), "Densidad hotelera")
    data_df = pd.DataFrame(layer.data) if isinstance(layer.data, list) else layer.data
    assert list(data_df.columns) == ["h3_index", "municipio", "tooltip_value", "fill_color"]
    assert data_df["municipio"].tolist() == ["Adeje", "Arona", "Adeje"]
    assert data_df["tooltip_value"].tolist() == ["0,0", "10,0", "20,0"]


def test_build_layer_tooltip_value_shows_sin_datos_for_missing():
    layer = build_layer(_gdf(), "Naturaleza (NDVI)")
    data_df = pd.DataFrame(layer.data) if isinstance(layer.data, list) else layer.data
    assert data_df["tooltip_value"].iloc[0] == "Sin datos"


def test_build_layer_tooltip_value_passes_through_categories_as_is():
    layer = build_layer(_gdf(), "Restricciones legales")
    data_df = pd.DataFrame(layer.data) if isinstance(layer.data, list) else layer.data
    assert data_df["tooltip_value"].tolist() == ["ENP", "Zona turística oficial", "Sin restricción"]


def test_build_layer_is_semi_transparent_by_default_so_the_basemap_shows_through():
    layer = build_layer(_gdf(), "Densidad hotelera")
    assert 0 < layer.opacity < 1


def test_build_layer_accepts_custom_opacity():
    layer = build_layer(_gdf(), "Densidad hotelera", opacity=0.2)
    assert layer.opacity == 0.2


def test_build_highlight_layer_targets_the_selected_hexagon():
    layer = build_highlight_layer("8834413693fffff")
    assert isinstance(layer, pdk.Layer)
    assert layer.data["h3_index"].tolist() == ["8834413693fffff"]
    assert layer.get_hexagon == "@@=h3_index"


def test_build_highlight_layer_is_an_outline_not_a_fill():
    # Sin relleno -- para no tapar el color de la capa de métrica que haya
    # debajo, solo un contorno llamativo alrededor del hexágono seleccionado.
    layer = build_highlight_layer("8834413693fffff")
    assert layer.filled is False
    assert layer.stroked is True
    assert layer.line_width_min_pixels >= 4


def test_build_deck_has_one_layer_centered_on_tenerife(monkeypatch):
    monkeypatch.setenv("MAPBOX_API_KEY", "pk.test_token")
    deck = build_deck(_gdf(), "Sentimiento")
    assert isinstance(deck, pdk.Deck)
    assert len(deck.layers) == 1
    assert round(deck.initial_view_state.latitude, 2) == 28.29
    assert round(deck.initial_view_state.longitude, 2) == -16.62


def test_build_deck_constrains_zoom_so_it_cant_show_the_whole_globe(monkeypatch):
    monkeypatch.setenv("MAPBOX_API_KEY", "pk.test_token")
    deck = build_deck(_gdf(), "Sentimiento")
    # min_zoom == the initial zoom: zooming out is clamped back to the
    # Tenerife framing instead of ever reaching a world view.
    assert deck.initial_view_state.min_zoom == deck.initial_view_state.zoom
    assert deck.initial_view_state.max_zoom == 16


def test_build_deck_uses_mapbox_satellite_provider(monkeypatch):
    monkeypatch.setenv("MAPBOX_API_KEY", "pk.test_token")
    deck = build_deck(_gdf(), "Sentimiento")
    assert deck.map_provider == "mapbox"
    assert deck.map_style == "mapbox://styles/mapbox/satellite-streets-v9"
    # pydeck 0.9.1 stores the mapbox api_keys entry as this attribute, not
    # as an inspectable `api_keys` dict on the Deck instance.
    assert deck.mapbox_key == "pk.test_token"


def test_build_deck_can_hide_the_hexagon_layer(monkeypatch):
    monkeypatch.setenv("MAPBOX_API_KEY", "pk.test_token")
    deck = build_deck(_gdf(), "Sentimiento", show_hexagons=False)
    assert deck.layers == []


def test_build_deck_accepts_custom_hexagon_opacity(monkeypatch):
    monkeypatch.setenv("MAPBOX_API_KEY", "pk.test_token")
    deck = build_deck(_gdf(), "Sentimiento", opacity=0.2)
    assert deck.layers[0].opacity == 0.2


def test_build_deck_defaults_to_a_translucent_opacity_so_satellite_shows_through(monkeypatch):
    monkeypatch.setenv("MAPBOX_API_KEY", "pk.test_token")
    deck = build_deck(_gdf(), "Sentimiento")
    assert deck.layers[0].opacity <= 0.45


def test_build_deck_tooltip_shows_municipio_and_metric_name(monkeypatch):
    monkeypatch.setenv("MAPBOX_API_KEY", "pk.test_token")
    deck = build_deck(_gdf(), "Sentimiento")
    assert "{municipio}" in deck._tooltip["text"]
    assert "Sentimiento" in deck._tooltip["text"]
    assert "{tooltip_value}" in deck._tooltip["text"]


def test_build_layer_3d_extrudes_and_includes_altitud():
    gdf = _gdf().copy()
    gdf["altitud_media_m"] = [100.0, 500.0, 1500.0]
    layer = build_layer(gdf, "Densidad hotelera", is_3d=True, elevation_scale=1.5)
    assert layer.extruded is True
    assert layer.elevation_scale == 1.5
    data_df = pd.DataFrame(layer.data) if isinstance(layer.data, list) else layer.data
    assert "altitud_m" in data_df.columns
    assert data_df["altitud_m"].tolist() == [100.0, 500.0, 1500.0]


def test_build_deck_3d_sets_pitch_and_altitude_tooltip(monkeypatch):
    monkeypatch.setenv("MAPBOX_API_KEY", "pk.test_token")
    gdf = _gdf().copy()
    gdf["altitud_media_m"] = [100.0, 500.0, 1500.0]
    deck = build_deck(gdf, "Densidad hotelera", is_3d=True, elevation_scale=1.2, pitch=55)
    assert deck.initial_view_state.pitch == 55
    assert deck.layers[0].extruded is True
    assert "Altitud MDT" in deck._tooltip["text"]


def test_build_deck_falls_back_to_carto_when_no_mapbox_token(monkeypatch):
    monkeypatch.delenv("MAPBOX_API_KEY", raising=False)
    deck = build_deck(_gdf(), "Sentimiento")
    assert deck.map_provider == "carto"
    assert deck.map_style == pdk.map_styles.CARTO_DARK


def test_legend_html_sequential_shows_gradient_with_min_max_labels():
    html = legend_html("Densidad hotelera", _gdf())
    assert "linear-gradient" in html
    assert "0" in html and "20" in html


def test_legend_html_diverging_shows_fixed_domain_labels():
    html = legend_html("Sentimiento", _gdf())
    assert "linear-gradient" in html
    assert "1" in html and "5" in html


def test_legend_html_categorical_shows_a_chip_per_category():
    html = legend_html("Restricciones legales", _gdf())
    assert "ENP" in html
    assert "Zona turística oficial" in html
    assert "Sin restricción" in html
    assert html.count("border-radius:3px") == 3


def _municipio_gdf():
    return gpd.GeoDataFrame(
        {
            "municipio": ["Adeje", "Arona", "Santa Cruz de Tenerife"],
            "plazas_por_1000_hab": [0.0, 50.0, 100.0],
            "densidad_plazas_km2": [10.0, 20.0, 30.0],
            "crec_plazas_vv_pct": [-5.0, 0.0, 15.0],
        },
        geometry=[box(0, 0, 1, 1), box(1, 0, 2, 1), box(2, 0, 3, 1)],
    )


def test_build_municipio_fill_color_column_scales_min_to_max():
    colors = build_municipio_fill_color_column(_municipio_gdf(), "Presión residencial")
    assert colors.iloc[0] == [205, 226, 251]  # light end of the blue ramp
    assert colors.iloc[2] == [13, 54, 107]  # dark end of the blue ramp


def test_build_municipio_fill_color_column_handles_null_values():
    gdf = _municipio_gdf()
    gdf.loc[0, "densidad_plazas_km2"] = None
    colors = build_municipio_fill_color_column(gdf, "Densidad turística")
    assert colors.iloc[0] == [107, 114, 128]  # NO_DATA_COLOR


def test_build_municipio_layer_returns_pickable_geojson_layer():
    layer = build_municipio_layer(_municipio_gdf(), "Densidad turística")
    assert isinstance(layer, pdk.Layer)
    assert layer.id == "municipio"
    assert layer.pickable is True
    assert layer.get_fill_color == "@@=properties.fill_color"
    assert len(layer.data["features"]) == 3


def test_build_municipio_layer_includes_municipio_and_formatted_tooltip_value():
    layer = build_municipio_layer(_municipio_gdf(), "Evolución de oferta VV")
    properties = [f["properties"] for f in layer.data["features"]]
    assert [p["municipio"] for p in properties] == ["Adeje", "Arona", "Santa Cruz de Tenerife"]
    assert properties[0]["tooltip_value"] == "-5,0"


def test_municipio_legend_html_shows_gradient_with_min_max_labels():
    html = municipio_legend_html("Densidad turística", _municipio_gdf())
    assert "linear-gradient" in html
    assert "10" in html and "30" in html


def test_build_municipio_layer_normalizes_mixed_geometry_types_to_multipolygon():
    # deck.gl's GeoJsonLayer throws inside its SolidPolygonLayer sub-layer
    # (TypeError: Cannot read properties of undefined (reading 'fill_color'))
    # when a FeatureCollection mixes Polygon and MultiPolygon features --
    # confirmed against gold_municipio_master, which has 29 Polygon + 2
    # MultiPolygon rows. Every feature must come out as MultiPolygon so the
    # layer (and therefore click-to-select) doesn't break.
    gdf = gpd.GeoDataFrame(
        {
            "municipio": ["Adeje", "San Sebastián de La Gomera"],
            "plazas_por_1000_hab": [10.0, 20.0],
            "densidad_plazas_km2": [1.0, 2.0],
            "crec_plazas_vv_pct": [0.0, 0.0],
        },
        geometry=[box(0, 0, 1, 1), MultiPolygon([box(2, 0, 3, 1), box(4, 0, 5, 1)])],
    )
    layer = build_municipio_layer(gdf, "Densidad turística")
    geometry_types = {f["geometry"]["type"] for f in layer.data["features"]}
    assert geometry_types == {"MultiPolygon"}
