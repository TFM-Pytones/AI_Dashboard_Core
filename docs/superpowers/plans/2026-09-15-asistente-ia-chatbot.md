# Asistente IA (Chatbot híbrido Text-to-SQL + RAG) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a chat page to the Streamlit dashboard that answers turismo questions about Tenerife, routing each question to either a hand-rolled Text-to-SQL agent (for aggregate questions against `gold.*` tables) or the existing RAG pipeline (for perception/complaint questions over traveler reviews).

**Architecture:** A new `analytics/chat/` package holds two pure, LLM-backed pieces — `router.py` (classifies a question as `"sql"` or `"rag"`) and `sql_agent.py` (generates, validates, and executes read-only SQL against a hand-curated schema of `gold.*` tables). A new `app/asistente.py` page wires these together with the already-working `analytics/rag/rag_answer.py` behind a `st.chat_input`/`st.chat_message` UI, registered in `app/main.py`'s existing `st.navigation` page list.

**Tech Stack:** Streamlit (chat components), Groq via the existing `analytics/llm/llm_client.LLMClient` (no LangChain), SQLAlchemy + pandas (`pd.read_sql`, matching `app/data.py`'s established pattern), pytest for TDD.

**Spec:** `docs/superpowers/specs/2026-09-15-asistente-ia-chatbot-design.md`

## Global Constraints

- No new dependencies — reuse `LLMClient` (Groq), SQLAlchemy, pandas, Streamlit; LangChain is explicitly out (see spec decision 2).
- The SQL agent may only execute a single read-only `SELECT` against the curated `gold.*` table list defined in `analytics/chat/sql_agent.py` — never DDL/DML, never multiple statements.
- Every LLM/DB call in the chat path is wrapped so failures show a readable message in the chat, never a raw traceback (spec "Manejo de errores").
- Chat history lives only in `st.session_state` for the current session — no persistence.
- Every new pure function (validation, classification, schema formatting) is developed test-first (red/green), per this project's established TDD convention (confirmed throughout `tests/app/`). Functions that need the LLM or a live DB take an injectable client/engine parameter so tests can pass a fake — no `unittest.mock` needed, matching the project's existing test style (plain fakes, no mocking framework in any current test file).
- End-to-end behavior (the actual Groq + Postgres calls, the rendered page) is verified by running the real app with Playwright against the live database, the same way points 8.1–8.3 were verified in this project — not by mocking Groq/Postgres in pytest.

---

### Task 1: Make `analytics/rag/rag_answer.py` importable as a dotted module

**Why this is first:** `app/asistente.py` (Task 4) needs to call `analytics.rag.rag_answer.responder()` via a normal dotted import (the same style `app/translation.py` already uses for `analytics.llm.llm_client`). Today, `rag_answer.py` only works when run directly as a script (`python analytics/rag/rag_answer.py`) — Python auto-adds a script's own directory to `sys.path` when it's run as `__main__`, which is what currently lets its bare `from filtros import ...` and `from retriever import ...` resolve (both `filtros.py` and `retriever.py` live in `analytics/rag/`, the same directory as `rag_answer.py`). Importing it as `analytics.rag.rag_answer` from elsewhere does **not** get that automatic path addition, so those bare imports fail. Confirmed empirically:

```
$ python -c "import analytics.rag.rag_answer"
ModuleNotFoundError: No module named 'filtros'
```

The fix: add an explicit `sys.path.insert` for `rag_answer.py`'s own directory, the same way it already does for `analytics/llm`. This is additive — running it as a script still works exactly as before (the directory is just added twice, which is harmless).

**Files:**
- Modify: `analytics/rag/rag_answer.py:21-30`
- Test: `tests/analytics/__init__.py` (create, empty)
- Test: `tests/analytics/rag/__init__.py` (create, empty)
- Test: `tests/analytics/rag/test_rag_answer_import.py` (create)

**Interfaces:**
- Produces: `analytics.rag.rag_answer.responder(pregunta: str, k: int = 8, filters: dict | None = None, hibrida: bool = True, fijos=frozenset()) -> Respuesta` — already exists and is unchanged; this task only fixes how the module is *reached*.

- [ ] **Step 1: Write the failing test**

Create `tests/analytics/__init__.py` with empty content, and `tests/analytics/rag/__init__.py` with empty content (mirrors the existing `tests/app/__init__.py` pattern used everywhere else in this project).

Create `tests/analytics/rag/test_rag_answer_import.py`:

```python
import importlib


def test_rag_answer_importable_as_dotted_module():
    # Regression test: analytics/rag/rag_answer.py used to only work when run
    # directly as a script (python analytics/rag/rag_answer.py), because
    # Python auto-adds a script's own directory to sys.path only when it's
    # __main__. Importing it as analytics.rag.rag_answer (the way
    # app/asistente.py needs to) raised ModuleNotFoundError: No module named
    # 'filtros', since filtros.py and retriever.py live next to it in
    # analytics/rag/ and were only reachable via that automatic path.
    modulo = importlib.import_module("analytics.rag.rag_answer")
    assert callable(modulo.responder)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/analytics/rag/test_rag_answer_import.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'filtros'`

- [ ] **Step 3: Write minimal implementation**

In `analytics/rag/rag_answer.py`, change:

```python
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "llm"))
```

to:

```python
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "llm"))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/analytics/rag/test_rag_answer_import.py -v`
Expected: PASS

Also run the full suite to confirm nothing else broke:

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: all tests pass (188 previously passing + 1 new)

- [ ] **Step 5: Commit**

```bash
git add analytics/rag/rag_answer.py tests/analytics/__init__.py tests/analytics/rag/__init__.py tests/analytics/rag/test_rag_answer_import.py
git commit -m "fix: make analytics/rag/rag_answer importable as a dotted module

app/asistente.py needs to import it the same way app/translation.py
imports analytics.llm.llm_client; it only worked as a directly-run
script before, since filtros.py/retriever.py were only reachable via
the sys.path entry Python adds automatically for __main__ scripts."
```

---

### Task 2: `analytics/chat/router.py` — question classifier

**Files:**
- Create: `analytics/chat/router.py`
- Test: `tests/analytics/chat/__init__.py` (create, empty)
- Test: `tests/analytics/chat/test_router.py` (create)

**Interfaces:**
- Consumes: `analytics.llm.llm_client.LLMClient` — `complete(self, prompt: str, temperature: float = 0.4, max_tokens: int = 1200) -> str` (existing, unchanged).
- Produces: `analytics.chat.router.clasificar(pregunta: str, llm: LLMClient | None = None) -> Literal["sql", "rag"]` — used by Task 4.

- [ ] **Step 1: Write the failing test**

Create `tests/analytics/chat/__init__.py` with empty content.

Create `tests/analytics/chat/test_router.py`:

```python
from analytics.chat.router import clasificar


class _LLMFalso:
    """Fake LLM client for tests -- no network call, no API key needed.
    Matches LLMClient.complete's signature so clasificar() can't tell the
    difference."""

    def __init__(self, respuesta: str):
        self.respuesta = respuesta
        self.prompts_recibidos = []

    def complete(self, prompt: str, temperature: float = 0.4, max_tokens: int = 1200) -> str:
        self.prompts_recibidos.append(prompt)
        return self.respuesta


def test_clasificar_devuelve_sql_para_pregunta_de_cifras():
    assert clasificar("¿cuántas plazas hoteleras hay en Adeje?", llm=_LLMFalso("SQL")) == "sql"


def test_clasificar_devuelve_rag_para_pregunta_de_opinion():
    assert clasificar("¿de qué se quejan los turistas en Adeje?", llm=_LLMFalso("RAG")) == "rag"


def test_clasificar_normaliza_mayusculas_y_espacios():
    assert clasificar("¿cuántos hoteles hay?", llm=_LLMFalso("  sql \n")) == "sql"


def test_clasificar_cae_a_rag_ante_respuesta_inesperada_del_llm():
    assert clasificar("pregunta ambigua", llm=_LLMFalso("No estoy seguro")) == "rag"


def test_clasificar_pasa_la_pregunta_al_prompt():
    llm = _LLMFalso("RAG")
    clasificar("¿qué opinan del ruido en Los Cristianos?", llm=llm)
    assert "¿qué opinan del ruido en Los Cristianos?" in llm.prompts_recibidos[0]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/analytics/chat/test_router.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'analytics.chat'`

- [ ] **Step 3: Write minimal implementation**

Create `analytics/chat/router.py`:

```python
"""Router del chatbot (Bloque 8, Subtarea 8.4): decide si una pregunta va
al agente Text-to-SQL (analytics.chat.sql_agent) o al motor RAG
(analytics.rag.rag_answer), antes de despachar.

Ver docs/superpowers/specs/2026-09-15-asistente-ia-chatbot-design.md,
decision 4, para el porqué de clasificar con el LLM en vez de con
palabras clave.
"""

from typing import Literal

from analytics.llm.llm_client import LLMClient

PROMPT_CLASIFICACION = """Eres un router que decide qué motor debe responder una pregunta sobre turismo en Tenerife.

Responde con una única palabra: SQL o RAG.

- SQL: la pregunta pide una cifra, un agregado, una comparación numérica o un ranking, calculable con una consulta SQL sobre tablas de datos oficiales (población, paro, empleo, plazas de vivienda vacacional, turismo hotelero, tráfico aéreo). Ejemplos: "¿cuántas plazas hoteleras hay en Adeje?", "¿qué municipio tiene mayor paro?", "¿cuántos pasajeros llegaron a Tenerife Sur en 2025?".
- RAG: la pregunta pide opiniones, percepciones, quejas o experiencias de viajeros, no calculables con una consulta SQL. Ejemplos: "¿por qué se quejan los turistas del transporte en el sur?", "¿qué opinan sobre las carreteras de Anaga?", "¿cómo describen la playa de Adeje?".

PREGUNTA: {pregunta}

Responde solo con SQL o RAG, sin explicación."""


def clasificar(pregunta: str, llm: LLMClient | None = None) -> Literal["sql", "rag"]:
    cliente = llm or LLMClient()
    respuesta = cliente.complete(
        PROMPT_CLASIFICACION.format(pregunta=pregunta), temperature=0.0, max_tokens=5
    )
    if respuesta.strip().upper().startswith("SQL"):
        return "sql"
    return "rag"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/analytics/chat/test_router.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add analytics/chat/router.py tests/analytics/chat/__init__.py tests/analytics/chat/test_router.py
git commit -m "feat: add SQL-vs-RAG router for the chatbot (8.4)"
```

---

### Task 3: `analytics/chat/sql_agent.py` — schema, validation, and the SQL agent

**Files:**
- Create: `analytics/chat/sql_agent.py`
- Test: `tests/analytics/chat/test_sql_agent.py` (create)

**Interfaces:**
- Consumes: `analytics.llm.llm_client.LLMClient` (same as Task 2); a SQLAlchemy `Engine` (from `app.data.get_engine()`, wired in Task 4).
- Produces:
  - `analytics.chat.sql_agent.ESQUEMA_GOLD: dict[str, list[tuple[str, str]]]` — table name → list of `(column, description)`.
  - `analytics.chat.sql_agent.TABLAS_PERMITIDAS: set[str]`
  - `analytics.chat.sql_agent.validar_sql(sql: str) -> tuple[bool, str | None]`
  - `analytics.chat.sql_agent.asegurar_limit(sql: str, limite: int = 200) -> str`
  - `analytics.chat.sql_agent.RespuestaSQL` dataclass: `texto: str`, `sql: str`, `filas: list[dict]`, `error: str | None`
  - `analytics.chat.sql_agent.responder_sql(pregunta: str, engine, llm: LLMClient | None = None) -> RespuestaSQL` — used by Task 4.

This task has two parts: pure functions first (TDD, no network/DB), then the orchestrating `responder_sql` (implemented directly — its correctness against real Groq/Postgres is checked in Task 6, per the Global Constraints section: this mirrors how `app/main.py`'s page-level wiring was verified for 8.1–8.3, not unit-tested).

#### Part A — pure functions (`validar_sql`, `asegurar_limit`)

- [ ] **Step 1: Write the failing tests**

Create `tests/analytics/chat/test_sql_agent.py`:

```python
import pandas as pd
import pytest

from analytics.chat.sql_agent import (
    ESQUEMA_GOLD,
    LIMIT_POR_DEFECTO,
    RespuestaSQL,
    asegurar_limit,
    describir_esquema,
    responder_sql,
    validar_sql,
)


def test_validar_sql_acepta_select_simple_sobre_tabla_permitida():
    es_valido, motivo = validar_sql("SELECT municipio, paro_actual FROM gold.gold_municipio_master")
    assert es_valido is True
    assert motivo is None


@pytest.mark.parametrize(
    "palabra",
    ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE", "GRANT", "CREATE"],
)
def test_validar_sql_rechaza_sentencia_que_no_es_select(palabra):
    # Cualquier sentencia de escritura por sí sola ya falla el primer
    # requisito (debe empezar por SELECT), antes de llegar a la lista de
    # palabras prohibidas -- se comprueba aquí explícitamente.
    es_valido, motivo = validar_sql(f"{palabra} INTO gold.gold_municipio_master VALUES (1)")
    assert es_valido is False
    assert "SELECT" in motivo


@pytest.mark.parametrize(
    "palabra",
    ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE", "GRANT", "CREATE"],
)
def test_validar_sql_rechaza_palabras_prohibidas_dentro_de_un_select(palabra):
    # La lista de palabras prohibidas es una segunda capa de defensa (por si
    # el SQL generado por el LLM, aunque empiece por SELECT y sea una única
    # sentencia, intentara colar una de estas palabras en cualquier parte de
    # la consulta).
    es_valido, motivo = validar_sql(
        f"SELECT municipio FROM gold.gold_municipio_master WHERE municipio = '{palabra}'"
    )
    assert es_valido is False
    assert palabra in motivo


def test_validar_sql_rechaza_multiples_sentencias():
    es_valido, motivo = validar_sql(
        "SELECT 1 FROM gold.gold_municipio_master; DROP TABLE gold.gold_municipio_master"
    )
    assert es_valido is False
    assert "única sentencia" in motivo


def test_validar_sql_rechaza_tablas_fuera_de_la_lista_curada():
    es_valido, motivo = validar_sql("SELECT * FROM gold.gold_h3_master")
    assert es_valido is False
    assert "gold.gold_h3_master" in motivo


def test_validar_sql_acepta_join_entre_tablas_permitidas():
    es_valido, motivo = validar_sql(
        "SELECT a.municipio, b.anio FROM gold.gold_municipio_master a "
        "JOIN gold.gold_municipio_anual b ON a.cod_municipio = b.cod_municipio"
    )
    assert es_valido is True
    assert motivo is None


def test_asegurar_limit_anade_limit_por_defecto_cuando_falta():
    resultado = asegurar_limit("SELECT * FROM gold.gold_municipio_master")
    assert "LIMIT 200" in resultado


def test_asegurar_limit_respeta_limit_explicito_menor():
    resultado = asegurar_limit("SELECT * FROM gold.gold_municipio_master LIMIT 5")
    assert resultado.count("LIMIT") == 1
    assert "LIMIT 5" in resultado


def test_esquema_gold_solo_incluye_tablas_curadas_a_nivel_municipio():
    # gold_h3_master (nivel hexágono, ~80 columnas técnicas) se excluye a
    # propósito -- ver decisión 3 de la spec.
    assert "gold.gold_h3_master" not in ESQUEMA_GOLD
    assert "gold.gold_municipio_master" in ESQUEMA_GOLD
    assert "gold.gold_aena_pasajeros" in ESQUEMA_GOLD


def test_describir_esquema_incluye_todas_las_tablas_y_columnas():
    texto = describir_esquema()
    for tabla, columnas in ESQUEMA_GOLD.items():
        assert tabla in texto
        for columna, _descripcion in columnas:
            assert columna in texto
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/analytics/chat/test_sql_agent.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'analytics.chat.sql_agent'`

- [ ] **Step 3: Write minimal implementation (schema + validation)**

Create `analytics/chat/sql_agent.py`:

```python
"""Agente Text-to-SQL del chatbot (Bloque 8, Subtarea 8.4): genera SQL de
solo lectura contra un esquema curado de tablas gold.* a nivel
municipio/isla, lo valida, lo ejecuta, y redacta la respuesta.

Sin LangChain a propósito -- ver docs/superpowers/specs/2026-09-15-asistente-ia-chatbot-design.md,
decisiones 2 y 3.
"""

import re
from dataclasses import dataclass, field

import pandas as pd

from analytics.llm.llm_client import LLMClient

# Esquema curado a mano (igual que KPI_COLUMNS/METRICS/MUNICIPIO_METRICS en
# app/): solo tablas a nivel municipio/isla ya usadas por el dashboard.
# gold_h3_master (nivel hexágono, ~80 columnas técnicas de satélite/clima) se
# excluye a propósito -- un esquema más pequeño produce SQL más preciso, y
# esas preguntas agregadas no son a nivel hexágono.
ESQUEMA_GOLD: dict[str, list[tuple[str, str]]] = {
    "gold.gold_municipio_master": [
        ("cod_municipio", "código INE del municipio"),
        ("municipio", "nombre del municipio"),
        ("area_km2", "superficie en km2"),
        ("poblacion_actual", "población total actual"),
        ("paro_actual", "personas en paro registrado, dato actual"),
        ("empleo_total_actual", "personas empleadas (asalariados + autónomos), dato actual"),
        ("empleo_autonomos_actual", "trabajadores autónomos, dato actual"),
        ("empleo_hosteleria_actual", "empleados en hostelería, dato actual"),
        ("plazas_vv_actual", "plazas de vivienda vacacional, dato actual"),
        ("tasa_ocupacion_vv_actual", "% de ocupación de vivienda vacacional, dato actual"),
        ("ingresos_vv_actual", "ingresos por vivienda vacacional en euros, dato actual"),
        ("n_establecimientos_registro", "número de alojamientos turísticos con registro oficial"),
        ("n_plazas_registro", "plazas turísticas registradas (capacidad total)"),
        ("n_hoteles", "número de hoteles"),
        ("n_vv", "número de viviendas vacacionales registradas"),
        ("densidad_plazas_km2", "plazas turísticas por km2"),
        ("plazas_por_1000_hab", "plazas turísticas por cada 1000 habitantes"),
        ("crec_poblacion_pct", "% de crecimiento de población desde 2022"),
        ("var_paro_pct", "% de variación del paro desde 2022"),
        ("crec_empleo_total_pct", "% de crecimiento del empleo total desde 2022"),
        ("crec_plazas_vv_pct", "% de crecimiento de plazas de vivienda vacacional desde 2022"),
        ("crec_ingresos_vv_pct", "% de crecimiento de ingresos de vivienda vacacional desde 2022"),
        ("n_establecimientos_booking", "número de alojamientos con presencia en Booking"),
        ("rating_booking_medio", "valoración media en Booking, escala 0-10"),
        ("n_reviews_booking", "número de reseñas en Booking"),
        ("n_establecimientos_tripadvisor", "número de alojamientos con presencia en TripAdvisor"),
        ("rating_tripadvisor_medio", "valoración media en TripAdvisor, escala 0-5"),
        ("n_pois_total", "número de puntos de interés turístico"),
        ("n_paradas_bus", "número de paradas de autobús"),
    ],
    "gold.gold_municipio_anual": [
        ("cod_municipio", "código INE del municipio"),
        ("municipio", "nombre del municipio"),
        ("anio", "año de la serie"),
        ("poblacion", "población total ese año"),
        ("paro_medio", "media anual de personas en paro registrado"),
        ("var_paro_yoy_pct", "% de variación del paro respecto al año anterior"),
        ("empleo_total_medio", "media anual de personas empleadas"),
        ("crec_empleo_total_yoy_pct", "% de crecimiento del empleo respecto al año anterior"),
        ("empleo_autonomos_medio", "media anual de trabajadores autónomos"),
        ("crec_empleo_autonomos_yoy_pct", "% de crecimiento de autónomos respecto al año anterior"),
        ("plazas_vv_media", "media anual de plazas de vivienda vacacional"),
        ("crec_plazas_vv_yoy_pct", "% de crecimiento de plazas VV respecto al año anterior"),
        ("ingresos_vv_media_mensual", "ingresos medios mensuales de vivienda vacacional en euros"),
        ("crec_ingresos_mensual_yoy_pct", "% de crecimiento de ingresos VV respecto al año anterior"),
        ("tasa_ocupacion_vv_media", "% medio de ocupación de vivienda vacacional ese año"),
        ("estancia_media_vv", "duración media de estancia en vivienda vacacional, en días"),
    ],
    "gold.gold_municipio_mensual": [
        ("cod_municipio", "código INE del municipio"),
        ("municipio", "nombre del municipio"),
        ("periodo", "periodo en formato YYYY-MM"),
        ("anio", "año"),
        ("mes", "mes (1-12)"),
        ("paro_registrado", "personas en paro registrado ese mes"),
        ("paro_yoy_pct", "% de variación del paro respecto al mismo mes del año anterior"),
        ("plazas_vv", "plazas de vivienda vacacional ese mes"),
        ("tasa_ocupacion_vv", "% de ocupación de vivienda vacacional ese mes"),
        ("estancia_media_vv", "duración media de estancia en vivienda vacacional, en días"),
        ("ingresos_vv", "ingresos de vivienda vacacional ese mes, en euros"),
        ("alojamientos_abiertos_vv", "número de alojamientos de vivienda vacacional abiertos ese mes"),
        ("plazas_vv_yoy_pct", "% de variación de plazas VV respecto al mismo mes del año anterior"),
        ("ingresos_vv_yoy_pct", "% de variación de ingresos VV respecto al mismo mes del año anterior"),
    ],
    "gold.gold_municipio_empleo": [
        ("cod_municipio", "código INE del municipio"),
        ("municipio", "nombre del municipio"),
        ("periodo", "periodo trimestral en formato YYYY-QN"),
        ("periodo_texto", "periodo trimestral en texto legible"),
        ("anio", "año"),
        ("trimestre", "trimestre (1-4)"),
        ("empleo_total", "total de personas afiliadas a la Seguridad Social"),
        ("empleo_asalariados", "personas afiliadas como asalariados"),
        ("empleo_autonomos", "personas afiliadas como autónomos"),
        ("pct_autonomos", "% de afiliados que son autónomos"),
        ("pct_asalariados", "% de afiliados que son asalariados"),
        ("crec_empleo_total_yoy_pct", "% de crecimiento del empleo total respecto al mismo trimestre del año anterior"),
        ("crec_empleo_autonomos_yoy_pct", "% de crecimiento de autónomos respecto al mismo trimestre del año anterior"),
    ],
    "gold.gold_turismo_hotelero_anual": [
        ("cod_municipio", "código INE del municipio"),
        ("municipio", "nombre del municipio"),
        ("polo_turistico", "polo turístico al que pertenece el municipio (ej. Polo Sur, Polo Norte)"),
        ("anio", "año"),
        ("viajeros_entrados_total", "viajeros alojados en establecimientos hoteleros ese año"),
        ("crec_viajeros_yoy_pct", "% de crecimiento de viajeros respecto al año anterior"),
        ("pernoctaciones_total", "noches pernoctadas en establecimientos hoteleros ese año"),
        ("crec_pernoctaciones_yoy_pct", "% de crecimiento de pernoctaciones respecto al año anterior"),
        ("ocupacion_media_plazas", "% medio de ocupación de plazas hoteleras ese año"),
        ("estancia_media_hotel_dias", "duración media de estancia en hotel, en días"),
    ],
    "gold.gold_turismo_hotelero_mensual": [
        ("cod_municipio", "código INE del municipio"),
        ("municipio", "nombre del municipio"),
        ("polo_turistico", "polo turístico al que pertenece el municipio"),
        ("periodo", "periodo en formato YYYY-MM"),
        ("anio", "año"),
        ("mes", "mes (1-12)"),
        ("viajeros_entrados", "viajeros alojados en establecimientos hoteleros ese mes"),
        ("pernoctaciones", "noches pernoctadas en establecimientos hoteleros ese mes"),
        ("tasa_ocupacion_plazas", "% de ocupación de plazas hoteleras ese mes"),
        ("estancia_media_hotel_dias", "duración media de estancia en hotel, en días"),
        ("crec_viajeros_yoy_pct", "% de variación de viajeros respecto al mismo mes del año anterior"),
        ("crec_pernoctaciones_yoy_pct", "% de variación de pernoctaciones respecto al mismo mes del año anterior"),
    ],
    "gold.gold_aena_pasajeros": [
        ("periodo", "periodo en formato YYYY-MM"),
        ("anio", "año"),
        ("mes", "mes (1-12)"),
        ("trimestre", "trimestre (Q1-Q4)"),
        ("temporada", "Invierno (Temporada Alta) o Verano (Temporada Media/Baja)"),
        ("aeropuerto_codigo", "TFS (Tenerife Sur) o TFN (Tenerife Norte)"),
        ("aeropuerto_nombre", "nombre completo del aeropuerto"),
        ("tipo_trafico_principal", "Internacional predominante (TFS) o Nacional e Interinsular (TFN)"),
        ("pasajeros", "pasajeros totales ese mes"),
        ("operaciones", "operaciones (despegues + aterrizajes) ese mes"),
        ("pasajeros_por_operacion", "pasajeros medios por operación ese mes"),
    ],
}

TABLAS_PERMITIDAS: set[str] = set(ESQUEMA_GOLD.keys())

PALABRAS_PROHIBIDAS = {"INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE", "GRANT", "CREATE"}

LIMIT_POR_DEFECTO = 200


def describir_esquema() -> str:
    bloques = []
    for tabla, columnas in ESQUEMA_GOLD.items():
        lineas_columnas = "\n".join(f"  - {col}: {desc}" for col, desc in columnas)
        bloques.append(f"Tabla {tabla}:\n{lineas_columnas}")
    return "\n\n".join(bloques)


def _tablas_referenciadas(sql: str) -> set[str]:
    return {t.lower() for t in re.findall(r"(?:FROM|JOIN)\s+([a-zA-Z0-9_\.]+)", sql, re.IGNORECASE)}


def validar_sql(sql: str) -> tuple[bool, str | None]:
    sql_limpio = sql.strip().rstrip(";").strip()
    if ";" in sql_limpio:
        return False, "Solo se permite una única sentencia SQL."
    if not re.match(r"(?is)^SELECT\b", sql_limpio):
        return False, "Solo se permiten sentencias SELECT."
    palabras = set(re.findall(r"[A-Za-z]+", sql_limpio.upper()))
    prohibidas = palabras & PALABRAS_PROHIBIDAS
    if prohibidas:
        return False, f"Palabras clave no permitidas: {', '.join(sorted(prohibidas))}."
    tablas = _tablas_referenciadas(sql_limpio)
    no_permitidas = tablas - TABLAS_PERMITIDAS
    if no_permitidas:
        return False, f"Tablas no permitidas: {', '.join(sorted(no_permitidas))}."
    return True, None


def asegurar_limit(sql: str, limite: int = LIMIT_POR_DEFECTO) -> str:
    sql_limpio = sql.strip().rstrip(";").strip()
    if re.search(r"\bLIMIT\s+\d+", sql_limpio, re.IGNORECASE):
        return sql_limpio
    return f"{sql_limpio}\nLIMIT {limite}"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/analytics/chat/test_sql_agent.py -v`
Expected: 9 tests pass, but the module-level import of `RespuestaSQL`, `responder_sql` in the test file will still fail (not yet defined) — continue to Part B before running the full file.

#### Part B — `RespuestaSQL` and `responder_sql` (implemented directly, verified live in Task 6)

- [ ] **Step 5: Append the orchestration code**

Append to `analytics/chat/sql_agent.py`:

```python
PROMPT_SQL = """Eres un generador de consultas SQL de solo lectura (PostgreSQL) sobre datos turísticos de Tenerife.

Devuelve UNICAMENTE la sentencia SQL, sin explicaciones, sin bloques de código markdown, sin punto y coma final.
Debe ser una única sentencia SELECT. Usa solo las tablas y columnas listadas abajo.

ESQUEMA DISPONIBLE:
{esquema}

PREGUNTA: {pregunta}
{motivo_reintento}
SQL:"""

PROMPT_NARRACION = """Eres un analista de turismo. Redacta una respuesta breve (1-2 frases) en español a la pregunta del usuario, basándote UNICAMENTE en estas filas de resultado de una consulta SQL. No inventes datos que no estén en las filas.

PREGUNTA: {pregunta}

FILAS:
{filas}

RESPUESTA:"""


@dataclass
class RespuestaSQL:
    texto: str
    sql: str
    filas: list[dict] = field(default_factory=list)
    error: str | None = None


def _generar_sql(pregunta: str, llm: LLMClient, motivo_reintento: str = "") -> str:
    prompt = PROMPT_SQL.format(esquema=describir_esquema(), pregunta=pregunta, motivo_reintento=motivo_reintento)
    respuesta = llm.complete(prompt, temperature=0.0, max_tokens=300)
    return respuesta.strip().strip("`").strip()


def responder_sql(pregunta: str, engine, llm: LLMClient | None = None) -> RespuestaSQL:
    cliente = llm or LLMClient()

    sql = _generar_sql(pregunta, cliente)
    es_valido, motivo = validar_sql(sql)
    if not es_valido:
        motivo_reintento = f"\nTu SQL anterior fue rechazada: {motivo}\nGenera una nueva sentencia SQL valida.\n"
        sql = _generar_sql(pregunta, cliente, motivo_reintento)
        es_valido, motivo = validar_sql(sql)
        if not es_valido:
            return RespuestaSQL(
                texto="No he podido generar una consulta SQL válida para esta pregunta.",
                sql=sql,
                error=motivo,
            )

    sql_final = asegurar_limit(sql)

    try:
        df = pd.read_sql(sql_final, engine)
    except Exception as exc:
        motivo_reintento = (
            f"\nTu SQL anterior fallo al ejecutarse con este error de Postgres: {exc}\n"
            "Genera una nueva sentencia SQL que lo corrija.\n"
        )
        sql = _generar_sql(pregunta, cliente, motivo_reintento)
        es_valido, motivo = validar_sql(sql)
        if not es_valido:
            return RespuestaSQL(
                texto="No he podido generar una consulta SQL válida para esta pregunta.",
                sql=sql,
                error=motivo,
            )
        sql_final = asegurar_limit(sql)
        try:
            df = pd.read_sql(sql_final, engine)
        except Exception as exc2:
            return RespuestaSQL(
                texto="La consulta generada no se pudo ejecutar correctamente contra la base de datos.",
                sql=sql_final,
                error=str(exc2),
            )

    if df.empty:
        return RespuestaSQL(texto="La consulta no devolvió resultados.", sql=sql_final, filas=[])

    filas = df.to_dict("records")
    prompt_narracion = PROMPT_NARRACION.format(pregunta=pregunta, filas=filas)
    texto = cliente.complete(prompt_narracion, temperature=0.3, max_tokens=200)
    return RespuestaSQL(texto=texto.strip(), sql=sql_final, filas=filas)
```

- [ ] **Step 6: Run the full test file to verify it passes**

Run: `.venv/bin/python -m pytest tests/analytics/chat/test_sql_agent.py -v`
Expected: all 9 tests pass (the module now imports cleanly; `responder_sql` itself isn't unit-tested per the Global Constraints section — it's verified live in Task 6).

Also run the full suite:

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: all tests pass

- [ ] **Step 7: Commit**

```bash
git add analytics/chat/sql_agent.py tests/analytics/chat/test_sql_agent.py
git commit -m "feat: add Text-to-SQL agent for the chatbot (8.4)

Curated gold.* schema (municipio/isla level, gold_h3_master excluded
on purpose), validated read-only SQL generation with a single retry
on validation or execution failure, no LangChain."
```

---

### Task 4: `app/asistente.py` — the chat page

**Files:**
- Create: `app/asistente.py`

**Interfaces:**
- Consumes:
  - `analytics.chat.router.clasificar(pregunta: str) -> Literal["sql", "rag"]` (Task 2)
  - `analytics.chat.sql_agent.responder_sql(pregunta: str, engine, llm=None) -> RespuestaSQL` (Task 3)
  - `analytics.rag.rag_answer.responder(pregunta: str, k=8, filters=None, hibrida=True, fijos=frozenset()) -> Respuesta` (existing, Task 1 made it importable)
  - `app.data.get_engine() -> Engine` (existing)
- Produces: `app.asistente.page_asistente() -> None` — used by Task 5.

This task has no automated test (it's a Streamlit page function with no pure logic to isolate — consistent with `app/main.py`'s other `page_*` functions, none of which have unit tests in this project). It's verified live in Task 6.

- [ ] **Step 1: Write the page**

Create `app/asistente.py`:

```python
import streamlit as st

from analytics.chat.router import clasificar
from analytics.chat.sql_agent import responder_sql
from analytics.rag.rag_answer import responder as responder_rag
from app.data import get_engine

AVISO = (
    "Este asistente combina dos motores: uno consulta cifras oficiales (población, paro, "
    "turismo, tráfico aéreo) con SQL generado automáticamente; el otro busca opiniones reales "
    "de viajeros. Cada respuesta muestra la consulta SQL usada (si aplica). El motor de "
    "opiniones nunca inventa cifras ni compara cantidades a partir de una muestra de reseñas."
)


def _generar_respuesta(pregunta: str) -> dict:
    try:
        tipo = clasificar(pregunta)
    except Exception:
        tipo = "rag"

    if tipo == "sql":
        try:
            respuesta = responder_sql(pregunta, get_engine())
            return {
                "role": "assistant",
                "content": respuesta.texto,
                "sql": respuesta.sql,
                "filas": respuesta.filas,
            }
        except Exception:
            return {
                "role": "assistant",
                "content": "No se ha podido consultar la base de datos en este momento.",
            }

    try:
        respuesta = responder_rag(pregunta)
        return {"role": "assistant", "content": respuesta.texto}
    except Exception:
        return {
            "role": "assistant",
            "content": "No se ha podido generar una respuesta en este momento.",
        }


def _render_mensaje(mensaje: dict) -> None:
    with st.chat_message(mensaje["role"]):
        st.markdown(mensaje["content"])
        if mensaje.get("sql"):
            with st.expander("Ver SQL generado"):
                st.code(mensaje["sql"], language="sql")
        if mensaje.get("filas"):
            st.dataframe(mensaje["filas"], hide_index=True)


def page_asistente() -> None:
    st.title("🤖 Asistente IA")
    st.info(AVISO)

    if "chat_historial" not in st.session_state:
        st.session_state["chat_historial"] = []

    for mensaje in st.session_state["chat_historial"]:
        _render_mensaje(mensaje)

    pregunta = st.chat_input("Pregunta algo sobre el turismo en Tenerife...")
    if pregunta:
        st.session_state["chat_historial"].append({"role": "user", "content": pregunta})
        with st.spinner("Pensando..."):
            st.session_state["chat_historial"].append(_generar_respuesta(pregunta))
        st.rerun()
```

- [ ] **Step 2: Verify the file imports cleanly**

Run: `.venv/bin/python -c "import app.asistente; print(app.asistente.page_asistente)"`
Expected: prints `<function page_asistente at 0x...>` with no error.

- [ ] **Step 3: Commit**

```bash
git add app/asistente.py
git commit -m "feat: add Asistente IA chat page (8.4)"
```

---

### Task 5: Register the page in `app/main.py`'s navigation

**Files:**
- Modify: `app/main.py:7-45` (imports), `app/main.py:439-461` (page registration)

**Interfaces:**
- Consumes: `app.asistente.page_asistente` (Task 4).

- [ ] **Step 1: Add the import**

In `app/main.py`, near the other `app.*` imports (after the `from app.alojamiento import render_alojamiento_tab` line):

```python
from app.asistente import page_asistente
```

- [ ] **Step 2: Register the page**

Find this block near the end of `app/main.py`:

```python
nav_resumen = st.Page(page_resumen, title="Resumen", icon="📊", default=True)
nav_mapa = st.Page(page_mapa, title="Mapa", icon="🗺️")
```

Add a new line right after `nav_mapa`:

```python
nav_resumen = st.Page(page_resumen, title="Resumen", icon="📊", default=True)
nav_mapa = st.Page(page_mapa, title="Mapa", icon="🗺️")
nav_asistente = st.Page(page_asistente, title="Asistente IA", icon="🤖")
```

Then find the `pages` list:

```python
pages = [
    nav_resumen,
    nav_mapa,
    nav_tabla,
```

Add `nav_asistente` right after `nav_mapa`:

```python
pages = [
    nav_resumen,
    nav_mapa,
    nav_asistente,
    nav_tabla,
```

- [ ] **Step 3: Verify the file has valid syntax**

Run: `.venv/bin/python -c "import ast; ast.parse(open('app/main.py').read()); print('syntax OK')"`
Expected: `syntax OK`

- [ ] **Step 4: Run the full test suite**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: all tests pass, no regressions

- [ ] **Step 5: Commit**

```bash
git add app/main.py
git commit -m "feat: register Asistente IA page in the app navigation (8.4)"
```

---

### Task 6: Live verification against the real app

**Files:** none (verification only — no code changes)

This mirrors how points 8.1–8.3 and the map choropleth (8.2) were verified in this project: launch the real Streamlit app against the live Azure database and Groq, drive it with Playwright, and read the actual screenshots. Do not report this feature as working without doing this — a router/SQL-agent/RAG chain has several real-world failure points (Groq auth, SQL the model generates for real tables, RAG's embedding model load) that no pure-function test can catch.

- [ ] **Step 1: Launch the app**

```bash
cd /Users/jorgetmn/Proyectos/AI_Dashboard_Core
.venv/bin/python -m streamlit run app/main.py --server.headless true --server.port 8765 > /tmp/streamlit_asistente.log 2>&1 &
sleep 6
curl -s -o /dev/null -w "HTTP %{http_code}\n" http://localhost:8765
```

Expected: `HTTP 200`. If not, check `/tmp/streamlit_asistente.log` for a startup error (most likely a missing `GROQ_API_KEY` in `.env`, or an import error) before continuing.

- [ ] **Step 2: Drive it with Playwright — one SQL-routed question, one RAG-routed question**

Write a throwaway script (in the session's scratchpad, not committed) that:
1. Navigates to `http://localhost:8765`.
2. Clicks the "Asistente IA" nav item.
3. Types `"¿qué municipio tiene más paro?"` into the chat input and submits it.
4. Waits for the assistant's response to render, screenshots the page.
5. Types `"¿de qué se quejan los turistas en Adeje?"` and submits it.
6. Waits for the assistant's response to render, screenshots the page.
7. Captures `pageerror` and console `error`-level events throughout.

- [ ] **Step 3: Read both screenshots and confirm**

- The SQL question's answer is present, plausible (names a real Tenerife municipio), and its "Ver SQL generado" expander contains a `SELECT` against one of the `TABLAS_PERMITIDAS`.
- The RAG question's answer is present and reads like the existing `rag_answer.py` CLI output style (citing fragments in brackets, or the "no hay información suficiente" fallback — either is correct behavior).
- No `pageerror` or console `error` events were logged for either interaction.

If either check fails, fix the underlying issue (not the test) and re-run this task from Step 1.

- [ ] **Step 4: Stop the test server**

```bash
pkill -f "streamlit run app/main.py"
```

- [ ] **Step 5: Report the result to the user**

Summarize what was verified (both routed paths, no console errors) with the two screenshots, the same way 8.1–8.3 were reported in this session.

---

## Self-Review Notes

- **Spec coverage:** all 4 decisions (page placement, no-LangChain SQL, curated schema, LLM router) map to Tasks 2-5; error handling maps to the `try/except` blocks in Tasks 3-4; testing plan maps to Tasks 1-3's TDD steps and Task 6's live verification; "fuera de alcance" items (map context, persistent history, writes) are simply absent from every task, which is correct — no task implements them.
- **Placeholder scan:** every step has literal, complete code — no "similar to Task N", no "add error handling" without showing it.
- **Type consistency checked:** `clasificar(pregunta, llm=None)` (Task 2) → called as `clasificar(pregunta)` in Task 4 (relies on the default, correct). `responder_sql(pregunta, engine, llm=None)` (Task 3) → called as `responder_sql(pregunta, get_engine())` in Task 4 (matches). `RespuestaSQL.filas` is `list[dict]` in both Task 3's definition and Task 4's `mensaje["filas"]` usage (passed straight to `st.dataframe`, which accepts a list of dicts). `Respuesta.texto` (existing RAG dataclass) matches `respuesta.texto` usage in Task 4.
