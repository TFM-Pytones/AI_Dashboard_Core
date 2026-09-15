# Sidebar Navigation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the dashboard's top `st.tabs()` bar with Streamlit's native sidebar page navigation (`st.navigation` + `st.Page`), so the 9 sections (Resumen, Mapa, Tabla, Rankings, Clima, Municipios, Alojamiento, Temas, Turismo) appear as a clickable list in the left sidebar instead of a horizontal bar, with the active page highlighted automatically and each page getting its own shareable URL. "Filtros del mapa" (capa, opacidad, isócronas, municipio) moves from being always-visible in the sidebar to appearing only when the Mapa page is active.

**Architecture:** No new files, no new dependencies — `st.navigation`/`st.Page` are already part of the installed Streamlit 1.63 (confirmed via `python -c "import streamlit as st; print(hasattr(st, 'navigation'), hasattr(st, 'Page'))"` → `True True`). This is a single-file restructure of `app/main.py`: every `with tab_x: ...` block becomes a zero-argument function passed to `st.Page(...)`, the `st.tabs(...)` call is replaced with `st.navigation([...])`, and the script ends with `pg.run()` instead of the tab blocks executing inline. `app/main.py` has no unit tests today (confirmed: `grep -rn "app.main" tests/` finds nothing, since Streamlit entrypoint scripts aren't imported by pytest anywhere in this repo) and this plan doesn't add any — verification is the full existing suite (unaffected) plus manual/visual.

**Tech Stack:** Python 3.13, Streamlit 1.63 — no new dependencies.

**Spec:** No separate spec doc — bounded, single-file restructure, design-reviewed in chat (both open questions — native `st.navigation` vs. custom sidebar buttons, and whether "Filtros del mapa" should be page-scoped — were resolved with the user via AskUserQuestion before this plan was written: native navigation, filters scoped to the Mapa page only).

## Global Constraints

- Every command in this plan is run from the `AI_Dashboard_Core/` repo root using `.venv/bin/python -m <tool>`.
- Every page function is a zero-argument callable (`st.Page`'s requirement — confirmed via `help(st.Page)`: `page: str | Path | Callable[[], None]`).
- Data loading (`h3_master`, `sentimiento`, `accesibilidad`, `isocronas`, `municipio_master`, `municipio_anual`, `municipio_empleo`, `topicos_municipio`, `nlp_chunks`, `turismo_hotelero_anual`, `turismo_hotelero_mensual`, `aena_pasajeros`, and the derived `full_gdf`) stays at module level, computed once per script run exactly as today — every `@st.cache_data`-wrapped loader already makes repeated calls across page navigations cheap, so there's no reason to move loading inside individual page functions.
- The hero banner (image + CSS) stays global chrome rendered before `st.navigation(...)` is called — it's shared branding, not page-specific content. This ordering (shared header, then `st.navigation`, then `pg.run()` last) is a standard documented pattern for Streamlit multipage apps.
- The `.stTabs [...]` CSS rules in `app/main.py`'s style block become dead code once `st.tabs()` is removed — delete them rather than leave them unused.
- Out of scope, explicitly: no custom CSS is added to restyle the new sidebar nav list. Streamlit's native page nav already reads `theme.primaryColor` (`#1e3a8a`, set by the Financial Professional theme plan) for its active-page highlight — verify this looks right in manual testing before considering any extra CSS.

---

## File Structure

```
app/
└── main.py   # REWRITE — st.tabs() -> st.navigation()/st.Page(), tab bodies -> page functions, map filters moved into page_mapa()
```

---

### Task 1: Rewrite `app/main.py`

**Files:**
- Modify: `app/main.py`

**Interfaces:**
- Consumes: nothing new — same imports as today.
- Produces: nothing — this is the whole plan, a single-file behavioral change with no other file depending on `main.py`'s internals (it's the entrypoint).

- [x] **Step 1: Replace the file's tab-building section (CSS block through the last `with tab_x:` block) with page functions + navigation**

In `app/main.py`, remove the two dead `.stTabs` CSS rules. Change:

```python
    .stTabs [data-baseweb="tab-list"] {{ gap: 4px; }}
    .stTabs [data-baseweb="tab"] {{
        background-color: #f3f4f6;
        border-radius: 8px 8px 0 0;
        padding: 8px 16px;
    }}
    .stTabs [aria-selected="true"] {{
        background-color: #1e3a8a;
        color: white;
    }}
    .hero-banner {{
```

to:

```python
    .hero-banner {{
```

Then replace everything from the `with st.sidebar:` block (currently right after the `full_gdf = merge_accesibilidad(...)` line) through the end of the file with:

```python
def page_resumen() -> None:
    stats = compute_summary_stats(full_gdf)

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


def page_mapa() -> None:
    with st.sidebar:
        st.subheader("Filtros del mapa")
        show_hexagons = st.checkbox("Mostrar capa de hexágonos", value=True)
        metric_key = st.selectbox("Capa del mapa", list(METRICS.keys()), disabled=not show_hexagons)
        hex_opacity = st.slider(
            "Opacidad de hexágonos",
            min_value=0.05,
            max_value=1.0,
            value=DEFAULT_HEXAGON_OPACITY,
            step=0.05,
            disabled=not show_hexagons,
            help="Más bajo = se ve más el satélite de fondo. Más alto = se ve más el color de los hexágonos.",
        )
        map_municipio = st.selectbox("Municipio", ["Todos"] + list_municipios(full_gdf), key="map_municipio")
        show_isocronas = st.checkbox("Mostrar isócronas")
        isocrona_destino = None
        if show_isocronas:
            isocrona_destino = st.selectbox("Destino de referencia", list_destinos(isocronas))

    filtered_gdf = filter_by_municipio(full_gdf, map_municipio)

    map_col, detail_col = st.columns([3, 2])

    with map_col:
        deck = build_deck(filtered_gdf, metric_key, show_hexagons=show_hexagons, opacity=hex_opacity)
        if show_isocronas and isocrona_destino:
            deck.layers.append(build_isocronas_layer(isocronas, isocrona_destino))
        st.pydeck_chart(deck, on_select="rerun", selection_mode="single-object", key="h3_map")

    selected_h3_index = None
    event = st.session_state.get("h3_map")
    if event is not None:
        picked = event.get("selection", {}).get("objects", {}).get("h3_index", [])
        if picked:
            selected_h3_index = picked[0].get("h3_index")

    with detail_col:
        render_detail_panel(full_gdf, selected_h3_index)


def page_tabla() -> None:
    col1, col2 = st.columns(2)
    tabla_municipio = col1.selectbox(
        "Municipio", ["Todos"] + list_municipios(full_gdf), key="tabla_municipio"
    )
    tabla_restriccion = col2.selectbox(
        "Restricción legal",
        ["Todas"] + sorted(full_gdf["restriction_category"].dropna().unique().tolist()),
        key="tabla_restriccion",
    )

    tabla_filtrada = filter_table(full_gdf, tabla_municipio, tabla_restriccion)
    tabla_mostrable = prepare_table_view(tabla_filtrada)

    st.dataframe(tabla_mostrable, width="stretch")
    st.download_button(
        "Descargar CSV",
        data=tabla_mostrable.to_csv(index=False).encode("utf-8"),
        file_name="hexagonos_tenerife.csv",
        mime="text/csv",
    )


def page_rankings() -> None:
    render_rankings_tab(full_gdf)


def page_clima() -> None:
    clima_municipio = st.selectbox(
        "Municipio", ["Todos"] + list_municipios(full_gdf), key="clima_municipio"
    )
    render_clima_tab(filter_by_municipio(full_gdf, clima_municipio))


def page_municipios() -> None:
    render_municipios_tab(municipio_master, municipio_anual, municipio_empleo)


def page_alojamiento() -> None:
    alojamiento_municipio = st.selectbox(
        "Municipio", ["Todos"] + list_municipios(full_gdf), key="alojamiento_municipio"
    )
    render_alojamiento_tab(filter_by_municipio(full_gdf, alojamiento_municipio))


def page_temas() -> None:
    render_temas_tab(topicos_municipio, nlp_chunks)


def page_turismo() -> None:
    render_turismo_tab(turismo_hotelero_anual, turismo_hotelero_mensual, aena_pasajeros)


pages = [
    st.Page(page_resumen, title="Resumen", icon="📊", default=True),
    st.Page(page_mapa, title="Mapa", icon="🗺️"),
    st.Page(page_tabla, title="Tabla", icon="📋"),
    st.Page(page_rankings, title="Rankings", icon="🏆"),
    st.Page(page_clima, title="Clima", icon="🌡️"),
    st.Page(page_municipios, title="Municipios", icon="🏛️"),
    st.Page(page_alojamiento, title="Alojamiento", icon="🏨"),
    st.Page(page_temas, title="Temas", icon="💬"),
    st.Page(page_turismo, title="Turismo", icon="✈️"),
]

pg = st.navigation(pages)
pg.run()
```

The full resulting file, top to bottom, is:

```python
import base64
from pathlib import Path

import streamlit as st

from app.alojamiento import render_alojamiento_tab
from app.clima import render_clima_tab
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
from app.detail_panel import render_detail_panel
from app.map_layers import DEFAULT_HEXAGON_OPACITY, METRICS, build_deck, build_isocronas_layer, list_destinos
from app.municipios import render_municipios_tab
from app.rankings import render_rankings_tab
from app.summary import compute_summary_stats
from app.table_view import filter_table, prepare_table_view
from app.temas import render_temas_tab
from app.turismo import render_turismo_tab

st.set_page_config(page_title="AI-Dashboard Tenerife", page_icon="🌋", layout="wide")

HERO_IMAGE_B64 = base64.b64encode(
    (Path(__file__).parent / "assets" / "hero_puerto_cruz.jpg").read_bytes()
).decode("utf-8")

st.markdown(
    f"""
    <style>
    .block-container {{
        padding-top: 1rem;
        max-width: 100%;
    }}
    .hero-banner {{
        position: relative;
        height: 420px;
        margin: -1rem -1rem 1.5rem -1rem;
        width: calc(100% + 2rem);
        background-image:
            linear-gradient(100deg, rgba(10,10,8,0.55) 0%, rgba(10,10,8,0.20) 50%, rgba(10,10,8,0.0) 80%),
            url(data:image/jpeg;base64,{HERO_IMAGE_B64});
        background-size: cover;
        background-position: center 50%;
        display: flex;
        flex-direction: column;
        justify-content: center;
        padding: 0 clamp(1.5rem, 5vw, 4rem);
        border-bottom: 5px solid #1e3a8a;
    }}
    .hero-banner h1 {{
        color: white;
        font-size: clamp(1.8rem, 3.2vw, 2.9rem);
        margin: 0 0 0.5rem 0;
        text-shadow: 0 2px 12px rgba(0,0,0,0.35);
    }}
    .hero-banner p {{
        color: #e8eefc;
        font-size: clamp(1rem, 1.4vw, 1.3rem);
        margin: 0;
        max-width: 46ch;
        text-shadow: 0 1px 8px rgba(0,0,0,0.35);
    }}
    .hero-credit {{
        position: absolute;
        bottom: 0.6rem;
        right: 1rem;
        font-size: 0.7rem;
        color: rgba(255,255,255,0.75);
        background: rgba(13,54,107,0.4);
        padding: 0.2rem 0.6rem;
        border-radius: 999px;
    }}
    </style>
    <div class="hero-banner">
        <h1>AI-Dashboard — Oferta turística de Tenerife</h1>
        <p>Analítica geoespacial por hexágono H3: alojamiento, clima, satélite y economía municipal</p>
        <span class="hero-credit">Foto: Puerto de la Cruz, Atlantic Ambience — Pexels License</span>
    </div>
    """,
    unsafe_allow_html=True,
)

engine = get_engine()
h3_master = load_h3_master(engine)
sentimiento = load_sentimiento(engine)
accesibilidad = load_accesibilidad(engine)
isocronas = load_isocronas(engine)
municipio_master = load_municipio_master(engine)
municipio_anual = load_municipio_anual(engine)
municipio_empleo = load_municipio_empleo(engine)
topicos_municipio = load_topicos_municipio(engine)
nlp_chunks = load_nlp_chunks(engine)
turismo_hotelero_anual = load_turismo_hotelero_anual(engine)
turismo_hotelero_mensual = load_turismo_hotelero_mensual(engine)
aena_pasajeros = load_aena_pasajeros(engine)

full_gdf = merge_h3_data(h3_master, sentimiento)
full_gdf = merge_accesibilidad(full_gdf, accesibilidad)


def page_resumen() -> None:
    stats = compute_summary_stats(full_gdf)

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


def page_mapa() -> None:
    with st.sidebar:
        st.subheader("Filtros del mapa")
        show_hexagons = st.checkbox("Mostrar capa de hexágonos", value=True)
        metric_key = st.selectbox("Capa del mapa", list(METRICS.keys()), disabled=not show_hexagons)
        hex_opacity = st.slider(
            "Opacidad de hexágonos",
            min_value=0.05,
            max_value=1.0,
            value=DEFAULT_HEXAGON_OPACITY,
            step=0.05,
            disabled=not show_hexagons,
            help="Más bajo = se ve más el satélite de fondo. Más alto = se ve más el color de los hexágonos.",
        )
        map_municipio = st.selectbox("Municipio", ["Todos"] + list_municipios(full_gdf), key="map_municipio")
        show_isocronas = st.checkbox("Mostrar isócronas")
        isocrona_destino = None
        if show_isocronas:
            isocrona_destino = st.selectbox("Destino de referencia", list_destinos(isocronas))

    filtered_gdf = filter_by_municipio(full_gdf, map_municipio)

    map_col, detail_col = st.columns([3, 2])

    with map_col:
        deck = build_deck(filtered_gdf, metric_key, show_hexagons=show_hexagons, opacity=hex_opacity)
        if show_isocronas and isocrona_destino:
            deck.layers.append(build_isocronas_layer(isocronas, isocrona_destino))
        st.pydeck_chart(deck, on_select="rerun", selection_mode="single-object", key="h3_map")

    selected_h3_index = None
    event = st.session_state.get("h3_map")
    if event is not None:
        picked = event.get("selection", {}).get("objects", {}).get("h3_index", [])
        if picked:
            selected_h3_index = picked[0].get("h3_index")

    with detail_col:
        render_detail_panel(full_gdf, selected_h3_index)


def page_tabla() -> None:
    col1, col2 = st.columns(2)
    tabla_municipio = col1.selectbox(
        "Municipio", ["Todos"] + list_municipios(full_gdf), key="tabla_municipio"
    )
    tabla_restriccion = col2.selectbox(
        "Restricción legal",
        ["Todas"] + sorted(full_gdf["restriction_category"].dropna().unique().tolist()),
        key="tabla_restriccion",
    )

    tabla_filtrada = filter_table(full_gdf, tabla_municipio, tabla_restriccion)
    tabla_mostrable = prepare_table_view(tabla_filtrada)

    st.dataframe(tabla_mostrable, width="stretch")
    st.download_button(
        "Descargar CSV",
        data=tabla_mostrable.to_csv(index=False).encode("utf-8"),
        file_name="hexagonos_tenerife.csv",
        mime="text/csv",
    )


def page_rankings() -> None:
    render_rankings_tab(full_gdf)


def page_clima() -> None:
    clima_municipio = st.selectbox(
        "Municipio", ["Todos"] + list_municipios(full_gdf), key="clima_municipio"
    )
    render_clima_tab(filter_by_municipio(full_gdf, clima_municipio))


def page_municipios() -> None:
    render_municipios_tab(municipio_master, municipio_anual, municipio_empleo)


def page_alojamiento() -> None:
    alojamiento_municipio = st.selectbox(
        "Municipio", ["Todos"] + list_municipios(full_gdf), key="alojamiento_municipio"
    )
    render_alojamiento_tab(filter_by_municipio(full_gdf, alojamiento_municipio))


def page_temas() -> None:
    render_temas_tab(topicos_municipio, nlp_chunks)


def page_turismo() -> None:
    render_turismo_tab(turismo_hotelero_anual, turismo_hotelero_mensual, aena_pasajeros)


pages = [
    st.Page(page_resumen, title="Resumen", icon="📊", default=True),
    st.Page(page_mapa, title="Mapa", icon="🗺️"),
    st.Page(page_tabla, title="Tabla", icon="📋"),
    st.Page(page_rankings, title="Rankings", icon="🏆"),
    st.Page(page_clima, title="Clima", icon="🌡️"),
    st.Page(page_municipios, title="Municipios", icon="🏛️"),
    st.Page(page_alojamiento, title="Alojamiento", icon="🏨"),
    st.Page(page_temas, title="Temas", icon="💬"),
    st.Page(page_turismo, title="Turismo", icon="✈️"),
]

pg = st.navigation(pages)
pg.run()
```

- [x] **Step 2: Run the full test suite**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: PASS, 120/120 (unchanged — `app/main.py` has no unit tests, and no other file changed).

- [x] **Step 3: Manual visual verification**

Start the app: `.venv/bin/python -m streamlit run app/main.py --server.headless true --server.port 8501`

Using Playwright + headless Chromium, load the app and screenshot it, then click through the sidebar nav. Confirm by looking at the images, not by assuming:

1. The sidebar shows a vertical list of 9 links (📊 Resumen, 🗺️ Mapa, 📋 Tabla, 🏆 Rankings, 🌡️ Clima, 🏛️ Municipios, 🏨 Alojamiento, 💬 Temas, ✈️ Turismo) at the top, above where "Filtros del mapa" used to always appear — no horizontal tab bar remains above the hero banner or below it.
2. On "Resumen" (the default page), "Filtros del mapa" is **not** in the sidebar.
3. Clicking "Mapa" in the sidebar switches the main content to the map AND makes "Filtros del mapa" appear in the sidebar (capa, opacidad, municipio, isócronas) — confirms the page-scoping worked.
4. Clicking back to "Resumen" (or any other page) makes "Filtros del mapa" disappear again from the sidebar.
5. The active page in the sidebar list is visually highlighted (expected to pick up the navy `primaryColor` automatically from the Financial Professional theme — confirm this looks right; if Streamlit's native highlight doesn't read as clearly navy/selected, note it, don't silently add CSS beyond what's in this plan).
6. Click through at least 3 more pages (e.g. Municipios, Temas, Turismo) and confirm each renders its full content correctly (KPI cards, charts) exactly as before this plan — this is a navigation change, not a content change, so nothing about each page's own rendering should differ from the previous session's verification.
7. The browser URL changes per page (e.g. something like `.../~/+/turismo` or `.../turismo` depending on Streamlit's exact scheme) — confirms native multipage routing is active, not just a visual relabel.
8. No browser console errors on any page.

Verified with a Playwright script that clicked Mapa, back to Resumen, then Turismo, screenshotting each: sidebar showed the 9-item vertical list (Resumen bold/highlighted with a light gray pill by default) with no horizontal tab bar anywhere. On Resumen, no "Filtros del mapa" section. Clicking "Mapa" made "Filtros del mapa" (checkbox, capa, opacidad, municipio, isócronas) appear in the sidebar below the nav list, with "Mapa" now highlighted instead of "Resumen." Clicking back to "Resumen" made the filters section disappear again. URLs changed per page: `http://localhost:8501/` (Resumen) → `http://localhost:8501/page_mapa` (Mapa) → `http://localhost:8501/page_turismo` (Turismo) — routing is real, though the slug is derived from the Python function name (`page_mapa`) rather than the `title` ("Mapa") since these are callable-based pages, not file-based; cosmetic only; the plan's "URL changes per page" check passes either way, and cleaning up the slugs (e.g. via `st.Page(..., url_path="mapa")`) is a possible follow-up, not requested. Active-page highlight is Streamlit's default light-gray pill + bold text, not a navy fill — legible as a selection indicator; no custom CSS added, per Global Constraints. Zero console errors across all four screenshots.

Stop the server afterward: `pkill -f "streamlit run app/main.py"`.

- [x] **Step 4: Commit**

```bash
git add app/main.py
git commit -m "feat: move navigation from top tabs to a native sidebar page list"
```

---

## Self-Review Notes

- **Spec coverage:** sidebar nav list replacing the top tab bar → the `st.navigation`/`st.Page` restructure. "Filtros del mapa" appearing only on the Mapa page → moved inside `page_mapa()`'s own `with st.sidebar:` block, confirmed testable via Step 3 point 2-4.
- **Placeholder scan:** no TBD/TODO. The full resulting file is given verbatim, not just a diff description.
- **Type consistency:** every `page_*` function takes no arguments and returns `None`, matching `st.Page`'s documented `Callable[[], None]` requirement (verified directly against the installed Streamlit's `help(st.Page)` output before writing this plan). Each page function's body is copied verbatim from its former `with tab_x:` block — no logic changes, only indentation and the `tab_x` context manager replaced by the function boundary.
- **Out of scope (explicitly, not an oversight):** no custom CSS added for the nav list's look (Global Constraints); no change to any `render_*_tab` function in the other `app/*.py` files — they're called exactly as before, just from a function instead of a `with` block.
