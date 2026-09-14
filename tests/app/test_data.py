import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

from app.data import (
    clean_accesibilidad_sentinel,
    compute_density_metric,
    compute_restriction_category,
    drop_municipio_alias_rows,
    filter_by_municipio,
    list_municipios,
    merge_accesibilidad,
    merge_h3_data,
)


def _h3_gdf():
    return gpd.GeoDataFrame(
        {
            "h3_index": ["a", "b", "c"],
            "municipio": ["Adeje", "Arona", None],
            "n_plazas_registro": [100, 0, 0],
            "n_establecimientos_registro": [5, 3, 0],
            "pct_area_enp": [0.0, 1.0, 0.0],
            "pct_area_zona_turistica": [0.5, 0.2, 0.0],
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


def test_merge_h3_data_includes_restriction_category():
    sentimiento_df = pd.DataFrame({"h3_index": ["a"], "sentimiento_medio": [4.2]})
    merged = merge_h3_data(_h3_gdf(), sentimiento_df)
    assert merged.loc[merged["h3_index"] == "b", "restriction_category"].iloc[0] == "ENP"


def test_compute_restriction_category_defaults_to_sin_restriccion():
    result = compute_restriction_category(_h3_gdf())
    assert result.loc[result["h3_index"] == "c", "restriction_category"].iloc[0] == "Sin restricción"


def test_compute_restriction_category_marks_zona_turistica():
    result = compute_restriction_category(_h3_gdf())
    assert result.loc[result["h3_index"] == "a", "restriction_category"].iloc[0] == "Zona turística oficial"


def test_compute_restriction_category_enp_takes_priority_over_zona_turistica():
    result = compute_restriction_category(_h3_gdf())
    assert result.loc[result["h3_index"] == "b", "restriction_category"].iloc[0] == "ENP"


def test_list_municipios_returns_sorted_unique_dropping_nan():
    assert list_municipios(_h3_gdf()) == ["Adeje", "Arona"]


def test_filter_by_municipio_returns_all_when_todos_or_none():
    gdf = _h3_gdf()
    assert len(filter_by_municipio(gdf, "Todos")) == 3
    assert len(filter_by_municipio(gdf, None)) == 3


def test_filter_by_municipio_filters_matching_rows():
    result = filter_by_municipio(_h3_gdf(), "Adeje")
    assert result["h3_index"].tolist() == ["a"]


def test_clean_accesibilidad_sentinel_converts_999_to_nan():
    df = pd.DataFrame({
        "h3_index": ["a", "b"],
        "tiempo_aeropuerto_min": [999.0, 25.5],
        "tiempo_teide_min": [999.0, 40.0],
    })
    result = clean_accesibilidad_sentinel(df)
    assert pd.isna(result.loc[0, "tiempo_aeropuerto_min"])
    assert pd.isna(result.loc[0, "tiempo_teide_min"])
    assert result.loc[1, "tiempo_aeropuerto_min"] == 25.5


def test_clean_accesibilidad_sentinel_only_touches_tiempo_columns():
    df = pd.DataFrame({"h3_index": ["a"], "dist_hospital_km": [999.0], "tiempo_aeropuerto_min": [999.0]})
    result = clean_accesibilidad_sentinel(df)
    assert result.loc[0, "dist_hospital_km"] == 999.0
    assert pd.isna(result.loc[0, "tiempo_aeropuerto_min"])


def test_merge_accesibilidad_joins_on_h3_index_and_cleans_sentinel():
    gdf = pd.DataFrame({"h3_index": ["a", "b"]})
    accesibilidad_df = pd.DataFrame({"h3_index": ["a"], "tiempo_aeropuerto_min": [999.0]})
    merged = merge_accesibilidad(gdf, accesibilidad_df)
    assert pd.isna(merged.loc[merged["h3_index"] == "a", "tiempo_aeropuerto_min"].iloc[0])
    assert pd.isna(merged.loc[merged["h3_index"] == "b", "tiempo_aeropuerto_min"].iloc[0])


def test_merge_accesibilidad_drops_duplicate_dist_costa_km_from_accesibilidad():
    # gold_h3_master already has its own dist_costa_km; without dropping
    # accesibilidad's copy first, pandas would suffix both to _x/_y and
    # "dist_costa_km" would silently disappear from the merged frame.
    gdf = pd.DataFrame({"h3_index": ["a"], "dist_costa_km": [3.0]})
    accesibilidad_df = pd.DataFrame({"h3_index": ["a"], "dist_costa_km": [999.0]})
    merged = merge_accesibilidad(gdf, accesibilidad_df)
    assert "dist_costa_km" in merged.columns
    assert "dist_costa_km_x" not in merged.columns
    assert "dist_costa_km_y" not in merged.columns
    assert merged.loc[0, "dist_costa_km"] == 3.0


def test_drop_municipio_alias_rows_removes_known_aliases_only():
    df = pd.DataFrame({
        "municipio": ["Guia de Isora", "Guía de Isora", "Adeje", "Güímar"],
        "n_opiniones": [1564, 9, 100, 12],
    })
    result = drop_municipio_alias_rows(df)
    assert sorted(result["municipio"].tolist()) == ["Adeje", "Guia de Isora"]


def test_drop_municipio_alias_rows_resets_index():
    df = pd.DataFrame({"municipio": ["Guía de Isora", "Adeje"], "n_opiniones": [9, 100]})
    result = drop_municipio_alias_rows(df)
    assert result.index.tolist() == [0]
