# Financial Professional Theme Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the dashboard's current light theme with the "Financial Professional" theme from [jmedia65/awesome-streamlit-themes](https://github.com/jmedia65/awesome-streamlit-themes) (MIT-licensed code, OFL-licensed fonts) — deep navy primary color, Inter/Source Code Pro typography, bordered widgets — propagated consistently across every hardcoded color literal in the app (not just `.streamlit/config.toml`), plus bordered KPI cards for every `st.metric` in the app so stat tiles read as cards instead of floating text.

**Architecture:** No new architecture. Three kinds of change: (1) a new theme config + two local font families served via Streamlit's static-file mechanism, (2) updating the app's single source-of-truth color module (`app/color_scales.py`) plus its two dependent test files, (3) mechanically replacing the old blue/warm-gray hex literals duplicated across every tab file's Plotly calls and `main.py`'s custom CSS with their new-theme equivalents, and wrapping every `st.metric(...)` call in `st.container(border=True)`.

**Tech Stack:** Python 3.13, Streamlit 1.63 (confirmed to support `[[theme.fontFaces]]`, `showWidgetBorder`, `baseRadius`, `[theme.sidebar]`, and `st.container(border=True)` — no upgrade needed), Plotly Express, pytest.

**Spec:** No separate spec doc — design-reviewed in chat (full color-literal inventory, exact hex/RGB mapping, and the added "KPI cards" scope item were all confirmed with the user before this plan was written). Not architectural: no new data, no new subsystem, no new cross-component interface.

## Global Constraints

- Every command in this plan is run from the `AI_Dashboard_Core/` repo root using `.venv/bin/python -m <tool>`.
- **Exact color mapping for this plan** (verified 2026-09-14 against the live theme repo and this codebase's own `grep -rEn "#[0-9a-fA-F]{6}" app/`):

  | Old | New | Hex | RGB | Role |
  |---|---|---|---|---|
  | `#2a78d6` | → | `#1e3a8a` | `[30, 58, 138]` | primary/categorical-slot-1 (navy) |
  | `#898781` / `[137, 135, 129]` | → | `#6b7280` | `[107, 114, 128]` | muted/no-data gray (cooled to match navy+charcoal) |
  | `#f0efec` / `#f0efe8` | → | `#f3f4f6` | `[243, 244, 246]` | light neutral bg / diverging midpoint (cooled) |
  | `#c3c2b7` | → | `#d1d5db` | `[209, 213, 219]` | muted secondary bar color (the theme's own `borderColor`) |
  | `#eb6834`, `#e34948`, `#f9e6dd`, `#cde2fb`, `#0d366b`, `#d03b3b`, `#0ca30c` | unchanged | — | — | secondary accent / status colors already fit the new palette (verified: `#0d366b` is already navy-adjacent) |

- `app/color_scales.py` is this app's single source of truth for map-layer colors (`app/map_layers.py` imports from it and hardcodes no colors itself) — updating it there is sufficient for the map; every other file listed in Task 3 hardcodes its own Plotly color literal independently and must be edited separately (confirmed by `grep -rEn "#[0-9a-fA-F]{6}" app/ --include="*.py"` finding 12 occurrences of `#2a78d6` alone, across 8 files).
- `st.container(border=True)` is a native Streamlit layout primitive (no CSS needed) — wrap each individual `st.metric(...)` call in its own bordered container inside its column, not the whole row in one container, so every stat reads as its own card.
- Out of scope, explicitly: the hero banner's photo overlay gradient and its `color: #e8eefc` subtitle text (`app/main.py`) are untouched — that's a photographic treatment, not part of the flat UI palette this plan rebrands. Plotly's default chart font is left as-is (a possible future refinement, not required by the approved design).

---

## File Structure

```
.streamlit/
└── config.toml          # REPLACE — Financial Professional theme

app/static/               # NEW — 6 font files (next to the app/main.py entrypoint, NOT repo root — see Task 1 Step 1 correction)
├── Inter_18pt-Regular.ttf
├── Inter_18pt-Medium.ttf
├── Inter_18pt-SemiBold.ttf
├── Inter_18pt-Bold.ttf
├── SourceCodePro-Regular.ttf
└── SourceCodePro-SemiBold.ttf

app/
├── color_scales.py   # MODIFY — 4 constants
├── main.py            # MODIFY — CSS colors + 6 metrics wrapped in cards
├── detail_panel.py    # MODIFY — 1 color + 3 metrics wrapped
├── alojamiento.py     # MODIFY — 1 color list + 3 metrics wrapped
├── clima.py            # MODIFY — 1 color
├── municipios.py       # MODIFY — 2 colors + 12 metrics wrapped (3 loops)
├── temas.py             # MODIFY — 1 color list + 1 color + 2 metrics wrapped
└── turismo.py            # MODIFY — 1 color + 7 metrics wrapped (2 loops)

tests/app/
├── test_color_scales.py  # MODIFY — 2 assertions
└── test_map_layers.py    # MODIFY — 4 assertions
```

---

### Task 1: Theme config + fonts

**Files:**
- Create/Replace: `.streamlit/config.toml`
- Create: `static/Inter_18pt-Regular.ttf`, `static/Inter_18pt-Medium.ttf`, `static/Inter_18pt-SemiBold.ttf`, `static/Inter_18pt-Bold.ttf`, `static/SourceCodePro-Regular.ttf`, `static/SourceCodePro-SemiBold.ttf`

**Interfaces:**
- Consumes: nothing.
- Produces: the new theme, active for every later task's manual verification.

- [x] **Step 1: Download the 6 font files**

The `financial/static/` folder of `jmedia65/awesome-streamlit-themes` (MIT-licensed repo; fonts are Inter and Source Code Pro, both SIL Open Font License) hosts these files.

**Correction found during execution:** the plan's original assumption (a `static/` folder at the repo root) was wrong. Streamlit's static-file server looks for `static/` **next to the entrypoint script**, not the repo root — since this app runs as `streamlit run app/main.py`, the folder must be `app/static/`. The URL path is always `app/static/<filename>` (a fixed Streamlit routing prefix, coincidentally the same word as this repo's `app/` package — unrelated facts), but the on-disk location is entrypoint-relative. Caught immediately by this task's own boot-check step (Streamlit logs `WARNING: ... no static folder found at .../app/static` and the font request 404s) before it could cascade into later tasks.

```bash
mkdir -p app/static
for f in Inter_18pt-Regular.ttf Inter_18pt-Medium.ttf Inter_18pt-SemiBold.ttf Inter_18pt-Bold.ttf SourceCodePro-Regular.ttf SourceCodePro-SemiBold.ttf; do
  curl -sL "https://raw.githubusercontent.com/jmedia65/awesome-streamlit-themes/main/financial/static/$f" -o "app/static/$f"
done
ls -la app/static/
```

Expected: 6 `.ttf` files, each a few hundred KB (not 0 bytes or an HTML error page — if `curl` returned an error page, `ls -la` will show a suspiciously small file; verify with `file app/static/*.ttf` that each reports as TrueType font data). Confirmed: all 6 downloaded correctly (133-344 KB each, all report as "TrueType Font data").

- [x] **Step 2: Replace `.streamlit/config.toml`**

```toml
[server]
enableStaticServing = true

[[theme.fontFaces]]
family = "Inter"
url = "app/static/Inter_18pt-Regular.ttf"
style = "normal"
weight = 400

[[theme.fontFaces]]
family = "Inter"
url = "app/static/Inter_18pt-Medium.ttf"
style = "normal"
weight = 500

[[theme.fontFaces]]
family = "Inter"
url = "app/static/Inter_18pt-SemiBold.ttf"
style = "normal"
weight = 600

[[theme.fontFaces]]
family = "Inter"
url = "app/static/Inter_18pt-Bold.ttf"
style = "normal"
weight = 700

[[theme.fontFaces]]
family = "SourceCodePro"
url = "app/static/SourceCodePro-Regular.ttf"
style = "normal"
weight = 400

[[theme.fontFaces]]
family = "SourceCodePro"
url = "app/static/SourceCodePro-SemiBold.ttf"
style = "normal"
weight = 600

[theme]
base = "light"
primaryColor = "#1e3a8a"
backgroundColor = "#fefefe"
secondaryBackgroundColor = "#f8fafc"
textColor = "#1f2937"
linkColor = "#1e40af"
borderColor = "#d1d5db"
showWidgetBorder = true
baseRadius = "0.375rem"
font = "Inter"
headingFont = "Inter"
codeFont = "SourceCodePro"
codeBackgroundColor = "#f3f4f6"
showSidebarBorder = true

[theme.sidebar]
backgroundColor = "#f1f5f9"
secondaryBackgroundColor = "#e5e7eb"
```

- [x] **Step 3: Boot check — confirm the theme actually applies**

```bash
.venv/bin/python -m streamlit run app/main.py --server.headless true --server.port 8501 &
sleep 6
tail -40 /tmp/streamlit_boot_check.log 2>/dev/null || true
curl -s -o /dev/null -w "HTTP %{http_code}\n" http://localhost:8501
curl -s -o /dev/null -w "Font HTTP %{http_code}\n" http://localhost:8501/app/static/Inter_18pt-Regular.ttf
```

Expected: both `curl` calls return `HTTP 200` (the second confirms the font file is actually being served, not just present on disk — a wrong path in `config.toml` would 404 here even though the app itself boots fine).

Using Playwright + headless Chromium, load `http://localhost:8501` and screenshot it. Confirm by looking at the image (font/border changes are visible immediately even though Task 3 hasn't touched the custom CSS yet — the active tab pill and hero border will still show the OLD blue at this point, that's expected and gets fixed in Task 3):

1. Body text renders in Inter (visibly different letterforms from the previous default sans-serif — most noticeable in the sidebar labels and KPI numbers).
2. The sidebar's checkbox, selectbox, and slider each show a visible border (`showWidgetBorder = true` + `showSidebarBorder = true`).
3. The sidebar background is a distinct light blue-gray (`#f1f5f9`), not the same off-white as the main content area.
4. No browser console errors.

Stop the server afterward: `pkill -f "streamlit run app/main.py"`.

- [x] **Step 4: Commit**

```bash
git add .streamlit/config.toml app/static/
git commit -m "feat: switch to Financial Professional theme (navy, Inter/Source Code Pro, bordered widgets)"
```

---

### Task 2: `app/color_scales.py` — the map's source of truth

**Files:**
- Modify: `app/color_scales.py`
- Modify: `tests/app/test_color_scales.py`
- Modify: `tests/app/test_map_layers.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `NO_DATA_COLOR`, `DIVERGING_SENTIMENT_MID`, `DIVERGING_SENTIMENT_HIGH`, `RESTRICTION_ZONA_TURISTICA` — same names, new values. `app/map_layers.py` imports these and needs no code change itself (confirmed it hardcodes no color literals of its own).

- [x] **Step 1: Update the constants**

In `app/color_scales.py`, change:

```python
NO_DATA_COLOR = [137, 135, 129]  # #898781 -- muted ink (dataviz skill palette)
```

to:

```python
NO_DATA_COLOR = [107, 114, 128]  # #6b7280 -- cool muted gray (Financial Professional theme)
```

Change:

```python
DIVERGING_SENTIMENT_MID = "#f0efec"
```

to:

```python
DIVERGING_SENTIMENT_MID = "#f3f4f6"
```

Change:

```python
DIVERGING_SENTIMENT_HIGH = "#2a78d6"
```

to:

```python
DIVERGING_SENTIMENT_HIGH = "#1e3a8a"
```

Change:

```python
RESTRICTION_ZONA_TURISTICA = [42, 120, 214]  # #2a78d6 -- categorical slot 1 (blue)
```

to:

```python
RESTRICTION_ZONA_TURISTICA = [30, 58, 138]  # #1e3a8a -- categorical slot 1 (navy)
```

- [x] **Step 2: Run the dependent tests to see them fail with the old expected values**

Run: `.venv/bin/python -m pytest tests/app/test_color_scales.py tests/app/test_map_layers.py -v`
Expected: FAIL — `test_diverging_color_at_mid_returns_neutral_gray`, `test_diverging_color_at_max_returns_high_pole`, `test_build_fill_color_column_diverging_uses_fixed_domain`, `test_build_fill_color_column_handles_null_values`, `test_build_fill_color_column_categorical_maps_known_categories`, `test_build_fill_color_column_categorical_handles_unknown_as_no_data` now return the new RGB values where the tests still assert the old ones.

- [x] **Step 3: Update `tests/app/test_color_scales.py`**

Change:

```python
def test_diverging_color_at_mid_returns_neutral_gray():
    assert diverging_color(3.0, 1.0, 3.0, 5.0) == [240, 239, 236]
```

to:

```python
def test_diverging_color_at_mid_returns_neutral_gray():
    assert diverging_color(3.0, 1.0, 3.0, 5.0) == [243, 244, 246]
```

Change:

```python
def test_diverging_color_at_max_returns_high_pole():
    assert diverging_color(5.0, 1.0, 3.0, 5.0) == [42, 120, 214]
```

to:

```python
def test_diverging_color_at_max_returns_high_pole():
    assert diverging_color(5.0, 1.0, 3.0, 5.0) == [30, 58, 138]
```

- [x] **Step 4: Update `tests/app/test_map_layers.py`**

Change:

```python
def test_build_fill_color_column_diverging_uses_fixed_domain():
    colors = build_fill_color_column(_gdf(), "Sentimiento")
    assert colors.tolist() == [[227, 73, 72], [240, 239, 236], [42, 120, 214]]
```

to:

```python
def test_build_fill_color_column_diverging_uses_fixed_domain():
    colors = build_fill_color_column(_gdf(), "Sentimiento")
    assert colors.tolist() == [[227, 73, 72], [243, 244, 246], [30, 58, 138]]
```

Change:

```python
def test_build_fill_color_column_handles_null_values():
    colors = build_fill_color_column(_gdf(), "Naturaleza (NDVI)")
    assert colors.iloc[0] == [137, 135, 129]  # NO_DATA_COLOR
```

to:

```python
def test_build_fill_color_column_handles_null_values():
    colors = build_fill_color_column(_gdf(), "Naturaleza (NDVI)")
    assert colors.iloc[0] == [107, 114, 128]  # NO_DATA_COLOR
```

Change:

```python
def test_build_fill_color_column_categorical_maps_known_categories():
    colors = build_fill_color_column(_gdf(), "Restricciones legales")
    assert colors.tolist() == [
        [208, 59, 59],  # ENP
        [42, 120, 214],  # Zona turística oficial
        [12, 163, 12],  # Sin restricción
    ]
```

to:

```python
def test_build_fill_color_column_categorical_maps_known_categories():
    colors = build_fill_color_column(_gdf(), "Restricciones legales")
    assert colors.tolist() == [
        [208, 59, 59],  # ENP
        [30, 58, 138],  # Zona turística oficial
        [12, 163, 12],  # Sin restricción
    ]
```

Change:

```python
def test_build_fill_color_column_categorical_handles_unknown_as_no_data():
    gdf = _gdf()
    gdf.loc[0, "restriction_category"] = "Categoría desconocida"
    colors = build_fill_color_column(gdf, "Restricciones legales")
    assert colors.iloc[0] == [137, 135, 129]  # NO_DATA_COLOR
```

to:

```python
def test_build_fill_color_column_categorical_handles_unknown_as_no_data():
    gdf = _gdf()
    gdf.loc[0, "restriction_category"] = "Categoría desconocida"
    colors = build_fill_color_column(gdf, "Restricciones legales")
    assert colors.iloc[0] == [107, 114, 128]  # NO_DATA_COLOR
```

- [x] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/app/test_color_scales.py tests/app/test_map_layers.py -v`
Expected: PASS, all tests.

- [x] **Step 6: Commit**

```bash
git add app/color_scales.py tests/app/test_color_scales.py tests/app/test_map_layers.py
git commit -m "feat: recolor the map's diverging/categorical/no-data scales for the navy theme"
```

---

### Task 3: Propagate the color swap + add bordered KPI cards everywhere else

**Files:**
- Modify: `app/main.py`, `app/detail_panel.py`, `app/alojamiento.py`, `app/clima.py`, `app/municipios.py`, `app/temas.py`, `app/turismo.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: nothing new — this is the last task.

- [x] **Step 1: `app/main.py`**

Change the CSS block:

```python
    .stTabs [data-baseweb="tab"] {{
        background-color: #f0efe8;
        border-radius: 8px 8px 0 0;
        padding: 8px 16px;
    }}
    .stTabs [aria-selected="true"] {{
        background-color: #2a78d6;
        color: white;
    }}
```

to:

```python
    .stTabs [data-baseweb="tab"] {{
        background-color: #f3f4f6;
        border-radius: 8px 8px 0 0;
        padding: 8px 16px;
    }}
    .stTabs [aria-selected="true"] {{
        background-color: #1e3a8a;
        color: white;
    }}
```

Change:

```python
        border-bottom: 5px solid #2a78d6;
```

to:

```python
        border-bottom: 5px solid #1e3a8a;
```

Change the Resumen tab's metrics:

```python
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Hexágonos analizados", stats["total_hexagonos"])
    col2.metric("Sin restricción legal", f"{stats['pct_sin_restriccion']}%")
    col3.metric("Con datos de sentimiento", f"{stats['pct_con_sentimiento']}%")
    col4.metric("Municipios", stats["n_municipios"])

    st.subheader("Reparto de restricciones legales")
    st.bar_chart(stats["restriction_counts"])

    col5, col6 = st.columns(2)
    col5.metric("Municipio con más oferta registrada", stats["municipio_mas_oferta"])
    col6.metric("Municipio con menos oferta registrada", stats["municipio_menos_oferta"])
```

to:

```python
    col1, col2, col3, col4 = st.columns(4)
    with col1.container(border=True):
        st.metric("Hexágonos analizados", stats["total_hexagonos"])
    with col2.container(border=True):
        st.metric("Sin restricción legal", f"{stats['pct_sin_restriccion']}%")
    with col3.container(border=True):
        st.metric("Con datos de sentimiento", f"{stats['pct_con_sentimiento']}%")
    with col4.container(border=True):
        st.metric("Municipios", stats["n_municipios"])

    st.subheader("Reparto de restricciones legales")
    st.bar_chart(stats["restriction_counts"])

    col5, col6 = st.columns(2)
    with col5.container(border=True):
        st.metric("Municipio con más oferta registrada", stats["municipio_mas_oferta"])
    with col6.container(border=True):
        st.metric("Municipio con menos oferta registrada", stats["municipio_menos_oferta"])
```

- [x] **Step 2: `app/detail_panel.py`**

Change:

```python
    cols = st.columns(3)
    for i, (column, label) in enumerate(KPI_COLUMNS):
        cols[i % 3].metric(label, format_kpi_value(row.get(column)))
```

to:

```python
    cols = st.columns(3)
    for i, (column, label) in enumerate(KPI_COLUMNS):
        with cols[i % 3].container(border=True):
            st.metric(label, format_kpi_value(row.get(column)))
```

Change:

```python
        color_discrete_map={True: "#2a78d6", False: "#c3c2b7"},
```

to:

```python
        color_discrete_map={True: "#1e3a8a", False: "#d1d5db"},
```

- [x] **Step 3: `app/alojamiento.py`**

Change:

```python
    col1, col2, col3 = st.columns(3)
    col1.metric("Rating medio Booking", summary["rating_booking_medio"])
    col2.metric("Rating medio TripAdvisor", summary["rating_tripadvisor_medio"])
    col3.metric("Reseñas Booking totales", summary["total_reviews_booking"])
```

to:

```python
    col1, col2, col3 = st.columns(3)
    with col1.container(border=True):
        st.metric("Rating medio Booking", summary["rating_booking_medio"])
    with col2.container(border=True):
        st.metric("Rating medio TripAdvisor", summary["rating_tripadvisor_medio"])
    with col3.container(border=True):
        st.metric("Reseñas Booking totales", summary["total_reviews_booking"])
```

Change:

```python
        color_discrete_sequence=["#2a78d6", "#eb6834", "#898781"],
```

to:

```python
        color_discrete_sequence=["#1e3a8a", "#eb6834", "#6b7280"],
```

- [x] **Step 4: `app/clima.py`**

Change:

```python
    fig.update_traces(line_color="#2a78d6")
```

to:

```python
    fig.update_traces(line_color="#1e3a8a")
```

- [x] **Step 5: `app/municipios.py`**

**Correction found during execution:** this plan drafted the `HEX_KPI_COLUMNS` snippet below at 8-space indentation (as if nested inside the `anual_row` `if`/`else`), but in the actual file this loop sits at the function's top level, before that `if`/`else` — 4-space indentation. Applied at the correct indentation; noted here so the diff isn't a surprise.

Change:

```python
    cols = st.columns(3)
    for i, (column, label) in enumerate(HEX_KPI_COLUMNS):
        cols[i % 3].metric(label, format_kpi_value(hex_row.get(column)))
```

to:

```python
    cols = st.columns(3)
    for i, (column, label) in enumerate(HEX_KPI_COLUMNS):
        with cols[i % 3].container(border=True):
            st.metric(label, format_kpi_value(hex_row.get(column)))
```

Change (the economía KPI loop):

```python
        cols = st.columns(4)
        for i, (column, delta_column, label) in enumerate(ECONOMIA_KPI_COLUMNS):
            delta = format_yoy_delta(anual_row.get(delta_column)) if delta_column else None
            cols[i % 4].metric(label, format_kpi_value(anual_row.get(column)), delta=delta)

        st.subheader("Turismo: vivienda vacacional")
        cols = st.columns(4)
        for i, (column, delta_column, label) in enumerate(TURISMO_VV_KPI_COLUMNS):
            delta = format_yoy_delta(anual_row.get(delta_column)) if delta_column else None
            cols[i % 4].metric(label, format_kpi_value(anual_row.get(column)), delta=delta)
```

to:

```python
        cols = st.columns(4)
        for i, (column, delta_column, label) in enumerate(ECONOMIA_KPI_COLUMNS):
            delta = format_yoy_delta(anual_row.get(delta_column)) if delta_column else None
            with cols[i % 4].container(border=True):
                st.metric(label, format_kpi_value(anual_row.get(column)), delta=delta)

        st.subheader("Turismo: vivienda vacacional")
        cols = st.columns(4)
        for i, (column, delta_column, label) in enumerate(TURISMO_VV_KPI_COLUMNS):
            delta = format_yoy_delta(anual_row.get(delta_column)) if delta_column else None
            with cols[i % 4].container(border=True):
                st.metric(label, format_kpi_value(anual_row.get(column)), delta=delta)
```

Change:

```python
    fig = px.line(
        serie, x="anio", y="valor", markers=True, title=f"{metrica_label} por año — {municipio}"
    )
    fig.update_traces(line_color="#2a78d6")
```

to:

```python
    fig = px.line(
        serie, x="anio", y="valor", markers=True, title=f"{metrica_label} por año — {municipio}"
    )
    fig.update_traces(line_color="#1e3a8a")
```

Change:

```python
        color_discrete_sequence=["#2a78d6", "#eb6834"],
```

to:

```python
        color_discrete_sequence=["#1e3a8a", "#eb6834"],
```

- [x] **Step 6: `app/temas.py`**

Change:

```python
    col1, col2 = st.columns(2)
    col1.metric("Opiniones analizadas", int(row["n_opiniones"]))
    col2.metric("Temas distintos detectados", int(row["n_topicos_distintos"]))
```

to:

```python
    col1, col2 = st.columns(2)
    with col1.container(border=True):
        st.metric("Opiniones analizadas", int(row["n_opiniones"]))
    with col2.container(border=True):
        st.metric("Temas distintos detectados", int(row["n_topicos_distintos"]))
```

Change:

```python
            color_discrete_sequence=["#2a78d6", "#eb6834", "#898781", "#f0efec"],
```

to:

```python
            color_discrete_sequence=["#1e3a8a", "#eb6834", "#6b7280", "#f3f4f6"],
```

Change:

```python
        fig_topicos.update_traces(marker_color="#2a78d6")
```

to:

```python
        fig_topicos.update_traces(marker_color="#1e3a8a")
```

- [x] **Step 7: `app/turismo.py`**

Change:

```python
        cols = st.columns(4)
        for i, (column, delta_column, label) in enumerate(HOTELERO_KPI_COLUMNS):
            delta = format_yoy_delta(anual_row.get(delta_column)) if delta_column else None
            cols[i % 4].metric(label, format_kpi_value(anual_row.get(column)), delta=delta)
```

to:

```python
        cols = st.columns(4)
        for i, (column, delta_column, label) in enumerate(HOTELERO_KPI_COLUMNS):
            delta = format_yoy_delta(anual_row.get(delta_column)) if delta_column else None
            with cols[i % 4].container(border=True):
                st.metric(label, format_kpi_value(anual_row.get(column)), delta=delta)
```

Change:

```python
        cols = st.columns(3)
        for i, (column, label) in enumerate(AENA_KPI_COLUMNS):
            cols[i].metric(label, format_kpi_value(latest_row.get(column)))
```

to:

```python
        cols = st.columns(3)
        for i, (column, label) in enumerate(AENA_KPI_COLUMNS):
            with cols[i].container(border=True):
                st.metric(label, format_kpi_value(latest_row.get(column)))
```

Change:

```python
    fig = px.bar(
        serie,
        x="mes_label",
        y="valor",
        category_orders={"mes_label": MES_ORDER},
        title=f"{metrica_label} media por mes — {municipio}",
    )
    fig.update_traces(marker_color="#2a78d6")
```

to:

```python
    fig = px.bar(
        serie,
        x="mes_label",
        y="valor",
        category_orders={"mes_label": MES_ORDER},
        title=f"{metrica_label} media por mes — {municipio}",
    )
    fig.update_traces(marker_color="#1e3a8a")
```

(`fig_aena`'s `line_color="#eb6834"` is unchanged — the orange accent stays as designed.)

- [x] **Step 8: Run the full test suite**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: PASS, 120/120 (unchanged count — this task touches only render functions and CSS/color literals that have no dedicated unit tests, matching this repo's established convention).

- [x] **Step 9: Manual visual verification — every tab**

Start the app: `.venv/bin/python -m streamlit run app/main.py --server.headless true --server.port 8501`

Using Playwright + headless Chromium, load the app and, for each of the 9 tabs (Resumen, Mapa, Tabla, Rankings, Clima, Municipios, Alojamiento, Temas, Turismo), click it and screenshot it. Confirm by looking at each image, not by assuming:

1. **Resumen:** the 6 KPI numbers each sit inside a bordered card, not floating on the bare background.
2. **Mapa:** the active tab pill and the hero banner's bottom border are now navy, not the old blue; toggle to the "Sentimiento" map layer and confirm the diverging scale's high end renders navy, not the old blue (hardest one to eyeball — zoom into a hexagon known to have high sentiment if needed).
3. **Tabla, Rankings:** general chrome (tabs, fonts, widget borders) matches the new theme; no readability regressions.
4. **Clima:** the line chart renders in navy.
5. **Municipios:** all three KPI rows show bordered cards with delta badges still colored correctly (green/red are Streamlit-native, unaffected by this plan); both charts (evolución line, empleo pie) use the new navy/orange.
6. **Alojamiento:** KPI cards bordered; pie chart uses navy/orange/cool-gray.
7. **Temas:** KPI cards bordered; pie and bar charts use navy/orange/cool-gray/light-cool-gray.
8. **Turismo:** all KPI cards (hotelero + AENA) bordered; both charts use navy/orange.
9. No browser console errors on any tab.

Verified with a Playwright script that clicked all 9 tabs in one run and screenshotted each: Resumen's 6 KPIs each in bordered cards, active tab pill and hero border navy, restriction bar chart bars navy. Mapa rendered cleanly (default "Densidad hotelera" layer; not re-verified pixel-by-pixel against the Sentimiento layer's navy high pole beyond Task 2's automated test coverage). Municipios showed all three KPI rows as bordered cards with the green/red delta badges intact and unaffected, plus a navy evolución line and a navy/orange empleo pie. Alojamiento and Temas both showed bordered KPI cards and navy/orange/cool-gray pie charts. Turismo showed bordered KPI cards (hotelero + AENA) and a navy seasonality bar chart. Tabla and Rankings showed correct chrome (Rankings' bar-chart-by-municipio colors are Plotly's own categorical cycle, untouched by this plan — never hardcoded, so nothing to change there). Zero console errors across all 9 screenshots.

Stop the server afterward: `pkill -f "streamlit run app/main.py"`.

- [x] **Step 10: Commit**

```bash
git add app/main.py app/detail_panel.py app/alojamiento.py app/clima.py app/municipios.py app/temas.py app/turismo.py
git commit -m "feat: apply navy theme colors and bordered KPI cards across every tab"
```

---

## Self-Review Notes

- **Spec coverage:** theme config + fonts → Task 1. Map's diverging/categorical/no-data scale recoloring (the one place with automated tests) → Task 2. Every remaining hardcoded color literal across all 7 tab-rendering files + `main.py`'s CSS → Task 3, Steps 1-7 (exhaustively enumerated from the `grep -rEn "#[0-9a-fA-F]{6}" app/` inventory in Global Constraints — 12 `#2a78d6` occurrences, all accounted for). Bordered KPI cards (the user-approved 4th point) → every `.metric(` call site found via `grep -rn "\.metric(" app/` (16 call sites across 6 files), all wrapped.
- **Placeholder scan:** no TBD/TODO. Every step gives exact before/after code, not a description of what to change.
- **Type consistency:** no function signatures change in this plan — every edit is either a literal constant, a CSS color, or wrapping an existing `.metric(...)` call in `with ....container(border=True): st.metric(...)` without changing its arguments.
- **Out of scope (explicitly, not an oversight):** hero banner photo gradient/subtitle color, Plotly's default chart font — both noted in Global Constraints as deliberate exclusions from the approved design.
