import json
import os

import pandas as pd
import pydeck as pdk

from app.color_scales import (
    DIVERGING_SENTIMENT_DOMAIN,
    DIVERGING_SENTIMENT_HIGH,
    DIVERGING_SENTIMENT_LOW,
    DIVERGING_SENTIMENT_MID,
    RESTRICTION_ENP,
    RESTRICTION_SIN_RESTRICCION,
    RESTRICTION_ZONA_TURISTICA,
    SEQUENTIAL_DENSITY,
    SEQUENTIAL_NDVI,
    categorical_color,
    diverging_color,
    sequential_color,
)
from app.ui_helpers import format_metric

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


DEFAULT_HEXAGON_OPACITY = 0.4


def _tooltip_value_column(gdf: pd.DataFrame, config: dict) -> pd.Series:
    values = gdf[config["column"]]
    if config["scale"] == "categorical":
        return values.apply(lambda v: "Sin datos" if pd.isna(v) else str(v))
    return values.apply(lambda v: "Sin datos" if pd.isna(v) else format_metric(v, "decimal"))


def build_layer(gdf: pd.DataFrame, metric_key: str, opacity: float = DEFAULT_HEXAGON_OPACITY) -> pdk.Layer:
    config = METRICS[metric_key]
    gdf = gdf.copy()
    gdf["fill_color"] = build_fill_color_column(gdf, metric_key)
    gdf["tooltip_value"] = _tooltip_value_column(gdf, config)
    return pdk.Layer(
        "H3HexagonLayer",
        data=gdf[["h3_index", "municipio", "tooltip_value", "fill_color"]],
        id="h3_index",
        pickable=True,
        stroked=True,
        filled=True,
        extruded=False,
        opacity=opacity,
        get_hexagon="h3_index",
        get_fill_color="fill_color",
        get_line_color=[255, 255, 255],
        line_width_min_pixels=1,
    )


def build_deck(
    gdf: pd.DataFrame,
    metric_key: str,
    show_hexagons: bool = True,
    opacity: float = DEFAULT_HEXAGON_OPACITY,
) -> pdk.Deck:
    layers = [build_layer(gdf, metric_key, opacity=opacity)] if show_hexagons else []
    return pdk.Deck(
        layers=layers,
        initial_view_state=TENERIFE_VIEW_STATE,
        map_provider="mapbox",
        map_style="mapbox://styles/mapbox/satellite-streets-v9",
        api_keys={"mapbox": os.environ["MAPBOX_API_KEY"]},
        tooltip={"text": f"{{municipio}}\n{metric_key}: {{tooltip_value}}"},
    )


def _gradient_bar_html(gradient_css: str, min_label: str, max_label: str) -> str:
    return (
        '<div style="font-size:0.85rem;padding:4px 0 10px;">'
        f'<div style="height:10px;border-radius:5px;background:{gradient_css};margin-bottom:4px;"></div>'
        '<div style="display:flex;justify-content:space-between;color:#6b7280;">'
        f"<span>{min_label}</span><span>{max_label}</span>"
        "</div></div>"
    )


def legend_html(metric_key: str, gdf: pd.DataFrame) -> str:
    config = METRICS[metric_key]

    if config["scale"] == "categorical":
        chips = "".join(
            '<span style="display:inline-flex;align-items:center;gap:6px;margin-right:16px;">'
            f'<span style="width:12px;height:12px;border-radius:3px;background:rgb({r},{g},{b});'
            f'display:inline-block;"></span>{label}</span>'
            for label, (r, g, b) in config["categories"].items()
        )
        return f'<div style="font-size:0.85rem;padding:4px 0 10px;">{chips}</div>'

    if config["scale"] == "diverging":
        vmin, _vmid, vmax = config["domain"]
        gradient = (
            f"linear-gradient(to right, {DIVERGING_SENTIMENT_LOW}, "
            f"{DIVERGING_SENTIMENT_MID}, {DIVERGING_SENTIMENT_HIGH})"
        )
        return _gradient_bar_html(gradient, format_metric(vmin, "decimal"), format_metric(vmax, "decimal"))

    light_hex, dark_hex = config["ramp"]
    values = gdf[config["column"]].dropna()
    vmin = float(values.min()) if not values.empty else 0.0
    vmax = float(values.max()) if not values.empty else 1.0
    gradient = f"linear-gradient(to right, {light_hex}, {dark_hex})"
    return _gradient_bar_html(gradient, format_metric(vmin, "decimal"), format_metric(vmax, "decimal"))


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
