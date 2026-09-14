import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

from app.table_view import CURATED_COLUMNS, build_table_column_config, filter_table, prepare_table_view


def _gdf():
    return pd.DataFrame(
        {
            "h3_index": ["a", "b", "c"],
            "municipio": ["Adeje", "Arona", "Adeje"],
            "restriction_category": ["ENP", "Sin restricción", "Sin restricción"],
        }
    )


def test_filter_table_returns_all_when_todos_and_todas():
    result = filter_table(_gdf(), "Todos", "Todas")
    assert len(result) == 3


def test_filter_table_filters_by_municipio():
    result = filter_table(_gdf(), "Adeje", "Todas")
    assert result["h3_index"].tolist() == ["a", "c"]


def test_filter_table_filters_by_restriction():
    result = filter_table(_gdf(), "Todos", "Sin restricción")
    assert result["h3_index"].tolist() == ["b", "c"]


def test_filter_table_filters_by_both():
    result = filter_table(_gdf(), "Adeje", "Sin restricción")
    assert result["h3_index"].tolist() == ["c"]


def test_prepare_table_view_drops_geometry_column():
    gdf = gpd.GeoDataFrame(_gdf(), geometry=[Point(0, 0), Point(1, 1), Point(2, 2)])
    result = prepare_table_view(gdf, show_technical=True)
    assert "geometry" not in result.columns
    assert "h3_index" in result.columns


def test_prepare_table_view_technical_keeps_all_non_geometry_columns():
    result = prepare_table_view(_gdf(), show_technical=True)
    assert list(result.columns) == ["h3_index", "municipio", "restriction_category"]


def test_prepare_table_view_default_shows_only_curated_columns_present():
    result = prepare_table_view(_gdf())
    assert list(result.columns) == ["municipio", "restriction_category"]
    assert "h3_index" not in result.columns


def test_build_table_column_config_covers_every_curated_column():
    config = build_table_column_config()
    assert set(config.keys()) == {column for column, _, _ in CURATED_COLUMNS}


def test_build_table_column_config_uses_spanish_labels():
    config = build_table_column_config()
    assert config["municipio"]["label"] == "Municipio"
    assert config["ndvi_medio"]["label"] == "NDVI medio"


def test_build_table_column_config_technical_returns_empty():
    assert build_table_column_config(show_technical=True) == {}
