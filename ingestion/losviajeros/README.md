# Ingesta de Foros de Viajeros: LosViajeros.com (Capa Bronze)

Documentación del módulo de ingesta y almacenamiento del corpus cualitativo procedente de la comunidad de viajes **LosViajeros.com**, enfocado en experiencias, itinerarios, recomendaciones y opiniones no estructuradas sobre la isla de Tenerife.

---

## 1. Arquitectura y Flujo de Datos

```
Foro LosViajeros.com (Hilos y Mensajes sobre Tenerife)
       │
       ▼  Scraping Web / Extracción HTML (BeautifulSoup)
Extracción estructurada en Hilos (Temas) y Posts individuales
       │
       ▼  Almacenamiento en Data Lake (Azure Blob Storage)
Contenedor: bronce-raw/losviajeros/
       ├── losviajeros_temas.parquet     (~248 hilos temáticos)
       └── losviajeros_mensajes.parquet  (~167.000 mensajes de viajeros)
       │
       ▼  Carga en Streaming COPY (ingestion/postgres/05_ingest_tabular_to_postgres.py)
PostgreSQL:
       ├── bronze.bronze_losviajeros_temas
       └── bronze.bronze_losviajeros_mensajes
       │
       ▼  Transformación analítica y depuración HTML con dbt
PostgreSQL:
       ├── silver.silver_losviajeros
       └── silver.silver_losviajeros_mensajes
       │
       ▼  Consumo en Modelos de Inteligencia Artificial (Analytics)
       ├── BERTopic Modelo A (Percepción global y tópicos insulares)
       ├── BERTopic Modelo B (Menciones geoespaciales a núcleos y hoteles)
       └── Sistema RAG y Generación de Informes Turísticos (LLM)
```

---

## 2. Conjuntos de Datos y Esquema en Capa Bronze

Los datos se estructuran en dos niveles jerárquicos complementarios:

### A. `losviajeros_temas.parquet` (`bronze.bronze_losviajeros_temas`)
Contiene los metadatos de los hilos de discusión principales:

| Columna | Tipo | Descripción | Ejemplo |
|---|---|---|---|
| `tema_id` | `VARCHAR` | Identificador único del hilo en el foro | `12345` |
| `titulo` | `VARCHAR` | Título del hilo de discusión | `Viajar a Tenerife en Noviembre: Clima y Zonas` |
| `url` | `VARCHAR` | Enlace permanente a la conversación | `https://www.losviajeros.com/foros.php?t=...` |

### B. `losviajeros_mensajes.parquet` (`bronze.bronze_losviajeros_mensajes`)
Contiene el corpus masivo de comentarios y respuestas de la comunidad:

| Columna | Tipo | Descripción |
|---|---|---|
| `tema_id` | `VARCHAR` | Identificador del hilo padre al que pertenece |
| `tema_titulo` | `VARCHAR` | Título del hilo temático asociado |
| `mensaje_id` | `VARCHAR` | Identificador único del post o mensaje |
| `url` | `VARCHAR` | URL directa al post dentro del foro |
| `contexto_pagina_raw`| `TEXT` | Texto bruto del mensaje (incluye marcado original y citas) |
| `fetched_at` | `TIMESTAMP` | Marca temporal de captura del dato |

---

## 3. Carga Eficiente a Base de Datos (Estrategia de Memoria)

Dado que `losviajeros_mensajes.parquet` contiene más de **167.000 registros de texto largo** (superando los cientos de megabytes en memoria RAM no comprimida), su carga a Azure PostgreSQL se gestiona mediante un procedimiento especializado en [`ingestion/postgres/05_ingest_tabular_to_postgres.py`](file:///c:/Users/ROBERTO/Proyectos_Python/TFM_TUI_Tenerife/AI_Dashboard_Core/ingestion/postgres/05_ingest_tabular_to_postgres.py#L305-L316):

1. **Lectura por Chunks / Streaming**: Se procesa el Parquet en fragmentos de tamaño acotado para evitar desbordar la memoria del servidor o cliente.
2. **Uso del comando `COPY` de PostgreSQL**: En lugar de inserciones `INSERT INTO` convencionales o volcados masivos mediante Pandas `to_sql` (que agotan las conexiones y el buffer), se utiliza streaming binario con `COPY FROM STDIN`, reduciendo el tiempo de carga a segundos.

---

## 4. Modelado en Capa Silver y Aplicación en IA

En la capa **Silver**, los modelos dbt ejecutan:
* [`silver_losviajeros`](file:///c:/Users/ROBERTO/Proyectos_Python/TFM_TUI_Tenerife/AI_Dashboard_Core/dbt_project/models/silver/losviajeros/silver_losviajeros.sql): Agrega métricas por hilo (volumen de respuestas, primer y último mensaje publicado).
* [`silver_losviajeros_mensajes`](file:///c:/Users/ROBERTO/Proyectos_Python/TFM_TUI_Tenerife/AI_Dashboard_Core/dbt_project/models/silver/losviajeros/silver_losviajeros_mensajes.sql): Limpieza de entidades HTML (`&amp;`, `&quot;`, `<br>`), eliminación de firmas automáticas y depuración léxica.

| Capa | Tabla PostgreSQL | Volumen Verificado | Descripción |
|---|---|:---:|---|
| **Bronze** | `bronze.bronze_losviajeros_temas` | **248** hilos | Hilos de discusión completos sobre Tenerife (2004–2026) |
| **Bronze** | `bronze.bronze_losviajeros_mensajes` | **167.274** mensajes | Posts brutos con texto íntegro y contexto de página |
| **Silver** | `silver.silver_losviajeros` | **248** hilos | Métricas consolidadas por tema |
| **Silver** | `silver.silver_losviajeros_mensajes` | **168.035** mensajes | Corpus textual limpio listo para NLP |

Posteriormente, este corpus alimenta:
* **BERTopic (Topic Modeling)**: Detección no supervisada de temáticas emergentes (rutas de senderismo en Anaga, alquiler de coches en los aeropuertos, masificación en el Teide, microclimas norte vs. sur).
* **RAG Turístico**: Base de conocimiento textual para responder dudas complejas de viajeros en el asistente conversacional con citas directas a opiniones reales.

---

## 5. Instrucciones de Carga

Para sincronizar los archivos Parquet desde Azure Blob Storage hacia PostgreSQL:

```bash
# Carga automática de losviajeros_temas y losviajeros_mensajes
python ingestion/postgres/05_ingest_tabular_to_postgres.py
```
