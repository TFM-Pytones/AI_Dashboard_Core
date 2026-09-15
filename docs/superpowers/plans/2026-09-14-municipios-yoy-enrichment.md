# Municipios Tab YoY Enrichment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Municipios tab's current data source (`silver.silver_istac_anual`/`silver.silver_istac_mensual`, both carrying documented data-quality bugs and used nowhere else in the app) with two purpose-built gold tables (`gold.gold_municipio_anual`, `gold.gold_municipio_empleo`) that already have year-over-year growth computed, and add a multi-year trend chart and an employment-type breakdown that weren't possible before.

**Architecture:** Same one-file-per-tab pattern as the rest of `app/`. `app/municipios.py` is rewritten (its pure functions and `render_municipios_tab` change signature and behavior, but the file's role in the app is unchanged), `app/data.py` swaps two loaders for two others, `app/main.py`'s wiring changes to pass the new dataframes through. No new architecture, no new dependencies. `st.metric`'s built-in `delta` parameter (not used anywhere else in this app yet) is the natural fit for displaying the new YoY percentages.

**Tech Stack:** Python 3.13, Streamlit ≥1.42, Plotly Express, pandas, SQLAlchemy, pytest — no new dependencies.

**Spec:** No separate spec doc — bounded extension of an existing tab, design-reviewed in chat (swaps the tab's data source and adds two sections; no new subsystem, no new cross-component interface). Extends `docs/superpowers/plans/2026-09-09-dashboard-v2-tabs-and-theme.md`'s and `docs/superpowers/plans/2026-09-14-temas-opinion-tab.md`'s established pattern.

## Global Constraints

- DB access reads `AZURE_DB_URL` from `.env` via `python-dotenv` (`app/data.py`'s existing `get_engine()`) — no change to that pattern.
- Every command in this plan is run from the `AI_Dashboard_Core/` repo root using `.venv/bin/python -m <tool>`.
- Color choices reuse the palette already established in `app/color_scales.py` / used across other tabs: blue `#2a78d6`, orange `#eb6834` — no new palette.
- `st.plotly_chart(...)` calls use `use_container_width=True` (the convention in the most recently added tabs, `app/alojamiento.py` and `app/temas.py`).
- No artificial try/except: a DB failure surfaces as-is. Missing values (a municipio/año combination with no row, or a `None`/`NaN` KPI value) render as "—" via the existing `app.detail_panel.format_kpi_value` — never silently coerced to 0.
- `gold.gold_municipio_anual` and `gold.gold_municipio_empleo` are read directly (`SELECT *`, no dbt model needed — both already exist and are populated, confirmed live on 2026-09-14: 155 rows / 31 municipios × years 2022-2026, and 558 rows / 31 municipios × quarters respectively).
- `silver.silver_istac_anual` and `silver.silver_istac_mensual` are used **nowhere else** in this app besides the Municipios tab (confirmed by `grep -rn "istac_anual\|istac_mensual" app/ tests/` on 2026-09-14) — safe to remove their loaders and queries entirely rather than leave them as dead code.

---

## File Structure

```
app/
├── data.py       # MODIFY — remove load_istac_anual/load_istac_mensual, add load_municipio_anual()/load_municipio_empleo()
├── municipios.py # REWRITE — new pure functions + render_municipios_tab() with new signature
└── main.py       # MODIFY — wire the new loaders/dataframes through

tests/app/
└── test_municipios.py  # REWRITE — cover the new municipios.py functions
```

---

### Task 1: Data loaders (`app/data.py`)

**Files:**
- Modify: `app/data.py`

**Interfaces:**
- Consumes: nothing new.
- Produces (used by Task 3's `main.py` wiring): `load_municipio_anual(_engine) -> pd.DataFrame`, `load_municipio_empleo(_engine) -> pd.DataFrame`.
- Removes: `ISTAC_ANUAL_QUERY`, `ISTAC_MENSUAL_QUERY`, `load_istac_anual`, `load_istac_mensual` (no longer referenced by anything after Task 3).

- [x] **Step 1: Replace the ISTAC queries and loaders with the new gold ones**

In `app/data.py`, replace this block:

```python
ISTAC_ANUAL_QUERY = "SELECT * FROM silver.silver_istac_anual"
ISTAC_MENSUAL_QUERY = "SELECT * FROM silver.silver_istac_mensual"
```

with:

```python
MUNICIPIO_ANUAL_QUERY = "SELECT * FROM gold.gold_municipio_anual"
MUNICIPIO_EMPLEO_QUERY = "SELECT * FROM gold.gold_municipio_empleo"
```

Then replace this block:

```python
@st.cache_data
def load_istac_anual(_engine: Engine) -> pd.DataFrame:
    return pd.read_sql(ISTAC_ANUAL_QUERY, _engine)


@st.cache_data
def load_istac_mensual(_engine: Engine) -> pd.DataFrame:
    return pd.read_sql(ISTAC_MENSUAL_QUERY, _engine)
```

with:

```python
@st.cache_data
def load_municipio_anual(_engine: Engine) -> pd.DataFrame:
    return pd.read_sql(MUNICIPIO_ANUAL_QUERY, _engine)


@st.cache_data
def load_municipio_empleo(_engine: Engine) -> pd.DataFrame:
    return pd.read_sql(MUNICIPIO_EMPLEO_QUERY, _engine)
```

(These are thin `pd.read_sql` wrappers like every other `load_*` in this file — per this repo's established convention, they have no dedicated unit test; `app/data.py`'s tests only cover its pure transform functions.)

- [x] **Step 2: Run the full test suite to confirm nothing else broke**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: FAIL only in `tests/app/test_municipios.py` (still importing `get_istac_anual_row`/`get_istac_mensual_row_for_year`, which Task 2 replaces) and possibly a collection error in `app/main.py`'s import chain being exercised indirectly — both expected at this intermediate point, not a regression to chase down now.

- [x] **Step 3: Commit**

```bash
git add app/data.py
git commit -m "feat(data): replace ISTAC loaders with gold_municipio_anual/empleo loaders"
```

---

### Task 2: Rewrite `app/municipios.py`

**Files:**
- Modify: `app/municipios.py`
- Test: `tests/app/test_municipios.py` (full rewrite)

**Interfaces:**
- Consumes: `app.detail_panel.format_kpi_value` (unchanged from before).
- Produces (used by Task 3's `main.py` wiring): `render_municipios_tab(municipio_master_df: pd.DataFrame, municipio_anual_df: pd.DataFrame, municipio_empleo_df: pd.DataFrame) -> None` — **signature changed** from the old `(municipio_master_df, istac_anual_df, istac_mensual_df)`.
- Keeps unchanged: `get_municipio_row(df, municipio) -> pd.Series | None`, `list_available_years(df) -> list[int]` (same behavior, now called on `municipio_anual_df` which also has an `anio` column), `HEX_KPI_COLUMNS`.
- Removes: `get_istac_anual_row`, `get_istac_mensual_row_for_year`, `ISTAC_ANUAL_KPI_COLUMNS`, `ISTAC_MENSUAL_KPI_COLUMNS` (and the two data-quality-bug comments documenting the tables this plan stops reading).
- Adds: `ECONOMIA_KPI_COLUMNS`, `TURISMO_VV_KPI_COLUMNS`, `EVOLUCION_METRICS`, `EMPLEO_TYPES`, `format_yoy_delta(value) -> str | None`, `get_anual_row(df, municipio, anio) -> pd.Series | None`, `evolucion_series(df, municipio, column) -> pd.DataFrame`, `get_latest_empleo_row(df, municipio, anio) -> pd.Series | None`, `empleo_breakdown(row) -> pd.DataFrame`.

- [x] **Step 1: Write the failing tests (full replacement of `tests/app/test_municipios.py`)**

```python
# tests/app/test_municipios.py
import pandas as pd

from app.municipios import (
    empleo_breakdown,
    evolucion_series,
    format_yoy_delta,
    get_anual_row,
    get_latest_empleo_row,
    get_municipio_row,
    list_available_years,
)


def _municipio_master_df():
    return pd.DataFrame(
        {
            "municipio": ["Adeje", "Arona"],
            "n_hexagonos": [50, 40],
        }
    )


def test_get_municipio_row_returns_matching_row():
    row = get_municipio_row(_municipio_master_df(), "Adeje")
    assert row["n_hexagonos"] == 50


def test_get_municipio_row_returns_none_for_unknown_municipio():
    assert get_municipio_row(_municipio_master_df(), "No Existe") is None


def _municipio_anual_df():
    return pd.DataFrame(
        [
            {
                "municipio": "Adeje", "anio": 2024, "n_meses": 12, "es_anio_completo": True,
                "poblacion": 50929.0, "paro_medio": 1996.0, "var_paro_yoy_pct": -9.9,
            },
            {
                "municipio": "Adeje", "anio": 2025, "n_meses": 12, "es_anio_completo": True,
                "poblacion": 50612.0, "paro_medio": 1925.0, "var_paro_yoy_pct": -3.6,
            },
            {
                "municipio": "Adeje", "anio": 2026, "n_meses": 8, "es_anio_completo": False,
                "poblacion": 50612.0, "paro_medio": 1902.0, "var_paro_yoy_pct": -1.2,
            },
            {
                "municipio": "Arona", "anio": 2025, "n_meses": 12, "es_anio_completo": True,
                "poblacion": 80000.0, "paro_medio": 3000.0, "var_paro_yoy_pct": 1.0,
            },
        ]
    )


def test_list_available_years_returns_sorted_unique_years():
    assert list_available_years(_municipio_anual_df()) == [2024, 2025, 2026]


def test_get_anual_row_returns_matching_municipio_and_year():
    row = get_anual_row(_municipio_anual_df(), "Adeje", 2025)
    assert row["poblacion"] == 50612.0


def test_get_anual_row_returns_none_when_year_not_available():
    assert get_anual_row(_municipio_anual_df(), "Arona", 2024) is None


def test_format_yoy_delta_formats_with_sign_and_percent():
    assert format_yoy_delta(-9.9) == "-9.9%"
    assert format_yoy_delta(7.8) == "+7.8%"


def test_format_yoy_delta_returns_none_for_missing_value():
    assert format_yoy_delta(None) is None
    assert format_yoy_delta(float("nan")) is None


def test_evolucion_series_returns_year_ordered_tidy_frame():
    result = evolucion_series(_municipio_anual_df(), "Adeje", "paro_medio")
    assert result["anio"].tolist() == [2024, 2025, 2026]
    assert result["valor"].tolist() == [1996.0, 1925.0, 1902.0]


def _municipio_empleo_df():
    return pd.DataFrame(
        [
            {
                "municipio": "Adeje", "anio": 2025, "trimestre": 3, "periodo": "2025-Q3",
                "periodo_texto": "2025 Tercer trimestre",
                "empleo_asalariados": 31969.0, "empleo_autonomos": 5402.0,
            },
            {
                "municipio": "Adeje", "anio": 2025, "trimestre": 4, "periodo": "2025-Q4",
                "periodo_texto": "2025 Cuarto trimestre",
                "empleo_asalariados": 32257.0, "empleo_autonomos": 5431.0,
            },
        ]
    )


def test_get_latest_empleo_row_picks_latest_quarter_in_year():
    row = get_latest_empleo_row(_municipio_empleo_df(), "Adeje", 2025)
    assert row["periodo"] == "2025-Q4"


def test_get_latest_empleo_row_returns_none_when_no_data_for_year():
    assert get_latest_empleo_row(_municipio_empleo_df(), "Adeje", 2026) is None


def test_empleo_breakdown_returns_tidy_frame():
    row = get_latest_empleo_row(_municipio_empleo_df(), "Adeje", 2025)
    result = empleo_breakdown(row)
    counts = dict(zip(result["tipo"], result["cantidad"]))
    assert counts == {"Asalariados": 32257.0, "Autónomos": 5431.0}
```

- [x] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/app/test_municipios.py -v`
Expected: FAIL with `ImportError` (`format_yoy_delta`, `get_anual_row`, `evolucion_series`, `get_latest_empleo_row`, `empleo_breakdown` don't exist yet).

- [x] **Step 3: Rewrite `app/municipios.py`**

```python
# app/municipios.py
import math

import pandas as pd
import plotly.express as px
import streamlit as st

from app.detail_panel import format_kpi_value

HEX_KPI_COLUMNS = [
    ("n_hexagonos", "Hexágonos analizados"),
    ("n_establecimientos_registro", "Alojamientos registrados"),
    ("n_plazas_registro", "Plazas registradas"),
    ("rating_booking_medio", "Rating Booking"),
    ("rating_tripadvisor_medio", "Rating TripAdvisor"),
    ("ndvi_medio", "NDVI medio"),
]

# (value_column, yoy_delta_column | None, label)
ECONOMIA_KPI_COLUMNS = [
    ("poblacion", None, "Población"),
    ("paro_medio", "var_paro_yoy_pct", "Paro medio"),
    ("empleo_total_medio", "crec_empleo_total_yoy_pct", "Empleo total medio"),
    ("empleo_autonomos_medio", "crec_empleo_autonomos_yoy_pct", "Empleo autónomos medio"),
]

TURISMO_VV_KPI_COLUMNS = [
    ("plazas_vv_media", "crec_plazas_vv_yoy_pct", "Plazas VV media"),
    ("ingresos_vv_media_mensual", "crec_ingresos_mensual_yoy_pct", "Ingresos VV media mensual (€)"),
    ("tasa_ocupacion_vv_media", None, "Ocupación VV media (%)"),
    ("estancia_media_vv", None, "Estancia media VV (días)"),
]

EVOLUCION_METRICS = {
    "Paro medio": "paro_medio",
    "Empleo total medio": "empleo_total_medio",
    "Ingresos VV media mensual": "ingresos_vv_media_mensual",
    "Ocupación VV media (%)": "tasa_ocupacion_vv_media",
}

EMPLEO_TYPES = [
    ("empleo_asalariados", "Asalariados"),
    ("empleo_autonomos", "Autónomos"),
]


def get_municipio_row(df: pd.DataFrame, municipio: str) -> pd.Series | None:
    matches = df.loc[df["municipio"] == municipio]
    if matches.empty:
        return None
    return matches.iloc[0]


def list_available_years(municipio_anual_df: pd.DataFrame) -> list[int]:
    return sorted(municipio_anual_df["anio"].dropna().unique().tolist())


def get_anual_row(df: pd.DataFrame, municipio: str, anio: int) -> pd.Series | None:
    matches = df.loc[(df["municipio"] == municipio) & (df["anio"] == anio)]
    if matches.empty:
        return None
    return matches.iloc[0]


def format_yoy_delta(value) -> str | None:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    return f"{value:+.1f}%"


def evolucion_series(df: pd.DataFrame, municipio: str, column: str) -> pd.DataFrame:
    rows = df.loc[df["municipio"] == municipio, ["anio", column]].sort_values("anio")
    return rows.rename(columns={column: "valor"})


def get_latest_empleo_row(df: pd.DataFrame, municipio: str, anio: int) -> pd.Series | None:
    matches = df.loc[(df["municipio"] == municipio) & (df["anio"] == anio)]
    if matches.empty:
        return None
    return matches.sort_values("periodo").iloc[-1]


def empleo_breakdown(row: pd.Series) -> pd.DataFrame:
    rows = [{"tipo": label, "cantidad": row[column]} for column, label in EMPLEO_TYPES]
    return pd.DataFrame(rows)


def render_municipios_tab(
    municipio_master_df: pd.DataFrame,
    municipio_anual_df: pd.DataFrame,
    municipio_empleo_df: pd.DataFrame,
) -> None:
    col1, col2 = st.columns([2, 1])
    municipio = col1.selectbox(
        "Municipio", sorted(municipio_master_df["municipio"].dropna().unique().tolist())
    )
    years = list_available_years(municipio_anual_df)
    anio = col2.selectbox("Año", years, index=len(years) - 1)

    hex_row = get_municipio_row(municipio_master_df, municipio)
    if hex_row is None:
        st.warning("No hay datos para este municipio.")
        return

    st.subheader("Oferta turística (hexágonos)")
    cols = st.columns(3)
    for i, (column, label) in enumerate(HEX_KPI_COLUMNS):
        cols[i % 3].metric(label, format_kpi_value(hex_row.get(column)))

    anual_row = get_anual_row(municipio_anual_df, municipio, anio)

    st.subheader(f"Población y economía ({anio})")
    if anual_row is None:
        st.info("No hay datos económicos para este municipio en el año seleccionado.")
    else:
        if not bool(anual_row.get("es_anio_completo", True)):
            st.caption(f"⚠️ Año en curso: datos de solo {int(anual_row['n_meses'])} de 12 meses.")
        cols = st.columns(4)
        for i, (column, delta_column, label) in enumerate(ECONOMIA_KPI_COLUMNS):
            delta = format_yoy_delta(anual_row.get(delta_column)) if delta_column else None
            cols[i % 4].metric(label, format_kpi_value(anual_row.get(column)), delta=delta)

        st.subheader("Turismo: vivienda vacacional")
        cols = st.columns(4)
        for i, (column, delta_column, label) in enumerate(TURISMO_VV_KPI_COLUMNS):
            delta = format_yoy_delta(anual_row.get(delta_column)) if delta_column else None
            cols[i % 4].metric(label, format_kpi_value(anual_row.get(column)), delta=delta)

    st.subheader("Evolución")
    metrica_label = st.selectbox(
        "Métrica", list(EVOLUCION_METRICS.keys()), key="municipios_evolucion_metrica"
    )
    serie = evolucion_series(municipio_anual_df, municipio, EVOLUCION_METRICS[metrica_label])
    fig = px.line(
        serie, x="anio", y="valor", markers=True, title=f"{metrica_label} por año — {municipio}"
    )
    fig.update_traces(line_color="#2a78d6")
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Empleo: asalariados vs. autónomos")
    empleo_row = get_latest_empleo_row(municipio_empleo_df, municipio, anio)
    if empleo_row is None:
        st.info("No hay datos de empleo para este municipio en el año seleccionado.")
        return
    st.caption(f"Datos de {empleo_row['periodo_texto']}")
    breakdown = empleo_breakdown(empleo_row)
    fig_empleo = px.pie(
        breakdown,
        names="tipo",
        values="cantidad",
        title="Reparto de empleo",
        color_discrete_sequence=["#2a78d6", "#eb6834"],
    )
    st.plotly_chart(fig_empleo, use_container_width=True)
```

- [x] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/app/test_municipios.py -v`
Expected: PASS, 11/11.

- [x] **Step 5: Commit**

```bash
git add app/municipios.py tests/app/test_municipios.py
git commit -m "feat: rewrite Municipios tab on gold_municipio_anual/empleo with YoY deltas and trend chart"
```

---

### Task 3: Wire into `app/main.py` + manual verification

**Files:**
- Modify: `app/main.py`

**Interfaces:**
- Consumes: `load_municipio_anual`, `load_municipio_empleo` (Task 1), `render_municipios_tab` with its new signature (Task 2).
- Produces: nothing further downstream — this is the last task.

- [x] **Step 1: Update the imports**

Change the `from app.data import (...)` block to remove `load_istac_anual`/`load_istac_mensual` and add `load_municipio_anual`/`load_municipio_empleo` in alphabetical position:

```python
from app.data import (
    filter_by_municipio,
    get_engine,
    list_municipios,
    load_accesibilidad,
    load_h3_master,
    load_isocronas,
    load_municipio_anual,
    load_municipio_empleo,
    load_municipio_master,
    load_nlp_chunks,
    load_sentimiento,
    load_topicos_municipio,
    merge_accesibilidad,
    merge_h3_data,
)
```

- [x] **Step 2: Update the data loading**

Change this block:

```python
istac_anual = load_istac_anual(engine)
istac_mensual = load_istac_mensual(engine)
```

to:

```python
municipio_anual = load_municipio_anual(engine)
municipio_empleo = load_municipio_empleo(engine)
```

- [x] **Step 3: Update the `render_municipios_tab` call**

Change:

```python
with tab_municipios:
    render_municipios_tab(municipio_master, istac_anual, istac_mensual)
```

to:

```python
with tab_municipios:
    render_municipios_tab(municipio_master, municipio_anual, municipio_empleo)
```

- [x] **Step 4: Run the full test suite**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: PASS, all tests (107 before this plan − 7 old `test_municipios.py` tests + 11 new = 111).

- [x] **Step 5: Manual visual verification**

Start the app: `.venv/bin/python -m streamlit run app/main.py --server.headless true --server.port 8501`

Using Playwright + headless Chromium, load the running app, click the "🏛️ Municipios" tab, and screenshot it. Confirm by looking at the resulting image, not by assuming:

1. Selecting "Adeje" + año 2025 shows: "Población y economía" KPIs with green/red delta badges next to Paro medio, Empleo total medio, Empleo autónomos medio (Población has no delta badge — expected, no YoY column for it).
2. Selecting año 2026 shows the "⚠️ Año en curso: datos de solo 8 de 12 meses." caption (2026 is a partial year in the live data as of 2026-09-14).
3. The "Evolución" line chart renders and changes when a different métrica is picked from its selectbox.
4. The "Empleo: asalariados vs. autónomos" pie chart renders with a caption naming the quarter (e.g. "Datos de 2026 Segundo trimestre").
5. No browser console errors.

Verified against the actually running app (default state, Adeje + año 2026, the latest available): "⚠️ Año en curso: datos de solo 8 de 12 meses." caption shown; Paro medio 1902.0 with a red "↓ -1.2%" badge, Empleo total medio 37548.0 with a green "↑ +1.2%" badge, Empleo autónomos medio 5392.0 with a red "↓ -0.2%" badge, Población 50612.0 with no badge — Streamlit's `st.metric` colored the deltas automatically from the `+`/`-` sign, no extra styling code needed. Turismo VV KPIs showed matching red badges on Plazas VV media (-13.8%) and Ingresos VV media mensual (-11.4%). Scrolling down: "Evolución" line chart titled "Paro medio por año — Adeje" rendered the expected declining trend across all 5 years (2022 ≈ 2700 down to 2026 ≈ 1900, matching the live DB query run during design). "Empleo: asalariados vs. autónomos" showed the caption "Datos de 2026 Segundo trimestre" and a pie chart (85.6% Asalariados / 14.4% Autónomos, blue/orange). Zero browser console errors across both screenshots.

- [x] **Step 6: Commit**

```bash
git add app/main.py
git commit -m "feat: wire the enriched Municipios tab into the dashboard"
```

---

## Self-Review Notes

- **Spec coverage:** YoY delta badges on economía/turismo KPIs → Task 2's `ECONOMIA_KPI_COLUMNS`/`TURISMO_VV_KPI_COLUMNS` + `format_yoy_delta`. Multi-year trend chart → Task 2's `evolucion_series` + the "Evolución" section. Asalariados vs. autónomos breakdown (new data, not shown anywhere before) → Task 2's `empleo_breakdown` + the last section. Removal of the two documented ISTAC data-quality workarounds → Task 1 (the loaders they were attached to are deleted) and Task 2 (the comments and the columns lists that worked around them are gone, replaced with clean gold-table columns). Partial-year caveat (2026 has only 8 months) → Task 2's `es_anio_completo` check.
- **Placeholder scan:** no TBD/TODO. Full code given for every step.
- **Type consistency:** `render_municipios_tab(municipio_master_df, municipio_anual_df, municipio_empleo_df)` (Task 2) is called exactly as `render_municipios_tab(municipio_master, municipio_anual, municipio_empleo)` in Task 3 — same three positional arguments, same order. `get_anual_row`/`get_latest_empleo_row`/`evolucion_series`/`empleo_breakdown` are used inside `render_municipios_tab` with the same parameter order and types they're defined with.
- **Out of scope (explicitly, not an oversight):** `gold_municipio_mensual` (monthly granularity) is not used — the annual table already carries YoY and a monthly chart would clutter the tab further; the existing "Evolución" line chart at annual grain covers the trend-visibility goal. `ingresos_vv_acumulados` (cumulative, not the per-month average) is not surfaced as its own KPI — `ingresos_vv_media_mensual` is the more comparable-across-municipios figure.
