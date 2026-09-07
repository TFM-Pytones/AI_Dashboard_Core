import pandas as pd

from app.data import filter_by_municipio


def filter_table(gdf: pd.DataFrame, municipio: str | None, restriction: str | None) -> pd.DataFrame:
    result = filter_by_municipio(gdf, municipio)
    if restriction and restriction != "Todas":
        result = result[result["restriction_category"] == restriction]
    return result


def prepare_table_view(gdf: pd.DataFrame) -> pd.DataFrame:
    return gdf.drop(columns=["geometry"], errors="ignore")
