NO_DATA_COLOR = [107, 114, 128]  # #6b7280 -- cool muted gray (Financial Professional theme)

# Sequential ramps: (light_hex, dark_hex). Blue = dataviz skill's default
# sequential hue (ramp steps 100 -> 700). NDVI reuses the next categorical
# slot's hue (orange), tinted 85% toward the chart surface for its light end.
SEQUENTIAL_DENSITY = ("#cde2fb", "#0d366b")
SEQUENTIAL_NDVI = ("#f9e6dd", "#eb6834")
SEQUENTIAL_TEAL = ("#a5f3fc", "#0e7490")  # travel-time charts (detail panel destinos)

# Diverging pair: blue <-> red poles, neutral gray midpoint (dataviz skill).
# Domain matches the 1-5 star scale of the nlptown multilingual BERT model.
DIVERGING_SENTIMENT_LOW = "#e34948"
DIVERGING_SENTIMENT_MID = "#f3f4f6"
DIVERGING_SENTIMENT_HIGH = "#1e3a8a"
DIVERGING_SENTIMENT_DOMAIN = (1.0, 3.0, 5.0)

# Restriction categories (site-selection view): a legal blocker (ENP) vs. a
# clear hexagon uses the reserved status pair (critical/good); the official
# touristic zone is pure identity, so it gets a categorical slot (blue).
RESTRICTION_ENP = [208, 59, 59]  # #d03b3b -- status critical
RESTRICTION_ZONA_TURISTICA = [30, 58, 138]  # #1e3a8a -- categorical slot 1 (navy)
RESTRICTION_SIN_RESTRICCION = [12, 163, 12]  # #0ca30c -- status good
RESTRICTION_COLOR_MAP_HEX = {
    "Espacio Natural Protegido": "#d03b3b",
    "ENP": "#d03b3b",
    "Zona turística oficial": "#1e3a8a",
    "Sin restricción": "#0ca30c",
}

# Clústeres territoriales (gold.h3_clusters): 6 tipologías oficiales HDBSCAN (V1)
CLUSTER_COLOR_MAP_HEX = {
    "Espacio Natural / Teide y Cumbre": "#475569",          # Pizarra / volcánico Teide
    "Espacios Rurales Protegidos (Anaga/Teno)": "#15803d",    # Verde bosque frondoso
    "Rural Agrícola / Medianías Norte": "#84cc16",          # Verde lima / huerta
    "Transición Costera y Medianías": "#f59e0b",            # Ámbar / transición conector
    "Saturado / Overtourism": "#ef4444",                    # Rojo intenso / masificación
    "Urbano Residencial": "#3b82f6",                        # Azul metropolitano residencial
}
CLUSTER_COLOR_MAP_RGB = {
    "Espacio Natural / Teide y Cumbre": [71, 85, 105],
    "Espacios Rurales Protegidos (Anaga/Teno)": [21, 128, 61],
    "Rural Agrícola / Medianías Norte": [132, 204, 22],
    "Transición Costera y Medianías": [245, 158, 11],
    "Saturado / Overtourism": [239, 68, 68],
    "Urbano Residencial": [59, 130, 246],
}

# Arquetipos de producto turístico TUI
ARCHETYPE_COLOR_MAP_HEX = {
    "🏖️ Sol y Playa": "#0284c7",
    "🌿 Ecoturismo Rural": "#16a34a",
    "🏛️ Cultural y Patrimonial": "#7c3aed",
    "🏔️ Aventura y Activo": "#ea580c",
    "🧘 Bienestar y Salud": "#0d9488",
}
ARCHETYPE_COLOR_MAP_RGB = {
    "🏖️ Sol y Playa": [2, 132, 199],
    "🌿 Ecoturismo Rural": [22, 163, 74],
    "🏛️ Cultural y Patrimonial": [124, 58, 237],
    "🏔️ Aventura y Activo": [234, 88, 12],
    "🧘 Bienestar y Salud": [13, 148, 136],
}

# Rampas secuenciales para ejes continuos y métricas satelitales
SEQUENTIAL_EJE1 = ("#fef3c7", "#b45309")  # Ámbar suave a naranja/rojo quemado (Saturación continua)
SEQUENTIAL_EJE2 = ("#d1fae5", "#047857")  # Verde menta a esmeralda profundo (Rural infrautilizado)
SEQUENTIAL_PTNA = ("#e0f2fe", "#0369a1")  # Azul celeste a cobalto (Potencial turístico)
SEQUENTIAL_ESG = ("#ecfdf5", "#065f46")   # Verde claro a bosque profundo (Score ESG)
SEQUENTIAL_VIIRS = ("#f3e8ff", "#6b21a8") # Púrpura suave a violeta eléctrico (Luz nocturna)
SEQUENTIAL_NDBI = ("#ffedd5", "#c2410c")  # Melocotón a terracota (Urbanización NDBI)

# Per-section accent colors (hex, for Plotly charts) -- every tab used the
# same navy for every chart regardless of what it showed. Each section gets
# its own fixed hue instead, so color carries which part of the dashboard
# you're in rather than being decorative.
ACCENT_MUNICIPIOS = "#1e3a8a"  # navy -- institutional/economy (unchanged, the "home" accent)
ACCENT_TURISMO = "#0891b2"  # teal -- travel/ocean
ACCENT_TURISMO_AEREO = "#d97706"  # amber -- contrasts hotel (teal) vs. air traffic within Turismo
ACCENT_ALOJAMIENTO = "#d97706"  # amber -- hospitality/warmth
ACCENT_TEMAS = "#7c3aed"  # purple -- opinion/insight
ACCENT_OPORTUNIDADES = "#0284c7"  # sky blue -- TUI opportunities

ACCENT_CLIMA_TEMPERATURA = "#dc2626"  # red -- heat
ACCENT_CLIMA_LLUVIA = "#2563eb"  # blue -- water
ACCENT_CLIMA_VIENTO = "#0891b2"  # teal -- air
ACCENT_CLIMA_HUMEDAD = "#7c3aed"  # purple -- moisture

# Rankings: each ranking type gets the hue that matches what it measures,
# instead of every ranking looking identical in navy.
ACCENT_RANKING_NDVI = "#15803d"  # green -- vegetation
ACCENT_RANKING_ALOJAMIENTOS = "#d97706"  # amber -- official establishments
ACCENT_RANKING_PLAZAS = "#0284c7"  # sky blue -- bed capacity
ACCENT_RANKING_TURISTICA = ACCENT_RANKING_ALOJAMIENTOS  # backwards-compatibility alias
ACCENT_RANKING_VALORADAS = "#7c3aed"  # purple -- quality/rating
ACCENT_RANKING_CALUROSAS = "#dc2626"  # red -- heat

# Contorno del hexágono seleccionado en el mapa -- amarillo vivo para que
# destaque sobre cualquier capa de métrica de color que haya debajo.
MAP_SELECTION_HIGHLIGHT = [250, 204, 21]  # #facc15

# Panel de detalle (mapa, al clicar un hexágono): pareja de acento propia,
# más llamativa que el navy/gris apagado que se usaba antes -- distingue
# "este hexágono" del resto/la media de un vistazo.
ACCENT_DETALLE_SELECCIONADO = "#db2777"  # magenta vivo -- el hexágono en foco
ACCENT_DETALLE_MEDIA = "#f59e0b"  # ámbar vivo -- el resto / la media del municipio


def _hex_to_rgb(hex_color: str) -> list[int]:
    hex_color = hex_color.lstrip("#")
    return [int(hex_color[i : i + 2], 16) for i in (0, 2, 4)]


def hex_to_rgba(hex_color: str, alpha: float) -> str:
    # Plotly's fillcolor rejects 8-digit hex (#rrggbbaa); rgba() is the
    # portable way to get a translucent fill from a plain hex accent color.
    r, g, b = _hex_to_rgb(hex_color)
    return f"rgba({r}, {g}, {b}, {alpha})"


def _is_missing(value) -> bool:
    return value is None or value != value  # NaN != NaN


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def interpolate_hex(t: float, light_hex: str, dark_hex: str) -> list[int]:
    t = _clamp01(t)
    light_rgb = _hex_to_rgb(light_hex)
    dark_rgb = _hex_to_rgb(dark_hex)
    return [round(light_rgb[i] + (dark_rgb[i] - light_rgb[i]) * t) for i in range(3)]


def sequential_color(value, vmin: float, vmax: float, light_hex: str, dark_hex: str) -> list[int]:
    if _is_missing(value):
        return NO_DATA_COLOR
    t = 0.0 if vmax == vmin else (value - vmin) / (vmax - vmin)
    return interpolate_hex(t, light_hex, dark_hex)


def diverging_color(value, vmin: float, vmid: float, vmax: float) -> list[int]:
    if _is_missing(value):
        return NO_DATA_COLOR
    if value <= vmid:
        span = vmid - vmin
        t = 0.0 if span == 0 else (value - vmin) / span
        return interpolate_hex(t, DIVERGING_SENTIMENT_LOW, DIVERGING_SENTIMENT_MID)
    span = vmax - vmid
    t = 0.0 if span == 0 else (value - vmid) / span
    return interpolate_hex(t, DIVERGING_SENTIMENT_MID, DIVERGING_SENTIMENT_HIGH)


def categorical_color(category, color_map: dict) -> list[int]:
    if _is_missing(category):
        return NO_DATA_COLOR
    return color_map.get(category, NO_DATA_COLOR)
