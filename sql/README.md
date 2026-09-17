# Catálogo DDL y Esquemas de Base de Datos Complementarios (`sql/`)

Repositorio centralizado de definiciones DDL (`CREATE TABLE`, extensiones, funciones generadas e índices) para las tablas de las capas **Silver** y **Gold** en **Azure PostgreSQL** que son gestionadas directamente por pipelines de **Machine Learning, NLP y RAG** en Python, fuera del motor de transformaciones de `dbt`.

---

## 1. Justificación Arquitectónica: ¿Por qué no están en dbt?

En la arquitectura de datos del proyecto conviven dos mecanismos de materialización:

1. **Modelos analíticos dbt (`dbt_project/models/`)**: Transformaciones SQL declarativas a partir de tablas relacionales existentes en la base de datos (vistas, tablas agregadas y dimensiones espaciales).
2. **Tablas analíticas de Machine Learning y NLP (`sql/`)**: Tablas cuyos registros provienen de inferencias pesadas de modelos de lenguaje (Hugging Face / PyTorch), llamadas a APIs externas o indexación vectorial. No pueden resolverse mediante simples consultas SQL dentro de dbt.

Para mantener la integridad referencial y el linaje de datos:
* Los scripts en Python de `analytics/` ejecutan estos archivos DDL de manera **idempotente** (`CREATE TABLE IF NOT EXISTS`, `ADD COLUMN IF NOT EXISTS`) mediante funciones `ensure_schema()` antes de insertar los resultados.
* Estas tablas están formalmente registradas como fuentes externas en [`dbt_project/models/gold/sources.yml`](file:///c:/Users/ROBERTO/Proyectos_Python/TFM_TUI_Tenerife/AI_Dashboard_Core/dbt_project/models/gold/sources.yml), permitiendo que los modelos dbt posteriores (como `gold_topicos_h3` o `gold_sentimiento_h3`) hagan `{{ source('gold_nlp', '...') }}` de manera trazable.

---

## 2. Mapa de Ficheros DDL y Correspondencia con Python

| Archivo SQL | Esquema y Tabla | Script / Módulo que lo ejecuta | Descripción y Características Técnicas |
| :--- | :--- | :--- | :--- |
| [`silver_aspect_results_schema.sql`](file:///c:/Users/ROBERTO/Proyectos_Python/TFM_TUI_Tenerife/AI_Dashboard_Core/sql/silver_aspect_results_schema.sql) | `silver.aspect_results` | [`analytics/aspects/batch_inference.py`](file:///c:/Users/ROBERTO/Proyectos_Python/TFM_TUI_Tenerife/AI_Dashboard_Core/analytics/aspects/batch_inference.py) | **Extracción de Aspectos (PyABSA ATEPC)**: Guarda los aspectos detectados (comida, limpieza, ubicación...) y su sentimiento por reseña/comentario. *(Capa Silver)*. |
| [`gold_geo_mentions_schema.sql`](file:///c:/Users/ROBERTO/Proyectos_Python/TFM_TUI_Tenerife/AI_Dashboard_Core/sql/gold_geo_mentions_schema.sql) | `gold.geo_mentions` | [`analytics/geo/extract_toponyms.py`](file:///c:/Users/ROBERTO/Proyectos_Python/TFM_TUI_Tenerife/AI_Dashboard_Core/analytics/geo/extract_toponyms.py) | **Georreferenciación por Topónimos (Gazetteer)**: Resuelve menciones espaciales en textos no estructurados sin GPS (mensajes de LosViajeros y YouTube), vinculándolos a municipios o zonas clave (Teide, Anaga, Masca). |
| [`gold_nlp_topics_schema.sql`](file:///c:/Users/ROBERTO/Proyectos_Python/TFM_TUI_Tenerife/AI_Dashboard_Core/sql/gold_nlp_topics_schema.sql) | `gold.nlp_topics` | [`analytics/topics/cargar_corpus.py`](file:///c:/Users/ROBERTO/Proyectos_Python/TFM_TUI_Tenerife/AI_Dashboard_Core/analytics/topics/cargar_corpus.py)<br>[`analytics/topics/volcar_topicos.py`](file:///c:/Users/ROBERTO/Proyectos_Python/TFM_TUI_Tenerife/AI_Dashboard_Core/analytics/topics/volcar_topicos.py) | **Modelado de Tópicos (BERTopic)**: Registra el tópico asignado a cada texto, etiqueta legible en español (`topic_label`), palabras clave c-TF-IDF y probabilidad/similitud coseno. |
| [`gold_nlp_chunks_schema.sql`](file:///c:/Users/ROBERTO/Proyectos_Python/TFM_TUI_Tenerife/AI_Dashboard_Core/sql/gold_nlp_chunks_schema.sql) | `gold.nlp_chunks` | [`analytics/rag/build_chunks.py`](file:///c:/Users/ROBERTO/Proyectos_Python/TFM_TUI_Tenerife/AI_Dashboard_Core/analytics/rag/build_chunks.py) | **Corpus RAG (Fase 1)**: Fragmentación del corpus en trozos de ~1.000 caracteres, enriquecidos con metadatos espaciotemporales para prefiltrado (`municipio`, `zona`, `h3_index`, `fecha`, `topic_id`, `rating`). |
| [`gold_nlp_chunks_embedding.sql`](file:///c:/Users/ROBERTO/Proyectos_Python/TFM_TUI_Tenerife/AI_Dashboard_Core/sql/gold_nlp_chunks_embedding.sql) | `gold.nlp_chunks`<br>*(columna `embedding`)* | [`analytics/rag/import_embeddings.py`](file:///c:/Users/ROBERTO/Proyectos_Python/TFM_TUI_Tenerife/AI_Dashboard_Core/analytics/rag/import_embeddings.py) | **pgvector (Fase 2 RAG)**: Habilita la extensión `vector` en PostgreSQL y añade el campo `embedding vector(768)` calculado con `paraphrase-multilingual-mpnet-base-v2`. |
| [`gold_nlp_chunks_hybrid.sql`](file:///c:/Users/ROBERTO/Proyectos_Python/TFM_TUI_Tenerife/AI_Dashboard_Core/sql/gold_nlp_chunks_hybrid.sql) | `gold.nlp_chunks`<br>*(columna `tsv` e índice GIN)* | [`analytics/rag/retriever.py`](file:///c:/Users/ROBERTO/Proyectos_Python/TFM_TUI_Tenerife/AI_Dashboard_Core/analytics/rag/retriever.py) | **Búsqueda Híbrida (Fase 4 RAG)**: Columna generada `tsvector` (`to_tsvector('simple', text)`) e índice GIN para recuperar nombres propios y términos exactos fusionados con *Reciprocal Rank Fusion (RRF)*. |
| [`gold_nlp_informe_global_schema.sql`](file:///c:/Users/ROBERTO/Proyectos_Python/TFM_TUI_Tenerife/AI_Dashboard_Core/sql/gold_nlp_informe_global_schema.sql) | `gold.nlp_informe_global` | [`analytics/llm/report_generator.py`](file:///c:/Users/ROBERTO/Proyectos_Python/TFM_TUI_Tenerife/AI_Dashboard_Core/analytics/llm/report_generator.py) | **Informes Narrativos LLM**: Almacena diagnósticos periódicos generados por LLM (Groq / Llama) diferenciando ámbito general y ámbito alojamiento. |

---

## 3. Detalle de los Esquemas

### 3.1. Extracción de Aspectos — `silver.aspect_results`
* **Archivo**: [`silver_aspect_results_schema.sql`](file:///c:/Users/ROBERTO/Proyectos_Python/TFM_TUI_Tenerife/AI_Dashboard_Core/sql/silver_aspect_results_schema.sql)
* **Diseño**: Admite granularidad 1:N (un comentario puede tener múltiples aspectos o ninguno). No utiliza clave única por comentario; el control de idempotencia se realiza mediante comprobaciones `NOT EXISTS (SELECT 1 FROM silver.aspect_results WHERE source = ... AND source_id = ...)`.

### 3.2. Normalización y Tópicos — `gold.nlp_topics` y `gold.geo_mentions`
* **Archivos**: [`gold_nlp_topics_schema.sql`](file:///c:/Users/ROBERTO/Proyectos_Python/TFM_TUI_Tenerife/AI_Dashboard_Core/sql/gold_nlp_topics_schema.sql), [`gold_geo_mentions_schema.sql`](file:///c:/Users/ROBERTO/Proyectos_Python/TFM_TUI_Tenerife/AI_Dashboard_Core/sql/gold_geo_mentions_schema.sql)
* **Diseño**: Clave única compuesta `(source, source_id)` para garantizar deduplicación en inserciones incrementales. Índices por `source`, `topic_id` y `place_name` para optimizar los cruces analíticos.

### 3.3. Motor RAG Híbrido — `gold.nlp_chunks`
* **Archivos**: [`gold_nlp_chunks_schema.sql`](file:///c:/Users/ROBERTO/Proyectos_Python/TFM_TUI_Tenerife/AI_Dashboard_Core/sql/gold_nlp_chunks_schema.sql), [`gold_nlp_chunks_embedding.sql`](file:///c:/Users/ROBERTO/Proyectos_Python/TFM_TUI_Tenerife/AI_Dashboard_Core/sql/gold_nlp_chunks_embedding.sql), [`gold_nlp_chunks_hybrid.sql`](file:///c:/Users/ROBERTO/Proyectos_Python/TFM_TUI_Tenerife/AI_Dashboard_Core/sql/gold_nlp_chunks_hybrid.sql)
* **Evolución Modular en 3 Fases**:
  1. **Fase 1 (Chunking y Metadatos)**: Crea la tabla base con clave única `(source, source_id, chunk_index)` e índices B-Tree en `municipio`, `zona`, `h3_index`, `topic_id`, `fecha` y `source`.
  2. **Fase 2 (pgvector)**: Añade la columna `embedding vector(768)` de forma no bloqueante para independizar la fase 1 de la disponibilidad de la extensión.
  3. **Fase 4 (Full-Text Search)**: Añade la columna calculada `tsv tsvector GENERATED ALWAYS AS (to_tsvector('simple', text)) STORED` y el índice GIN `idx_nlp_chunks_tsv`. Se utiliza la configuración `'simple'` (no `'spanish'`) debido a que el corpus de reseñas de Booking y TripAdvisor es multilingüe (inglés, alemán, italiano, español).

### 3.4. Informes Ejecutivos — `gold.nlp_informe_global`
* **Archivo**: [`gold_nlp_informe_global_schema.sql`](file:///c:/Users/ROBERTO/Proyectos_Python/TFM_TUI_Tenerife/AI_Dashboard_Core/sql/gold_nlp_informe_global_schema.sql)
* **Diseño**: Almacén append-only para historificar versiones de informes narrativos generados en distintas fechas. Admite filtro por columna `ambito` (`'general'` para modelos de percepción insular y `'alojamiento'` para reputación hotelera).

---

## 4. Ejecución y Despliegue

### Automático (Recomendado)
Los scripts en Python leen automáticamente estos archivos al iniciar mediante funciones como:
```python
schema_path = Path(__file__).resolve().parents[2] / "sql" / "gold_nlp_chunks_schema.sql"
with open(schema_path, "r", encoding="utf-8") as f:
    conn.execute(text(f.read()))
```

### Manual (Inicialización o Mantenimiento de Azure PostgreSQL)
Si se requiere inicializar o verificar el esquema manualmente con `psql` o un cliente SQL:
```bash
psql "$AZURE_DB_URL" -f sql/silver_aspect_results_schema.sql
psql "$AZURE_DB_URL" -f sql/gold_geo_mentions_schema.sql
psql "$AZURE_DB_URL" -f sql/gold_nlp_topics_schema.sql
psql "$AZURE_DB_URL" -f sql/gold_nlp_chunks_schema.sql
psql "$AZURE_DB_URL" -f sql/gold_nlp_chunks_embedding.sql
psql "$AZURE_DB_URL" -f sql/gold_nlp_chunks_hybrid.sql
psql "$AZURE_DB_URL" -f sql/gold_nlp_informe_global_schema.sql
```
