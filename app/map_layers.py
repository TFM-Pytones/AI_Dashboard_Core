import json
import os
from typing import Any

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

METRICS: dict[str, dict[str, Any]] = {
    # ── Tipología Territorial y Estrategia TUI ──
    "Clústeres territoriales": {
        "column": "tipo_zona",
        "scale": "categorical",
        "unit": "Tipología HDBSCAN",
        "categories": CLUSTER_COLOR_MAP_RGB,
    },
    "Arquetipo TUI óptimo": {
        "column": "arquetipo_principal",
        "scale": "categorical",
        "unit": "Segmento de producto",
        "categories": ARCHETYPE_COLOR_MAP_RGB,
    },
    "Saturación turística": {
        "column": "eje_1_saturacion",
        "scale": "sequential",
        "ramp": SEQUENTIAL_EJE1,
        "min_max": (0.0, 1.0),
        "format": "decimal2",
        "unit": "Índice continuo (0 - 1)",
    },
    "Potencial rural y sostenible": {
        "column": "eje_2_rural_infrautilizado",
        "scale": "sequential",
        "ramp": SEQUENTIAL_EJE2,
        "min_max": (0.0, 1.0),
        "format": "decimal2",
        "unit": "Índice continuo (0 - 1)",
    },
    "Potencial turístico": {
        "column": "ptna_score",
        "scale": "sequential",
        "ramp": SEQUENTIAL_PTNA,
        "format": "decimal2",
        "unit": "Puntuación PTNA (0 - 1)",
    },
    "Índice ESG (Sostenibilidad)": {
        "column": "esg_h3_score",
        "scale": "sequential",
        "ramp": SEQUENTIAL_ESG,
        "format": "decimal",
        "unit": "Puntuación ESG (0 - 100)",
    },
    # ── Análisis de Densidad y Oferta ──
    "Densidad hotelera": {
        "column": "densidad_metric",
        "scale": "sequential",
        "ramp": SEQUENTIAL_DENSITY,
        "unit": "Plazas turísticas / km²",
    },
    "Sentimiento": {
        "column": "sentimiento_medio",
        "scale": "diverging",
        "domain": DIVERGING_SENTIMENT_DOMAIN,
        "unit": "Polaridad de reseñas (1.0 - 5.0)",
    },
    "Naturaleza (NDVI)": {
        "column": "ndvi_medio",
        "scale": "sequential",
        "ramp": SEQUENTIAL_NDVI,
        "unit": "Índice vegetación (-1 a +1)",
    },
    "Luz Nocturna (VIIRS)": {
        "column": "viirs_medio",
        "scale": "sequential",
        "ramp": SEQUENTIAL_VIIRS,
        "format": "decimal2",
        "unit": "Radiancia nW/(cm²·sr)",
    },
    "Urbanización (NDBI)": {
        "column": "ndbi_medio",
        "scale": "sequential",
        "ramp": SEQUENTIAL_NDBI,
        "format": "decimal2",
        "unit": "Índice edificación (-1 a +1)",
    },
    # ── Factores de Emplazamiento ──
    "Distancia a la costa": {
        "column": "dist_costa_km",
        "scale": "sequential",
        "ramp": SEQUENTIAL_DENSITY,
        "unit": "Kilómetros (km)",
    },
    "Puntos de interés turísticos": {
        "column": "n_pois_total",
        "scale": "sequential",
        "ramp": SEQUENTIAL_DENSITY,
        "unit": "Recursos (POIs)",
    },
    "Pendiente del terreno": {
        "column": "slope_mean",
        "scale": "sequential",
        "ramp": SEQUENTIAL_DENSITY,
        "unit": "Grados (°)",
    },
    "Restricciones legales": {
        "column": "restriction_category",
        "scale": "categorical",
        "unit": "Régimen de protección",
        "categories": {
            "Espacio Natural Protegido": RESTRICTION_ENP,
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
        "unit": "Minutos en coche",
    },
    "Distancia a hospital": {
        "column": "dist_hospital_km",
        "scale": "sequential",
        "ramp": SEQUENTIAL_DENSITY,
        "unit": "Kilómetros (km)",
    },
    "Paradas de bus cercanas": {
        "column": "n_paradas_bus_500m",
        "scale": "sequential",
        "ramp": SEQUENTIAL_DENSITY,
        "unit": "Paradas (< 500m)",
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
    ramp: tuple[str, str] = config.get("ramp", SEQUENTIAL_DENSITY)
    light_hex, dark_hex = ramp
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


def _tooltip_value_column(gdf: pd.DataFrame, config: dict[str, Any]) -> pd.Series:
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
    tooltip: dict | None = None,
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
    effective_tooltip = tooltip if tooltip is not None else {"text": tooltip_text}

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
        tooltip=effective_tooltip,
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
    unit_str = config.get("unit", "")
    unit_badge = (
        f'<div style="font-size:0.8rem;color:#94a3b8;margin-bottom:6px;">Unidad: <b style="color:#e2e8f0;">{unit_str}</b></div>'
        if unit_str
        else ""
    )

    if scale == "categorical":
        col = config.get("column")
        present_values = set(gdf[col].dropna().astype(str).unique()) if (col and col in gdf.columns) else None
        chips = []
        for label, color in config.get("categories", {}).items():
            if present_values is not None and label not in present_values:
                continue
            color_css = _format_legend_color(color)
            chips.append(
                '<span style="display:inline-flex;align-items:center;gap:6px;margin-right:16px;">'
                f'<span style="width:12px;height:12px;border-radius:3px;background:{color_css};'
                f'display:inline-block;"></span>{label}</span>'
            )
        return f'{unit_badge}<div style="font-size:0.85rem;padding:2px 0 10px;">{"".join(chips)}</div>'

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
        return unit_badge + _gradient_bar_html(gradient, format_metric(vmin, "decimal"), format_metric(vmax, "decimal"))

    # Sequential scale
    ramp: tuple[str, str] = config.get("ramp", SEQUENTIAL_DENSITY)
    light_hex, dark_hex = ramp
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
    return unit_badge + _gradient_bar_html(gradient, format_metric(vmin, kind), format_metric(vmax, kind))


# ── Capa coroplética municipal ampliada (gold_municipio_master) ──
MUNICIPIO_METRICS: dict[str, dict[str, Any]] = {
    "Presión residencial": {
        "column": "plazas_por_1000_hab",
        "unit": "Plazas turísticas / 1.000 hab",
        "format": "decimal",
    },
    "Densidad turística": {
        "column": "densidad_plazas_km2",
        "unit": "Plazas turísticas / km²",
        "format": "decimal",
    },
    "Evolución de oferta VV": {
        "column": "crec_plazas_vv_pct",
        "unit": "Variación porcentual (%)",
        "format": "pct",
    },
    "Población total": {
        "column": "poblacion_actual",
        "unit": "Habitantes empadronados",
        "format": "entero",
    },
    "Empleo total registrado": {
        "column": "empleo_total_actual",
        "unit": "Afiliados a la Seguridad Social",
        "format": "entero",
    },
    "Dependencia del turismo (% hostelería)": {
        "column": "pct_dependencia_hosteleria",
        "unit": "% afiliados en hostelería",
        "format": "pct",
    },
    "Ingresos vivienda vacacional": {
        "column": "ingresos_vv_actual",
        "unit": "Euros mensuales estimados",
        "format": "euro",
    },
    "Ocupación vivienda vacacional": {
        "column": "tasa_ocupacion_vv_actual",
        "unit": "Tasa de ocupación (%)",
        "format": "pct",
    },
    "Superficie protegida (ENP)": {
        "column": "pct_area_enp_medio",
        "unit": "% territorio en Espacio Protegido",
        "format": "pct",
    },
    "Plazas turísticas oficiales": {
        "column": "n_plazas_registro",
        "unit": "Plazas oficiales registradas",
        "format": "entero",
    },
    "Recursos turísticos y culturales (POIs)": {
        "column": "n_pois_total",
        "unit": "Puntos de interés catalogados",
        "format": "entero",
    },
    "Reputación hotelera (Booking)": {
        "column": "rating_booking_medio",
        "unit": "Puntuación media (1 a 10)",
        "format": "decimal",
    },
}


def build_municipio_fill_color_column(gdf: pd.DataFrame, metric_key: str) -> pd.Series:
    config = MUNICIPIO_METRICS[metric_key]
    column = config["column"]
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
    config = MUNICIPIO_METRICS[metric_key]
    column = config["column"]
    kind = config.get("format", "decimal")
    unit = config.get("unit", "")
    gdf = gdf.copy()
    gdf["fill_color"] = build_municipio_fill_color_column(gdf, metric_key)
    gdf["tooltip_value"] = gdf[column].apply(
        lambda v: "Sin datos" if pd.isna(v) else f"{format_metric(v, kind)} ({unit})"
    )
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
    config = MUNICIPIO_METRICS[metric_key]
    column = config["column"]
    unit_str = config.get("unit", "")
    kind = config.get("format", "decimal")
    light_hex, dark_hex = SEQUENTIAL_DENSITY
    values = gdf[column].dropna()
    vmin = float(values.min()) if not values.empty else 0.0
    vmax = float(values.max()) if not values.empty else 1.0
    gradient = f"linear-gradient(to right, {light_hex}, {dark_hex})"
    unit_badge = (
        f'<div style="font-size:0.8rem;color:#94a3b8;margin-bottom:6px;">Unidad: <b style="color:#e2e8f0;">{unit_str}</b></div>'
        if unit_str
        else ""
    )
    return unit_badge + _gradient_bar_html(gradient, format_metric(vmin, kind), format_metric(vmax, kind))


# ── Isócronas de transporte (gold.isocronas_visuales) ──
ISOCRONAS_DESTINOS_INFO: dict[str, dict[str, Any]] = {
    "anaga": {
        "label": "Parque Rural de Anaga",
        "coords": [-16.1573, 28.5660],
    },
    "extremo_norte": {
        "label": "Extremo Norte Tenerife (Puerto de la Cruz)",
        "coords": [-16.5488, 28.4148],
    },
    "extremo_sur": {
        "label": "Extremo Sur Tenerife (Costa Adeje)",
        "coords": [-16.7356, 28.0805],
    },
    "tfn": {
        "label": "Aeropuerto Tenerife Norte (TFN)",
        "coords": [-16.3413, 28.4827],
    },
    "tfs": {
        "label": "Aeropuerto Tenerife Sur (TFS)",
        "coords": [-16.5726, 28.0445],
    },
    "capital": {
        "label": "Santa Cruz de Tenerife (Puerto)",
        "coords": [-16.2519, 28.4700],
    },
    "teide": {
        "label": "Teleférico del Teide (Base)",
        "coords": [-16.6214, 28.2547],
    },
    "la_laguna": {
        "label": "San Cristóbal de La Laguna (Patrimonio UNESCO)",
        "coords": [-16.3155, 28.4871],
    },
    "candelaria": {
        "label": "Basílica de Candelaria",
        "coords": [-16.3683, 28.3516],
    },
    "los_gigantes": {
        "label": "Acantilados de Los Gigantes",
        "coords": [-16.8415, 28.2435],
    },
    "el_medano": {
        "label": "El Médano (Playa y Surf)",
        "coords": [-16.5366, 28.0461],
    },
    "garachico": {
        "label": "Garachico (Casco Histórico)",
        "coords": [-16.7645, 28.3734],
    },
    "masca": {
        "label": "Caserío de Masca (Parque Rural de Teno)",
        "coords": [-16.8344, 28.3197],
    },
    "la_orotava": {
        "label": "La Orotava (Valle Norte)",
        "coords": [-16.5227, 28.3903],
    },
    "vilaflor": {
        "label": "Vilaflor de Chasna",
        "coords": [-16.6377, 28.1582],
    },
    "guimar": {
        "label": "Pirámides de Güímar",
        "coords": [-16.4088, 28.3078],
    },
    "buenavista": {
        "label": "Buenavista del Norte (Teno)",
        "coords": [-16.8897, 28.3722],
    },
    "arico": {
        "label": "Porís de Abona / Arico",
        "coords": [-16.4648, 28.1655],
    },
}

ISOCRONA_DOMAIN_MIN = 15.0
ISOCRONA_DOMAIN_MAX = 60.0


def list_destinos(isocronas_gdf: pd.DataFrame) -> list[str]:
    return sorted(isocronas_gdf["destino"].dropna().unique().tolist())


def build_isocronas_fill_color(rangos: pd.Series) -> pd.Series:
    light_hex, dark_hex = SEQUENTIAL_DENSITY
    return rangos.apply(
        lambda v: sequential_color(-v, -ISOCRONA_DOMAIN_MAX, -ISOCRONA_DOMAIN_MIN, light_hex, dark_hex)
    )


def build_isocronas_layer(isocronas_gdf: pd.DataFrame, destinos: list[str] | str) -> pdk.Layer:
    target_destinos = [destinos] if isinstance(destinos, str) else list(destinos)
    subset = isocronas_gdf[isocronas_gdf["destino"].isin(target_destinos)].copy()
    subset["fill_color"] = build_isocronas_fill_color(subset["rango_min"])
    subset["destino_nombre"] = subset["destino"].apply(
        lambda d: ISOCRONAS_DESTINOS_INFO.get(d, {}).get("label", d)
    )
    geojson = json.loads(subset[["destino", "destino_nombre", "rango_min", "fill_color", "geometry"]].to_json())
    return pdk.Layer(
        "GeoJsonLayer",
        id="isocronas",
        data=geojson,
        pickable=True,
        stroked=True,
        filled=True,
        get_fill_color="properties.fill_color",
        get_line_color=[255, 255, 255, 140],
        line_width_min_pixels=1,
        opacity=0.42,
    )


def build_isocronas_origen_pins_layer(destinos: list[str] | str) -> pdk.Layer:
    target_destinos = [destinos] if isinstance(destinos, str) else list(destinos)
    pins_data = []
    for d in target_destinos:
        if d in ISOCRONAS_DESTINOS_INFO:
            info = ISOCRONAS_DESTINOS_INFO[d]
            pins_data.append({
                "destino": d,
                "label": info["label"],
                "coordinates": info["coords"],
            })
    pins_df = pd.DataFrame(pins_data)
    return pdk.Layer(
        "ScatterplotLayer",
        id="isocronas_pins",
        data=pins_df,
        pickable=True,
        opacity=1.0,
        stroked=True,
        filled=True,
        radius_scale=1,
        radius_min_pixels=8,
        radius_max_pixels=16,
        line_width_min_pixels=2.5,
        get_position="coordinates",
        get_radius=350,
        get_fill_color=[239, 68, 68, 255],  # Rojo pin distintivo
        get_line_color=[255, 255, 255, 255],
    )


def build_isocronas_pins_labels_layer(destinos: list[str] | str) -> pdk.Layer:
    target_destinos = [destinos] if isinstance(destinos, str) else list(destinos)
    pins_data = []
    for d in target_destinos:
        if d in ISOCRONAS_DESTINOS_INFO:
            info = ISOCRONAS_DESTINOS_INFO[d]
            pins_data.append({
                "label": f"📍 {info['label']}",
                "coordinates": info["coords"],
            })
    pins_df = pd.DataFrame(pins_data)
    return pdk.Layer(
        "TextLayer",
        id="isocronas_labels",
        data=pins_df,
        pickable=False,
        get_position="coordinates",
        get_text="label",
        get_size=12,
        get_color=[255, 255, 255, 255],
        get_angle=0,
        get_text_anchor="'start'",
        get_alignment_baseline="'center'",
        get_pixel_offset=[14, 0],
        background=True,
        get_background_color=[15, 23, 42, 210],
    )


def isocronas_legend_html() -> str:
    light_hex, dark_hex = SEQUENTIAL_DENSITY
    gradient = f"linear-gradient(to right, {dark_hex}, {light_hex})"
    return (
        '<div style="font-size:0.8rem;color:#94a3b8;margin-bottom:6px;">Unidad: <b style="color:#e2e8f0;">Tiempo de conducción (minutos)</b></div>'
        + _gradient_bar_html(gradient, "≤ 15 min (zona inmediata)", "60 min (periferia)")
    )


# ── Capas Vectoriales de Apoyo Insular ──

def build_gtfs_rutas_layer(gtfs_gdf: pd.DataFrame, opacity: float = 0.85) -> pdk.Layer:
    gdf = gtfs_gdf.copy()
    geojson = json.loads(gdf[["shape_id", "route_short_name", "route_long_name", "operador", "geometry"]].to_json())
    return pdk.Layer(
        "GeoJsonLayer",
        id="gtfs_rutas",
        data=geojson,
        pickable=True,
        stroked=True,
        filled=False,
        get_line_color=[14, 165, 233, 230],  # Azul celeste vibrante
        line_width_min_pixels=2,
        opacity=opacity,
    )


def gtfs_legend_html() -> str:
    return (
        '<div style="font-size:0.85rem;padding:4px 0 10px;color:#cbd5e1;">'
        '<div style="font-size:0.8rem;color:#94a3b8;margin-bottom:6px;">Unidad: <b style="color:#e2e8f0;">Trazado geográfico de líneas de transporte</b></div>'
        '<span style="display:inline-flex;align-items:center;gap:8px;">'
        '<span style="width:24px;height:4px;background:#0ea5e9;display:inline-block;border-radius:2px;"></span>'
        '<span>Rutas regulares TITSA & Metropolitano de Tenerife</span></span>'
        '</div>'
    )


def build_bic_layer(bic_gdf: pd.DataFrame, opacity: float = 0.55) -> pdk.Layer:
    gdf = bic_gdf.copy()
    gdf["geometry"] = gdf["geometry"].apply(_as_multipolygon)
    geojson = json.loads(gdf[["id", "nombre", "tipo", "municipio", "geometry"]].to_json())
    return pdk.Layer(
        "GeoJsonLayer",
        id="bic",
        data=geojson,
        pickable=True,
        stroked=True,
        filled=True,
        get_fill_color=[245, 158, 11, 150],  # Ámbar patrimonio
        get_line_color=[217, 119, 6, 255],
        line_width_min_pixels=2,
        opacity=opacity,
    )


def bic_legend_html() -> str:
    return (
        '<div style="font-size:0.85rem;padding:4px 0 10px;color:#cbd5e1;">'
        '<div style="font-size:0.8rem;color:#94a3b8;margin-bottom:6px;">Unidad: <b style="color:#e2e8f0;">Recintos protegidos de Interés Cultural</b></div>'
        '<span style="display:inline-flex;align-items:center;gap:8px;">'
        '<span style="width:14px;height:14px;background:rgba(245,158,11,0.65);border:1.5px solid #d97706;display:inline-block;border-radius:3px;"></span>'
        '<span>Bienes de Interés Cultural (Gobierno de Canarias / Cabildo)</span></span>'
        '</div>'
    )


def build_estaciones_agrocabildo_layer(estaciones_gdf: pd.DataFrame) -> pdk.Layer:
    gdf = estaciones_gdf.copy()
    if "latitud" in gdf.columns and "longitud" in gdf.columns:
        gdf["lon"] = gdf["longitud"].astype(float)
        gdf["lat"] = gdf["latitud"].astype(float)
    else:
        gdf["lon"] = gdf.geometry.x
        gdf["lat"] = gdf.geometry.y

    gdf["coordinates"] = gdf.apply(lambda r: [r["lon"], r["lat"]], axis=1)
    return pdk.Layer(
        "ScatterplotLayer",
        id="estaciones_agrocabildo",
        data=gdf[["id_estacion", "nombre_estacion", "municipio", "altitud_m", "coordinates"]],
        pickable=True,
        opacity=0.9,
        stroked=True,
        filled=True,
        radius_scale=1,
        radius_min_pixels=6,
        radius_max_pixels=14,
        line_width_min_pixels=2,
        get_position="coordinates",
        get_radius=250,
        get_fill_color=[16, 185, 129, 230],  # Verde esmeralda agroclimático
        get_line_color=[255, 255, 255, 255],
    )


def estaciones_legend_html() -> str:
    return (
        '<div style="font-size:0.85rem;padding:4px 0 10px;color:#cbd5e1;">'
        '<div style="font-size:0.8rem;color:#94a3b8;margin-bottom:6px;">Unidad: <b style="color:#e2e8f0;">Estación meteorológica activa</b></div>'
        '<span style="display:inline-flex;align-items:center;gap:8px;">'
        '<span style="width:12px;height:12px;border-radius:50%;background:#10b981;border:2px solid white;display:inline-block;"></span>'
        '<span>Red de estaciones agroclimáticas (Agrocabildo de Tenerife)</span></span>'
        '</div>'
    )

