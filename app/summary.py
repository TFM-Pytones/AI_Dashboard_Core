import pandas as pd


def restriction_counts_dataframe(counts: dict, metric_col_name: str = "n_hexagonos") -> pd.DataFrame:
    return pd.DataFrame(
        {
            "restriction_category": list(counts.keys()),
            metric_col_name: list(counts.values()),
        }
    ).sort_values(metric_col_name, ascending=False)


def compute_summary_stats(gdf: pd.DataFrame) -> dict:
    total = len(gdf)
    cat_series = gdf["restriction_category"].replace({"ENP": "Espacio Natural Protegido"})
    restriction_counts = cat_series.value_counts().to_dict()
    
    # Superficie real en km2 por restricción
    area_col = "area_km2" if "area_km2" in gdf.columns else None
    if area_col:
        restriction_areas = gdf.groupby(cat_series)["area_km2"].sum().round(1).to_dict()
    else:
        # Fallback a área media de celda H3 res 8 (~0.737 km2)
        restriction_areas = {k: round(v * 0.737, 1) for k, v in restriction_counts.items()}

    oferta_por_municipio = gdf.groupby("municipio")["n_establecimientos_registro"].sum()

    return {
        "total_hexagonos": total,
        "pct_sin_restriccion": round(100 * restriction_counts.get("Sin restricción", 0) / total, 1),
        "pct_con_sentimiento": round(100 * gdf["sentimiento_medio"].notna().sum() / total, 1),
        "restriction_counts": restriction_counts,
        "restriction_areas": restriction_areas,
        "n_municipios": gdf["municipio"].dropna().nunique(),
        "municipio_mas_oferta": oferta_por_municipio.idxmax() if not oferta_por_municipio.empty else None,
        "municipio_menos_oferta": oferta_por_municipio.idxmin() if not oferta_por_municipio.empty else None,
    }
