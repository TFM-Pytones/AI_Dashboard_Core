# Analítica Avanzada e Inteligencia Espacial (Bloque 4 y 5 del TFM)

Este directorio centraliza los módulos de **Machine Learning, Procesamiento de Lenguaje Natural (NLP), Modelado Geoespacial, Regresión Espacial Multiescalar (MGWR) y Sistemas Basados en LLM** del proyecto *Tenerife Tourism AI Dashboard*, transformando las capas Silver y Gold en conocimiento predictivo, diagnóstico territorial y prescripción estratégica.

---

## Mapa de Componentes Analíticos

```
analytics/
├── sentiment/          # Inferencia de sentimiento multilingüe (dual: XLM-RoBERTa + nlptown)
├── topics/             # Modelado de tópicos de conversación turística (BERTopic PCA+KMeans + LLM)
├── aspects/            # Extracción y normalización de aspectos/quejas (PyABSA ATEPC + traductor híbrido)
├── clustering/         # Tipificación territorial y detección de brechas (HDBSCAN 6 clusters + 2D TUI)
├── accesibilidad/      # Tiempos de acceso e isócronas (OpenRouteService ORS API + GTFS TITSA)
├── mgwr/               # Regresión Geográfica Ponderada Multiescalar (MGWR) y Potencial Turístico (PTNA)
├── geo/                # Resolución toponímica en textos no estructurados (Gazetteer canónico)
├── chat/               # Agente analítico conversacional con Text-to-SQL y enrutador inteligente
├── rag/                # Motor RAG híbrido (pgvector 768 dims + BM25 Full-Text Search y RRF)
└── llm/                # Cliente unificado Groq/LLM y generador de informes narrativos ejecutivos
```

---

## 1. Módulos y Metodologías Aplicadas

### 1.1. Análisis de Sentimiento Multilingüe ([`sentiment/`](sentiment/))
* **Arquitectura Dual**:
  * **Comentarios de YouTube**: Filtro zero-shot de relevancia turística (`MoritzLaurer/mDeBERTa-v3-base-mnli-xnli`, margen 0,25) + clasificación de polaridad en 3 clases (`cardiffnlp/twitter-xlm-roberta-base-sentiment`: positivo, neutro, negativo; Macro F1 0,874) volcados en `bronze.ml_sentiment_results`.
  * **Reseñas de Alojamiento (Booking y TripAdvisor)**: Inferencia continua de 1 a 5 estrellas (`nlptown/bert-base-multilingual-uncased-sentiment`; Macro F1 0,832) procesada por lotes de 32 con checkpoints cada 320 registros, volcados en `gold.nlp_sentimiento_resenas` con asignación directa al hexágono H3.
* **Documentación completa**: Ver [`analytics/sentiment/README.md`](sentiment/README.md).

### 1.2. Modelado de Tópicos de Conversación ([`topics/`](topics/))
* **Tecnología**: **BERTopic** multilingüe con embeddings semánticos (`paraphrase-multilingual-mpnet-base-v2`, 768 dimensiones).
* **Pipeline Metodológico**:
  * Eliminación de títulos redundantes de Booking ("Excepcional", "Fantástico") para evitar sesgo hacia la nota.
  * **Centrado por idioma** de embeddings (la dependencia tema-idioma NMI se redujo drásticamente de 0,218 a 0,031).
  * Reducción de dimensionalidad con **PCA (50 componentes)** y partición con **K-Means** ($k=20$ en Modelo A general y $k=50$ en Modelo B geoespacial sobre 51.252 reseñas), evitando el descarte masivo del 76,8% como ruido inherente a HDBSCAN en textos cortos.
  * Extracción de palabras clave c-TF-IDF y etiquetado automático al castellano mediante LLM (API Groq con modelo Llama-3 / GPT-OSS).
* **Documentación completa**: Ver [`analytics/topics/README.md`](topics/README.md).

### 1.3. Extracción de Aspectos y Quejas Específicas ([`aspects/`](aspects/))
* **Tecnología**: **PyABSA ATEPC** (*Aspect-Based Sentiment Analysis* multilingüe via [`batch_inference.py`](aspects/batch_inference.py)) y **Traducción Híbrida** ([`traducir_aspectos.py`](aspects/traducir_aspectos.py)).
* **Objetivo**: Aislar el aspecto evaluado (*limpieza*, *ruido*, *ubicación*, *comida*, *atención*) y su polaridad asociada.
* **Normalización**: Agrupación canónica en 6 macro-dimensiones (`gold.aspecto_traducciones`) para determinar la `queja_principal` modal (`MODE() ... WHERE sentimiento = 'Negative'`) en exactamente las 410 celdas H3 con reseñas turísticas dentro de `gold.gold_sentimiento_h3`.
* **Documentación completa**: Ver [`analytics/aspects/README.md`](aspects/README.md).

### 1.4. Detección de Hotspots y Brechas de Mercado ([`clustering/`](clustering/))
* **Algoritmo**: **HDBSCAN** (*Hierarchical Density-Based Spatial Clustering of Applications with Noise*) calibrado con `min_cluster_size=30, min_samples=10`.
* **Espacio de Características**: 8 variables territoriales (plazas hoteleras `log1p`, radianza VIIRS `log1p`, NDVI, NDBI, altitud, pendiente, distancia a costa y porcentaje de Espacio Natural Protegido `pct_area_enp`).
* **Reducción y Cobertura**: StandardScaler + PCA(3) explicando el **81,5% de la varianza**, seguido de reasignación espacial experta de celdas ruido para lograr una cobertura del **100% de la isla (2.579 celdas H3)** en **6 tipologías oficiales**.
* **Matriz Estratégica 2D**: Proyección continua en Eje 1 (Saturación Turística) vs Eje 2 (Potencial Rural y Sostenible / PTNA / ESG) vinculada a los **5 Arquetipos de Producto TUI** (*Sol y Playa*, *Ecoturismo*, *Cultural*, *Aventura*, *Bienestar*).
* **Documentación completa**: Ver [`analytics/clustering/README.md`](clustering/README.md).

### 1.5. Modelado de Accesibilidad e Isócronas ([`accesibilidad/`](accesibilidad/))
* **Tecnología**: Integración de la API de **OpenRouteService (ORS)** para tiempos de conducción por carretera hacia los aeropuertos de Tenerife Sur (TFS) y Tenerife Norte (TFN), junto con la red de transporte público regular **GTFS TITSA**.
* **Salida**: Métricas de fricción territorial en `gold.gold_h3_accesibilidad` (tiempos mínimos, frecuencias horarias y proximidad a nodos de movilidad).

### 1.6. Regresión Espacial Multiescalar y Potencial Turístico ([`mgwr/`](mgwr/))
* **Modelo**: **MGWR** (*Multiscale Geographically Weighted Regression*) sobre 2.579 hexágonos H3 modelando la no-estacionariedad espacial de la densidad de plazas turísticas frente a 14 variables ambientales, climáticas, de accesibilidad y reputación.
* **Bondad de Ajuste y Diagnóstico Espacial**: Eleva el $R^2$ global (no ajustado) de **0,5444** (OLS) a **0,8272**, reduciendo la I de Moran de los residuos de **0,3065** ($p = 0,0010$) a **0,0355** ($p = 0,0110$, permutación 999 iteraciones), mitigando sustancialmente la dependencia espacial residual.
* **Escalas de Operación**: Anchos de banda locales para `altitud_media_m` (bw=138), `n_naturaleza` (bw=132), `n_restaurantes` (bw=177) y `ndvi_medio` (bw=198), y saturación cuasi-global en 9 covariables (bw≈2.573) que marca 259 celdas (10,0%) con `confianza_ptna = 'baja'`.
* **Índice PTNA y Oportunidades Ideales**: $\text{PTNA} = \hat{y}_{\text{MGWR}} - y_{\text{observado}}$. El filtro combinado $\text{PTNA} > 0$ y $\text{ESG} > 60$ aísla **247 hexágonos** (9,6% insular) prioritarios para TUI, concentrados en Santa Cruz (34), La Laguna (29), La Orotava (22), Buenavista (20), El Tanque (19) y Los Realejos (18).
* **Documentación completa**: Ver [`analytics/mgwr/README.md`](mgwr/README.md).


### 1.7. Agente Analítico y Búsqueda Híbrida RAG ([`chat/`](chat/), [`rag/`](rag/), [`llm/`](llm/))
* **Agente Text-to-SQL**: Módulo [`chat/sql_agent.py`](chat/sql_agent.py) con catálogo estructurado de tablas Gold para resolver consultas cuantitativas y comparativas de forma autónoma.
* **Motor RAG Híbrido**: Módulo [`rag/rag_answer.py`](rag/rag_answer.py) con base de datos vectorial `pgvector` (`vector(768)`) fusionada con búsqueda léxica BM25 (`tsvector`) mediante *Reciprocal Rank Fusion* (RRF) sobre `gold.nlp_chunks`.
* **Enrutador Inteligente**: Módulo [`chat/router.py`](chat/router.py) que clasifica la intención del usuario con el LLM para dirigir a Text-to-SQL o a RAG.
* **Generación de Informes**: Módulo [`llm/report_generator.py`](llm/report_generator.py) para la síntesis periódica de diagnósticos ejecutivos archivados en `gold.nlp_informe_global`.

---

## 2. Contrato de Dependencias y Linaje de Datos

```
Capa Silver (dbt)
  ├── silver_booking_reviews ───────┐
  ├── silver_tripadvisor_resenas ───┼──▶ analytics/sentiment/batch_inference.py ──▶ gold.nlp_sentimiento_resenas
  ├── silver_youtube_comentarios ───┘                                             (y bronze.ml_sentiment_results)
  │
  ├── silver_booking_reviews ───────┐
  └── silver_tripadvisor_resenas ───┴──▶ analytics/aspects/batch_inference.py   ──▶ gold.nlp_aspectos_resenas
                                           │
                                           ▼
                                         analytics/aspects/traducir_aspectos.py ──▶ gold.aspecto_traducciones
                                           │
                                           ▼
                                         dbt run --select gold_sentimiento_h3  ──▶ gold.gold_sentimiento_h3
  │
  ├── silver_h3_grid ───────────────┐
  ├── silver_gtfs_paradas ──────────┼──▶ analytics/accesibilidad/              ──▶ gold.gold_h3_accesibilidad
  └── silver_osm_pois ──────────────┘
  │
  ├── gold_h3_master ───────────────┐
  ├── gold_h3_accesibilidad ────────┼──▶ analytics/clustering/                 ──▶ gold.h3_clusters (6 tipologías)
  └── gold_sentimiento_h3 ──────────┤
                                    └──▶ analytics/mgwr/                       ──▶ gold.h3_oportunidad (PTNA)
                                                                                  gold.gold_h3_esg_v1 (ESG)
```
