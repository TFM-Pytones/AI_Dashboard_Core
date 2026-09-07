import json

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
    # Accesibilidad real (gold_h3_accesibilidad) -- el centinela 999 ya se
    # limpia a NaN en app.data.clean_accesibilidad_sentinel antes de llegar aquí.
    "Tiempo al aeropuerto": {
        "column": "tiempo_aeropuerto_min",
        "scale": "sequential",
        "ramp": SEQUENTIAL_DENSITY,
    },
    "Distancia a hospital": {
        "column": "dist_hospital_km",
        "scale": "sequential",
        "ramp": SEQUENTIAL_DENSITY,
    },
    "Paradas de bus cercanas": {
        "column": "n_paradas_bus_500m",
        "scale": "sequential",
        "ramp": SEQUENTIAL_DENSITY,
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


# Isócronas (gold.isocronas_visuales): un polígono por (destino, rango_min).
# Los rangos son fijos (15/30/45/60 min) -- se colorea con la misma rampa
# secuencial invirtiendo el dominio, para que el anillo más cercano (15 min)
# sea el más oscuro.
ISOCRONA_DOMAIN_MIN = 15.0
ISOCRONA_DOMAIN_MAX = 60.0


def list_destinos(isocronas_gdf: pd.DataFrame) -> list[str]:
    return sorted(isocronas_gdf["destino"].dropna().unique().tolist())


def build_isocronas_fill_color(rangos: pd.Series) -> pd.Series:
    light_hex, dark_hex = SEQUENTIAL_DENSITY
    return rangos.apply(
        lambda v: sequential_color(-v, -ISOCRONA_DOMAIN_MAX, -ISOCRONA_DOMAIN_MIN, light_hex, dark_hex)
    )


def build_isocronas_layer(isocronas_gdf, destino: str) -> pdk.Layer:
    subset = isocronas_gdf[isocronas_gdf["destino"] == destino].copy()
    subset["fill_color"] = build_isocronas_fill_color(subset["rango_min"])
    geojson = json.loads(subset.to_json())
    return pdk.Layer(
        "GeoJsonLayer",
        data=geojson,
        pickable=True,
        stroked=True,
        filled=True,
        get_fill_color="properties.fill_color",
        get_line_color=[255, 255, 255],
        line_width_min_pixels=1,
        opacity=0.45,
    )
