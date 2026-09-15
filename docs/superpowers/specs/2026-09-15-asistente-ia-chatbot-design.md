# Asistente IA — Chatbot híbrido Text-to-SQL + RAG (punto 8.4 del plan)

**Fecha:** 2026-09-15
**Estado:** Aprobado para implementación (pendiente de plan de ejecución)

## Contexto y punto de partida

El plan original (`plan_final_mejorado.md`, Subtarea 8.4 — "Panel Lateral del Chatbot IA Híbrido") describe un chatbot integrado en el dashboard que combina:

1. Un **agente Text-to-SQL** para preguntas cuantitativas/agregadas ("¿cuántas plazas hoteleras hay en Adeje?", "¿qué municipio tiene mayor paro?") contra las tablas `gold.*`.
2. Un **motor RAG** para preguntas de percepción/experiencia del viajero ("¿por qué se quejan los turistas del transporte en el sur?") sobre el corpus de reseñas.
3. Un **router** que decide a cuál de los dos despachar cada pregunta.
4. Contextualización cartográfica: al hacer clic en el mapa, inyectar el municipio/hexágono seleccionado como contexto de la conversación.

Antes de diseñar se auditó el estado real del repositorio (no solo el plan):

- **No existe ningún flujo de chat** en la app: cero usos de `st.chat_input`/`st.chat_message` en `app/`.
- **No existe ningún agente Text-to-SQL**: se buscó `SQLDatabaseChain`, `create_sql_agent`, "text-to-sql" en todo el código — solo aparece mencionado en documentación como pendiente.
- **El motor RAG SÍ existe y funciona**: `analytics/rag/rag_answer.py` expone `responder(pregunta, k, filters, hibrida, fijos) -> Respuesta(texto, chunks, filtros_descartados, perspectiva)`, una función pura y lista para importar — construida sobre `analytics/rag/retriever.py` (búsqueda híbrida léxica+vectorial con pgvector sobre `gold.nlp_chunks`, modelo de embeddings `paraphrase-multilingual-mpnet-base-v2` ya en `requirements.txt` junto con `torch`) y `analytics/llm/llm_client.py` (`LLMClient`, wrapper directo sobre la API de Groq, modelo `openai/gpt-oss-120b`, sin frameworks intermedios).
- `requirements.txt` **no incluye LangChain** — el proyecto evita frameworks de orquestación de agentes; `llm_client.py` es deliberadamente un wrapper mínimo.
- La navegación de la app (`app/main.py`) usa `st.navigation` con una página (`st.Page`) por funcionalidad (Mapa, Tabla, Rankings, Clima, Municipios, Alojamiento, Temas, Turismo) — no hay precedente de paneles laterales compartidos entre páginas.

Estos hallazgos motivaron las tres decisiones de diseño más importantes (detalladas abajo, con su alternativa descartada y el porqué).

## Decisiones de diseño

### 1. Página propia "Asistente IA", no panel lateral en el Mapa

**Decisión:** nueva página `nav_chat = st.Page(page_asistente, title="Asistente IA", icon="🤖")`, igual que el resto de funcionalidades.

**Alternativa descartada:** panel lateral dentro de `page_mapa()`, tal como lo imaginaba el plan original, para poder inyectar el contexto del hexágono/municipio clicado directamente en el prompt.

**Por qué:** la app no tiene ningún precedente de estado compartido entre páginas más allá de filtros sueltos en `session_state`; maquetar mapa+chat en columnas dentro de una misma página añade acoplamiento y complejidad de layout no necesaria para la primera versión. Se prioriza consistencia con el patrón existente y entregar el chat funcionando antes. La inyección de contexto de mapa queda **fuera de alcance de esta iteración** — es un candidato natural para una mejora posterior, igual que el centrado automático de cámara quedó fuera del punto 8.2.

### 2. Text-to-SQL con prompt + validación manual, sin LangChain

**Decisión:** el LLM (Groq, vía `LLMClient`) recibe la pregunta y un esquema de tablas `gold.*` **curado a mano**, y devuelve una sentencia SQL. Antes de ejecutarla se valida en Python; se ejecuta con SQLAlchemy (mismo patrón que `app/data.py`).

**Alternativa descartada:** `langchain.agents.create_sql_agent`, tal como sugería el plan.

**Por qué:** LangChain no está instalado y el proyecto evita explícitamente esa clase de dependencia (ver el comentario de diseño en `llm_client.py`, que justifica Groq frente a otras opciones precisamente por simplicidad). Un agente LangChain también itera de forma menos predecible (puede ejecutar SQL intermedio de exploración); el enfoque prompt+validación da control total y explícito sobre qué se ejecuta contra la base de datos real de Azure — relevante porque es una base de datos de producción del TFM, no una sandbox.

### 3. Esquema curado a mano, no introspección automática de la base de datos

**Decisión:** una constante en `analytics/chat/sql_agent.py` (análoga a `KPI_COLUMNS`/`METRICS`/`MUNICIPIO_METRICS` ya existentes en `app/`) con las tablas y columnas relevantes a nivel municipio/isla:

- `gold.gold_municipio_master` (población, paro, empleo, plazas VV, densidad turística, ratings — snapshot actual + variación 2022→hoy)
- `gold.gold_municipio_anual`, `gold.gold_municipio_mensual`, `gold.gold_municipio_empleo`
- `gold.gold_turismo_hotelero_anual`, `gold.gold_turismo_hotelero_mensual`
- `gold.gold_aena_pasajeros`

**Excluida deliberadamente:** `gold.gold_h3_master` (2.579 filas a nivel hexágono — no aporta a preguntas agregadas tipo "qué municipio tiene más..."; su volumen y sus ~80 columnas técnicas (satélite, clima IDW, accesibilidad) degradarían la precisión de la generación de SQL) y las tablas del propio RAG (`gold.nlp_chunks`, `gold.nlp_sentimiento_resenas`, etc. — esas preguntas van al RAG, no al SQL agent).

**Por qué:** es sabido que en Text-to-SQL, un esquema más pequeño y con descripciones claras produce SQL más preciso que introspeccionar automáticamente toda la base de datos (que arrastraría columnas técnicas, nombres ambiguos, tablas silver/bronze no pensadas para preguntas en lenguaje natural). Es además coherente con el estilo ya establecido en la app: curación explícita en vez de generalización automática.

### 4. Router con clasificación por LLM, no por palabras clave

**Decisión:** `analytics/chat/router.py` — `clasificar(pregunta) -> "sql" | "rag"`, una llamada corta a Groq con ejemplos de ambas categorías en el prompt. Si la respuesta del LLM no es una de las dos etiquetas esperadas, se usa `"rag"` como default.

**Alternativa descartada:** heurística de palabras clave, reutilizando el estilo de `detectar_perspectiva()` (ya existente en `analytics/llm/filtros.py`).

**Por qué:** las preguntas reales son ambiguas con más frecuencia de lo que una lista de palabras clave puede cubrir ("¿cómo está el paro en el sur?" mezcla agregación con una zona geográfica que requiere resolución de sinónimos). El coste de una llamada extra al LLM es bajo comparado con el coste de enrutar mal una pregunta. El fallback a `"rag"` es la opción segura: en el peor caso da una respuesta genérica en vez de ejecutar SQL sobre una clasificación incorrecta.

## Arquitectura

```
┌─────────────────────────────────────────────────────────┐
│  app/asistente.py  (nueva página "Asistente IA")         │
│  st.chat_input / st.chat_message                          │
│  historial en st.session_state["chat_historial"]          │
└───────────────────────┬───────────────────────────────────┘
                         │ pregunta del usuario
                         ▼
┌─────────────────────────────────────────────────────────┐
│  analytics/chat/router.py                                 │
│  clasificar(pregunta) -> "sql" | "rag"                    │
│  1 llamada a Groq (LLMClient), fallback "rag"              │
└───────────┬─────────────────────────────┬─────────────────┘
            │ "sql"                       │ "rag"
            ▼                             ▼
┌───────────────────────────┐   ┌───────────────────────────────┐
│ analytics/chat/            │   │ analytics/rag/rag_answer.py     │
│ sql_agent.py (nuevo)        │   │ responder() -- YA EXISTE         │
│                              │   │ (Fase 3 del RAG, funcional)      │
│ responder_sql(pregunta) ->  │   │                                  │
│   RespuestaSQL(texto, sql,  │   │ Respuesta(texto, chunks,         │
│   filas)                    │   │   filtros_descartados,           │
│                              │   │   perspectiva)                   │
└───────────────────────────┘   └───────────────────────────────┘
```

## Componentes

### `analytics/chat/router.py`

```python
def clasificar(pregunta: str) -> Literal["sql", "rag"]:
    ...
```

Prompt corto con 4-6 ejemplos de cada categoría. Respuesta esperada: una sola palabra (`SQL` o `RAG`). Cualquier respuesta que no sea exactamente una de esas dos (mayúsculas/minúsculas normalizadas) cae a `"rag"`.

### `analytics/chat/sql_agent.py`

```python
@dataclass
class RespuestaSQL:
    texto: str
    sql: str
    filas: list[dict]

def responder_sql(pregunta: str, engine: Engine) -> RespuestaSQL:
    ...
```

Flujo interno:

1. Prompt al LLM con el esquema curado (tabla + columnas + una línea de descripción cada una) + la pregunta → devuelve una sentencia SQL en texto plano.
2. **Validación** (`validar_sql(sql: str) -> tuple[bool, str | None]`, función pura y testeable sin BD ni LLM):
   - Debe ser una única sentencia `SELECT` (rechaza `;` seguido de más contenido).
   - Rechaza palabras clave de escritura/DDL: `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `TRUNCATE`, `GRANT`, `CREATE`.
   - Todas las tablas referenciadas deben estar en la lista curada de `gold.*` permitida.
   - Si no trae `LIMIT`, se le añade `LIMIT 200` automáticamente antes de ejecutar.
3. Si la validación falla: un reintento pasándole al LLM el motivo del rechazo. Si vuelve a fallar, se devuelve un mensaje de error al usuario (nunca se ejecuta SQL sin pasar la validación).
4. Ejecución con SQLAlchemy (mismo `engine` que ya usa `app/data.py`).
5. Si la ejecución falla en Postgres (columna inexistente, tipo incompatible...): un reintento con el mensaje de error de Postgres añadido al prompt. Si vuelve a fallar, mensaje de error legible al usuario (nunca un traceback crudo).
6. El LLM redacta una frase de respuesta a partir de las filas obtenidas (reutilizando `LLMClient`).

La UI muestra: la frase de respuesta, una tabla con las filas (`st.dataframe`), y la sentencia SQL generada dentro de un `st.expander("Ver SQL generado")` — transparencia sobre qué se ejecutó, relevante en el contexto de un TFM.

### `app/asistente.py`

- Historial de conversación en `st.session_state["chat_historial"]` (lista de `{role, content}`), pintado con `st.chat_message`. Sin persistencia más allá de la sesión, igual que el resto del estado de la app.
- `st.chat_input` captura la pregunta → `clasificar()` → despacha a `responder_sql()` (SQL) o a `responder()` (RAG, de `analytics/rag/rag_answer.py`) → se añade la respuesta al historial.
- `st.info` fijo al principio de la página explicando qué puede y qué no puede responder el asistente (mismo espíritu que las reglas ya integradas en el prompt de `rag_answer.py`: nunca inventa cifras a partir de una muestra, etc.), para que la demo del TFM no dé sorpresas.

## Flujo de ejemplo

Pregunta: *"¿qué municipio tiene más paro?"*

1. `router.clasificar(...)` → `"sql"`.
2. `sql_agent.responder_sql(...)` genera:
   ```sql
   SELECT municipio, paro_actual
   FROM gold.gold_municipio_master
   ORDER BY paro_actual DESC
   LIMIT 1
   ```
3. `validar_sql(...)` → OK (SELECT único, tabla permitida, LIMIT ya presente).
4. Se ejecuta contra Azure Postgres.
5. El LLM redacta: *"El municipio con más paro registrado es X, con Y personas."*
6. La UI muestra la frase + tabla de 1 fila + el SQL en el expander.

Pregunta: *"¿por qué se quejan los turistas del transporte en el sur?"*

1. `router.clasificar(...)` → `"rag"`.
2. `rag_answer.responder(...)` recupera fragmentos reales de reseñas y responde citándolos, con las mismas reglas anti-alucinación ya probadas del Bloque 3.

## Manejo de errores

- Sin `GROQ_API_KEY` o Groq no disponible: cada llamada al LLM va en `try/except`, mostrando un mensaje de error legible en el chat en vez de un traceback de Streamlit.
- SQL que no pasa validación tras el reintento: mensaje de error al usuario, nunca se ejecuta.
- Ejecución SQL fallida tras el reintento: mensaje de error al usuario, nunca un traceback crudo de psycopg2/SQLAlchemy.
- RAG sin fragmentos suficientes: ya gestionado por `rag_answer.responder()` (devuelve el mensaje "No hay información suficiente...").

## Testing

Siguiendo TDD, igual que el resto del proyecto (`tests/app/`):

- `tests/analytics/chat/test_router.py` — casos claros de cada categoría ("¿cuántas plazas hoteleras hay en Adeje?" → sql; "¿de qué se quejan en Adeje?" → rag) y el fallback ante una respuesta inesperada del LLM (con el LLM mockeado — es la única pieza de este diseño donde mockear es necesario, ya que la función envuelve una llamada de red a Groq).
- `tests/analytics/chat/test_sql_agent.py` — `validar_sql()` es una función pura: se testea sin BD ni LLM.
  - Acepta un `SELECT` simple sobre una tabla permitida.
  - Rechaza `INSERT`/`UPDATE`/`DELETE`/`DROP`/`ALTER`/`TRUNCATE`/`GRANT`/`CREATE`.
  - Rechaza múltiples sentencias (`;` seguido de más SQL).
  - Rechaza tablas fuera de la lista curada.
  - Añade `LIMIT 200` cuando no hay `LIMIT`.
  - Respeta un `LIMIT` explícito menor que 200.
- La integración real (Groq + Postgres + la página de Streamlit) se verifica igual que en los puntos 8.1-8.3: levantando la app con Playwright contra la base de datos real y comprobando ambas rutas (una pregunta SQL, una pregunta RAG) sin errores de consola.

## Fuera de alcance de esta iteración

- Inyección de contexto de mapa (clic en hexágono/municipio → contexto del chat) — requiere el panel lateral descartado en la decisión 1.
- Historial persistente entre sesiones.
- Cualquier escritura a la base de datos desde el chat (el diseño es explícitamente de solo lectura).
