import pandas as pd
import pydeck as pdk

from app.color_scales import (
    DIVERGING_SENTIMENT_DOMAIN,
    RESTRICTION_ENP,
    RESTRICTION_SIN_RESTRICCION,
    RESTRICTION_ZONA_TURISTICA,
    SEQUENTIAL_DENSITY,
    SEQUENTIAL_NDVI,
    categorical_color,
    diverging_color,
    sequential_color,
)

TENERIFE_VIEW_STATE = pdk.ViewState(latitude=28.29, longitude=-16.62, zoom=9, pitch=0)

METRICS = {
    "Densidad hotelera": {
        "column": "densidad_metric",
        "scale": "sequential",
        "ramp": SEQUENTIAL_DENSITY,
    },
    "Sentimiento": {
        "column": "sentimiento_medio",
        "scale": "diverging",
        "domain": DIVERGING_SENTIMENT_DOMAIN,
    },
    "Naturaleza (NDVI)": {
        "column": "ndvi_medio",
        "scale": "sequential",
        "ramp": SEQUENTIAL_NDVI,
    },
    # Site-selection layers (alojamiento turístico): cada una es una columna
    # real de gold_h3_master, sin combinarlas en un índice/score inventado.
    "Distancia a la costa": {
        "column": "distancia_costa_metros",
        "scale": "sequential",
        "ramp": SEQUENTIAL_DENSITY,
    },
    "Puntos de interés turísticos": {
        "column": "n_pois_total",
        "scale": "sequential",
        "ramp": SEQUENTIAL_DENSITY,
    },
    "Pendiente del terreno": {
        "column": "slope_mean",
        "scale": "sequential",
        "ramp": SEQUENTIAL_DENSITY,
    },
    "Restricciones legales": {
        "column": "restriction_category",
        "scale": "categorical",
        "categories": {
            "ENP": RESTRICTION_ENP,
            "Zona turística oficial": RESTRICTION_ZONA_TURISTICA,
            "Sin restricción": RESTRICTION_SIN_RESTRICCION,
        },
    },
}


def build_fill_color_column(gdf: pd.DataFrame, metric_key: str) -> pd.Series:
    config = METRICS[metric_key]
    values = gdf[config["column"]]
    if config["scale"] == "sequential":
        light_hex, dark_hex = config["ramp"]
        non_null = values.dropna()
        vmin = float(non_null.min()) if not non_null.empty else 0.0
        vmax = float(non_null.max()) if not non_null.empty else 1.0
        return values.apply(lambda v: sequential_color(v, vmin, vmax, light_hex, dark_hex))
    if config["scale"] == "categorical":
        return values.apply(lambda v: categorical_color(v, config["categories"]))
    vmin, vmid, vmax = config["domain"]
    return values.apply(lambda v: diverging_color(v, vmin, vmid, vmax))


def build_layer(gdf: pd.DataFrame, metric_key: str) -> pdk.Layer:
    gdf = gdf.copy()
    gdf["fill_color"] = build_fill_color_column(gdf, metric_key)
    return pdk.Layer(
        "H3HexagonLayer",
        data=gdf[["h3_index", "fill_color"]],
        id="h3_index",
        pickable=True,
        stroked=True,
        filled=True,
        extruded=False,
        get_hexagon="h3_index",
        get_fill_color="fill_color",
        get_line_color=[255, 255, 255],
        line_width_min_pixels=1,
    )


def build_deck(gdf: pd.DataFrame, metric_key: str) -> pdk.Deck:
    return pdk.Deck(
        layers=[build_layer(gdf, metric_key)],
        initial_view_state=TENERIFE_VIEW_STATE,
        map_style=None,
        tooltip={"text": "Hexágono: {h3_index}"},
    )
