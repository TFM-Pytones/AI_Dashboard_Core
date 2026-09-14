# Dashboard v1 — Mapa H3 + KPIs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Streamlit app that renders Tenerife as a toggleable H3 hexagon map (densidad hotelera / sentimiento / NDVI) with a click-to-inspect KPI + NLP-aspects panel, reading directly from the existing `gold.gold_h3_master` and `gold.gold_sentimiento_h3` Postgres tables.

**Architecture:** A new `app/` package with one file per responsibility (data loading, color scales, map layers, detail panel, orchestration). Streamlit talks to Postgres directly — no intermediate API/service layer. Every piece of logic that doesn't need a live Streamlit session or DB connection (color math, merging, filtering, KPI formatting, aspect aggregation) is a plain function covered by pytest; the orchestration file (`app/main.py`) wires those functions into widgets and is verified manually by running the app.

**Tech Stack:** Python 3.13, Streamlit (`st.pydeck_chart` native selection), PyDeck (`H3HexagonLayer`), Plotly Express, GeoPandas, SQLAlchemy, pytest.

**Spec:** `docs/superpowers/specs/2026-09-07-streamlit-dashboard-design.md`

## Global Constraints

- DB access reads `AZURE_DB_URL` from `.env` via `python-dotenv` (pattern already used in `migration/test_azure_postgres_conn.py`) — no new env vars.
- No intermediate API/service layer: Streamlit queries Postgres directly.
- `NULL`/`NaN` metric values render as "sin datos" (map, gray `#898781`) or "—" (KPI cards) — never silently coerced to 0, never dropped from the dataset.
- No artificial try/except: a DB connection failure surfaces as Streamlit's own traceback.
- No third-party map-selection component: hexagon click uses Streamlit's native `st.pydeck_chart(..., on_select="rerun")`.
- The venv's console-script shebangs are stale (project was moved from `~/Desktop/AI_Dashboard_Core`), so every command in this plan uses `.venv/bin/python -m <tool>` instead of `.venv/bin/<tool>` directly, and is run from the `AI_Dashboard_Core/` repo root.

---

## File Structure

```
app/
├── __init__.py
├── data.py            # DB loaders + pure merge/filter helpers
├── color_scales.py    # pure RGB interpolation for the 3 map metrics
├── map_layers.py       # PyDeck layer/deck construction
├── detail_panel.py     # KPI cards + aspect comparison chart
├── main.py             # Streamlit entrypoint, wires everything together
└── README.md           # how to run the app locally

tests/
├── __init__.py
└── app/
    ├── __init__.py
    ├── test_environment.py
    ├── test_data.py
    ├── test_color_scales.py
    ├── test_map_layers.py
    └── test_detail_panel.py

requirements.txt        # + streamlit, pydeck, plotly, pytest
```

---

### Task 1: Dependencies & environment smoke test

**Files:**
- Modify: `requirements.txt`
- Create: `app/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/app/__init__.py`
- Test: `tests/app/test_environment.py`

**Interfaces:**
- Produces: confirms `streamlit`, `pydeck`, `plotly` are installed and that the installed Streamlit exposes `st.pydeck_chart(on_select=..., selection_mode=...)`, which every later task's map-selection code depends on.

- [ ] **Step 1: Write the failing test**

```python
# tests/app/test_environment.py
import inspect

import pydeck
import plotly
import streamlit as st


def test_pydeck_and_plotly_are_importable():
    assert pydeck.__version__
    assert plotly.__version__


def test_streamlit_pydeck_chart_supports_click_selection():
    signature = inspect.signature(st.pydeck_chart)
    assert "on_select" in signature.parameters
    assert "selection_mode" in signature.parameters
```

- [ ] **Step 2: Run it to verify it fails**

Run (from `AI_Dashboard_Core/`): `.venv/bin/python -m pytest tests/app/test_environment.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'streamlit'` (or `pydeck`/`plotly`).

- [ ] **Step 3: Add the dependencies**

Append to `requirements.txt`:

```
# Dashboard (app/) — Bloque 8 v1: mapa H3 + KPIs
streamlit>=1.42  # st.pydeck_chart(on_select=..., selection_mode=...) requires >=1.42
pydeck==0.9.1
plotly==5.24.1
pytest==8.3.4  # ya estaba instalado en el venv; se declara para reproducibilidad
```

Install: `.venv/bin/python -m pip install -r requirements.txt`

- [ ] **Step 4: Create the empty package/test-package markers**

Create `app/__init__.py`, `tests/__init__.py`, `tests/app/__init__.py` — all empty files.

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/app/test_environment.py -v`
Expected: PASS (2 tests).

If `test_streamlit_pydeck_chart_supports_click_selection` still fails after installing the latest `streamlit`, that Streamlit release doesn't support native PyDeck click-selection yet — stop and re-check the spec's interaction section (Task 6 below depends on this).

- [ ] **Step 6: Commit**

```bash
git add requirements.txt app/__init__.py tests/__init__.py tests/app/__init__.py tests/app/test_environment.py
git commit -m "chore: add streamlit/pydeck/plotly deps and app package skeleton"
```

---

### Task 2: Data layer (`app/data.py`)

**Files:**
- Create: `app/data.py`
- Test: `tests/app/test_data.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces (used by Tasks 4, 5, 6):
  - `compute_density_metric(gdf: pd.DataFrame) -> pd.DataFrame` — adds `densidad_metric` column.
  - `merge_h3_data(h3_gdf: gpd.GeoDataFrame, sentimiento_df: pd.DataFrame) -> gpd.GeoDataFrame` — left-joins on `h3_index`, includes `densidad_metric`.
  - `list_municipios(gdf: pd.DataFrame) -> list[str]`
  - `filter_by_municipio(gdf: pd.DataFrame, municipio: str | None) -> pd.DataFrame`
  - `get_engine() -> sqlalchemy.engine.Engine`
  - `load_h3_master(_engine) -> gpd.GeoDataFrame`
  - `load_sentimiento(_engine) -> pd.DataFrame`

- [ ] **Step 1: Write the failing tests for the pure helpers**

```python
# tests/app/test_data.py
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

from app.data import (
    compute_density_metric,
    filter_by_municipio,
    list_municipios,
    merge_h3_data,
)


def _h3_gdf():
    return gpd.GeoDataFrame(
        {
            "h3_index": ["a", "b", "c"],
            "municipio": ["Adeje", "Arona", None],
            "n_plazas_registro": [100, 0, 0],
            "n_establecimientos_registro": [5, 3, 0],
        },
        geometry=[Point(0, 0), Point(1, 1), Point(2, 2)],
    )


def test_compute_density_metric_uses_plazas_when_positive():
    result = compute_density_metric(_h3_gdf())
    assert result.loc[result["h3_index"] == "a", "densidad_metric"].iloc[0] == 100


def test_compute_density_metric_falls_back_to_establecimientos_when_plazas_zero():
    result = compute_density_metric(_h3_gdf())
    assert result.loc[result["h3_index"] == "b", "densidad_metric"].iloc[0] == 3


def test_merge_h3_data_joins_on_h3_index_and_keeps_unmatched_rows():
    sentimiento_df = pd.DataFrame({"h3_index": ["a"], "sentimiento_medio": [4.2]})
    merged = merge_h3_data(_h3_gdf(), sentimiento_df)
    assert merged.loc[merged["h3_index"] == "a", "sentimiento_medio"].iloc[0] == 4.2
    assert pd.isna(merged.loc[merged["h3_index"] == "b", "sentimiento_medio"].iloc[0])
    assert "densidad_metric" in merged.columns


def test_list_municipios_returns_sorted_unique_dropping_nan():
    assert list_municipios(_h3_gdf()) == ["Adeje", "Arona"]


def test_filter_by_municipio_returns_all_when_todos_or_none():
    gdf = _h3_gdf()
    assert len(filter_by_municipio(gdf, "Todos")) == 3
    assert len(filter_by_municipio(gdf, None)) == 3


def test_filter_by_municipio_filters_matching_rows():
    result = filter_by_municipio(_h3_gdf(), "Adeje")
    assert result["h3_index"].tolist() == ["a"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/app/test_data.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.data'`.

- [ ] **Step 3: Implement `app/data.py`**

```python
# app/data.py
import os

import geopandas as gpd
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

load_dotenv()

H3_MASTER_QUERY = "SELECT * FROM gold.gold_h3_master"
SENTIMIENTO_QUERY = "SELECT * FROM gold.gold_sentimiento_h3"


@st.cache_resource
def get_engine() -> Engine:
    return create_engine(os.environ["AZURE_DB_URL"])


@st.cache_data
def load_h3_master(_engine: Engine) -> gpd.GeoDataFrame:
    return gpd.read_postgis(H3_MASTER_QUERY, _engine, geom_col="geometry")


@st.cache_data
def load_sentimiento(_engine: Engine) -> pd.DataFrame:
    return pd.read_sql(SENTIMIENTO_QUERY, _engine)


def compute_density_metric(gdf: pd.DataFrame) -> pd.DataFrame:
    gdf = gdf.copy()
    gdf["densidad_metric"] = gdf["n_plazas_registro"].where(
        gdf["n_plazas_registro"] > 0, gdf["n_establecimientos_registro"]
    )
    return gdf


def merge_h3_data(h3_gdf: gpd.GeoDataFrame, sentimiento_df: pd.DataFrame) -> gpd.GeoDataFrame:
    merged = h3_gdf.merge(sentimiento_df, on="h3_index", how="left")
    return compute_density_metric(merged)


def list_municipios(gdf: pd.DataFrame) -> list[str]:
    return sorted(gdf["municipio"].dropna().unique().tolist())


def filter_by_municipio(gdf: pd.DataFrame, municipio: str | None) -> pd.DataFrame:
    if municipio is None or municipio == "Todos":
        return gdf
    return gdf[gdf["municipio"] == municipio]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/app/test_data.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add app/data.py tests/app/test_data.py
git commit -m "feat: add data loading and merge/filter helpers for the dashboard"
```

---

### Task 3: Color scales (`app/color_scales.py`)

**Files:**
- Create: `app/color_scales.py`
- Test: `tests/app/test_color_scales.py`

**Interfaces:**
- Consumes: nothing.
- Produces (used by Task 4):
  - `NO_DATA_COLOR: list[int]`
  - `SEQUENTIAL_DENSITY: tuple[str, str]`, `SEQUENTIAL_NDVI: tuple[str, str]` (light_hex, dark_hex)
  - `DIVERGING_SENTIMENT_DOMAIN: tuple[float, float, float]` (vmin, vmid, vmax)
  - `interpolate_hex(t: float, light_hex: str, dark_hex: str) -> list[int]`
  - `sequential_color(value, vmin: float, vmax: float, light_hex: str, dark_hex: str) -> list[int]`
  - `diverging_color(value, vmin: float, vmid: float, vmax: float) -> list[int]`

Color values come from the `dataviz` skill's validated palette
(`references/palette.md`): blue sequential ramp steps 100→700 for
density, the categorical orange (slot 2) tinted toward the chart
surface for NDVI, and the blue↔red diverging pair with a neutral gray
midpoint for sentiment. The sentiment domain (1.0 / 3.0 / 5.0) matches
the 1–5 star output of `nlptown/bert-base-multilingual-uncased-sentiment`,
the model used in `analytics/tarea2/nlp_sentimiento_2_1.ipynb`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/app/test_color_scales.py
import math

from app.color_scales import (
    NO_DATA_COLOR,
    diverging_color,
    interpolate_hex,
    sequential_color,
)


def test_interpolate_hex_at_light_endpoint():
    assert interpolate_hex(0.0, "#000000", "#ffffff") == [0, 0, 0]


def test_interpolate_hex_at_dark_endpoint():
    assert interpolate_hex(1.0, "#000000", "#ffffff") == [255, 255, 255]


def test_interpolate_hex_midpoint():
    assert interpolate_hex(0.5, "#000000", "#ffffff") == [128, 128, 128]


def test_interpolate_hex_clamps_t_above_one():
    assert interpolate_hex(1.5, "#000000", "#ffffff") == [255, 255, 255]


def test_interpolate_hex_clamps_t_below_zero():
    assert interpolate_hex(-0.5, "#000000", "#ffffff") == [0, 0, 0]


def test_sequential_color_scales_between_bounds():
    assert sequential_color(5, 0, 10, "#000000", "#ffffff") == [128, 128, 128]


def test_sequential_color_none_returns_no_data():
    assert sequential_color(None, 0, 10, "#000000", "#ffffff") == NO_DATA_COLOR


def test_sequential_color_nan_returns_no_data():
    assert sequential_color(float("nan"), 0, 10, "#000000", "#ffffff") == NO_DATA_COLOR


def test_diverging_color_at_min_returns_low_pole():
    assert diverging_color(1.0, 1.0, 3.0, 5.0) == [227, 73, 72]


def test_diverging_color_at_mid_returns_neutral_gray():
    assert diverging_color(3.0, 1.0, 3.0, 5.0) == [240, 239, 236]


def test_diverging_color_at_max_returns_high_pole():
    assert diverging_color(5.0, 1.0, 3.0, 5.0) == [42, 120, 214]


def test_diverging_color_none_returns_no_data():
    assert diverging_color(None, 1.0, 3.0, 5.0) == NO_DATA_COLOR


def test_diverging_color_nan_returns_no_data():
    assert diverging_color(float("nan"), 1.0, 3.0, 5.0) == NO_DATA_COLOR
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/app/test_color_scales.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.color_scales'`.

- [ ] **Step 3: Implement `app/color_scales.py`**

```python
# app/color_scales.py

NO_DATA_COLOR = [137, 135, 129]  # #898781 -- muted ink (dataviz skill palette)

# Sequential ramps: (light_hex, dark_hex). Blue = dataviz skill's default
# sequential hue (ramp steps 100 -> 700). NDVI reuses the next categorical
# slot's hue (orange), tinted 85% toward the chart surface for its light end.
SEQUENTIAL_DENSITY = ("#cde2fb", "#0d366b")
SEQUENTIAL_NDVI = ("#f9e6dd", "#eb6834")

# Diverging pair: blue <-> red poles, neutral gray midpoint (dataviz skill).
# Domain matches the 1-5 star scale of the nlptown multilingual BERT model.
DIVERGING_SENTIMENT_LOW = "#e34948"
DIVERGING_SENTIMENT_MID = "#f0efec"
DIVERGING_SENTIMENT_HIGH = "#2a78d6"
DIVERGING_SENTIMENT_DOMAIN = (1.0, 3.0, 5.0)


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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/app/test_color_scales.py -v`
Expected: PASS (13 tests).

- [ ] **Step 5: Commit**

```bash
git add app/color_scales.py tests/app/test_color_scales.py
git commit -m "feat: add sequential/diverging color scales for the H3 map"
```

---

### Task 4: Map layers (`app/map_layers.py`)

**Files:**
- Create: `app/map_layers.py`
- Test: `tests/app/test_map_layers.py`

**Interfaces:**
- Consumes: `app.color_scales.{NO_DATA_COLOR, SEQUENTIAL_DENSITY, SEQUENTIAL_NDVI, DIVERGING_SENTIMENT_DOMAIN, sequential_color, diverging_color}` (Task 3).
- Produces (used by Task 6):
  - `METRICS: dict[str, dict]` — keys are the sidebar labels ("Densidad hotelera", "Sentimiento", "Naturaleza (NDVI)").
  - `build_fill_color_column(gdf: pd.DataFrame, metric_key: str) -> pd.Series`
  - `build_layer(gdf: pd.DataFrame, metric_key: str) -> pydeck.Layer`
  - `build_deck(gdf: pd.DataFrame, metric_key: str) -> pydeck.Deck`

- [ ] **Step 1: Write the failing tests**

```python
# tests/app/test_map_layers.py
import pandas as pd
import pydeck as pdk

from app.map_layers import build_deck, build_fill_color_column, build_layer


def _gdf():
    return pd.DataFrame(
        {
            "h3_index": ["a", "b", "c"],
            "densidad_metric": [0, 10, 20],
            "sentimiento_medio": [1.0, 3.0, 5.0],
            "ndvi_medio": [None, 0.5, 1.0],
        }
    )


def test_build_fill_color_column_sequential_scales_min_to_max():
    colors = build_fill_color_column(_gdf(), "Densidad hotelera")
    assert colors.iloc[0] == [205, 226, 251]  # light end of the blue ramp
    assert colors.iloc[2] == [13, 54, 107]  # dark end of the blue ramp


def test_build_fill_color_column_diverging_uses_fixed_domain():
    colors = build_fill_color_column(_gdf(), "Sentimiento")
    assert colors.tolist() == [[227, 73, 72], [240, 239, 236], [42, 120, 214]]


def test_build_fill_color_column_handles_null_values():
    colors = build_fill_color_column(_gdf(), "Naturaleza (NDVI)")
    assert colors.iloc[0] == [137, 135, 129]  # NO_DATA_COLOR


def test_build_layer_returns_pickable_h3_layer():
    layer = build_layer(_gdf(), "Densidad hotelera")
    assert isinstance(layer, pdk.Layer)
    assert layer.id == "h3_index"
    assert layer.pickable is True
    assert layer.get_hexagon == "h3_index"
    assert layer.get_fill_color == "fill_color"


def test_build_deck_has_one_layer_centered_on_tenerife():
    deck = build_deck(_gdf(), "Sentimiento")
    assert isinstance(deck, pdk.Deck)
    assert len(deck.layers) == 1
    assert round(deck.initial_view_state.latitude, 2) == 28.29
    assert round(deck.initial_view_state.longitude, 2) == -16.62
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/app/test_map_layers.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.map_layers'`.

- [ ] **Step 3: Implement `app/map_layers.py`**

```python
# app/map_layers.py
import pandas as pd
import pydeck as pdk

from app.color_scales import (
    DIVERGING_SENTIMENT_DOMAIN,
    SEQUENTIAL_DENSITY,
    SEQUENTIAL_NDVI,
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/app/test_map_layers.py -v`
Expected: PASS (5 tests).

If `layer.id`, `layer.get_hexagon`, or `layer.get_fill_color` raise `AttributeError` against the installed `pydeck` version, print `vars(layer)` to see the actual stored attribute names and adjust the assertions (and, if needed, `build_layer`'s kwargs) to match — the constructor kwargs are expected to round-trip as attributes, but this is worth confirming against the pinned `pydeck==0.9.1`.

- [ ] **Step 5: Commit**

```bash
git add app/map_layers.py tests/app/test_map_layers.py
git commit -m "feat: add PyDeck H3 layer construction for the 3 map metrics"
```

---

### Task 5: Detail panel helpers (`app/detail_panel.py`)

**Files:**
- Create: `app/detail_panel.py`
- Test: `tests/app/test_detail_panel.py`

**Interfaces:**
- Consumes: nothing from earlier tasks (pure pandas + `streamlit`/`plotly` for the render function only).
- Produces (used by Task 6):
  - `format_kpi_value(value, decimals: int = 1) -> str`
  - `municipio_aspect_comparison(gdf: pd.DataFrame, h3_index: str) -> pd.DataFrame | None`
  - `render_detail_panel(gdf: pd.DataFrame, selected_h3_index: str | None) -> None`

- [ ] **Step 1: Write the failing tests for the pure helpers**

```python
# tests/app/test_detail_panel.py
import math

import pandas as pd

from app.detail_panel import format_kpi_value, municipio_aspect_comparison


def test_format_kpi_value_none_returns_dash():
    assert format_kpi_value(None) == "—"


def test_format_kpi_value_nan_returns_dash():
    assert format_kpi_value(float("nan")) == "—"


def test_format_kpi_value_float_formats_with_one_decimal_by_default():
    assert format_kpi_value(4.567) == "4.6"


def test_format_kpi_value_int_returns_plain_string():
    assert format_kpi_value(7) == "7"


def _peer_gdf():
    return pd.DataFrame(
        {
            "h3_index": ["a", "b", "c", "d"],
            "municipio": ["Adeje", "Adeje", "Adeje", "Arona"],
            "queja_principal": ["ruido", "precio", "ruido", "limpieza"],
        }
    )


def test_municipio_aspect_comparison_counts_peers_in_same_municipio():
    result = municipio_aspect_comparison(_peer_gdf(), "a")
    counts = dict(zip(result["aspecto"], result["n_hexagonos"]))
    assert counts == {"ruido": 2, "precio": 1}


def test_municipio_aspect_comparison_marks_selected_hexagon_aspect():
    result = municipio_aspect_comparison(_peer_gdf(), "b")
    row = result.loc[result["aspecto"] == "precio"].iloc[0]
    assert row["es_seleccionado"] is True or bool(row["es_seleccionado"]) is True


def test_municipio_aspect_comparison_returns_none_for_unknown_hexagon():
    assert municipio_aspect_comparison(_peer_gdf(), "unknown") is None


def test_municipio_aspect_comparison_drops_null_quejas():
    gdf = _peer_gdf()
    gdf.loc[gdf["h3_index"] == "c", "queja_principal"] = None
    result = municipio_aspect_comparison(gdf, "a")
    assert result["aspecto"].tolist() == ["ruido", "precio"]
    assert result.loc[result["aspecto"] == "ruido", "n_hexagonos"].iloc[0] == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/app/test_detail_panel.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.detail_panel'`.

- [ ] **Step 3: Implement `app/detail_panel.py`**

```python
# app/detail_panel.py
import math

import pandas as pd
import plotly.express as px
import streamlit as st

KPI_COLUMNS = [
    ("n_hoteles", "Nº hoteles"),
    ("n_establecimientos_registro", "Nº alojamientos registrados"),
    ("ndvi_medio", "NDVI medio"),
    ("sentimiento_medio", "Sentimiento medio"),
    ("rating_booking_medio", "Rating Booking"),
    ("rating_tripadvisor_medio", "Rating TripAdvisor"),
]


def format_kpi_value(value, decimals: int = 1) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "—"
    if isinstance(value, float):
        return f"{value:.{decimals}f}"
    return str(value)


def municipio_aspect_comparison(gdf: pd.DataFrame, h3_index: str) -> pd.DataFrame | None:
    if h3_index not in gdf["h3_index"].values:
        return None
    row = gdf.loc[gdf["h3_index"] == h3_index].iloc[0]
    peers = gdf[gdf["municipio"] == row["municipio"]]
    counts = peers["queja_principal"].dropna().value_counts().reset_index()
    counts.columns = ["aspecto", "n_hexagonos"]
    counts["es_seleccionado"] = counts["aspecto"] == row["queja_principal"]
    return counts


def render_detail_panel(gdf: pd.DataFrame, selected_h3_index: str | None) -> None:
    if selected_h3_index is None:
        st.info("Haz clic en un hexágono del mapa para ver su detalle.")
        return
    matches = gdf.loc[gdf["h3_index"] == selected_h3_index]
    if matches.empty:
        st.warning("No hay datos para el hexágono seleccionado.")
        return
    row = matches.iloc[0]
    st.subheader(f"Hexágono {selected_h3_index}")
    cols = st.columns(3)
    for i, (column, label) in enumerate(KPI_COLUMNS):
        cols[i % 3].metric(label, format_kpi_value(row.get(column)))
    comparison = municipio_aspect_comparison(gdf, selected_h3_index)
    if comparison is None or comparison.empty:
        st.caption("Sin aspectos NLP registrados para este municipio.")
        return
    fig = px.bar(
        comparison,
        x="aspecto",
        y="n_hexagonos",
        color="es_seleccionado",
        color_discrete_map={True: "#2a78d6", False: "#c3c2b7"},
        title=f"Aspectos más mencionados en {row['municipio']}",
    )
    st.plotly_chart(fig, use_container_width=True)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/app/test_detail_panel.py -v`
Expected: PASS (8 tests).

- [ ] **Step 5: Commit**

```bash
git add app/detail_panel.py tests/app/test_detail_panel.py
git commit -m "feat: add KPI formatting and NLP aspect comparison for the detail panel"
```

---

### Task 6: Orchestration (`app/main.py`) + manual verification

**Files:**
- Create: `app/main.py`
- Create: `app/README.md`

**Interfaces:**
- Consumes: `app.data.{get_engine, load_h3_master, load_sentimiento, merge_h3_data, list_municipios, filter_by_municipio}` (Task 2), `app.map_layers.{METRICS, build_deck}` (Task 4), `app.detail_panel.render_detail_panel` (Task 5).
- Produces: the runnable app (`streamlit run app/main.py`) — no further task consumes this.

This task has no automated tests: it's Streamlit session/widget wiring against a live DB connection, which is exactly the "manual verification" case the spec calls out. Steps below are still concrete and checkable one at a time.

- [ ] **Step 1: Implement `app/main.py`**

```python
# app/main.py
import streamlit as st

from app.data import (
    filter_by_municipio,
    get_engine,
    list_municipios,
    load_h3_master,
    load_sentimiento,
    merge_h3_data,
)
from app.detail_panel import render_detail_panel
from app.map_layers import METRICS, build_deck

st.set_page_config(page_title="AI-Dashboard Tenerife", layout="wide")
st.title("AI-Dashboard — Oferta turística de Tenerife")

engine = get_engine()
h3_master = load_h3_master(engine)
sentimiento = load_sentimiento(engine)
full_gdf = merge_h3_data(h3_master, sentimiento)

with st.sidebar:
    metric_key = st.selectbox("Capa del mapa", list(METRICS.keys()))
    municipio = st.selectbox("Municipio", ["Todos"] + list_municipios(full_gdf))

filtered_gdf = filter_by_municipio(full_gdf, municipio)

map_col, detail_col = st.columns([3, 2])

with map_col:
    deck = build_deck(filtered_gdf, metric_key)
    st.pydeck_chart(deck, on_select="rerun", selection_mode="single-object", key="h3_map")

selected_h3_index = None
event = st.session_state.get("h3_map")
if event is not None:
    picked = event.get("selection", {}).get("objects", {}).get("h3_index", [])
    if picked:
        selected_h3_index = picked[0].get("h3_index")

with detail_col:
    render_detail_panel(full_gdf, selected_h3_index)
```

- [ ] **Step 2: Verify the selection event shape against the installed Streamlit**

Run: `.venv/bin/python -m streamlit run app/main.py`, click a hexagon, then temporarily add `st.write(st.session_state["h3_map"])` above the `selected_h3_index` block to inspect the real structure. If it doesn't match `{"selection": {"objects": {"h3_index": [{"h3_index": ...}, ...]}}}`, adjust the extraction block in Step 1 to match what's actually there, then remove the debug `st.write`.

- [ ] **Step 3: Write `app/README.md`**

```markdown
# AI-Dashboard — app/

Dashboard v1: mapa H3 interactivo (densidad hotelera / sentimiento / NDVI)
+ panel de detalle por hexágono. Ver el diseño completo en
`docs/superpowers/specs/2026-09-07-streamlit-dashboard-design.md`.

## Ejecutar en local

1. Asegúrate de que `.env` tiene `AZURE_DB_URL` relleno (ver `.env.example`).
2. Instala dependencias: `.venv/bin/python -m pip install -r requirements.txt`
3. Arranca la app: `.venv/bin/python -m streamlit run app/main.py`

## Fuera de alcance de esta v1

Chatbot Text-to-SQL, simulador what-if, capas de PTNA/Clustering/Isócronas,
informe narrativo y bandeja de alertas — ver la sección "Fuera de alcance"
del spec.
```

- [ ] **Step 4: Manual verification against the real database**

With the app running (`.venv/bin/python -m streamlit run app/main.py`), confirm all four criteria from the spec's Testing section:

1. All 3 layers ("Densidad hotelera", "Sentimiento", "Naturaleza (NDVI)") render and repaint correctly when switched in the sidebar.
2. The municipio filter narrows the map to only that municipio's hexagons.
3. Clicking a hexagon populates the detail panel with that hexagon's KPIs and its municipio's aspect comparison chart.
4. A hexagon with no reviews (`sentimiento_medio` is `NULL`) renders gray on the map and shows "—" for `sentimiento_medio` in the detail panel, without crashing the app.

- [ ] **Step 5: Run the full test suite one last time**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: all tests from Tasks 1–5 PASS.

- [ ] **Step 6: Commit**

```bash
git add app/main.py app/README.md
git commit -m "feat: wire up the Streamlit dashboard entrypoint (H3 map + detail panel)"
```

---

## Self-Review Notes

- **Spec coverage:** Arquitectura/ficheros → Tasks 1–6. Interacción de clic → Task 6 (native `on_select`). Capas del mapa → Task 4 (`METRICS`). Panel de detalle → Task 5. Manejo de errores (NULL → "sin datos"/"—", sin try/except) → `color_scales.py` (`NO_DATA_COLOR`) and `detail_panel.py` (`format_kpi_value`). Dependencias nuevas → Task 1. Testing → Task 6 Step 4 (matches the spec's own manual checklist verbatim). Fuera de alcance → explicitly not built, called out in `app/README.md`.
- **Placeholder scan:** no TBD/TODO; the two spots with genuine external-API uncertainty (whether the installed `pydeck` version exposes `.id`/`.get_hexagon` as attributes, and the exact shape of the Streamlit selection event) are resolved with a concrete inspection command (`vars(layer)`, `st.write(st.session_state[...])`) and an explicit instruction on what to change, not left open-ended.
- **Type consistency:** `metric_key` values are the `METRICS` dict keys ("Densidad hotelera", "Sentimiento", "Naturaleza (NDVI)") used identically in `app/map_layers.py` (Task 4) and `app/main.py` (Task 6). `h3_index` is a `str` key throughout `data.py`, `map_layers.py`, and `detail_panel.py`.

---

**Plan complete and saved to `docs/superpowers/plans/2026-09-07-dashboard-v1-h3-map.md`. Two execution options:**

1. **Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
