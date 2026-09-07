import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

from app.table_view import filter_table, prepare_table_view


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
    result = prepare_table_view(gdf)
    assert "geometry" not in result.columns
    assert "h3_index" in result.columns


def test_prepare_table_view_is_noop_without_geometry():
    result = prepare_table_view(_gdf())
    assert list(result.columns) == ["h3_index", "municipio", "restriction_category"]
