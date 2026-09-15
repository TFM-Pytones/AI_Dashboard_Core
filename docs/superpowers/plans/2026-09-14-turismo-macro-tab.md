# Turismo Macro Tab Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a new "✈️ Turismo" tab surfacing island-level tourism macro data that isn't shown anywhere in the dashboard yet: hotel-sector arrivals/overnight-stays/occupancy for the 6 municipios recognized as official tourist hubs (`gold.gold_turismo_hotelero_anual`/`_mensual`), a monthly seasonality view, and airport passenger traffic for both Tenerife airports (`gold.gold_aena_pasajeros`).

**Architecture:** Same one-file-per-tab pattern as every other tab in `app/`. Pure pandas functions covered by pytest, a `render_turismo_tab()` wired into `app/main.py`. No new dbt models — all three gold tables already exist and are populated. Reuses the `st.metric(..., delta=...)` YoY pattern introduced in the Municipios tab plan and the "selectbox métrica → chart" pattern from the Clima tab plan; `format_yoy_delta` is duplicated locally in this tab's file rather than imported from `app.municipios`, matching this repo's existing convention of each tab file being self-contained (e.g. the `#2a78d6` color literal is duplicated across `rankings.py`, `clima.py`, `alojamiento.py`, `temas.py`, `municipios.py` rather than shared).

**Tech Stack:** Python 3.13, Streamlit ≥1.42, Plotly Express, pandas, SQLAlchemy, pytest — no new dependencies.

**Spec:** No separate spec doc — bounded addition of a new tab following the repo's established file-per-tab pattern, design-reviewed in chat. Extends `docs/superpowers/plans/2026-09-14-temas-opinion-tab.md` and `docs/superpowers/plans/2026-09-14-municipios-yoy-enrichment.md`'s established pattern.

## Global Constraints

- DB access reads `AZURE_DB_URL` from `.env` via `python-dotenv` (`app/data.py`'s existing `get_engine()`) — no change to that pattern.
- Every command in this plan is run from the `AI_Dashboard_Core/` repo root using `.venv/bin/python -m <tool>`.
- Color choices reuse the palette already established in `app/color_scales.py` / used across other tabs: blue `#2a78d6`, orange `#eb6834` — no new palette.
- `st.plotly_chart(...)` calls use `use_container_width=True` (the convention in the most recently added tabs).
- No artificial try/except: a DB failure surfaces as-is. Missing values render as "—" via the existing `app.detail_panel.format_kpi_value` — never silently coerced to 0.
- `gold.gold_turismo_hotelero_anual`/`_mensual` and `gold.gold_aena_pasajeros` are read directly (`SELECT *`, no dbt model needed) — confirmed live on 2026-09-14: hotelero_anual has 24 rows (6 municipios × 4 years, 2022-2025), hotelero_mensual has 330 rows (6 municipios × ~55 months, 2022-01 to 2026-07-ish), aena_pasajeros has 110 rows (2 airports × 55 months, 2022-01 to 2026-07).
- `gold_turismo_hotelero_anual`/`_mensual` only cover **6 of the 31 municipios** — the ones officially recognized as tourist hubs (`polo_turistico`): Adeje, Arona, Granadilla de Abona, Santiago del Teide (→ Polo Sur), Puerto de la Cruz (→ Polo Norte), Santa Cruz de Tenerife (→ Polo Metropolitano). The tab's municipio selector is built from this table's own municipio list (6 options), not `gold_h3_master`'s 31 — matching the established per-tab-owns-its-selector-list convention already used by `app/municipios.py` and `app/temas.py`.

---

## File Structure

```
app/
├── data.py     # MODIFY — add load_turismo_hotelero_anual(), load_turismo_hotelero_mensual(), load_aena_pasajeros()
├── turismo.py  # NEW — tab helpers + render_turismo_tab()
└── main.py     # MODIFY — wire in the new tab

tests/app/
└── test_turismo.py  # NEW
```

---

### Task 1: Data loaders (`app/data.py`)

**Files:**
- Modify: `app/data.py`

**Interfaces:**
- Consumes: nothing new.
- Produces (used by Task 3's `main.py` wiring): `load_turismo_hotelero_anual(_engine) -> pd.DataFrame`, `load_turismo_hotelero_mensual(_engine) -> pd.DataFrame`, `load_aena_pasajeros(_engine) -> pd.DataFrame`.

- [x] **Step 1: Add the queries and loaders**

Add near the other query constants (after `MUNICIPIO_EMPLEO_QUERY`):

```python
TURISMO_HOTELERO_ANUAL_QUERY = "SELECT * FROM gold.gold_turismo_hotelero_anual"
TURISMO_HOTELERO_MENSUAL_QUERY = "SELECT * FROM gold.gold_turismo_hotelero_mensual"
AENA_PASAJEROS_QUERY = "SELECT * FROM gold.gold_aena_pasajeros"
```

Add near the other `load_*` functions (after `load_municipio_empleo`):

```python
@st.cache_data
def load_turismo_hotelero_anual(_engine: Engine) -> pd.DataFrame:
    return pd.read_sql(TURISMO_HOTELERO_ANUAL_QUERY, _engine)


@st.cache_data
def load_turismo_hotelero_mensual(_engine: Engine) -> pd.DataFrame:
    return pd.read_sql(TURISMO_HOTELERO_MENSUAL_QUERY, _engine)


@st.cache_data
def load_aena_pasajeros(_engine: Engine) -> pd.DataFrame:
    return pd.read_sql(AENA_PASAJEROS_QUERY, _engine)
```

(Thin `pd.read_sql` wrappers like every other `load_*` in this file — no dedicated unit test, matching this repo's established convention.)

- [x] **Step 2: Run the full test suite to confirm nothing broke**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: PASS, 111/111 (unchanged — this task only adds new, unreferenced functions).

- [x] **Step 3: Commit**

```bash
git add app/data.py
git commit -m "feat(data): add turismo_hotelero_anual/mensual and aena_pasajeros loaders"
```

---

### Task 2: Turismo tab helpers (`app/turismo.py`)

**Files:**
- Create: `app/turismo.py`
- Test: `tests/app/test_turismo.py`

**Interfaces:**
- Consumes: `app.detail_panel.format_kpi_value` (existing helper, reused as-is).
- Produces (used only by Task 3's wiring in `main.py`): `render_turismo_tab(hotelero_anual_df: pd.DataFrame, hotelero_mensual_df: pd.DataFrame, aena_df: pd.DataFrame) -> None`.

- [x] **Step 1: Write the failing tests**

```python
# tests/app/test_turismo.py
import pandas as pd

from app.turismo import (
    aena_series,
    estacionalidad_by_mes,
    format_yoy_delta,
    get_hotelero_anual_row,
    get_latest_aena_row,
)


def _hotelero_anual_df():
    return pd.DataFrame(
        [
            {
                "municipio": "Adeje", "polo_turistico": "Polo Sur", "anio": 2024,
                "viajeros_entrados_total": 1938929.0, "crec_viajeros_yoy_pct": 2.7,
                "pernoctaciones_total": 13840017.0, "crec_pernoctaciones_yoy_pct": 1.8,
                "ocupacion_media_plazas": 81.3, "estancia_media_hotel_dias": 7.14,
            },
            {
                "municipio": "Adeje", "polo_turistico": "Polo Sur", "anio": 2025,
                "viajeros_entrados_total": 1858237.0, "crec_viajeros_yoy_pct": -4.2,
                "pernoctaciones_total": 13113733.0, "crec_pernoctaciones_yoy_pct": -5.2,
                "ocupacion_media_plazas": 79.5, "estancia_media_hotel_dias": 7.06,
            },
        ]
    )


def test_get_hotelero_anual_row_returns_matching_row():
    row = get_hotelero_anual_row(_hotelero_anual_df(), "Adeje", 2025)
    assert row["pernoctaciones_total"] == 13113733.0


def test_get_hotelero_anual_row_returns_none_when_year_missing():
    assert get_hotelero_anual_row(_hotelero_anual_df(), "Adeje", 2020) is None


def test_format_yoy_delta_formats_with_sign_and_percent():
    assert format_yoy_delta(-4.2) == "-4.2%"
    assert format_yoy_delta(2.7) == "+2.7%"


def test_format_yoy_delta_returns_none_for_missing_value():
    assert format_yoy_delta(None) is None
    assert format_yoy_delta(float("nan")) is None


def _hotelero_mensual_df():
    return pd.DataFrame(
        [
            {"municipio": "Adeje", "mes": 1, "pernoctaciones": 900000.0},
            {"municipio": "Adeje", "mes": 1, "pernoctaciones": 1000000.0},
            {"municipio": "Adeje", "mes": 7, "pernoctaciones": 1200000.0},
            {"municipio": "Arona", "mes": 1, "pernoctaciones": 500000.0},
        ]
    )


def test_estacionalidad_by_mes_averages_across_years():
    result = estacionalidad_by_mes(_hotelero_mensual_df(), "Adeje", "pernoctaciones")
    row = result.loc[result["mes"] == 1].iloc[0]
    assert row["valor"] == 950000.0


def test_estacionalidad_by_mes_sorts_by_month_and_labels_in_spanish():
    result = estacionalidad_by_mes(_hotelero_mensual_df(), "Adeje", "pernoctaciones")
    assert result["mes"].tolist() == [1, 7]
    assert result["mes_label"].tolist() == ["Ene", "Jul"]


def _aena_df():
    return pd.DataFrame(
        [
            {"aeropuerto_codigo": "TFS", "periodo": "2026-05", "pasajeros": 938372.0, "operaciones": 6429.0},
            {"aeropuerto_codigo": "TFS", "periodo": "2026-06", "pasajeros": 935707.0, "operaciones": 6325.0},
            {"aeropuerto_codigo": "TFN", "periodo": "2026-06", "pasajeros": 300000.0, "operaciones": 3000.0},
        ]
    )


def test_get_latest_aena_row_picks_latest_period_for_airport():
    row = get_latest_aena_row(_aena_df(), "TFS")
    assert row["periodo"] == "2026-06"


def test_get_latest_aena_row_returns_none_for_unknown_airport():
    assert get_latest_aena_row(_aena_df(), "XXX") is None


def test_aena_series_filters_and_sorts_by_periodo():
    result = aena_series(_aena_df(), "TFS")
    assert result["periodo"].tolist() == ["2026-05", "2026-06"]
```

- [x] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/app/test_turismo.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.turismo'`.

- [x] **Step 3: Implement `app/turismo.py`**

```python
# app/turismo.py
import math

import pandas as pd
import plotly.express as px
import streamlit as st

from app.detail_panel import format_kpi_value

# (value_column, yoy_delta_column | None, label)
HOTELERO_KPI_COLUMNS = [
    ("viajeros_entrados_total", "crec_viajeros_yoy_pct", "Viajeros entrados"),
    ("pernoctaciones_total", "crec_pernoctaciones_yoy_pct", "Pernoctaciones"),
    ("ocupacion_media_plazas", None, "Ocupación media plazas (%)"),
    ("estancia_media_hotel_dias", None, "Estancia media (días)"),
]

ESTACIONALIDAD_METRICS = {
    "Pernoctaciones": "pernoctaciones",
    "Viajeros entrados": "viajeros_entrados",
    "Ocupación plazas (%)": "tasa_ocupacion_plazas",
    "Estancia media (días)": "estancia_media_hotel_dias",
}

MES_LABELS = {
    1: "Ene", 2: "Feb", 3: "Mar", 4: "Abr", 5: "May", 6: "Jun",
    7: "Jul", 8: "Ago", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dic",
}
MES_ORDER = [MES_LABELS[m] for m in range(1, 13)]

AENA_KPI_COLUMNS = [
    ("pasajeros", "Pasajeros"),
    ("operaciones", "Operaciones"),
    ("pasajeros_por_operacion", "Pasajeros por operación"),
]


def format_yoy_delta(value) -> str | None:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    return f"{value:+.1f}%"


def get_hotelero_anual_row(df: pd.DataFrame, municipio: str, anio: int) -> pd.Series | None:
    matches = df.loc[(df["municipio"] == municipio) & (df["anio"] == anio)]
    if matches.empty:
        return None
    return matches.iloc[0]


def estacionalidad_by_mes(df: pd.DataFrame, municipio: str, column: str) -> pd.DataFrame:
    subset = df.loc[df["municipio"] == municipio, ["mes", column]]
    result = subset.groupby("mes", as_index=False)[column].mean()
    result = result.rename(columns={column: "valor"}).sort_values("mes")
    result["mes_label"] = result["mes"].map(MES_LABELS)
    return result


def get_latest_aena_row(df: pd.DataFrame, aeropuerto_codigo: str) -> pd.Series | None:
    matches = df.loc[df["aeropuerto_codigo"] == aeropuerto_codigo]
    if matches.empty:
        return None
    return matches.sort_values("periodo").iloc[-1]


def aena_series(df: pd.DataFrame, aeropuerto_codigo: str) -> pd.DataFrame:
    return df.loc[df["aeropuerto_codigo"] == aeropuerto_codigo].sort_values("periodo")


def render_turismo_tab(
    hotelero_anual_df: pd.DataFrame,
    hotelero_mensual_df: pd.DataFrame,
    aena_df: pd.DataFrame,
) -> None:
    st.subheader("Turismo hotelero por polo turístico")
    municipios = sorted(hotelero_anual_df["municipio"].dropna().unique().tolist())
    col1, col2 = st.columns([2, 1])
    municipio = col1.selectbox("Municipio", municipios, key="turismo_municipio")
    years = sorted(
        hotelero_anual_df.loc[hotelero_anual_df["municipio"] == municipio, "anio"].unique().tolist()
    )
    anio = col2.selectbox("Año", years, index=len(years) - 1, key="turismo_anio")

    anual_row = get_hotelero_anual_row(hotelero_anual_df, municipio, anio)
    if anual_row is None:
        st.info("No hay datos hoteleros para este municipio en el año seleccionado.")
    else:
        st.caption(anual_row["polo_turistico"])
        cols = st.columns(4)
        for i, (column, delta_column, label) in enumerate(HOTELERO_KPI_COLUMNS):
            delta = format_yoy_delta(anual_row.get(delta_column)) if delta_column else None
            cols[i % 4].metric(label, format_kpi_value(anual_row.get(column)), delta=delta)

    st.subheader("Estacionalidad")
    metrica_label = st.selectbox(
        "Métrica", list(ESTACIONALIDAD_METRICS.keys()), key="turismo_estacionalidad_metrica"
    )
    serie = estacionalidad_by_mes(hotelero_mensual_df, municipio, ESTACIONALIDAD_METRICS[metrica_label])
    fig = px.bar(
        serie,
        x="mes_label",
        y="valor",
        category_orders={"mes_label": MES_ORDER},
        title=f"{metrica_label} media por mes — {municipio}",
    )
    fig.update_traces(marker_color="#2a78d6")
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Tráfico aéreo")
    aeropuertos = sorted(aena_df["aeropuerto_nombre"].dropna().unique().tolist())
    aeropuerto_nombre = st.selectbox("Aeropuerto", aeropuertos, key="turismo_aeropuerto")
    codigo = aena_df.loc[aena_df["aeropuerto_nombre"] == aeropuerto_nombre, "aeropuerto_codigo"].iloc[0]

    latest_row = get_latest_aena_row(aena_df, codigo)
    if latest_row is not None:
        st.caption(f"Último dato: {latest_row['periodo']}")
        cols = st.columns(3)
        for i, (column, label) in enumerate(AENA_KPI_COLUMNS):
            cols[i].metric(label, format_kpi_value(latest_row.get(column)))

    serie_aena = aena_series(aena_df, codigo)
    fig_aena = px.line(
        serie_aena, x="periodo", y="pasajeros", title=f"Pasajeros mensuales — {aeropuerto_nombre}"
    )
    fig_aena.update_traces(line_color="#eb6834")
    st.plotly_chart(fig_aena, use_container_width=True)
```

- [x] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/app/test_turismo.py -v`
Expected: PASS, 9/9.

- [x] **Step 5: Commit**

```bash
git add app/turismo.py tests/app/test_turismo.py
git commit -m "feat: add Turismo tab (hotelero por polo, estacionalidad, tráfico aéreo)"
```

---

### Task 3: Wire into `app/main.py` + manual verification

**Files:**
- Modify: `app/main.py`

**Interfaces:**
- Consumes: `load_turismo_hotelero_anual`, `load_turismo_hotelero_mensual`, `load_aena_pasajeros` (Task 1), `render_turismo_tab` (Task 2).
- Produces: nothing further downstream — this is the last task.

- [x] **Step 1: Update the imports**

Change the `from app.data import (...)` block to add the three new loaders in alphabetical position:

```python
from app.data import (
    filter_by_municipio,
    get_engine,
    list_municipios,
    load_accesibilidad,
    load_aena_pasajeros,
    load_h3_master,
    load_isocronas,
    load_municipio_anual,
    load_municipio_empleo,
    load_municipio_master,
    load_nlp_chunks,
    load_sentimiento,
    load_topicos_municipio,
    load_turismo_hotelero_anual,
    load_turismo_hotelero_mensual,
    merge_accesibilidad,
    merge_h3_data,
)
```

Add this import line right after `from app.temas import render_temas_tab`:

```python
from app.turismo import render_turismo_tab
```

- [x] **Step 2: Load the new data**

Change this block:

```python
topicos_municipio = load_topicos_municipio(engine)
nlp_chunks = load_nlp_chunks(engine)
```

to:

```python
topicos_municipio = load_topicos_municipio(engine)
nlp_chunks = load_nlp_chunks(engine)
turismo_hotelero_anual = load_turismo_hotelero_anual(engine)
turismo_hotelero_mensual = load_turismo_hotelero_mensual(engine)
aena_pasajeros = load_aena_pasajeros(engine)
```

- [x] **Step 3: Add the tab**

Change the tabs line to add `tab_turismo` / `"✈️ Turismo"`:

```python
tab_resumen, tab_mapa, tab_tabla, tab_rankings, tab_clima, tab_municipios, tab_alojamiento, tab_temas, tab_turismo = st.tabs(
    [
        "📊 Resumen",
        "🗺️ Mapa",
        "📋 Tabla",
        "🏆 Rankings",
        "🌡️ Clima",
        "🏛️ Municipios",
        "🏨 Alojamiento",
        "💬 Temas",
        "✈️ Turismo",
    ]
)
```

Add this block right after the existing `with tab_temas:` block, at the end of the file:

```python
with tab_turismo:
    render_turismo_tab(turismo_hotelero_anual, turismo_hotelero_mensual, aena_pasajeros)
```

- [x] **Step 4: Run the full test suite**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: PASS, all tests (111 before this plan + 9 new = 120).

- [x] **Step 5: Manual visual verification**

Start the app: `.venv/bin/python -m streamlit run app/main.py --server.headless true --server.port 8501`

Using Playwright + headless Chromium, load the running app, click the "✈️ Turismo" tab, and screenshot it. Confirm by looking at the resulting image, not by assuming:

1. Municipio selector shows exactly 6 options (Adeje, Arona, Granadilla de Abona, Puerto de la Cruz, Santa Cruz de Tenerife, Santiago del Teide) — confirms the tab correctly draws its own municipio list from the hotelero table, not the 31-municipio list used elsewhere.
2. Selecting a municipio shows its `polo_turistico` as a caption and KPI cards with YoY delta badges on Viajeros entrados / Pernoctaciones.
3. The "Estacionalidad" bar chart renders with months in calendar order (Ene → Dic, not alphabetical) and changes when a different métrica is picked.
4. Selecting an aeropuerto shows KPI cards for the latest available month and a line chart of pasajeros spanning 2022-2026 with a visible seasonal pattern.
5. No browser console errors.

Verified against the actually running app: municipio dropdown listed exactly `['Adeje', 'Arona', 'Granadilla de Abona', 'Puerto de la Cruz', 'Santa Cruz de Tenerife', 'Santiago del Teide']` (6, confirmed programmatically, not just visually). Default view (Adeje, año 2025, the latest available): caption "Polo Sur", Viajeros entrados 1858237.0 with a red "↓ -4.2%" badge, Pernoctaciones 13113733.0 with a red "↓ -5.2%" badge, Ocupación media plazas 79.5 and Estancia media 7.1 with no badge (as expected, no YoY column for either). "Estacionalidad" bar chart ("Pernoctaciones media por mes — Adeje") rendered in correct calendar order Ene→Dic (not alphabetical — confirms `category_orders` worked) with a clear real-world seasonal peak in August (~1.25M) tapering into spring lows. "Tráfico aéreo" defaulted to "Tenerife Norte - Ciudad de La Laguna", caption "Último dato: 2026-07", KPIs Pasajeros 706962.0 / Operaciones 8094.0 / Pasajeros por operación 87.3, and a line chart spanning Jan 2022 → Jul 2026 showing a clear upward trend with visible seasonal oscillation. Zero browser console errors across all screenshots.

- [x] **Step 6: Commit**

```bash
git add app/main.py
git commit -m "feat: wire the Turismo tab into the dashboard"
```

---

## Self-Review Notes

- **Spec coverage:** hotel-sector KPIs with YoY → Task 2's `HOTELERO_KPI_COLUMNS` + `format_yoy_delta`. Seasonality view → Task 2's `estacionalidad_by_mes` + the "Estacionalidad" bar chart (calendar-ordered via `category_orders`, not alphabetical). Airport passenger traffic and trend → Task 2's `get_latest_aena_row`/`aena_series` + the "Tráfico aéreo" section.
- **Placeholder scan:** no TBD/TODO. Full code given for every step.
- **Type consistency:** `render_turismo_tab(hotelero_anual_df, hotelero_mensual_df, aena_df)` (Task 2) is called exactly as `render_turismo_tab(turismo_hotelero_anual, turismo_hotelero_mensual, aena_pasajeros)` in Task 3 — same three positional arguments, same order.
- **Out of scope (explicitly, not an oversight):** the tab does not attempt to reconcile or merge `gold_turismo_hotelero_*`'s 6-municipio grain with the rest of the dashboard's 31-municipio grain (e.g. no attempt to show "N/A" placeholders for the other 25 municipios) — it's a genuinely different, coarser-grained dataset (official tourist hubs only) and is presented as its own self-contained section, consistent with how `app/temas.py` also owns its own municipio list independent of `gold_h3_master`'s.
