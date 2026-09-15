# Temas / Opinión Tab Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a new "💬 Temas" tab to the existing Streamlit dashboard (`Feat/Dashboard-Proyecto` branch) that surfaces the BERTopic topic-modeling results (`gold.gold_topicos_municipio`, `gold.nlp_chunks`) already computed by the NLP team — per-municipio topic breakdown, source mix, and drill-down to real review text — with topic labels normalized to curated Spanish (BERTopic's raw labels are multilingual, un-normalized keyword lists).

**Architecture:** Same one-file-per-tab pattern as every other tab in `app/` (`rankings.py`, `clima.py`, `municipios.py`, `alojamiento.py`): pure pandas functions covered by pytest, a `render_*_tab()` function wired into `app/main.py`. No new architecture. Two new gold-schema tables are read directly (no new dbt models needed — both already exist and are populated). One new small module (`app/topic_labels_es.py`) holds a hand-curated topic_id → Spanish label mapping, since BERTopic's raw labels are not fit for direct display (see Task 1).

**Tech Stack:** Python 3.13, Streamlit ≥1.42, Plotly Express, pandas, SQLAlchemy, pytest — no new dependencies.

**Spec:** No separate spec doc — this is a bounded extension of the existing tab-per-file pattern, design-reviewed in chat (not architectural: no new subsystem, no new interfaces other components depend on). It extends `docs/superpowers/plans/2026-09-09-dashboard-v2-tabs-and-theme.md`'s established pattern (one plan per tab, TDD steps, Playwright manual verification).

## Global Constraints

- DB access reads `AZURE_DB_URL` from `.env` via `python-dotenv` (`app/data.py`'s existing `get_engine()`) — no change to that pattern.
- Every command in this plan is run from the `AI_Dashboard_Core/` repo root using `.venv/bin/python -m <tool>`.
- Color choices reuse the palette already established in `app/color_scales.py` / used across other tabs: blue `#2a78d6`, orange `#eb6834`, muted gray `#898781`, light gray `#f0efec` — no new palette.
- `st.dataframe(...)` calls use `width="stretch"` (the convention in `app/main.py` and `app/table_view.py`); `st.plotly_chart(...)` calls use `use_container_width=True` (the convention in the most recently added tab, `app/alojamiento.py`).
- No artificial try/except: a DB failure surfaces as-is. `None`/missing values in the drill-down sample table are left as pandas produces them (`NaN`/`None` render as blank cells in `st.dataframe`) — this is a raw browsing table like the existing "Tabla" tab, not a KPI card or map layer, so the stricter "sin datos"/"—" rule from the v2 plan's Global Constraints doesn't apply here.
- New pure data-transform functions that clean/normalize a full table (not filter for one selection) belong in `app/data.py` next to the other cleaning helpers (`compute_density_metric`, `clean_accesibilidad_sentinel`) and are tested in `tests/app/test_data.py` — this matches the existing convention: `app/data.py` never has direct unit tests for its `load_*` DB-reading functions (they're thin `pd.read_sql` wrappers, unit-tested indirectly is not possible without a live DB and isn't done anywhere else in this repo), but it does unit-test its pure cleaning/merging functions.

---

## Known data-quality issue this plan works around (read before Task 2)

Audited directly against the live Azure DB on 2026-09-14: `gold.gold_topicos_municipio` has **37 rows for Tenerife's 31 real municipios**. The extra 6 are alias rows using an accented or official-long-form spelling that doesn't match the spelling `gold.gold_h3_master` (and therefore the rest of this dashboard) uses:

| Canonical (used everywhere else in the app) | Alias row in `gold_topicos_municipio` | Alias's `n_opiniones` vs. canonical's |
|---|---|---|
| Guia de Isora | Guía de Isora | 9 vs. 1564 |
| Guimar | Güímar | 12 vs. 1004 |
| La Laguna | San Cristobal de La Laguna | 189 vs. 3679 |
| La Laguna | San Cristóbal de La Laguna | 7 vs. 3679 |
| Santa Ursula | Santa Úrsula | 13 vs. 223 |
| Vilaflor | Vilaflor de Chasna | 23 vs. 80 |

This is an upstream naming-normalization bug in whichever join populated `gold_topicos_municipio`'s `municipio` column — out of scope for this dashboard plan to fix at the source. Each alias row carries a small minority of that municipio's opinions (worst case ~5%, most cases <1%), so Task 2 simply **drops the 6 alias rows** rather than merging their counts into the canonical row (merging would require recomputing `topicos_top3`'s ranking from scratch, which is unnecessary complexity for a <5% correction). This is documented inline in the code, matching the precedent already set in `app/municipios.py` for other ISTAC data-quality issues.

---

## File Structure

```
app/
├── topic_labels_es.py   # NEW — curated topic_id -> Spanish label mapping + fallback
├── data.py              # MODIFY — add load_topicos_municipio(), load_nlp_chunks(), drop_municipio_alias_rows()
├── temas.py             # NEW — tab helpers + render_temas_tab()
└── main.py              # MODIFY — wire in the new tab

tests/app/
├── test_topic_labels_es.py  # NEW
├── test_data.py             # MODIFY — cover drop_municipio_alias_rows
└── test_temas.py            # NEW
```

---

### Task 1: Curated Spanish topic labels (`app/topic_labels_es.py`)

**Files:**
- Create: `app/topic_labels_es.py`
- Test: `tests/app/test_topic_labels_es.py`

**Interfaces:**
- Consumes: nothing.
- Produces (used by Task 3): `TOPIC_LABELS_ES: dict[int, str]`, `topic_label_es(topic_id: int, fallback_label: str) -> str`.

- [x] **Step 1: Write the failing tests**

```python
# tests/app/test_topic_labels_es.py
from app.topic_labels_es import TOPIC_LABELS_ES, topic_label_es


def test_topic_label_es_returns_curated_label_when_known():
    assert topic_label_es(67, "sendero, senderos, teleférico, pico viejo, miradores, pico") == (
        "Senderismo: teleférico del Teide y miradores"
    )


def test_topic_label_es_falls_back_to_raw_label_when_unknown():
    assert topic_label_es(999999, "unknown, raw, keywords") == "unknown, raw, keywords"


def test_topic_labels_es_has_56_curated_entries():
    assert len(TOPIC_LABELS_ES) == 56


def test_topic_labels_es_has_no_empty_values():
    assert all(isinstance(v, str) and v.strip() for v in TOPIC_LABELS_ES.values())
```

- [x] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/app/test_topic_labels_es.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.topic_labels_es'`.

- [x] **Step 3: Implement `app/topic_labels_es.py`**

These 56 topic_ids are every one that appears in `gold.gold_topicos_municipio.topicos_top3` across all 37 rows (audited directly against the live DB on 2026-09-14 with `SELECT DISTINCT (t->>'topic_id')::int FROM gold.gold_topicos_municipio, jsonb_array_elements(topicos_top3) AS t`). Each label was written by reading real sample reviews from `gold.nlp_chunks` for that `topic_id`, not machine-translated from the raw keyword list — several of BERTopic's raw clusters are dominated by a single reviewer language or a specific host's name rather than a clean semantic theme, and the label says so explicitly in those cases (e.g. "Opiniones en ruso: ...", "Anfitriones muy valorados (caso: Cruzy y Rubén)") instead of forcing a generic theme name that wouldn't match the cluster's real content.

```python
# app/topic_labels_es.py
"""Curated Spanish labels for the topic clusters produced by the BERTopic
pipeline (gold.nlp_topics / gold.gold_topicos_municipio). BERTopic's raw
labels are keyword lists, often in a single reviewer language (Italian,
German, Russian, Dutch...) or dominated by a specific host's name, rather
than a clean human-readable topic. This module hand-curates a Spanish label
for each topic_id currently seen in gold_topicos_municipio's top-3 breakdown
(56 ids, audited 2026-09-14). A topic_id introduced by a future re-run of
the BERTopic model that isn't in this dict yet falls back to its raw
keyword label via topic_label_es() instead of crashing.
"""

TOPIC_LABELS_ES: dict[int, str] = {
    0: "Buena comida y servicio en restaurantes",
    1: "Guachinches y gastronomía canaria (mojo, papas)",
    3: "Ubicación en el centro de Santa Cruz",
    4: "Quejas sobre pedidos y tiempos de espera en restaurantes",
    7: "Denuncias de estafa con el depósito o reembolso",
    8: "Ubicación en el centro de Puerto de la Cruz",
    9: "Opiniones en italiano sobre la zona de Los Cristianos",
    10: "Personal amable e instalaciones limpias",
    11: "Villas familiares con espacio exterior",
    12: "Apartamentos pequeños tipo estudio (cocina, lavadora)",
    13: "Buena relación calidad-precio",
    21: "Centro histórico de La Laguna",
    23: "Ruta de vinos: Icod de los Vinos y Garachico",
    24: "Buffet y variedad de cenas en hoteles",
    26: "Instalaciones antiguas que necesitan reforma",
    31: "Elogios muy positivos al apartamento",
    35: "Cercanía al aeropuerto (ruido de aviones)",
    44: "Limpieza y detalles cuidados, exterior descuidado",
    56: "Ambiente de hostel: voluntarios, literas, dormitorio compartido",
    66: "Lugar tranquilo para desconectar",
    67: "Senderismo: teleférico del Teide y miradores",
    78: "Casa muy bonita y cómoda",
    80: "Alojamiento limpio y cómodo, con auto check-in",
    86: "Eventos culturales y fiestas locales",
    87: "Senderismo en el Parque Rural de Anaga",
    96: "Ubicación en Candelaria",
    107: "Casa limpia y bien situada",
    110: "Foro: elegir hotel para viajar con niños",
    116: "Alquiler de coche y transporte público",
    120: "Zona tranquila",
    121: "Opiniones en alemán: vistas al mar y buena ubicación",
    124: "Apartamento espacioso bien ubicado (Garachico)",
    140: "Falta de toallas o utensilios, mobiliario antiguo",
    148: "Foro: recomendaciones de hotel antes del viaje",
    161: "Anfitriones muy valorados (caso: Cruzy y Rubén)",
    183: "Anfitriona atenta y casa tranquila (caso: Lourdes)",
    193: "Problemas de instalaciones (baños, insonorización)",
    207: "Vistas a los acantilados de Los Gigantes",
    208: "Opiniones en alemán: clientes recurrentes, buena ubicación",
    216: "Ubicación en La Orotava",
    220: "Zona tranquila y apartamento limpio",
    227: "Opiniones en ruso: personal amable y buena ubicación",
    231: "Presencia o falta de ascensor",
    232: "Foro/blog: recomendaciones de qué visitar",
    249: "Sensación de estar en casa, anfitrión atento (caso: Pedro)",
    250: "Relación calidad-precio, sofá incómodo",
    292: "Opiniones en neerlandés: casa tranquila, poco turística",
    310: "Anfitriona excelente y ubicación céntrica (caso: Maria)",
    313: "Villa con vistas espectaculares",
    318: "Vistas espectaculares",
    351: "Buena ubicación cerca de Playa de las Américas",
    370: "Hotel con encanto en casco histórico",
    382: "Opiniones breves multilingües: buen anfitrión y vistas",
    400: "Foro: dónde comprar cerca de Callao Salvaje",
    414: "Foro: consejos y respuestas sobre excursiones",
    426: "Opiniones en alemán: jardín y casa",
}


def topic_label_es(topic_id: int, fallback_label: str) -> str:
    return TOPIC_LABELS_ES.get(topic_id, fallback_label)
```

- [x] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/app/test_topic_labels_es.py -v`
Expected: PASS, 4/4.

- [x] **Step 5: Commit**

```bash
git add app/topic_labels_es.py tests/app/test_topic_labels_es.py
git commit -m "feat: add curated Spanish labels for BERTopic topic clusters"
```

---

### Task 2: Data loaders + municipio alias cleanup (`app/data.py`)

**Files:**
- Modify: `app/data.py`
- Test: `tests/app/test_data.py`

**Interfaces:**
- Consumes: nothing new.
- Produces (used by Task 3 and `main.py`): `load_topicos_municipio(_engine) -> pd.DataFrame`, `load_nlp_chunks(_engine) -> pd.DataFrame`, `drop_municipio_alias_rows(df: pd.DataFrame) -> pd.DataFrame`, `MUNICIPIO_ALIAS_DROP: set[str]`.

- [x] **Step 1: Write the failing tests**

Add to `tests/app/test_data.py` (add `drop_municipio_alias_rows` to the existing `from app.data import (...)` block at the top, keeping the rest of that import list unchanged):

```python
def test_drop_municipio_alias_rows_removes_known_aliases_only():
    df = pd.DataFrame({
        "municipio": ["Guia de Isora", "Guía de Isora", "Adeje", "Güímar"],
        "n_opiniones": [1564, 9, 100, 12],
    })
    result = drop_municipio_alias_rows(df)
    assert sorted(result["municipio"].tolist()) == ["Adeje", "Guia de Isora"]


def test_drop_municipio_alias_rows_resets_index():
    df = pd.DataFrame({"municipio": ["Guía de Isora", "Adeje"], "n_opiniones": [9, 100]})
    result = drop_municipio_alias_rows(df)
    assert result.index.tolist() == [0]
```

- [x] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/app/test_data.py -v`
Expected: FAIL with `ImportError: cannot import name 'drop_municipio_alias_rows'`.

- [x] **Step 3: Add the queries, constant, loaders, and cleaning function to `app/data.py`**

Add these two query constants right after the existing `ISTAC_MENSUAL_QUERY = "SELECT * FROM silver.silver_istac_mensual"` line:

```python
TOPICOS_MUNICIPIO_QUERY = "SELECT * FROM gold.gold_topicos_municipio"
NLP_CHUNKS_QUERY = """
    SELECT chunk_id, source, source_id, chunk_index, text, topic_id, topic_label,
           municipio, zona, h3_index, fecha, pais_resenante, rating, processed_at
    FROM gold.nlp_chunks
"""
```

(`NLP_CHUNKS_QUERY` explicitly lists columns to exclude `embedding` and `tsv` — both large binary/full-text-search columns from the semantic search pipeline that this dashboard has no use for.)

Add this constant and function right after `SENTIMIENTO_COLUMNS`'s closing bracket (before `@st.cache_resource def get_engine`):

```python
# gold_topicos_municipio has 37 rows for Tenerife's 31 real municipios -- 6
# are alias rows using an accented/official-long-form spelling that doesn't
# match the spelling gold_h3_master (and the rest of this app) uses, e.g.
# "Guía de Isora" alongside the canonical "Guia de Isora" (confirmed by
# direct audit 2026-09-14: every alias carries a small minority of that
# municipio's opinions, worst case "San Cristobal de La Laguna" 189 +
# "San Cristóbal de La Laguna" 7 vs. canonical "La Laguna" 3679). Dropped
# outright rather than merged into the canonical row: merging would require
# recomputing topicos_top3's ranking from scratch for a <5% correction.
MUNICIPIO_ALIAS_DROP = {
    "Guía de Isora",
    "Güímar",
    "San Cristobal de La Laguna",
    "San Cristóbal de La Laguna",
    "Santa Úrsula",
    "Vilaflor de Chasna",
}


def drop_municipio_alias_rows(df: pd.DataFrame) -> pd.DataFrame:
    return df.loc[~df["municipio"].isin(MUNICIPIO_ALIAS_DROP)].reset_index(drop=True)
```

Add these two loaders right after `load_istac_mensual`:

```python
@st.cache_data
def load_topicos_municipio(_engine: Engine) -> pd.DataFrame:
    return drop_municipio_alias_rows(pd.read_sql(TOPICOS_MUNICIPIO_QUERY, _engine))


@st.cache_data
def load_nlp_chunks(_engine: Engine) -> pd.DataFrame:
    return pd.read_sql(NLP_CHUNKS_QUERY, _engine)
```

(`load_topicos_municipio` applies the cleanup itself so every caller gets the deduplicated 31-row table for free — `main.py` never needs to remember to call `drop_municipio_alias_rows` separately.)

- [x] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/app/test_data.py -v`
Expected: PASS, all tests (existing + 2 new).

- [x] **Step 5: Commit**

```bash
git add app/data.py tests/app/test_data.py
git commit -m "feat(data): add topicos_municipio/nlp_chunks loaders, drop municipio alias rows"
```

---

### Task 3: Temas tab helpers (`app/temas.py`)

**Files:**
- Create: `app/temas.py`
- Test: `tests/app/test_temas.py`

**Interfaces:**
- Consumes: `app.topic_labels_es.topic_label_es` (Task 1).
- Produces (used only by Task 4's wiring in `main.py`): `SOURCE_LABELS: dict[str, str]`, `get_topicos_row(df, municipio) -> pd.Series | None`, `fuentes_breakdown(row) -> pd.DataFrame`, `top_topicos_dataframe(row) -> pd.DataFrame`, `sample_chunks(chunks_df, municipio, topic_id, n=15) -> pd.DataFrame`, `render_temas_tab(topicos_municipio_df, chunks_df) -> None`.

- [x] **Step 1: Write the failing tests**

```python
# tests/app/test_temas.py
import pandas as pd

from app.temas import (
    fuentes_breakdown,
    get_topicos_row,
    sample_chunks,
    top_topicos_dataframe,
)


def _topicos_municipio_df():
    return pd.DataFrame(
        [
            {
                "municipio": "Adeje",
                "n_opiniones": 14973.0,
                "n_topicos_distintos": 439,
                "topic_id_principal": 11,
                "topico_principal": "villa, outdoor, family, drive, kids, seating",
                "n_opiniones_principal": 417,
                "topicos_top3": [
                    {"n": 417, "label": "villa, outdoor, family, drive, kids, seating", "topic_id": 11},
                    {"n": 376, "label": "small, coffee, living room, washing, buy, complex", "topic_id": 12},
                    {
                        "n": 221,
                        "label": "highly, truly, appreciated, incredibly, wonderful, apartment absolutely",
                        "topic_id": 31,
                    },
                ],
                "fuentes": {"booking_review": 13251, "tripadvisor_review": 103, "losviajeros_message": 1619},
            },
            {
                "municipio": "Arona",
                "n_opiniones": 21539.0,
                "n_topicos_distintos": 439,
                "topic_id_principal": 12,
                "topico_principal": "small, coffee, living room, washing, buy, complex",
                "n_opiniones_principal": 321,
                "topicos_top3": [
                    {"n": 321, "label": "small, coffee, living room, washing, buy, complex", "topic_id": 12},
                ],
                "fuentes": {"booking_review": 20616},
            },
        ]
    )


def test_get_topicos_row_returns_matching_row():
    row = get_topicos_row(_topicos_municipio_df(), "Adeje")
    assert row["n_opiniones"] == 14973.0


def test_get_topicos_row_returns_none_for_unknown_municipio():
    assert get_topicos_row(_topicos_municipio_df(), "No Existe") is None


def test_fuentes_breakdown_maps_known_sources_to_display_labels():
    row = get_topicos_row(_topicos_municipio_df(), "Adeje")
    result = fuentes_breakdown(row)
    counts = dict(zip(result["fuente"], result["cantidad"]))
    assert counts == {"Booking": 13251, "TripAdvisor": 103, "Los Viajeros (foro)": 1619}


def test_fuentes_breakdown_falls_back_to_raw_key_for_unknown_source():
    row = pd.Series({"fuentes": {"reddit_post": 5}})
    result = fuentes_breakdown(row)
    assert result["fuente"].tolist() == ["reddit_post"]


def test_top_topicos_dataframe_uses_curated_spanish_labels():
    row = get_topicos_row(_topicos_municipio_df(), "Adeje")
    result = top_topicos_dataframe(row)
    assert result["label_es"].tolist() == [
        "Villas familiares con espacio exterior",
        "Apartamentos pequeños tipo estudio (cocina, lavadora)",
        "Elogios muy positivos al apartamento",
    ]
    assert result["n"].tolist() == [417, 376, 221]
    assert result["topic_id"].tolist() == [11, 12, 31]


def _chunks_df():
    return pd.DataFrame(
        [
            {
                "chunk_id": 1, "source": "booking_review", "text": "Precioso apartamento",
                "topic_id": 11, "municipio": "Adeje", "h3_index": "a",
                "fecha": "2025-01-10", "pais_resenante": "España", "rating": 9.0,
            },
            {
                "chunk_id": 2, "source": "tripadvisor_review", "text": "Great villa",
                "topic_id": 11, "municipio": "Adeje", "h3_index": "b",
                "fecha": "2025-03-01", "pais_resenante": "Reino Unido", "rating": 5.0,
            },
            {
                "chunk_id": 3, "source": "booking_review", "text": "Otro tema",
                "topic_id": 12, "municipio": "Adeje", "h3_index": "c",
                "fecha": "2025-02-15", "pais_resenante": "Francia", "rating": 8.0,
            },
            {
                "chunk_id": 4, "source": "booking_review", "text": "Villa en Arona",
                "topic_id": 11, "municipio": "Arona", "h3_index": "d",
                "fecha": "2025-01-20", "pais_resenante": "Italia", "rating": 10.0,
            },
        ]
    )


def test_sample_chunks_filters_by_municipio_and_topic():
    result = sample_chunks(_chunks_df(), "Adeje", 11, n=15)
    assert sorted(result["chunk_id"].tolist()) == [1, 2]


def test_sample_chunks_sorts_by_fecha_descending():
    result = sample_chunks(_chunks_df(), "Adeje", 11, n=15)
    assert result["chunk_id"].tolist() == [2, 1]


def test_sample_chunks_respects_n():
    result = sample_chunks(_chunks_df(), "Adeje", 11, n=1)
    assert len(result) == 1


def test_sample_chunks_maps_source_to_display_label():
    result = sample_chunks(_chunks_df(), "Adeje", 11, n=15)
    assert set(result["fuente"]) == {"Booking", "TripAdvisor"}
```

- [x] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/app/test_temas.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.temas'`.

- [x] **Step 3: Implement `app/temas.py`**

```python
# app/temas.py
import pandas as pd
import plotly.express as px
import streamlit as st

from app.topic_labels_es import topic_label_es

SOURCE_LABELS = {
    "booking_review": "Booking",
    "tripadvisor_review": "TripAdvisor",
    "losviajeros_message": "Los Viajeros (foro)",
    "youtube_comment": "YouTube",
}


def get_topicos_row(df: pd.DataFrame, municipio: str) -> pd.Series | None:
    matches = df.loc[df["municipio"] == municipio]
    if matches.empty:
        return None
    return matches.iloc[0]


def fuentes_breakdown(row: pd.Series) -> pd.DataFrame:
    rows = [
        {"fuente": SOURCE_LABELS.get(fuente, fuente), "cantidad": cantidad}
        for fuente, cantidad in row["fuentes"].items()
    ]
    return pd.DataFrame(rows)


def top_topicos_dataframe(row: pd.Series) -> pd.DataFrame:
    rows = [
        {
            "topic_id": t["topic_id"],
            "label_es": topic_label_es(t["topic_id"], t["label"]),
            "n": t["n"],
        }
        for t in row["topicos_top3"]
    ]
    return pd.DataFrame(rows)


def sample_chunks(chunks_df: pd.DataFrame, municipio: str, topic_id: int, n: int = 15) -> pd.DataFrame:
    filtered = chunks_df.loc[
        (chunks_df["municipio"] == municipio) & (chunks_df["topic_id"] == topic_id)
    ].copy()
    filtered["fuente"] = filtered["source"].map(lambda s: SOURCE_LABELS.get(s, s))
    return filtered.sort_values("fecha", ascending=False).head(n)


def render_temas_tab(topicos_municipio_df: pd.DataFrame, chunks_df: pd.DataFrame) -> None:
    municipio = st.selectbox(
        "Municipio", sorted(topicos_municipio_df["municipio"].tolist()), key="temas_municipio"
    )
    row = get_topicos_row(topicos_municipio_df, municipio)
    if row is None:
        st.warning("No hay datos de temas para este municipio.")
        return

    col1, col2 = st.columns(2)
    col1.metric("Opiniones analizadas", int(row["n_opiniones"]))
    col2.metric("Temas distintos detectados", int(row["n_topicos_distintos"]))

    fuentes_df = fuentes_breakdown(row)
    topicos_df = top_topicos_dataframe(row)

    col_fuentes, col_topicos = st.columns(2)
    with col_fuentes:
        fig_fuentes = px.pie(
            fuentes_df,
            names="fuente",
            values="cantidad",
            title="Origen de las opiniones",
            color_discrete_sequence=["#2a78d6", "#eb6834", "#898781", "#f0efec"],
        )
        st.plotly_chart(fig_fuentes, use_container_width=True)
    with col_topicos:
        fig_topicos = px.bar(
            topicos_df.sort_values("n"),
            x="n",
            y="label_es",
            orientation="h",
            title="Temas más mencionados",
        )
        fig_topicos.update_traces(marker_color="#2a78d6")
        st.plotly_chart(fig_topicos, use_container_width=True)

    st.subheader("Ver opiniones reales de un tema")
    topico_elegido = st.selectbox("Tema", topicos_df["label_es"].tolist(), key="temas_topico_elegido")
    topic_id_elegido = int(topicos_df.loc[topicos_df["label_es"] == topico_elegido, "topic_id"].iloc[0])

    muestra = sample_chunks(chunks_df, municipio, topic_id_elegido, n=15)
    if muestra.empty:
        st.info("No hay opiniones de muestra para este tema en este municipio.")
        return
    st.dataframe(
        muestra[["fecha", "pais_resenante", "rating", "fuente", "text"]],
        width="stretch",
    )
```

- [x] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/app/test_temas.py -v`
Expected: PASS, 9/9.

- [x] **Step 5: Commit**

```bash
git add app/temas.py tests/app/test_temas.py
git commit -m "feat: add Temas/Opinión tab helpers (topic breakdown, source mix, review drill-down)"
```

---

### Task 4: Wire the tab into `app/main.py` + manual verification

**Files:**
- Modify: `app/main.py`

**Interfaces:**
- Consumes: `load_topicos_municipio`, `load_nlp_chunks` (Task 2), `render_temas_tab` (Task 3).
- Produces: nothing further downstream — this is the last task.

- [x] **Step 1: Add the imports**

In `app/main.py`, change the `from app.data import (...)` block (currently lines 8-21) to add `load_nlp_chunks` and `load_topicos_municipio` in their alphabetical position:

```python
from app.data import (
    filter_by_municipio,
    get_engine,
    list_municipios,
    load_accesibilidad,
    load_h3_master,
    load_isocronas,
    load_istac_anual,
    load_istac_mensual,
    load_municipio_master,
    load_nlp_chunks,
    load_sentimiento,
    load_topicos_municipio,
    merge_accesibilidad,
    merge_h3_data,
)
```

Add this import line right after `from app.table_view import filter_table, prepare_table_view` (currently line 27):

```python
from app.temas import render_temas_tab
```

- [x] **Step 2: Load the new data**

Change this block (currently lines 101-108):

```python
engine = get_engine()
h3_master = load_h3_master(engine)
sentimiento = load_sentimiento(engine)
accesibilidad = load_accesibilidad(engine)
isocronas = load_isocronas(engine)
municipio_master = load_municipio_master(engine)
istac_anual = load_istac_anual(engine)
istac_mensual = load_istac_mensual(engine)
```

to:

```python
engine = get_engine()
h3_master = load_h3_master(engine)
sentimiento = load_sentimiento(engine)
accesibilidad = load_accesibilidad(engine)
isocronas = load_isocronas(engine)
municipio_master = load_municipio_master(engine)
istac_anual = load_istac_anual(engine)
istac_mensual = load_istac_mensual(engine)
topicos_municipio = load_topicos_municipio(engine)
nlp_chunks = load_nlp_chunks(engine)
```

- [x] **Step 3: Add the tab**

Change the tabs line (currently lines 132-142):

```python
tab_resumen, tab_mapa, tab_tabla, tab_rankings, tab_clima, tab_municipios, tab_alojamiento = st.tabs(
    [
        "📊 Resumen",
        "🗺️ Mapa",
        "📋 Tabla",
        "🏆 Rankings",
        "🌡️ Clima",
        "🏛️ Municipios",
        "🏨 Alojamiento",
    ]
)
```

to:

```python
tab_resumen, tab_mapa, tab_tabla, tab_rankings, tab_clima, tab_municipios, tab_alojamiento, tab_temas = st.tabs(
    [
        "📊 Resumen",
        "🗺️ Mapa",
        "📋 Tabla",
        "🏆 Rankings",
        "🌡️ Clima",
        "🏛️ Municipios",
        "🏨 Alojamiento",
        "💬 Temas",
    ]
)
```

Add this block right after the existing `with tab_alojamiento:` block (currently lines 215-219, at the end of the file):

```python
with tab_temas:
    render_temas_tab(topicos_municipio, nlp_chunks)
```

- [x] **Step 4: Run the full test suite**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: PASS, all tests (previous 92 + this plan's 15 new: 4 in `test_topic_labels_es.py`, 2 in `test_data.py`, 9 in `test_temas.py`).

- [x] **Step 5: Manual visual verification**

Start the app: `.venv/bin/python -m streamlit run app/main.py`

Using Playwright + headless Chromium (install if not already present in this environment: `.venv/bin/python -m pip install playwright && .venv/bin/python -m playwright install chromium`), load the running app, click the "💬 Temas" tab, and screenshot it. Confirm by looking at the resulting image, not by assuming:

1. Municipio selector shows 31 options (not 37 — confirms `drop_municipio_alias_rows` worked; spot-check that "Guía de Isora" / "Güímar" / "San Cristobal de La Laguna" / "San Cristóbal de La Laguna" / "Santa Úrsula" / "Vilaflor de Chasna" are NOT in the dropdown, only their canonical counterparts are).
2. Selecting "Adeje" shows: KPI cards with real numbers (not "—"), a pie chart of Booking/TripAdvisor/Los Viajeros, a horizontal bar chart with 3 Spanish topic labels (not raw multilingual keyword lists).
3. Selecting one of the 3 topics from the "Tema" dropdown populates the table below with real review text, a date, a country, and a source label — confirm the table isn't empty and the `fuente` column shows "Booking"/"TripAdvisor"/"Los Viajeros (foro)", not raw `booking_review`/etc.
4. No browser console errors.

**Discovered during this step, not part of the original plan:** the first launch crashed on `KeyError: 'es_zona_turistica_oficial'` — unrelated to this plan, `gold.gold_h3_master` had its old boolean `es_zona_turistica_oficial`/`es_enp` columns replaced with `pct_area_zona_turistica`/`pct_area_enp` (overlap fraction) sometime after this dashboard was last verified live. This broke every tab, not just Temas, since `full_gdf` is built before any tab renders. User approved a same-session hotfix: `app/data.py::compute_restriction_category` and `app/detail_panel.py::restriction_badges` now threshold the new `pct_area_*` columns at `> 0` to reproduce the old boolean semantics (both existing test files updated to match). Committed separately (`7573077`) from this plan's own commits so the schema-drift fix is easy to distinguish from the Temas tab work. Screenshots below are from the app running with this hotfix applied.

Screenshots taken (saved outside the repo, in the session's scratch area): default "Temas" view for Adeje — KPI cards (14973 opiniones, 439 temas), pie chart (Booking 88.5% / Los Viajeros 10.8% / TripAdvisor 0.688%), bar chart with the 3 curated Spanish labels ("Villas familiares con espacio exterior", "Apartamentos pequeños tipo estudio (cocina, lavadora)", "Elogios muy positivos al apartamento") — matching Task 1's curated dict exactly, not raw BERTopic keywords. Municipio dropdown opened: alphabetical list starting "Adeje, Arafo, Arico, Arona, Buenavista del Norte, Candelaria, El Rosario, El Sauzal, El Tanque, Fasnia, Garachico..." — no alias duplicates in this range. Sample-reviews table for topic "Villas familiares con espacio exterior": 10+ real Booking reviews, sorted by `fecha` descending (2026-08-22 down to 2026-08-09), `pais_resenante` and `rating` populated, `fuente` showing "Booking" (not `booking_review`). Zero browser console errors across all screenshots.

- [x] **Step 6: Commit**

```bash
git add app/main.py
git commit -m "feat: wire Temas/Opinión tab into the dashboard"
```

---

## Self-Review Notes

- **Spec coverage:** topic breakdown per municipio + source mix + drill-down to real text → Task 3. Spanish normalization of BERTopic's raw labels → Task 1. Known `gold_topicos_municipio` alias-row data quality issue → Task 2 (documented and handled, not silently ignored). Wiring + visual proof it actually works against the live Azure DB → Task 4.
- **Placeholder scan:** no TBD/TODO. All 56 curated labels are written out in full in Task 1 (not "see design doc" or "similar to the table above").
- **Type consistency:** `render_temas_tab(topicos_municipio_df, chunks_df)` (Task 3) is called exactly as `render_temas_tab(topicos_municipio, nlp_chunks)` in Task 4's `main.py` wiring — same two positional arguments, same order. `topic_label_es(topic_id: int, fallback_label: str)` (Task 1) is called with matching argument order and types inside `top_topicos_dataframe` (Task 3).
- **Out of scope (explicitly, not an oversight):** hexagon-grain topic data (`gold.gold_topicos_h3`) is not used — this tab stays at municipio grain, consistent with the existing `app/municipios.py` tab. Merging the 6 alias rows into their canonical municipio (instead of dropping them) is left as a possible future improvement if the upstream naming bug isn't fixed first.

---

**Plan complete and saved to `docs/superpowers/plans/2026-09-14-temas-opinion-tab.md`. Two execution options:**

1. **Subagent-Driven** — I dispatch a fresh subagent per task, review between tasks, fast iteration, but you only see each task's result once it's done.
2. **Inline Execution** — Ejecutamos en esta misma sesión, tarea a tarea, con checkpoints, como hicimos con el plan de dashboard v2.

¿Cuál prefieres?
