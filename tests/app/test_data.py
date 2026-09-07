import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

from app.data import (
    compute_density_metric,
    filter_by_municipio,
    list_municipios,
    merge_h3_data,
)


def _h3_gdf():
    return gpd.GeoDataFrame(
        {
            "h3_index": ["a", "b", "c"],
            "municipio": ["Adeje", "Arona", None],
            "n_plazas_registro": [100, 0, 0],
            "n_establecimientos_registro": [5, 3, 0],
        },
        geometry=[Point(0, 0), Point(1, 1), Point(2, 2)],
    )


def test_compute_density_metric_uses_plazas_when_positive():
    result = compute_density_metric(_h3_gdf())
    assert result.loc[result["h3_index"] == "a", "densidad_metric"].iloc[0] == 100


def test_compute_density_metric_falls_back_to_establecimientos_when_plazas_zero():
    result = compute_density_metric(_h3_gdf())
    assert result.loc[result["h3_index"] == "b", "densidad_metric"].iloc[0] == 3


def test_merge_h3_data_joins_on_h3_index_and_keeps_unmatched_rows():
    sentimiento_df = pd.DataFrame({"h3_index": ["a"], "sentimiento_medio": [4.2]})
    merged = merge_h3_data(_h3_gdf(), sentimiento_df)
    assert merged.loc[merged["h3_index"] == "a", "sentimiento_medio"].iloc[0] == 4.2
    assert pd.isna(merged.loc[merged["h3_index"] == "b", "sentimiento_medio"].iloc[0])
    assert "densidad_metric" in merged.columns


def test_list_municipios_returns_sorted_unique_dropping_nan():
    assert list_municipios(_h3_gdf()) == ["Adeje", "Arona"]


def test_filter_by_municipio_returns_all_when_todos_or_none():
    gdf = _h3_gdf()
    assert len(filter_by_municipio(gdf, "Todos")) == 3
    assert len(filter_by_municipio(gdf, None)) == 3


def test_filter_by_municipio_filters_matching_rows():
    result = filter_by_municipio(_h3_gdf(), "Adeje")
    assert result["h3_index"].tolist() == ["a"]
