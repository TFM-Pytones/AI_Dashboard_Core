import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

from app.table_view import (
    CURATED_COLUMNS,
    build_column_glossary,
    build_table_column_config,
    filter_table,
    prepare_table_view,
)


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
    assert set(config.keys()) == {column for column, _, _, _ in CURATED_COLUMNS}


def test_build_table_column_config_uses_spanish_labels():
    config = build_table_column_config()
    assert config["municipio"]["label"] == "Municipio"
    assert config["ndvi_medio"]["label"] == "NDVI medio"


def test_build_table_column_config_technical_returns_empty():
    assert build_table_column_config(show_technical=True) == {}


def test_prepare_table_view_shows_dash_instead_of_none_for_missing_ratings():
    # Bug real detectado en pruebas manuales: st.dataframe con NumberColumn
    # muestra el texto literal "None" para valores nulos (la mayoria de
    # hexagonos no tienen rating porque no tienen alojamiento con presencia
    # en Booking/TripAdvisor -- es un dato real ausente, no un error). Se
    # sustituye por "-" para que sea legible.
    gdf = pd.DataFrame(
        {
            "municipio": ["Adeje", "Arona"],
            "restriction_category": ["ENP", "Sin restricción"],
            "rating_booking_medio": [9.2, None],
            "rating_tripadvisor_medio": [None, 3.5],
        }
    )
    result = prepare_table_view(gdf)
    assert result["rating_booking_medio"].tolist() == ["9,2", "—"]
    assert result["rating_tripadvisor_medio"].tolist() == ["—", "3,5"]


def test_prepare_table_view_shows_dash_instead_of_none_for_missing_queja_principal():
    # Mismo bug que con los ratings, pero en una columna de texto
    # (queja_principal): TextColumn tambien muestra "None" en crudo para
    # los huecos, no solo NumberColumn.
    gdf = pd.DataFrame(
        {
            "municipio": ["Adeje", "Arona"],
            "restriction_category": ["ENP", "Sin restricción"],
            "queja_principal": ["ruido", None],
        }
    )
    result = prepare_table_view(gdf)
    assert result["queja_principal"].tolist() == ["ruido", "—"]


def test_build_table_column_config_uses_text_column_for_sparse_ratings():
    config = build_table_column_config()
    assert config["rating_booking_medio"]["type_config"]["type"] == "text"


def test_build_column_glossary_covers_every_curated_column_by_label():
    glossary = build_column_glossary()
    assert glossary["NDVI medio"] == (
        "Índice de vegetación medio por satélite, de 0 (sin vegetación) a 1 (vegetación densa)."
    )
    for _, label, _, _ in CURATED_COLUMNS:
        assert label in glossary


def test_build_column_glossary_also_covers_technical_columns():
    glossary = build_column_glossary()
    assert "h3_index" in glossary
    assert "dist_costa_km" in glossary
    assert "tiempo_aeropuerto_min" in glossary


def test_prepare_table_view_drops_columns_that_are_entirely_missing():
    # Bug real: gold_sentimiento_h3 no existe en la BD, asi que
    # sentimiento_medio/queja_principal salen siempre a None para todas las
    # filas -- no aporta nada mostrar una columna sin ni un solo dato.
    gdf = pd.DataFrame(
        {
            "municipio": ["Adeje", "Arona"],
            "restriction_category": ["ENP", "Sin restricción"],
            "sentimiento_medio": [None, None],
            "rating_booking_medio": [9.2, None],
        }
    )
    result = prepare_table_view(gdf)
    assert "sentimiento_medio" not in result.columns
    assert "rating_booking_medio" in result.columns


def test_build_table_column_config_excludes_entirely_missing_columns():
    gdf = pd.DataFrame(
        {
            "municipio": ["Adeje", "Arona"],
            "restriction_category": ["ENP", "Sin restricción"],
            "sentimiento_medio": [None, None],
        }
    )
    config = build_table_column_config(gdf=gdf)
    assert "sentimiento_medio" not in config
