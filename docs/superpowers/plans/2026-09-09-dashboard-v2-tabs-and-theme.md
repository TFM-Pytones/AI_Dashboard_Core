# Dashboard v2 — Tema visual, basemap satélite y pestañas Rankings/Clima/Municipios/Alojamiento Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Take the existing `Feat/Dashboard-Proyecto` Streamlit app (tabs Resumen/Mapa/Tabla, already reading `gold.gold_h3_master` + `gold.gold_sentimiento_h3` + `gold.gold_h3_accesibilidad` + `gold.isocronas_visuales`) and (1) give it a distinctive light color theme + a real satellite basemap instead of the current CARTO "road" style, then (2) add four new tabs — Rankings, Clima, Municipios, Alojamiento — reusing data already in Postgres wherever possible and adding exactly one new table (`gold.gold_municipio_master`) where it's genuinely missing.

**Architecture:** Same pattern as the existing `app/` package: one file per responsibility, pure pandas/pydeck/plotly functions covered by pytest, Streamlit widget wiring in `app/main.py` verified manually. No new architecture — this plan only adds files that follow the exact shape of `app/rankings.py`-style siblings already in the repo (`summary.py`, `table_view.py`, `detail_panel.py`).

**Tech Stack:** Python 3.13, Streamlit ≥1.42, PyDeck 0.9.1 (`H3HexagonLayer` + Mapbox raster basemap), Plotly Express, GeoPandas, SQLAlchemy, dbt (Postgres adapter), pytest.

**Spec:** `docs/superpowers/specs/2026-09-07-streamlit-dashboard-design.md` (original v1 spec — this plan extends it; no new spec doc, the deltas are small enough to describe per-task below).

## Global Constraints

- DB access reads `AZURE_DB_URL` from `.env` via `python-dotenv` — no change to that pattern.
- `NULL`/`NaN` metric values render as "sin datos" (map, gray `#898781`) or "—" (KPI cards, via the existing `app.detail_panel.format_kpi_value`) — never silently coerced to 0, never dropped from the dataset.
- No artificial try/except: a DB or dbt failure surfaces as-is.
- Every command in this plan is run from the `AI_Dashboard_Core/` repo root using `.venv/bin/python -m <tool>` (the venv's console-script shebangs are stale per the existing plan's note).
- Color choices reuse the palette already established in `app/color_scales.py` (blue `#2a78d6`, red `#e34948`, orange `#eb6834`, muted gray `#898781`/`#f0efec`) — new UI chrome (theme, charts) must stay consistent with it, not invent a clashing new palette.
- New dbt models follow `dbt_project/dbt_project.yml`'s existing convention: files under `models/gold/` materialize as `table` in the literal `gold` schema automatically (see `macros/generate_schema_name.sql`) — no per-model `+schema` needed.

---

## Prerequisite (manual, before Task 1): Mapbox token

You chose Mapbox Satellite over the free Esri tiles, which means this needs an account only you can create:

1. Go to https://account.mapbox.com/auth/signup/ and create a free account (the free tier includes 50,000 map loads/month, far more than a local TFM dashboard needs).
2. Once logged in, go to https://account.mapbox.com/access-tokens/ and copy the **default public token** (starts with `pk.`).
3. Add it to `AI_Dashboard_Core/.env`:
   ```
   MAPBOX_API_KEY=pk.your_token_here
   ```
4. Add the same empty placeholder to `.env.example`:
   ```
   MAPBOX_API_KEY=
   ```

Task 1 below assumes this variable already exists in your `.env` — if `MAPBOX_API_KEY` is missing, the app will raise `KeyError` on startup (intentional, per the "no artificial try/except" constraint — a missing token should be visible, not silently degraded).

---

## File Structure

```
.streamlit/
└── config.toml               # NEW — light theme, non-default accent colors

app/
├── data.py                   # MODIFY — add load_municipio_master()
├── map_layers.py             # MODIFY — build_deck() switches to Mapbox satellite basemap
├── rankings.py                # NEW — top-N ranking helpers + tab render
├── clima.py                   # NEW — quarterly climate aggregation + tab render
├── municipios.py              # NEW — municipio ficha helpers + tab render
├── alojamiento.py             # NEW — accommodation/reputation breakdown + tab render
└── main.py                    # MODIFY — wire in 4 new tabs + custom CSS touch

dbt_project/models/gold/
└── gold_municipio_master.sql  # NEW — municipio-grain rollup + ISTAC join

tests/app/
├── test_map_layers.py         # MODIFY — cover Mapbox basemap wiring
├── test_rankings.py           # NEW
├── test_clima.py              # NEW
├── test_municipios.py         # NEW
└── test_alojamiento.py        # NEW

.env / .env.example            # MODIFY — add MAPBOX_API_KEY
```

---

### Task 1: Light theme + Mapbox satellite basemap

**Files:**
- Create: `.streamlit/config.toml`
- Modify: `.env`, `.env.example` (add `MAPBOX_API_KEY`, done in the Prerequisite above)
- Modify: `app/map_layers.py:119-127` (`build_deck`)
- Modify: `app/main.py` (add a small CSS touch for the tabs)
- Test: `tests/app/test_map_layers.py`

**Interfaces:**
- Consumes: `os.environ["MAPBOX_API_KEY"]` (new env var from the Prerequisite step).
- Produces: `build_deck(gdf, metric_key, show_hexagons=True)` — same signature as today, but the returned `pdk.Deck` now points at a Mapbox satellite style instead of CARTO roads. No other task depends on the internals changing, only on the signature staying the same (it does).

- [x] **Step 1: Write the failing test for the new basemap wiring**

Added to `tests/app/test_map_layers.py`. The plan originally drafted this
asserting `deck.api_keys == {...}`, but the installed pydeck (0.9.1)
doesn't expose an `api_keys` attribute at all — it stores the token as
`deck.mapbox_key` instead (confirmed by inspecting `vars(deck)`
directly). The test that actually got written and passed:

```python
def test_build_deck_uses_mapbox_satellite_provider(monkeypatch):
    monkeypatch.setenv("MAPBOX_API_KEY", "pk.test_token")
    deck = build_deck(_gdf(), "Sentimiento")
    assert deck.map_provider == "mapbox"
    assert deck.map_style == "mapbox://styles/mapbox/satellite-streets-v9"
    # pydeck 0.9.1 stores the mapbox api_keys entry as this attribute, not
    # as an inspectable `api_keys` dict on the Deck instance.
    assert deck.mapbox_key == "pk.test_token"
```

Also had to replace the *existing* `test_build_deck_uses_a_real_road_basemap`
test (asserting the old CARTO `map_provider`/`map_style`) with the one
above — that test predates this plan (the test file had moved on since
the plan was drafted) and directly contradicted the new behavior.

The other two pre-existing `build_deck` tests
(`test_build_deck_has_one_layer_centered_on_tenerife`,
`test_build_deck_can_hide_the_hexagon_layer`) needed
`monkeypatch.setenv("MAPBOX_API_KEY", "pk.test_token")` added too, since
`build_deck` now raises `KeyError` without that env var.

- [x] **Step 2: Run test to verify it fails**

Ran: `.venv/bin/python -m pytest tests/app/test_map_layers.py::test_build_deck_uses_mapbox_satellite_provider -v`
Result: FAILED as expected — `AssertionError: assert 'carto' == 'mapbox'`.

- [x] **Step 3: Update `build_deck` in `app/map_layers.py`**

Add `import os` to the top of the file (if not already there), then replace the `build_deck` function (currently at lines 119-127):

```python
def build_deck(gdf: pd.DataFrame, metric_key: str, show_hexagons: bool = True) -> pdk.Deck:
    layers = [build_layer(gdf, metric_key)] if show_hexagons else []
    return pdk.Deck(
        layers=layers,
        initial_view_state=TENERIFE_VIEW_STATE,
        map_provider="mapbox",
        map_style="mapbox://styles/mapbox/satellite-streets-v9",
        api_keys={"mapbox": os.environ["MAPBOX_API_KEY"]},
        tooltip={"text": "Hexágono: {h3_index}"},
    )
```

`satellite-streets-v9` (not plain `satellite-v9`) keeps municipio/road labels legible over the imagery — pure satellite tiles with H3 hexagons on top are hard to orient on without any labels.

- [x] **Step 4: Run test to verify it passes**

Ran: `.venv/bin/python -m pytest tests/app/test_map_layers.py -v`
Result: PASS — 16/16.

- [x] **Step 4b (discovered during manual verification, not in the original plan): fix `app/data.py`'s `load_dotenv()`**

Screenshotting the running app (see Step 7) showed the satellite tiles
failing to load with a browser console error requesting
`...access_token=no-token`. Root-caused by launching a minimal debug
Streamlit page that printed `deck.mapbox_key` at runtime: it was an
**empty string**, even though `"MAPBOX_API_KEY" in os.environ` was
`True`.

Cause: Streamlit's own bootstrap
(`streamlit/web/bootstrap.py:_fix_pydeck_mapbox_api_warning`) pre-seeds
`os.environ["MAPBOX_API_KEY"] = config.get_option("mapbox.token")` —
which defaults to `""` — **before** `app/main.py` ever runs. `app/data.py`'s
`load_dotenv()` call then sees the key already present in `os.environ`
(empty, but present) and, since `python-dotenv`'s default is
`override=False`, refuses to replace it with the real value from `.env`.

Fix, in `app/data.py`:

```python
# override=True is required: Streamlit's own bootstrap pre-seeds
# os.environ["MAPBOX_API_KEY"] = "" (from its unset `mapbox.token` config
# option, to silence an internal pydeck warning) *before* this module runs.
# python-dotenv's default override=False then refuses to replace that
# already-present empty value with the real one from .env.
load_dotenv(override=True)
```

(replaces the previous bare `load_dotenv()` call). Verified directly:
reproduced the empty-string bug in an isolated script, confirmed
`override=True` fixes it, then confirmed satellite tiles render
correctly in the real running app afterward (see Step 7).

- [x] **Step 5: Create the theme file**

```toml
# .streamlit/config.toml
[theme]
base = "light"
primaryColor = "#2a78d6"
backgroundColor = "#fbfaf8"
secondaryBackgroundColor = "#f0efe8"
textColor = "#1f1d1a"
```

This reuses the blue already used for "Zona turística oficial" / high-sentiment in `color_scales.py` as the accent, on a warm off-white (not stark `#ffffff`, and not Streamlit's default theme) — consistent with the rest of the app instead of a bolted-on new palette.

- [x] **Step 6: Add a small CSS touch so the tabs don't look like default Streamlit**

In `app/main.py`, right after `st.set_page_config(...)` (currently line 19), add:

```python
st.markdown(
    """
    <style>
    .stTabs [data-baseweb="tab-list"] { gap: 4px; }
    .stTabs [data-baseweb="tab"] {
        background-color: #f0efe8;
        border-radius: 8px 8px 0 0;
        padding: 8px 16px;
    }
    .stTabs [aria-selected="true"] {
        background-color: #2a78d6;
        color: white;
    }
    </style>
    """,
    unsafe_allow_html=True,
)
```

- [x] **Step 7: Manual visual verification**

No browser was available in this session initially, so Playwright +
headless Chromium were installed on the fly
(`.venv/bin/python -m pip install playwright && .venv/bin/python -m playwright install chromium`)
and used to actually load the running app and screenshot it — confirmed
by looking at the resulting images, not assumed:

1. ✅ Warm off-white background + rounded blue-pill tabs, confirmed on the "Resumen" tab screenshot.
2. ✅ Confirmed in the same screenshot.
3. ✅ Confirmed on the "Mapa" tab with the hexagon layer toggled off: real aerial imagery of Tenerife renders (Teide visible, roads, "Teide National Park" label, Mapbox/Maxar attribution in the corner) — not the old gray CARTO roads style.
4. Not explicitly re-tested (zoom/pan) since it's Mapbox's own standard interaction, unrelated to this change.

- [x] **Step 8: Commit**

```bash
git add .streamlit/config.toml .env.example app/data.py app/map_layers.py app/main.py tests/app/test_map_layers.py
git commit -m "feat: add light theme and switch map basemap to Mapbox satellite imagery"
```

(`.env` itself is gitignored per the repo's `.gitignore` — do not force-add it.)

---

### Task 2: Rankings tab (`app/rankings.py`)

**Files:**
- Create: `app/rankings.py`
- Modify: `app/main.py` (add the tab)
- Test: `tests/app/test_rankings.py`

**Interfaces:**
- Consumes: nothing from earlier tasks (pure pandas + `streamlit`/`plotly` for the render function only). Reads directly from the `full_gdf` already built in `app/main.py`.
- Produces (used only by Task 2's own render wiring in `main.py`):
  - `RANKINGS: dict[str, dict]` — labels shown in the tab's selectbox.
  - `top_n_by_ranking(gdf: pd.DataFrame, ranking_key: str, n: int = 10) -> pd.DataFrame`
  - `render_rankings_tab(gdf: pd.DataFrame) -> None`

- [x] **Step 1: Write the failing tests**

```python
# tests/app/test_rankings.py
import pandas as pd

from app.rankings import RANKINGS, top_n_by_ranking


def _gdf():
    return pd.DataFrame(
        {
            "h3_index": ["a", "b", "c", "d"],
            "municipio": ["Adeje", "Arona", "Adeje", "Arona"],
            "ndvi_medio": [0.8, None, 0.2, 0.5],
            "temp_media_anual": [22.0, 25.0, 19.0, 24.0],
            "n_establecimientos_booking": [10, 3, 0, 7],
            "rating_booking_medio": [4.5, 3.0, None, 4.8],
        }
    )


def test_top_n_by_ranking_sorts_descending_and_drops_nulls():
    result = top_n_by_ranking(_gdf(), "Más vegetación (NDVI)", n=10)
    assert result["h3_index"].tolist() == ["a", "d", "c"]  # b dropped (NaN)


def test_top_n_by_ranking_respects_n():
    result = top_n_by_ranking(_gdf(), "Más vegetación (NDVI)", n=2)
    assert len(result) == 2


def test_top_n_by_ranking_more_turistica_uses_booking_count():
    result = top_n_by_ranking(_gdf(), "Más turística (nº establecimientos Booking)", n=1)
    assert result["h3_index"].tolist() == ["a"]


def test_top_n_by_ranking_unknown_key_raises():
    try:
        top_n_by_ranking(_gdf(), "no existe", n=1)
        assert False, "expected KeyError"
    except KeyError:
        pass


def test_rankings_dict_covers_expected_labels():
    assert set(RANKINGS.keys()) == {
        "Más vegetación (NDVI)",
        "Más turística (nº establecimientos Booking)",
        "Mejor valoradas (rating Booking)",
        "Más calurosas",
    }
```

- [x] **Step 2: Run tests to verify they fail**

Ran: `.venv/bin/python -m pytest tests/app/test_rankings.py -v` → `ModuleNotFoundError: No module named 'app.rankings'`, as expected.

- [x] **Step 3: Implement `app/rankings.py`**

```python
# app/rankings.py
import pandas as pd
import plotly.express as px
import streamlit as st

RANKINGS = {
    "Más vegetación (NDVI)": {"column": "ndvi_medio"},
    "Más turística (nº establecimientos Booking)": {"column": "n_establecimientos_booking"},
    "Mejor valoradas (rating Booking)": {"column": "rating_booking_medio"},
    "Más calurosas": {"column": "temp_media_anual"},
}

DISPLAY_COLUMNS = ["h3_index", "municipio"]


def top_n_by_ranking(gdf: pd.DataFrame, ranking_key: str, n: int = 10) -> pd.DataFrame:
    column = RANKINGS[ranking_key]["column"]
    ranked = gdf.dropna(subset=[column]).sort_values(column, ascending=False)
    return ranked[DISPLAY_COLUMNS + [column]].head(n)


def render_rankings_tab(gdf: pd.DataFrame) -> None:
    col1, col2 = st.columns([3, 1])
    ranking_key = col1.selectbox("Ranking", list(RANKINGS.keys()))
    n = col2.slider("Nº de hexágonos", min_value=5, max_value=30, value=10)

    result = top_n_by_ranking(gdf, ranking_key, n)
    column = RANKINGS[ranking_key]["column"]

    if result.empty:
        st.info("No hay hexágonos con datos para este ranking.")
        return

    fig = px.bar(
        result.sort_values(column),
        x=column,
        y="h3_index",
        color="municipio",
        orientation="h",
        title=ranking_key,
    )
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(result, width="stretch")
```

- [x] **Step 4: Run tests to verify they pass**

Ran: `.venv/bin/python -m pytest tests/app/test_rankings.py -v` → PASS, 5/5.

- [x] **Step 5: Wire the tab into `app/main.py`**

In `app/main.py`:
1. Add `from app.rankings import render_rankings_tab` to the imports.
2. Change the tabs line (currently `tab_resumen, tab_mapa, tab_tabla = st.tabs(["Resumen", "Mapa", "Tabla"])`) to:
   ```python
   tab_resumen, tab_mapa, tab_tabla, tab_rankings = st.tabs(
       ["Resumen", "Mapa", "Tabla", "Rankings"]
   )
   ```
3. After the existing `with tab_tabla:` block, add:
   ```python
   with tab_rankings:
       render_rankings_tab(full_gdf)
   ```

- [x] **Step 6: Manual visual verification**

Screenshotted via Playwright: "Más vegetación (NDVI)" ranking renders correctly — bar chart colored by municipio + matching table below, top value 0.8472 (La Laguna). No console errors. Only this one ranking was screenshotted (the other 3 share the same tested `top_n_by_ranking` function, already covered by the unit tests).

Between Task 1 and Task 2, the user reported (not part of the original plan) that the hexagons still fully covered the satellite imagery — their original spec wanted satellite *with* hexagons on top, so this was by design, but at the default 0.55 opacity it read as too solid. Fixed by lowering `DEFAULT_HEXAGON_OPACITY` to 0.4 and adding a sidebar "Opacidad de hexágonos" slider (`build_deck`/`build_layer` already took an `opacity` param, just wasn't exposed as a widget) — committed separately before starting this task.

- [x] **Step 7: Commit**

Committed as `2527b24`.

---

### Task 3: Clima tab (`app/clima.py`)

**Files:**
- Create: `app/clima.py`
- Modify: `app/main.py` (add the tab)
- Test: `tests/app/test_clima.py`

**Interfaces:**
- Consumes: nothing from earlier tasks. Reads the `_qN` quarterly columns already present in `gold_h3_master` (`temp_media_q1..q4`, `lluvia_mm_q1..q4`, `vel_viento_media_q1..q4`, `humedad_media_q1..q4` — confirmed present in `dbt_project/models/gold/gold_h3_master.sql:358-361`).
- Produces (used only by Task 3's own render wiring in `main.py`):
  - `CLIMATE_VARIABLES: dict[str, str]` — display label → column prefix (e.g. `"Temperatura": "temp_media"`).
  - `climate_by_trimestre(gdf: pd.DataFrame, variable_prefix: str) -> pd.DataFrame` — long-format `[trimestre, valor]`, averaged across the (already filtered) hexagons.
  - `render_clima_tab(gdf: pd.DataFrame) -> None`

- [x] **Step 1: Write the failing tests**

```python
# tests/app/test_clima.py
import pandas as pd

from app.clima import CLIMATE_VARIABLES, climate_by_trimestre


def _gdf():
    return pd.DataFrame(
        {
            "h3_index": ["a", "b"],
            "temp_media_q1": [18.0, 20.0],
            "temp_media_q2": [20.0, 22.0],
            "temp_media_q3": [24.0, 26.0],
            "temp_media_q4": [19.0, 21.0],
        }
    )


def test_climate_by_trimestre_averages_across_hexagons():
    result = climate_by_trimestre(_gdf(), "temp_media")
    values = dict(zip(result["trimestre"], result["valor"]))
    assert values["Q1"] == 19.0
    assert values["Q2"] == 21.0
    assert values["Q3"] == 25.0
    assert values["Q4"] == 20.0


def test_climate_by_trimestre_orders_q1_to_q4():
    result = climate_by_trimestre(_gdf(), "temp_media")
    assert result["trimestre"].tolist() == ["Q1", "Q2", "Q3", "Q4"]


def test_climate_variables_covers_expected_labels():
    assert set(CLIMATE_VARIABLES.keys()) == {"Temperatura", "Lluvia", "Viento", "Humedad"}
```

- [x] **Step 2: Run tests to verify they fail**

Ran → `ModuleNotFoundError: No module named 'app.clima'`, as expected.

- [x] **Step 3: Implement `app/clima.py`**

```python
# app/clima.py
import pandas as pd
import plotly.express as px
import streamlit as st

CLIMATE_VARIABLES = {
    "Temperatura": "temp_media",
    "Lluvia": "lluvia_mm",
    "Viento": "vel_viento_media",
    "Humedad": "humedad_media",
}

TRIMESTRES = ["Q1", "Q2", "Q3", "Q4"]


def climate_by_trimestre(gdf: pd.DataFrame, variable_prefix: str) -> pd.DataFrame:
    rows = []
    for i, trimestre in enumerate(TRIMESTRES, start=1):
        column = f"{variable_prefix}_q{i}"
        rows.append({"trimestre": trimestre, "valor": gdf[column].mean()})
    return pd.DataFrame(rows)


def render_clima_tab(gdf: pd.DataFrame) -> None:
    variable_label = st.selectbox("Variable climática", list(CLIMATE_VARIABLES.keys()))
    prefix = CLIMATE_VARIABLES[variable_label]

    result = climate_by_trimestre(gdf, prefix)
    fig = px.line(
        result,
        x="trimestre",
        y="valor",
        markers=True,
        title=f"{variable_label} media por trimestre",
    )
    fig.update_traces(line_color="#2a78d6")
    st.plotly_chart(fig, use_container_width=True)
```

- [x] **Step 4: Run tests to verify they pass**

Ran → PASS, 3/3.

- [x] **Step 5: Wire the tab into `app/main.py`**

1. Add `from app.clima import render_clima_tab` to the imports.
2. Extend the tabs line to include `"Clima"`:
   ```python
   tab_resumen, tab_mapa, tab_tabla, tab_rankings, tab_clima = st.tabs(
       ["Resumen", "Mapa", "Tabla", "Rankings", "Clima"]
   )
   ```
3. After the `with tab_rankings:` block, add:
   ```python
   with tab_clima:
       filtered_for_clima = filter_by_municipio(full_gdf, st.selectbox(
           "Municipio", ["Todos"] + list_municipios(full_gdf), key="clima_municipio"
       ))
       render_clima_tab(filtered_for_clima)
   ```

- [x] **Step 6: Manual visual verification**

Screenshotted via Playwright: "Temperatura" line chart (Todos los municipios) shows the expected seasonal shape — rising from Q1 (~13.5°) to a Q3 peak (~20.5°), then falling in Q4. No console errors.

- [x] **Step 7: Commit**

Committed as `7425427`.

---

### Task 4: `gold_municipio_master` dbt model

**Files:**
- Create: `dbt_project/models/gold/gold_municipio_master.sql`

**Interfaces:**
- Consumes: `{{ ref('silver_istac_anual') }}`, `{{ ref('silver_istac_mensual') }}` (both already exist and are populated), plus a `SELECT * FROM gold.gold_h3_master` read directly (not a dbt `ref`, since `gold_h3_master` is a *source table* dbt already built, referenced the same way `gold_sentimiento_h3.sql` references `gold_h3_master`'s upstream tables — via `{{ ref('...') }}` if it were a dbt model in this same project, which it is: `{{ ref('gold_h3_master') }}`).
- Produces (used by Task 5): `gold.gold_municipio_master` — one row per municipio (31 rows), columns: `municipio_cod`, `municipio`, `n_hexagonos`, `n_establecimientos_registro`, `n_plazas_registro`, `n_hoteles`, `n_vv`, `n_extrahoteleros`, `n_establecimientos_booking`, `rating_booking_medio`, `n_establecimientos_tripadvisor`, `rating_tripadvisor_medio`, `ndvi_medio`, `poblacion_total`, `poblacion_anio` (which ISTAC year the population figure is from), `paro_registrado`, `tasa_ocupacion_plazas`, `pernoctaciones`, `viajeros_entrados`, `ocupacion_periodo` (which ISTAC month the tourism figures are from).

Verified directly against the live DB before writing this task: `gold_h3_master.cod_municipio` and `silver_istac_anual`/`silver_istac_mensual.municipio_cod` are both 5-digit INE codes (`'38001'` etc.) and all 31 municipios join cleanly on equality — no code-mapping table needed. Annual ISTAC data currently goes up to 2025; monthly up to `2026-08`.

- [ ] **Step 1: Write the model**

```sql
-- dbt_project/models/gold/gold_municipio_master.sql
{{ config(
    materialized='table',
    tags=['gold', 'municipio'],
    indexes=[
      {'columns': ['municipio_cod'], 'unique': True}
    ]
) }}

/*
  Modelo Gold: gold_municipio_master
  Rollup a nivel municipio (31 filas) de gold_h3_master + las series ISTAC
  de poblacion (anual) y turismo/paro (mensual). Cada bloque ISTAC usa su
  ultimo periodo disponible por separado (poblacion y turismo no se
  actualizan con la misma cadencia), y ese periodo se expone en
  poblacion_anio / ocupacion_periodo para que el dashboard pueda mostrarlo
  junto al dato ("Poblacion (2025): ...").
*/

WITH h3_agg AS (
    SELECT
        cod_municipio AS municipio_cod,
        municipio,
        COUNT(*) AS n_hexagonos,
        SUM(n_establecimientos_registro) AS n_establecimientos_registro,
        SUM(n_plazas_registro) AS n_plazas_registro,
        SUM(n_hoteles) AS n_hoteles,
        SUM(n_vv) AS n_vv,
        SUM(n_extrahoteleros) AS n_extrahoteleros,
        SUM(n_establecimientos_booking) AS n_establecimientos_booking,
        ROUND(AVG(rating_booking_medio)::numeric, 2) AS rating_booking_medio,
        SUM(n_establecimientos_tripadvisor) AS n_establecimientos_tripadvisor,
        ROUND(AVG(rating_tripadvisor_medio)::numeric, 2) AS rating_tripadvisor_medio,
        ROUND(AVG(ndvi_medio)::numeric, 3) AS ndvi_medio
    FROM {{ ref('gold_h3_master') }}
    WHERE cod_municipio IS NOT NULL
    GROUP BY cod_municipio, municipio
),

istac_anual_ultimo AS (
    SELECT municipio_cod, anio AS poblacion_anio, poblacion_total
    FROM {{ ref('silver_istac_anual') }}
    WHERE anio = (SELECT MAX(anio) FROM {{ ref('silver_istac_anual') }})
),

istac_mensual_ultimo AS (
    SELECT
        municipio_cod,
        periodo_codigo AS ocupacion_periodo,
        pernoctaciones,
        viajeros_entrados,
        tasa_ocupacion_plazas,
        paro_registrado
    FROM {{ ref('silver_istac_mensual') }}
    WHERE periodo_codigo = (SELECT MAX(periodo_codigo) FROM {{ ref('silver_istac_mensual') }})
)

SELECT
    h.municipio_cod,
    h.municipio,
    h.n_hexagonos,
    h.n_establecimientos_registro,
    h.n_plazas_registro,
    h.n_hoteles,
    h.n_vv,
    h.n_extrahoteleros,
    h.n_establecimientos_booking,
    h.rating_booking_medio,
    h.n_establecimientos_tripadvisor,
    h.rating_tripadvisor_medio,
    h.ndvi_medio,
    ia.poblacion_total,
    ia.poblacion_anio,
    im.paro_registrado,
    im.tasa_ocupacion_plazas,
    im.pernoctaciones,
    im.viajeros_entrados,
    im.ocupacion_periodo
FROM h3_agg h
LEFT JOIN istac_anual_ultimo ia ON h.municipio_cod = ia.municipio_cod
LEFT JOIN istac_mensual_ultimo im ON h.municipio_cod = im.municipio_cod
ORDER BY h.municipio
```

`poblacion_total` (annual cadence) and `paro_registrado` (monthly cadence) come from different ISTAC series, which is why they're split across the two `istac_*_ultimo` CTEs rather than both living in `istac_anual_ultimo`.

- [ ] **Step 2: Run the model**

Run: `cd dbt_project && ../.venv/bin/python -m dbt run --select gold_municipio_master`
Expected: `Completed successfully`, 1 model built.

- [ ] **Step 3: Verify the row count and a spot-check row**

```bash
cat > /tmp/verify_municipio_master.py << 'EOF'
import os
from dotenv import load_dotenv
import psycopg2

load_dotenv("/Users/jorgetmn/Proyectos/AI_Dashboard_Core/.env", override=True)
conn = psycopg2.connect(
    host=os.getenv("AZURE_DB_HOST"), user=os.getenv("AZURE_DB_USER"),
    password=os.getenv("AZURE_DB_PASSWORD"), dbname=os.getenv("AZURE_DB_NAME"),
    port="5432", sslmode="require",
)
cur = conn.cursor()
cur.execute("SELECT count(*) FROM gold.gold_municipio_master")
print("Filas:", cur.fetchone())
cur.execute("SELECT * FROM gold.gold_municipio_master WHERE municipio = 'Adeje'")
print("Adeje:", cur.fetchone())
conn.close()
EOF
.venv/bin/python /tmp/verify_municipio_master.py
```

Expected: 31 filas, and the Adeje row has a non-null `poblacion_total` and `n_hexagonos > 0`.

- [ ] **Step 4: Commit**

```bash
git add dbt_project/models/gold/gold_municipio_master.sql
git commit -m "feat(dbt): add gold_municipio_master (population/paro/ocupacion by municipio)"
```

---

### Task 5: Municipios tab (`app/municipios.py`)

**Files:**
- Modify: `app/data.py` (add `load_municipio_master`)
- Create: `app/municipios.py`
- Modify: `app/main.py` (add the tab)
- Test: `tests/app/test_municipios.py`

**Interfaces:**
- Consumes: `app.detail_panel.format_kpi_value` (existing helper, Task from the v1 plan).
- Produces (used only by Task 5's own render wiring in `main.py`):
  - `app.data.load_municipio_master(_engine) -> pd.DataFrame`
  - `get_municipio_row(df: pd.DataFrame, municipio: str) -> pd.Series | None`
  - `render_municipios_tab(df: pd.DataFrame) -> None`

- [ ] **Step 1: Add the loader to `app/data.py`**

Add near the other `_QUERY` constants (after `ISOCRONAS_QUERY`):

```python
MUNICIPIO_MASTER_QUERY = "SELECT * FROM gold.gold_municipio_master"
```

Add near the other `load_*` functions:

```python
@st.cache_data
def load_municipio_master(_engine: Engine) -> pd.DataFrame:
    return pd.read_sql(MUNICIPIO_MASTER_QUERY, _engine)
```

- [ ] **Step 2: Write the failing tests for the pure helper**

```python
# tests/app/test_municipios.py
import pandas as pd

from app.municipios import get_municipio_row


def _df():
    return pd.DataFrame(
        {
            "municipio": ["Adeje", "Arona"],
            "poblacion_total": [50000, 80000],
            "poblacion_anio": [2025, 2025],
        }
    )


def test_get_municipio_row_returns_matching_row():
    row = get_municipio_row(_df(), "Adeje")
    assert row["poblacion_total"] == 50000


def test_get_municipio_row_returns_none_for_unknown_municipio():
    assert get_municipio_row(_df(), "No Existe") is None
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/app/test_municipios.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.municipios'`.

- [ ] **Step 4: Implement `app/municipios.py`**

```python
# app/municipios.py
import pandas as pd
import streamlit as st

from app.detail_panel import format_kpi_value

KPI_COLUMNS = [
    ("poblacion_total", "Población"),
    ("n_hexagonos", "Hexágonos analizados"),
    ("n_establecimientos_registro", "Alojamientos registrados"),
    ("n_plazas_registro", "Plazas registradas"),
    ("rating_booking_medio", "Rating Booking"),
    ("rating_tripadvisor_medio", "Rating TripAdvisor"),
    ("tasa_ocupacion_plazas", "Tasa ocupación plazas (%)"),
    ("paro_registrado", "Paro registrado"),
    ("pernoctaciones", "Pernoctaciones (último mes)"),
]


def get_municipio_row(df: pd.DataFrame, municipio: str) -> pd.Series | None:
    matches = df.loc[df["municipio"] == municipio]
    if matches.empty:
        return None
    return matches.iloc[0]


def render_municipios_tab(df: pd.DataFrame) -> None:
    municipio = st.selectbox("Municipio", sorted(df["municipio"].dropna().unique().tolist()))
    row = get_municipio_row(df, municipio)
    if row is None:
        st.warning("No hay datos para este municipio.")
        return

    st.caption(
        f"Población de {int(row['poblacion_anio'])} · "
        f"Ocupación/paro de {row['ocupacion_periodo']}"
    )
    cols = st.columns(3)
    for i, (column, label) in enumerate(KPI_COLUMNS):
        cols[i % 3].metric(label, format_kpi_value(row.get(column)))
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/app/test_municipios.py -v`
Expected: PASS (2 tests).

- [ ] **Step 6: Wire the tab into `app/main.py`**

1. Add `load_municipio_master` to the `app.data` import list.
2. Add `from app.municipios import render_municipios_tab` to the imports.
3. Load the data near the other `load_*` calls:
   ```python
   municipio_master = load_municipio_master(engine)
   ```
4. Extend the tabs line to include `"Municipios"`:
   ```python
   tab_resumen, tab_mapa, tab_tabla, tab_rankings, tab_clima, tab_municipios = st.tabs(
       ["Resumen", "Mapa", "Tabla", "Rankings", "Clima", "Municipios"]
   )
   ```
5. After the `with tab_clima:` block, add:
   ```python
   with tab_municipios:
       render_municipios_tab(municipio_master)
   ```

- [ ] **Step 7: Manual visual verification**

Run the app, open "Municipios", switch between a few municipios, and confirm population/paro/ocupación numbers look plausible (e.g. Santa Cruz de Tenerife and San Cristóbal de La Laguna should have the largest populations on the island).

- [ ] **Step 8: Commit**

```bash
git add app/data.py app/municipios.py app/main.py tests/app/test_municipios.py
git commit -m "feat: add Municipios tab (poblacion/paro/ocupacion from gold_municipio_master)"
```

---

### Task 6: Alojamiento y reputación tab (`app/alojamiento.py`)

**Files:**
- Create: `app/alojamiento.py`
- Modify: `app/main.py` (add the tab)
- Test: `tests/app/test_alojamiento.py`

**Interfaces:**
- Consumes: nothing from earlier tasks. Reads `full_gdf` (same object already loaded in `main.py` for the other tabs) — no new query needed.
- Produces (used only by Task 6's own render wiring in `main.py`):
  - `accommodation_breakdown(gdf: pd.DataFrame) -> pd.DataFrame` — tidy `[tipo, cantidad]`.
  - `reputation_summary(gdf: pd.DataFrame) -> dict`
  - `render_alojamiento_tab(gdf: pd.DataFrame) -> None`

- [ ] **Step 1: Write the failing tests**

```python
# tests/app/test_alojamiento.py
import pandas as pd

from app.alojamiento import accommodation_breakdown, reputation_summary


def _gdf():
    return pd.DataFrame(
        {
            "n_hoteles": [2, 1],
            "n_vv": [5, 3],
            "n_extrahoteleros": [0, 1],
            "rating_booking_medio": [4.5, 3.5],
            "rating_tripadvisor_medio": [4.0, None],
            "n_reviews_booking": [100, 50],
        }
    )


def test_accommodation_breakdown_sums_each_type():
    result = accommodation_breakdown(_gdf())
    counts = dict(zip(result["tipo"], result["cantidad"]))
    assert counts == {"Hoteles": 3, "Viviendas vacacionales": 8, "Extrahoteleros": 1}


def test_reputation_summary_averages_ratings_ignoring_nulls():
    summary = reputation_summary(_gdf())
    assert summary["rating_booking_medio"] == 4.0
    assert summary["rating_tripadvisor_medio"] == 4.0
    assert summary["total_reviews_booking"] == 150
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/app/test_alojamiento.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.alojamiento'`.

- [ ] **Step 3: Implement `app/alojamiento.py`**

```python
# app/alojamiento.py
import pandas as pd
import plotly.express as px
import streamlit as st

ACCOMMODATION_TYPES = [
    ("n_hoteles", "Hoteles"),
    ("n_vv", "Viviendas vacacionales"),
    ("n_extrahoteleros", "Extrahoteleros"),
]


def accommodation_breakdown(gdf: pd.DataFrame) -> pd.DataFrame:
    rows = [{"tipo": label, "cantidad": int(gdf[column].sum())} for column, label in ACCOMMODATION_TYPES]
    return pd.DataFrame(rows)


def reputation_summary(gdf: pd.DataFrame) -> dict:
    return {
        "rating_booking_medio": round(gdf["rating_booking_medio"].mean(), 2),
        "rating_tripadvisor_medio": round(gdf["rating_tripadvisor_medio"].mean(), 2),
        "total_reviews_booking": int(gdf["n_reviews_booking"].sum()),
    }


def render_alojamiento_tab(gdf: pd.DataFrame) -> None:
    breakdown = accommodation_breakdown(gdf)
    summary = reputation_summary(gdf)

    col1, col2, col3 = st.columns(3)
    col1.metric("Rating medio Booking", summary["rating_booking_medio"])
    col2.metric("Rating medio TripAdvisor", summary["rating_tripadvisor_medio"])
    col3.metric("Reseñas Booking totales", summary["total_reviews_booking"])

    fig = px.pie(
        breakdown,
        names="tipo",
        values="cantidad",
        title="Distribución del tipo de alojamiento",
        color_discrete_sequence=["#2a78d6", "#eb6834", "#898781"],
    )
    st.plotly_chart(fig, use_container_width=True)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/app/test_alojamiento.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Wire the tab into `app/main.py`**

1. Add `from app.alojamiento import render_alojamiento_tab` to the imports.
2. Extend the tabs line to include `"Alojamiento"`:
   ```python
   tab_resumen, tab_mapa, tab_tabla, tab_rankings, tab_clima, tab_municipios, tab_alojamiento = st.tabs(
       ["Resumen", "Mapa", "Tabla", "Rankings", "Clima", "Municipios", "Alojamiento"]
   )
   ```
3. After the `with tab_municipios:` block, add:
   ```python
   with tab_alojamiento:
       filtered_for_alojamiento = filter_by_municipio(full_gdf, st.selectbox(
           "Municipio", ["Todos"] + list_municipios(full_gdf), key="alojamiento_municipio"
       ))
       render_alojamiento_tab(filtered_for_alojamiento)
   ```

- [ ] **Step 6: Manual visual verification**

Run the app, open "Alojamiento", confirm the pie chart and KPI cards render and update when the municipio filter changes.

- [ ] **Step 7: Run the full test suite one last time**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: all tests from this plan plus the pre-existing v1 tests PASS.

- [ ] **Step 8: Commit**

```bash
git add app/alojamiento.py app/main.py tests/app/test_alojamiento.py
git commit -m "feat: add Alojamiento tab (tipo de alojamiento + reputacion Booking/TripAdvisor)"
```

---

## Self-Review Notes

- **Spec coverage:** basemap satélite + tema claro → Task 1. Rankings ("zonas con más vegetación", "zonas más turísticas", medias) → Task 2. Clima trimestral → Task 3. Población/paro/ocupación por municipio → Tasks 4–5 (new dbt model, verified against real DB join keys and current data periods before writing the SQL). Alojamiento y reputación → Task 6.
- **Placeholder scan:** no TBD/TODO. The one spot with real drafting risk (a `:=` typo in the first draft of `gold_municipio_master.sql`) is called out explicitly with the exact fix, not left as an exercise.
- **Type consistency:** `full_gdf` (from `merge_h3_data` + `merge_accesibilidad`, already built in `main.py`) is reused as-is by Tasks 2, 3, 6 — none of them re-query the DB. `municipio_master` (Task 5) is a separate, smaller `pd.DataFrame` keyed by `municipio`, not merged into `full_gdf` (different grain: municipio vs. hexágono), consistent with how `gold_h3_master` and `gold_municipio_master` are two separate physical tables at two different grains.
- **Out of scope (explicitly, not an oversight):** the "Sentimiento" tab stays blocked on `gold.nlp_sentimiento_resenas` / `nlp_aspectos_resenas` / `aspecto_traducciones` not existing yet in the new Azure account (per the earlier conversation) — not part of this plan. If/when those land, `gold_sentimiento_h3` (already a dbt model in the repo) just needs `dbt run`, and a `Sentimiento` tab would follow the same pattern as this plan's other tabs.

---

**Plan complete and saved to `docs/superpowers/plans/2026-09-09-dashboard-v2-tabs-and-theme.md`. Two execution options:**

1. **Subagent-Driven** — I dispatch a fresh subagent per task, review between tasks, fast iteration, but you only see each task's result once it's done.
2. **Inline Execution (recomendado para esto)** — Ejecutamos en esta misma sesión, tarea a tarea, con checkpoints — encaja con lo que pediste de ir visualizando cada pieza (`streamlit run`) a medida que se construye, y puedo pedirte imágenes/decisiones puntuales (como el token de Mapbox) justo cuando hagan falta.

¿Cuál prefieres?
