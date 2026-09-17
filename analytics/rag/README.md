# Motor RAG Híbrido Multilingüe (`analytics/rag`)

Este módulo implementa el pipeline de **Generación Aumentada por Recuperación (RAG)** de alta precisión sobre el corpus cualitativo de turismo de Tenerife (~88.000 opiniones y reseñas). Está diseñado para responder preguntas sobre la experiencia del visitante garantizando trazabilidad absoluta y erradicando alucinaciones.

---

## 1. Arquitectura del Pipeline RAG

```mermaid
flowchart TD
    Q[Pregunta en Lenguaje Natural] --> F[Extracción Determinista de Filtros\nfiltros.py]
    F --> D[Detección de Perspectiva:\nAlojamiento / Destino / General]
    
    subgraph Recuperacion_Hibrida [retriever.py - Búsqueda Híbrida]
        Q --> |Vectorización MPNet 768d| SEM[Rama Semántica:\npgvector HNSW Cosine Distance]
        Q --> |Extracción Nombres Propios| LEX[Rama Léxica:\nBM25 ts_rank_cd GIN]
        SEM --> |Ranking 1..N| RRF[Reciprocal Rank Fusion\nk = 60]
        LEX --> |Ranking 1..N| RRF
        RRF --> DEDUP[Deduplicación de Citas\ny Balanceo por Cuotas]
    end
    
    D --> Recuperacion_Hibrida
    DEDUP --> C[k Chunks Enriquecidos]
    C --> LLM[Generador de Respuesta\nrag_answer.py + Groq LPU]
    LLM --> R[Respuesta Ejecutiva con Citas [1][2]\no Protocolo de Abstención]
```

---

## 2. Componentes del Sistema

### 2.1. Segmentación y Enriquecimiento (`build_chunks.py`)
* **Estrategia de Troceado:** El 95,5 % de las reseñas del corpus tienen $\le 1.000$ caracteres y entran íntegras, preservando el contexto narrativo completo. Para reseñas largas (>1.000 caracteres), se aplica segmentación recursiva por oraciones con `CHUNK_SIZE = 800` caracteres y `CHUNK_OVERLAP = 100`.
* **Resolución Espacial de Metadatos:**
  * **Booking:** `review_id` $\rightarrow$ coordenadas de establecimiento $\rightarrow$ `ST_Contains` con `gold_h3_master` para asignar `h3_index` y `municipio`.
  * **TripAdvisor:** `location_id` $\rightarrow$ coordenadas de establecimiento $\rightarrow$ cruce espacial con malla H3 y municipio.
  * **LosViajeros:** Cruce por hash MD5 contra `gold.geo_mentions` para extraer mención toponímica y zona turística.
  * **YouTube:** Contexto insular global de percepción de marca (sin coordenadas puntuales).
* **Almacenamiento:** Tabla analítica `gold.nlp_chunks` con metadatos de autor, fuente, fecha, calificación, idioma, municipio, zona y tópico asignado por BERTopic.

### 2.2. Indexación Vectorial (`import_embeddings.py`)
* **Modelo Denso:** `sentence-transformers/paraphrase-multilingual-mpnet-base-v2` (768 dimensiones).
* **Índice PostgreSQL:** Índice HNSW (`pgvector`) sobre `gold.nlp_chunks.embedding vector(768)` configurado con:
  $$\text{Parámetros de Construcción: } m = 16, \quad ef\_construction = 64$$
  $$\text{Parámetros de Búsqueda: } ef\_search = 100, \quad iterative\_scan = \text{'relaxed\_order'}$$
* El escaneo iterativo (`relaxed_order`) garantiza que las consultas con cláusulas `WHERE` selectivas recuperen la totalidad de los $k$ candidatos solicitados en milisegundos, reordenando sobre un CTE `MATERIALIZED`.

### 2.3. Normalización y Extracción Determinista de Filtros (`filtros.py`)
Para eliminar la latencia y evitar alucinaciones en el reconocimiento de entidades, la extracción de filtros se realiza mediante diccionarios canónicos y expresiones regulares:
* **Municipios y Localidades:** Resuelve nombres turísticos informales a sus términos municipales oficiales (e.g. *"Los Cristianos"* o *"Las Américas"* $\rightarrow$ *Arona / Adeje*; *"Vilaflor de Chasna"* $\rightarrow$ *Vilaflor*).
* **Zonas Turísticas:** Mapea menciones naturales a polígonos oficiales (*"Teide"*, *"Masca"*, *"Anaga"*, *"Los Gigantes"*).
* **Gentilicios:** Extrae nacionalidades del emisor utilizando únicamente formas en plural (*"los alemanes"*, *"los británicos"* $\rightarrow$ `pais_resenante`), evitando falsos positivos con adjetivos singulares de idioma.
* **Relajación Adaptativa (`relajar_filtros`):** Si la intersección estricta de filtros no arroja ningún fragmento, el motor relaja gradualmente las restricciones temporales o de país conservando siempre los filtros geográficos obligatorios fijados por el usuario.

### 2.4. Recuperación Híbrida y Fusión RRF (`retriever.py`)
Combina lo mejor de la búsqueda semántica vectorial (afinidades conceptuales multilingües) con la búsqueda léxica BM25 (nombres propios exactos de hoteles, playas o parques):
* **Fórmula de Fusión (Reciprocal Rank Fusion):**
  $$RRF(d) = \sum_{m \in \{\text{semántica},\, \text{léxica}\}} \frac{1}{60 + \text{pos}_m(d)}$$
* **Control del Sesgo de Corpus (`TOPES_POR_PERSPECTIVA`):** Booking representa el 84 % del volumen bruto. Para evitar que monopolice los fragmentos en preguntas sobre el destino insular, se establecen cuotas dinámicas:
  * Preguntas de *Alojamiento*: Sin límite por fuente.
  * Preguntas de *Destino General*: Máximo 2 fragmentos de Booking y 5 del foro LosViajeros, garantizando la entrada de YouTube y reseñas de actividades.
* **Deduplicación de Citas:** Algoritmo de hashing sobre los primeros 200 caracteres normalizados para descartar réplicas del foro que citan íntegramente el mensaje anterior.

### 2.5. Generación y Guardrails Anti-Alucinación (`rag_answer.py`)
* **Descomposición Estructurada de Booking:** Las reseñas de Booking se reensamblan en tres campos explícitos (`Título`, `Lo que gustó`, `Lo que no gustó`) para evitar que el LLM confunda elogios con quejas.
* **Citas Obligatorias:** Cada afirmación factual debe referenciar explícitamente entre corchetes el fragmento de origen (`[1]`, `[3]`).
* **Protocolo de Abstención Exacta:** Si el contexto no contiene evidencia directa, el modelo está forzado a responder con la frase exacta:
  > *"No hay información suficiente en las opiniones recuperadas para responder a esto."*
* **Prohibición de Agregación Numérica:** El prompt prohíbe emitir conteos absolutos, porcentajes o rankings globales a partir de los fragmentos muestreados, redirigiendo dichas consultas al agente Text-to-SQL.

---

## 3. Evaluación Comparativa (`eval/`)

El subdirectorio `eval/` contiene un conjunto de evaluación de referencia (*Gold Standard*) con 22 pruebas tipificadas en `preguntas.yaml`:
1. **Preguntas Normales:** Miden cobertura de filtros, `Recall@k` y presencia de términos clave en cualquier idioma del corpus multilingüe.
2. **Pruebas de Abstención:** Validan que el sistema rechaza preguntas fuera de dominio (e.g. tipos de interés del BCE, campeonatos de fútbol) sin inventar respuestas.
3. **Trampas de Agregación:** Prueban que el motor rechaza contar o ranquear, salvaguardando la integridad analítica.
4. **LLM-as-a-Judge (`run_eval.py`):** Un evaluador automatizado puntúa la fidelidad factual de las respuestas en una escala de 0 a 5.

```bash
# Ejecutar benchmark de evaluación sobre el conjunto de oro
python analytics/rag/eval/run_eval.py
```

---

## 4. Guía de Uso del Módulo

```bash
# Consulta RAG con extracción automática de entidades
python analytics/rag/rag_answer.py "¿De qué se quejan en Adeje sobre el ruido nocturno?"

# Consulta acotada con parámetros explícitos CLI
python analytics/rag/rag_answer.py "¿Cómo es la experiencia en el Teide?" --municipio "La Orotava" --k 10
```
