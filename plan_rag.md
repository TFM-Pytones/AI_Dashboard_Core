# 🔍 Plan RAG — Consultas en Lenguaje Natural sobre el Corpus de Opiniones

**Bloque:** 3 (ampliación de la Subtarea 3.2) | **Responsable:** Mario | **Acordado:** 12 septiembre 2026

> Este plan **no está en `plan_final_mejorado.md`** — es un acuerdo posterior del equipo. El resto del proyecto sigue rigiéndose por ese documento.

---

## 1. Por qué, y qué cambia respecto a la Subtarea 3.2 original

La Subtarea 3.2 tal y como estaba especificada genera un informe de 3 párrafos a partir de las **etiquetas agregadas** de BERTopic (`gold.nlp_topics`: label + conteo). El LLM nunca ve una reseña real, así que:

- no puede citar evidencia concreta,
- no puede responder preguntas que no sean "resúmeme todo",
- el informe es estático: se genera una vez y no admite repreguntas.

El RAG resuelve las tres cosas: indexa el **texto real** de las 81.559 opiniones ya cargadas en `gold.nlp_topics` y permite preguntar sobre ellas recuperando fragmentos concretos como evidencia.

---

## 2. Decisión de arquitectura: dos herramientas, no una

**Un RAG por sí solo no cubre "distintas preguntas".** Hay dos familias de pregunta y cada una necesita un mecanismo distinto:

| Tipo | Ejemplo | Mecanismo | Por qué el otro falla |
|---|---|---|---|
| **Agregada / numérica** | *"¿Qué municipio tiene peor sentimiento?"* | SQL (Bloque 7) | El RAG solo ve ~8 fragmentos de 81.559: no puede contar ni promediar, se inventa la cifra |
| **Cualitativa / verbatim** | *"¿Por qué se quejan en Adeje?"* | **RAG (este plan)** | SQL no sabe buscar por significado; un `LIKE '%queja%'` es inútil |
| **Mixta** | *"Zonas con alto PTNA y qué dice la gente de ellas"* | Ambas, encadenadas | — |

La arquitectura objetivo es un **router** que clasifica la pregunta y delega en la herramienta adecuada. La fila "mixta" es la que da valor diferencial en la defensa del TFM.

### Frontera con el Squad B (⚠️ acordar antes de empezar)

El Bloque 7 (Text-to-SQL) y el 8.3 (panel de chatbot en Streamlit) están asignados al **Squad B (personas 3 y 4)**. Propuesta de reparto para no construir dos chatbots:

- **Bloque 3 (Mario):** el índice vectorial, el recuperador y la herramienta RAG.
- **Squad B:** la herramienta Text-to-SQL y el panel de Streamlit.
- **Conjunto:** el router y el contrato de interfaz entre ambas herramientas.

---

## 3. Estado verificado del punto de partida

Comprobado contra la BD el 2026-09-12 — nada de esto hay que volver a generarlo:

| Fuente | Docs en `gold.nlp_topics` | Long. media | Enganche geográfico verificado |
|---|---|---|---|
| `booking_review` | 70.251 | 288 car. | `review_id` → `silver_booking_reviews.establishment_id` → `silver_booking_establishments.geometry` → `ST_Contains` con `gold_h3_master` (3.740 establecimientos con hexágono) |
| `losviajeros_message` | 7.992 | 625 car. | `source_id` (MD5) → `gold.geo_mentions.place_name` (5.925 municipio + 1.492 zona) — **7.405 de 7.992 (93%)** |
| `youtube_comment` | 2.512 | 147 car. | Sin ubicación (por diseño: percepción de marca global) |
| `tripadvisor_review` | 804 | 503 car. | `review_id` → `location_id` → `silver_tripadvisor_ubicaciones.municipio` (viene ya resuelto) |

**`municipio` es la dimensión de filtro común** a las tres fuentes georreferenciadas. `h3_index` está disponible para Booking y TripAdvisor (ambas tienen `geometry`), lo que permite enlazar el RAG con el resto del proyecto H3.

Metadatos extra aprovechables ya existentes: `review_date` y `reviewer_country` (Booking), `fecha_publicacion`/`fecha_viaje`/`tipo_viaje` (TripAdvisor), `topic_id`/`topic_label` (BERTopic, las cuatro fuentes).

---

## 4. Fase 0 — Desbloqueo de pgvector (⚠️ empezar hoy, va en paralelo)

**Situación:** la extensión `vector` (v0.8.2) **está disponible** en el servidor pero **no instalable**: el parámetro `azure.extensions` de `db-tfm-tenerife2` solo contiene `POSTGIS`.

**Acción:** quien tenga acceso al portal de Azure debe añadir `VECTOR` a la allowlist:
`Azure Portal → db-tfm-tenerife2 → Server parameters → azure.extensions → marcar VECTOR → Save`
No requiere reinicio. Después: `CREATE EXTENSION vector;`

**Plan B si lo deniegan:** ChromaDB persistido en disco y subido a Blob Storage. Funciona, pero se pierde poder filtrar por metadatos y hacer JOIN con las tablas `gold` en la misma consulta — el filtrado habría que hacerlo en dos pasos desde Python. Es peor, pero no bloquea el proyecto.

> `pg_trgm` tampoco está en la allowlist. No importa: para la mitad léxica de la búsqueda híbrida se usa **`tsvector`, que es nativo de PostgreSQL** y no necesita extensión.

---

## 5. Fase 1 — `gold.nlp_chunks`: fragmentos + metadatos

Primera tabla del pipeline. **No depende de pgvector ni del Squad B: se puede hacer ya.**

### Esquema

```sql
CREATE TABLE gold.nlp_chunks (
    chunk_id        SERIAL PRIMARY KEY,
    source          TEXT NOT NULL,        -- booking_review | tripadvisor_review | losviajeros_message | youtube_comment
    source_id       TEXT NOT NULL,        -- enlaza con gold.nlp_topics
    chunk_index     INTEGER NOT NULL,     -- 0 si el documento no se partió
    text            TEXT NOT NULL,
    -- Metadatos para filtrado previo a la búsqueda:
    topic_id        INTEGER,
    topic_label     TEXT,
    municipio       TEXT,
    h3_index        TEXT,
    fecha           DATE,
    pais_resenante  TEXT,
    rating          REAL,
    UNIQUE (source, source_id, chunk_index)
);
CREATE INDEX idx_chunks_municipio ON gold.nlp_chunks(municipio);
CREATE INDEX idx_chunks_topic     ON gold.nlp_chunks(topic_id);
CREATE INDEX idx_chunks_fecha     ON gold.nlp_chunks(fecha);
```

### Regla de fragmentación

La reseña media de Booking son 288 caracteres: **ya es un fragmento óptimo, no hay que partir nada**. Solo requiere troceo LosViajeros (625 de media, 16.315 el mayor):

- documento ≤ 1.000 caracteres → 1 fragmento (afecta a ~90% del corpus),
- documento > 1.000 → trozos de ~800 caracteres con 100 de solape, cortando en final de frase.

Volumen estimado resultante: **~95.000 fragmentos**.

### Entregable

`analytics/rag/build_chunks.py` → puebla `gold.nlp_chunks`.
Debe imprimir la cobertura real de `municipio` por fuente, para detectar si el join espacial de Booking deja fuera más de lo esperado (verificado: 3.740 establecimientos caen en hexágono; hay que cuantificar cuántas reseñas quedan sin municipio y decidir si se rescatan por dirección).

---

## 6. Fase 2 — Embeddings

- **Modelo:** `paraphrase-multilingual-mpnet-base-v2` (768 dimensiones).
  Razones: es **el mismo que ya usa BERTopic** (coherencia metodológica defendible en la memoria), es multilingüe — imprescindible, el corpus tiene inglés, alemán, ruso, italiano, húngaro… — y es local y gratuito. *Nota: Groq no ofrece API de embeddings, así que la alternativa de pago tampoco estaba sobre la mesa.*
- **Dónde:** Colab con GPU, mismo patrón que ya se usó para BERTopic (CSV a Drive → montar → procesar → descargar). ~15 min para 95k fragmentos en T4, frente a varias horas en CPU local.
- **Almacenamiento:** ~292 MB en `float32`. Con pgvector: columna `embedding vector(768)` + índice HNSW.

### Entregables
- `analytics/rag/export_chunks.py` (BD → CSV para Colab)
- `analytics/rag/embed_chunks_colab.ipynb`
- `analytics/rag/import_embeddings.py` (vectores → `gold.nlp_chunks.embedding`)

---

## 7. Fase 3 — Recuperador + generación con citas ← *primer punto demostrable*

```python
# analytics/rag/retriever.py
def search(query: str, k: int = 8, filters: dict | None = None) -> list[Chunk]:
    """Filtra por metadatos PRIMERO, busca por similitud DESPUÉS."""
```

```python
# analytics/rag/rag_answer.py
# recupera -> monta prompt con fragmentos numerados -> LLM -> respuesta con [1][2]
```

Reutiliza `analytics/llm/llm_client.py` (Groq, `openai/gpt-oss-120b`) — ya existe y `GROQ_API_KEY` está en el `.env`.

**El prompt debe forzar el anclaje:** responder *únicamente* con lo que digan los fragmentos, citar el número de cada uno, y decir explícitamente "no hay información suficiente" cuando no esté. Sin esta restricción el LLM rellena huecos con conocimiento general sobre Tenerife y el RAG deja de ser verificable.

Prueba: `python analytics/rag/rag_answer.py "¿de qué se quejan los turistas en Adeje?"`

---

## 8. Fase 4 — Búsqueda híbrida y filtros por metadatos ← *el diferencial del TFM*

**Híbrida (vectorial + léxica).** La búsqueda vectorial difumina los nombres propios: "Siam Park", "Loro Parque" o el nombre de un hotel concreto se pierden entre vecinos semánticos. Se combina con `tsvector` (configuración `simple`, segura para corpus multilingüe) y se fusionan los dos rankings por **Reciprocal Rank Fusion**: `score = 1/(60+rank_vec) + 1/(60+rank_lex)`.

```sql
ALTER TABLE gold.nlp_chunks ADD COLUMN tsv tsvector
  GENERATED ALWAYS AS (to_tsvector('simple', text)) STORED;
CREATE INDEX idx_chunks_tsv ON gold.nlp_chunks USING GIN(tsv);
```

**Filtrado por metadatos.** Extraer de la pregunta (municipio, rango de fechas, país, tópico) y aplicarlo como `WHERE` **antes** de la búsqueda vectorial. *"¿De qué se quejaban los alemanes en Adeje en 2024?"* pasa de buscar en 95.000 fragmentos a buscar en unos cientos, y la precisión sube drásticamente.

Esto es lo que convierte el RAG en una pieza integrada con la arquitectura H3/medallón del TFM en lugar de un añadido genérico, y es lo que hay que destacar en la memoria.

---

## 9. Fase 5 — Evaluación ← *lo que lo hace defendible*

Sin esto, "he montado un RAG" no se sostiene ante un tribunal.

- **Conjunto de oro:** ~20 preguntas en `analytics/rag/eval/preguntas.yaml`, cada una con las fuentes que *deberían* recuperarse.
- **Métricas:**
  - `recall@8` — ¿aparece al menos una fuente esperada entre las 8 recuperadas?
  - *groundedness* con LLM-as-judge — ¿cada afirmación de la respuesta está respaldada por un fragmento citado?
  - tasa de abstención correcta — ante preguntas cuya respuesta no está en el corpus, ¿dice "no lo sé" en lugar de inventar?
- **Incluir 3-4 preguntas trampa agregadas** (*"¿cuántas reseñas hay en Arona?"*) que el RAG **no** debe responder: sirven para justificar empíricamente la decisión de arquitectura de dos herramientas de la sección 2.

---

## 10. Fase 6 — Integración en el chatbot (requiere acuerdo con Squad B)

Router que clasifica la pregunta en `sql` / `rag` / `ambas` y compone la respuesta. Se integra en el panel lateral de Streamlit de la Subtarea 8.3.

---

## 11. Resumen de fases y corte

| Fase | Entregable | Dep. | Est. |
|---|---|---|---|
| 0 | `VECTOR` en allowlist de Azure | Portal Azure | — (paralelo) |
| 1 | `gold.nlp_chunks` poblada | **ninguna** | 0,5 d |
| 2 | Embeddings cargados | Fase 0 ó plan B | 0,5 d |
| 3 | **RAG funcionando en CLI con citas** | Fase 2 | 0,5 d |
| 4 | Híbrido + filtros por metadatos | Fase 3 | 1 d |
| 5 | Evaluación con métricas | Fase 4 | 0,5 d |
| 6 | Integrado en Streamlit | Squad B | 1 d |

**Total ≈ 4 días.** Líneas de corte por si aprieta el calendario:
- **Fases 1-3** = RAG funcionando y demostrable.
- **+ Fases 4-5** = calidad y rigor de TFM.
- **+ Fase 6** = producto integrado.

**La Fase 1 no depende de nada**, así que se puede arrancar mientras se resuelven la allowlist de Azure y el reparto con el Squad B.

---

## 12. Riesgos

| Riesgo | Mitigación |
|---|---|
| Azure deniega `VECTOR` en la allowlist | Plan B con ChromaDB (sección 4) |
| Solape con el chatbot del Squad B | Acordar frontera **antes** de la Fase 6 (sección 2) |
| Calendario: Bloques 5 y 6 sin empezar | Cortar en Fase 3 o 5 (sección 11) |
| Reseñas de Booking sin municipio tras el join espacial | Cuantificar en Fase 1; rescate por `address` si el hueco es grande |
| El LLM responde sin anclarse en los fragmentos | Prompt restrictivo + métrica de *groundedness* (Fases 3 y 5) |

## 13. Librerías

```
pip install sentence-transformers pgvector psycopg2-binary groq pyyaml
# Plan B: chromadb
```

Nada nuevo de peso: `sentence-transformers` y `groq` ya están en uso en el proyecto.
