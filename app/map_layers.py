import json
import os

import pandas as pd
import pydeck as pdk
from shapely.geometry import MultiPolygon

from app.color_scales import (
    ARCHETYPE_COLOR_MAP_RGB,
    CLUSTER_COLOR_MAP_RGB,
    DIVERGING_SENTIMENT_DOMAIN,
    DIVERGING_SENTIMENT_HIGH,
    DIVERGING_SENTIMENT_LOW,
    DIVERGING_SENTIMENT_MID,
    MAP_SELECTION_HIGHLIGHT,
    RESTRICTION_ENP,
    RESTRICTION_SIN_RESTRICCION,
    RESTRICTION_ZONA_TURISTICA,
    SEQUENTIAL_DENSITY,
    SEQUENTIAL_EJE1,
    SEQUENTIAL_EJE2,
    SEQUENTIAL_ESG,
    SEQUENTIAL_NDBI,
    SEQUENTIAL_NDVI,
    SEQUENTIAL_PTNA,
    SEQUENTIAL_VIIRS,
    categorical_color,
    diverging_color,
    sequential_color,
)
from app.ui_helpers import format_metric

# min_zoom == the initial zoom: scrolling/pinching out is clamped right back
# to the Tenerife framing instead of zooming out to the rest of the world.
# (Streamlit's pydeck widget doesn't expose per-gesture controller options --
# e.g. disabling scrollZoom specifically -- so min/max zoom is the only
# reliable lever here; confirmed empirically against the rendered widget.)
TENERIFE_VIEW_STATE = pdk.ViewState(
    latitude=28.29, longitude=-16.62, zoom=9, pitch=0, min_zoom=9, max_zoom=16
)

METRICS = {
    # ── Tipología Territorial y Estrategia TUI ──
    "Tipología Territorial (Clústeres)": {
        "column": "tipo_zona",
        "scale": "categorical",
        "categories": CLUSTER_COLOR_MAP_RGB,
    },
    "Arquetipo TUI Óptimo": {
        "column": "arquetipo_principal",
        "scale": "categorical",
        "categories": ARCHETYPE_COLOR_MAP_RGB,
    },
    "Eje 1: Saturación Turística (HDBSCAN)": {
        "column": "eje_1_saturacion",
        "scale": "sequential",
        "ramp": SEQUENTIAL_EJE1,
        "min_max": (0.0, 1.0),
        "format": "decimal2",
    },
    "Eje 2: Rural Infrautilizado [0-1]": {
        "column": "eje_2_rural_infrautilizado",
        "scale": "sequential",
        "ramp": SEQUENTIAL_EJE2,
        "min_max": (0.0, 1.0),
        "format": "decimal2",
    },
    "Potencial Turístico (PTNA)": {
        "column": "ptna_score",
        "scale": "sequential",
        "ramp": SEQUENTIAL_PTNA,
        "format": "decimal2",
    },
    "Índice ESG (Sostenibilidad)": {
        "column": "esg_h3_score",
        "scale": "sequential",
        "ramp": SEQUENTIAL_ESG,
        "format": "decimal",
    },
    # ── Análisis de Densidad y Oferta ──
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
    "Luz Nocturna (VIIRS)": {
        "column": "viirs_medio",
        "scale": "sequential",
        "ramp": SEQUENTIAL_VIIRS,
        "format": "decimal2",
    },
    "Urbanización (NDBI)": {
        "column": "ndbi_medio",
        "scale": "sequential",
        "ramp": SEQUENTIAL_NDBI,
        "format": "decimal2",
    },
    # ── Factores de Emplazamiento ──
    "Distancia a la costa": {
        "column": "dist_costa_km",
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
    # ── Accesibilidad ──
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
    col = config["column"]
    values = gdf[col] if col in gdf.columns else pd.Series([None] * len(gdf), index=gdf.index)

    scale = config.get("scale", "sequential")
    if scale == "categorical":
        return values.apply(lambda v: categorical_color(v, config.get("categories", {})))

    if scale == "diverging":
        domain = config.get("domain", DIVERGING_SENTIMENT_DOMAIN)
        if len(domain) == 3:
            vmin, vmid, vmax = domain
        else:
            vmin, vmax = domain[0], domain[-1]
            vmid = (vmin + vmax) / 2.0
        return values.apply(lambda v: diverging_color(v, vmin, vmid, vmax))

    # scale == "sequential"
    light_hex, dark_hex = config.get("ramp", SEQUENTIAL_DENSITY)
    if "min_max" in config:
        vmin, vmax = config["min_max"]
    elif "domain" in config and len(config["domain"]) == 2:
        vmin, vmax = config["domain"]
    else:
        non_null = values.dropna()
        vmin = float(non_null.min()) if not non_null.empty else 0.0
        vmax = float(non_null.max()) if not non_null.empty else 1.0
    return values.apply(lambda v: sequential_color(v, vmin, vmax, light_hex, dark_hex))


DEFAULT_HEXAGON_OPACITY = 0.4


def _tooltip_value_column(gdf: pd.DataFrame, config: dict) -> pd.Series:
    col = config["column"]
    values = gdf[col] if col in gdf.columns else pd.Series([None] * len(gdf), index=gdf.index)
    if config.get("scale") == "categorical":
        return values.apply(lambda v: "Sin datos" if pd.isna(v) else str(v))
    kind = config.get("format", "decimal")
    return values.apply(lambda v: "Sin datos" if pd.isna(v) else format_metric(v, kind))


def build_layer(
    gdf: pd.DataFrame,
    metric_key: str,
    opacity: float = DEFAULT_HEXAGON_OPACITY,
    is_3d: bool = False,
    elevation_scale: float = 1.0,
    elevation_column: str = "altitud_media_m",
) -> pdk.Layer:
    config = METRICS[metric_key]
    gdf = gdf.copy()
    gdf["fill_color"] = build_fill_color_column(gdf, metric_key)
    gdf["tooltip_value"] = _tooltip_value_column(gdf, config)

    cols = ["h3_index", "municipio", "tooltip_value", "fill_color"]
    if is_3d:
        if elevation_column in gdf.columns:
            gdf["altitud_m"] = gdf[elevation_column].fillna(0.0).clip(lower=0.0)
        else:
            gdf["altitud_m"] = 0.0
        gdf["altitud_display"] = gdf["altitud_m"].apply(lambda v: f"{v:.0f} m")
        cols.extend(["altitud_m", "altitud_display"])

    return pdk.Layer(
        "H3HexagonLayer",
        data=gdf[cols],
        id="h3_index",
        pickable=True,
        stroked=True,
        filled=True,
        extruded=is_3d,
        get_elevation="altitud_m" if is_3d else 0,
        elevation_scale=elevation_scale if is_3d else 1.0,
        opacity=opacity,
        get_hexagon="h3_index",
        get_fill_color="fill_color",
        get_line_color=[255, 255, 255, 60] if is_3d else [255, 255, 255],
        line_width_min_pixels=1,
        auto_highlight=True,
    )


def build_highlight_layer(h3_index: str) -> pdk.Layer:
    # H3HexagonLayer calcula la geometría a partir del propio índice H3, así
    # que no hace falta buscar la fila/geometría del hexágono -- basta con su
    # id. Sin relleno (filled=False) para no tapar la capa de métrica de
    # color que haya debajo, solo un contorno llamativo alrededor.
    return pdk.Layer(
        "H3HexagonLayer",
        data=pd.DataFrame({"h3_index": [h3_index]}),
        pickable=False,
        stroked=True,
        filled=False,
        extruded=False,
        get_hexagon="h3_index",
        get_line_color=MAP_SELECTION_HIGHLIGHT,
        line_width_min_pixels=5,
    )


def build_deck(
    gdf: pd.DataFrame,
    metric_key: str,
    show_hexagons: bool = True,
    opacity: float = DEFAULT_HEXAGON_OPACITY,
    is_3d: bool = False,
    elevation_scale: float = 1.0,
    pitch: int = 50,
    bearing: int = -15,
) -> pdk.Deck:
    layers = (
        [
            build_layer(
                gdf,
                metric_key,
                opacity=opacity,
                is_3d=is_3d,
                elevation_scale=elevation_scale,
            )
        ]
        if show_hexagons
        else []
    )
    view_state = (
        pdk.ViewState(
            latitude=28.29,
            longitude=-16.62,
            zoom=9.3,
            min_zoom=8.5,
            max_zoom=16,
            pitch=pitch,
            bearing=bearing,
        )
        if is_3d
        else TENERIFE_VIEW_STATE
    )
    tooltip_text = (
        f"{{municipio}}\n{metric_key}: {{tooltip_value}}\nAltitud MDT: {{altitud_display}}"
        if is_3d
        else f"{{municipio}}\n{metric_key}: {{tooltip_value}}"
    )
    mapbox_token = os.environ.get("MAPBOX_API_KEY", "").strip()
    if mapbox_token:
        map_provider = "mapbox"
        map_style = "mapbox://styles/mapbox/satellite-streets-v9"
        api_keys = {"mapbox": mapbox_token}
    else:
        map_provider = "carto"
        map_style = pdk.map_styles.CARTO_DARK
        api_keys = None

    return pdk.Deck(
        layers=layers,
        initial_view_state=view_state,
        map_provider=map_provider,
        map_style=map_style,
        api_keys=api_keys,
        tooltip={"text": tooltip_text},
    )


def _gradient_bar_html(gradient_css: str, min_label: str, max_label: str) -> str:
    return (
        '<div style="font-size:0.85rem;padding:4px 0 10px;">'
        f'<div style="height:10px;border-radius:5px;background:{gradient_css};margin-bottom:4px;"></div>'
        '<div style="display:flex;justify-content:space-between;color:#6b7280;">'
        f"<span>{min_label}</span><span>{max_label}</span>"
        "</div></div>"
    )


def _format_legend_color(color) -> str:
    if isinstance(color, str):
        return color
    if isinstance(color, (list, tuple)) and len(color) >= 3:
        return f"rgb({color[0]},{color[1]},{color[2]})"
    return "#6b7280"


def legend_html(metric_key: str, gdf: pd.DataFrame) -> str:
    if metric_key not in METRICS:
        return ""
    config = METRICS[metric_key]
    scale = config.get("scale", "sequential")

    if scale == "categorical":
        chips = []
        for label, color in config.get("categories", {}).items():
            color_css = _format_legend_color(color)
            chips.append(
                '<span style="display:inline-flex;align-items:center;gap:6px;margin-right:16px;">'
                f'<span style="width:12px;height:12px;border-radius:3px;background:{color_css};'
                f'display:inline-block;"></span>{label}</span>'
            )
        return f'<div style="font-size:0.85rem;padding:4px 0 10px;">{"".join(chips)}</div>'

    if scale == "diverging":
        domain = config.get("domain", DIVERGING_SENTIMENT_DOMAIN)
        if len(domain) == 3:
            vmin, _vmid, vmax = domain
        else:
            vmin, vmax = domain[0], domain[-1]
        gradient = (
            f"linear-gradient(to right, {DIVERGING_SENTIMENT_LOW}, "
            f"{DIVERGING_SENTIMENT_MID}, {DIVERGING_SENTIMENT_HIGH})"
        )
        return _gradient_bar_html(gradient, format_metric(vmin, "decimal"), format_metric(vmax, "decimal"))

    # Sequential scale
    light_hex, dark_hex = config.get("ramp", SEQUENTIAL_DENSITY)
    kind = config.get("format", "decimal")
    if "min_max" in config:
        vmin, vmax = config["min_max"]
    elif "domain" in config and len(config["domain"]) == 2:
        vmin, vmax = config["domain"]
    else:
        col = config["column"]
        if col in gdf.columns:
            values = gdf[col].dropna()
            vmin = float(values.min()) if not values.empty else 0.0
            vmax = float(values.max()) if not values.empty else 1.0
        else:
            vmin, vmax = 0.0, 1.0

    gradient = f"linear-gradient(to right, {light_hex}, {dark_hex})"
    return _gradient_bar_html(gradient, format_metric(vmin, kind), format_metric(vmax, kind))


# Capa coroplética municipal (gold_municipio_master): un polígono por
# municipio, coloreado con la misma rampa secuencial genérica que ya usan las
# métricas de sitio (dist_costa_km, n_pois_total, etc.) en vez de inventar un
# esquema de color nuevo.
MUNICIPIO_METRICS = {
    "Presión residencial": "plazas_por_1000_hab",
    "Densidad turística": "densidad_plazas_km2",
    "Evolución de oferta VV": "crec_plazas_vv_pct",
}


def build_municipio_fill_color_column(gdf: pd.DataFrame, metric_key: str) -> pd.Series:
    column = MUNICIPIO_METRICS[metric_key]
    light_hex, dark_hex = SEQUENTIAL_DENSITY
    values = gdf[column]
    non_null = values.dropna()
    vmin = float(non_null.min()) if not non_null.empty else 0.0
    vmax = float(non_null.max()) if not non_null.empty else 1.0
    return values.apply(lambda v: sequential_color(v, vmin, vmax, light_hex, dark_hex))


def _as_multipolygon(geometry):
    if geometry is not None and geometry.geom_type == "Polygon":
        return MultiPolygon([geometry])
    return geometry


def build_municipio_layer(gdf: pd.DataFrame, metric_key: str, opacity: float = 0.45) -> pdk.Layer:
    column = MUNICIPIO_METRICS[metric_key]
    gdf = gdf.copy()
    gdf["fill_color"] = build_municipio_fill_color_column(gdf, metric_key)
    gdf["tooltip_value"] = gdf[column].apply(
        lambda v: "Sin datos" if pd.isna(v) else format_metric(v, "decimal")
    )
    # deck.gl's GeoJsonLayer throws inside its SolidPolygonLayer sub-layer
    # when a FeatureCollection mixes Polygon and MultiPolygon features --
    # gold_municipio_master has both, so every geometry is normalized to
    # MultiPolygon before serializing.
    gdf["geometry"] = gdf["geometry"].apply(_as_multipolygon)
    geojson = json.loads(gdf[["municipio", "tooltip_value", "fill_color", "geometry"]].to_json())
    return pdk.Layer(
        "GeoJsonLayer",
        id="municipio",
        data=geojson,
        pickable=True,
        stroked=True,
        filled=True,
        get_fill_color="properties.fill_color",
        get_line_color=[255, 255, 255],
        line_width_min_pixels=2,
        opacity=opacity,
    )


def municipio_legend_html(metric_key: str, gdf: pd.DataFrame) -> str:
    column = MUNICIPIO_METRICS[metric_key]
    light_hex, dark_hex = SEQUENTIAL_DENSITY
    values = gdf[column].dropna()
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
