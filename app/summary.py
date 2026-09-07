import pandas as pd


def compute_summary_stats(gdf: pd.DataFrame) -> dict:
    total = len(gdf)
    restriction_counts = gdf["restriction_category"].value_counts().to_dict()
    oferta_por_municipio = gdf.groupby("municipio")["n_establecimientos_registro"].sum()

    return {
        "total_hexagonos": total,
        "pct_sin_restriccion": round(100 * restriction_counts.get("Sin restricción", 0) / total, 1),
        "pct_con_sentimiento": round(100 * gdf["sentimiento_medio"].notna().sum() / total, 1),
        "restriction_counts": restriction_counts,
        "n_municipios": gdf["municipio"].dropna().nunique(),
        "municipio_mas_oferta": oferta_por_municipio.idxmax() if not oferta_por_municipio.empty else None,
        "municipio_menos_oferta": oferta_por_municipio.idxmin() if not oferta_por_municipio.empty else None,
    }
