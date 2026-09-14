NO_DATA_COLOR = [107, 114, 128]  # #6b7280 -- cool muted gray (Financial Professional theme)

# Sequential ramps: (light_hex, dark_hex). Blue = dataviz skill's default
# sequential hue (ramp steps 100 -> 700). NDVI reuses the next categorical
# slot's hue (orange), tinted 85% toward the chart surface for its light end.
SEQUENTIAL_DENSITY = ("#cde2fb", "#0d366b")
SEQUENTIAL_NDVI = ("#f9e6dd", "#eb6834")

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


def _hex_to_rgb(hex_color: str) -> list[int]:
    hex_color = hex_color.lstrip("#")
    return [int(hex_color[i : i + 2], 16) for i in (0, 2, 4)]


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
