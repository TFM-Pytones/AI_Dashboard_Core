# Modelado de Tópicos de Conversación Turística: BERTopic (`analytics/topics/`)

Este módulo implementa el modelado semántico no supervisado del discurso turístico sobre Tenerife mediante **BERTopic**, descubriendo los temas latentes tanto en el debate macro-insular como en las opiniones específicas de los huéspedes en establecimientos hoteleros y municipios.

---

## 1. Arquitectura de Dos Modelos Semánticos

Para evitar mezclar la discusión sobre políticas de destino, masificación y naturaleza general con detalles específicos de estancia (habitaciones, bufés, limpieza), se entrenan dos modelos independientes:

| Característica | Modelo A (Macro General) | Modelo B (Micro Geoespacial) |
|---|---|---|
| **Ámbito** | Gran debate insular y percepción general | Experiencia en alojamientos y lugares georreferenciados |
| **Fuentes** | Comentarios de YouTube (relevantes) y foros generales de LosViajeros | Reseñas de Booking.com, TripAdvisor y menciones de LosViajeros con topónimo |
| **Volumen** | ~12.000 comentarios y mensajes | **51.252 reseñas** estructuradas vinculadas a coordenadas H3 |
| **Clústeres ($k$)** | **$k = 20$** macro-temas insulares | **$k = 50$** micro-temas operativos |
| **Parámetro min_df** | 2 | 5 |
| **Salida dbt** | `gold_topicos_municipio` | `gold_topicos_h3` y `gold_topicos_municipio` |

---

## 2. Innovaciones y Decisiones Metodológicas Clave

Frente a una aproximación estándar con BERTopic que presentaba severas limitaciones en este corpus, se introdujeron cinco mejoras metodológicas críticas:

```
                               ┌────────────────────────────────────────────────────────┐
                               │           Pipeline Metodológico BERTopic               │
                               └────────────────────────────────────────────────────────┘
                                                            │
                                                            ▼
                                        1. Extracción y Reutilización de Embeddings
                                           paraphrase-multilingual-mpnet-base-v2 (768d)
                                           Reutiliza embeddings precalculados en gold.nlp_chunks
                                                            │
                                                            ▼
                                        2. Supresión de Títulos Redundantes de Booking
                                           Elimina adjetivos automáticos ("Fantástico", "Pésimo")
                                           para evitar agrupar por puntuación en vez de contenido
                                                            │
                                                            ▼
                                        3. Centrado Semántico por Idioma (Anti-Language Bias)
                                           Resta el vector medio del idioma al embedding
                                           NMI idioma-tópico se reduce de 0,218 a 0,031
                                                            │
                                                            ▼
                                        4. Reducción PCA(50) + K-Means (100% Cobertura)
                                           Reemplaza HDBSCAN (que descartaba el 76,8% como ruido)
                                           Asignación al centroide más próximo y similitud coseno
                                                            │
                                                            ▼
                                        5. Extracción c-TF-IDF y Etiquetado con LLM (Groq)
                                           Extracción de palabras clave y asignación de nombre en español
                                           con LLM condicionado por palabras, textos centrales y rating medio
```

1. **Reutilización de Embeddings de `gold.nlp_chunks`**:
   * Emplea el modelo `paraphrase-multilingual-mpnet-base-v2` (768 dimensiones). Los vectores ya calculados en la capa RAG se promedian por documento, evitando recomputar costosas inferencias en GPU.
2. **Depuración de Títulos de Booking**:
   * Las reseñas de Booking incluyen por defecto adjetivos asignados según la nota numérica ("Excepcional", "Fantástico", "Muy bien", "Aceptable", "Pésimo"). Mantenerlos sesgaba los tópicos hacia el rating en lugar de la temática, por lo que se eliminaron del texto de entrenamiento.
3. **Centrado por Idioma (Language-Centering)**:
   * Los modelos multilingües conservan una firma de idioma que provocaba la aparición de tópicos monoculturales (ej. temas enteros exclusivamente en alemán o neerlandés). Al restar la media vectorial del idioma detectado, la Información Mutua Normalizada (**NMI**) entre idioma y tópico se desplomó de **0,218 a 0,031**, logrando clústeres genuinamente temáticos y multilingües.
4. **PCA(50) + K-Means frente a HDBSCAN**:
   * El algoritmo HDBSCAN estándar sobre UMAP descartaba el **76,8%** de las reseñas del Modelo B como ruido (-1), requiriendo reasignaciones forzadas con métricas negativas de silueta (-0,195).
   * Al reemplazarlo por **PCA (50 componentes)** + **K-Means** ($k=20$ y $k=50$), el 100% de las reseñas queda asignado al centroide más cercano, definiendo `probability` como la similitud coseno con dicho centroide.
5. **Etiquetado Semántico Automático con LLM (Groq)**:
   * Los tópicos c-TF-IDF crudos se traducen y titulan en español canónico mediante la API de Groq (`openai/gpt-oss-120b`). El prompt contextualiza las palabras clave, los fragmentos más centrales, muestras aleatorias y la nota media del tópico para evitar sesgos de polaridad (ej. "Camas confortables" frente a un genérico "Camas").
   * Incorpora un diccionario de validación experta (`NOMBRES_REVISADOS`) para proteger tópicos emblemáticos (*Visita al Teide*, *Restaurantes y gastronomía*, *Equipamiento de cocina*, etc.).

---

## 3. Estructura de Scripts

```
analytics/topics/
├── cargar_corpus.py           # Extracción y preparación de textos desde PostgreSQL
├── entrenar_topicos.py        # Entrenamiento de Modelos A y B (PCA, K-Means, c-TF-IDF y LLM)
├── volcar_topicos.py          # Carga de asignaciones y etiquetas en gold.nlp_topics
├── export_general_corpus.py   # Exportación del corpus general (Modelo A)
├── export_geo_corpus.py       # Exportación del corpus georreferenciado (Modelo B)
├── idioma.py                  # Detección y normalización de código ISO de idioma
└── README.md                  # Esta documentación técnica
```

---

## 4. Instrucciones de Ejecución

```bash
# 1. Cargar el corpus de textos y preparar matrices
python analytics/topics/cargar_corpus.py

# 2. Entrenar los modelos A y B con etiquetado LLM automático
python analytics/topics/entrenar_topicos.py

# Alternativa rápida: Entrenar sin invocar la API del LLM (etiquetas basadas en c-TF-IDF)
python analytics/topics/entrenar_topicos.py --sin-llm

# Alternativa: Aplicar nombres revisados sin reentrenar matrices
python analytics/topics/entrenar_topicos.py --solo-renombrar

# 3. Volcar los resultados definitivos a Azure PostgreSQL
python analytics/topics/volcar_topicos.py
```

---

## 5. Integración en el Data Warehouse y Visualización

* **Tabla Maestra**: `gold.nlp_topics` (DDL en [`sql/gold_nlp_topics_schema.sql`](../../sql/gold_nlp_topics_schema.sql)), con campos `topic_id`, `topic_label` (título en español), `topic_keywords` y `probability`.
* **Modelos dbt**:
  * `gold_topicos_h3`: Distribución ponderada de temas por celda de la malla H3.
  * `gold_topicos_municipio`: Agregación temática para los 31 municipios insulares.
* **Dashboard Streamlit**:
  * Página `Alojamiento y Oferta` (`app/alojamiento.py`, `app/temas.py`) con visualización de nubes de temas, comparador por municipio y selector de tópicos traducidos (`app/topic_labels_es.py`).
