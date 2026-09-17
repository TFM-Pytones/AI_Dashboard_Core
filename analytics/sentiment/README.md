# Inferencia de Sentimiento Multilingüe por Lotes (`analytics/sentiment/`)

Este módulo implementa el pipeline de **análisis de sentimiento multilingüe** para el proyecto *Tenerife Tourism AI Dashboard*, procesando más de 55.000 opiniones y comentarios procedentes de tres fuentes heterogéneas: **YouTube**, **Booking.com** y **TripAdvisor**.

---

## 1. Arquitectura Dual del Pipeline

El análisis cualitativo opera mediante una **arquitectura bifurcada** según la naturaleza del texto de origen:

```
                               ┌────────────────────────────────────────────────────────┐
                               │       Pipeline Dual de Análisis de Sentimiento        │
                               └────────────────────────────────────────────────────────┘
                                                            │
                            ┌───────────────────────────────┴───────────────────────────────┐
                            ▼                                                               ▼
             Rama 1: Comentarios de YouTube                                Rama 2: Reseñas de Alojamiento
              (Contenido ruidoso y social)                                   (Booking.com y TripAdvisor)
                            │                                                               │
                            ▼                                                               │
             Filtro de Relevancia Zero-Shot                                                 │
          MoritzLaurer/mDeBERTa-v3-base-mnli-xnli                                           │
         (Margen de confianza off-topic > 0,25)                                             │
                            │                                                               │
                            ▼                                                               ▼
             Clasificador de Polaridad (3 Clases)                           Clasificador de Calificación (1-5 Estrellas)
         cardiffnlp/twitter-xlm-roberta-base-sentiment                     nlptown/bert-base-multilingual-uncased-sentiment
             (Negativo, Neutro, Positivo)                                  (Puntuación continua de satisfacción 1 a 5)
                            │                                                               │
                            ▼                                                               ▼
                Tabla de Persistencia:                                          Tabla de Persistencia:
              bronze.ml_sentiment_results                                     gold.nlp_sentimiento_resenas
                            │                                                               │
                            ▼                                                               ▼
                 Capa dbt Silver y RAG:                                           Capa dbt Gold Espacial:
           Consumo para Model A de BERTopic                                    gold.gold_sentimiento_h3 (410 celdas H3)
```

### 1.1. Rama 1: Comentarios de YouTube (Contenido Social)
* **Reto**: Los comentarios de vídeos turísticos con frecuencia tratan sobre el creador de contenido, la edición del vídeo, publicidad o conversaciones interpersonales sin relación con el destino.
* **Etapa 1 — Filtro Zero-Shot**: Se evalúa cada texto con `MoritzLaurer/mDeBERTa-v3-base-mnli-xnli` frente a 4 hipótesis:
  1. *Comentario sobre turismo, viajes o el impacto del turismo en Canarias o Tenerife* (relevante).
  2. *Comentario sobre el vídeo o el canal de YouTube* (off-topic).
  3. *Conversación personal no relacionada con turismo* (off-topic).
  4. *Spam o publicidad* (off-topic).
  * Se descartan aquellos donde una opción off-topic supere a la relevante por un margen mayor a `0,25`.
* **Etapa 2 — Clasificador de Polaridad**: Los textos relevantes se procesan con `cardiffnlp/twitter-xlm-roberta-base-sentiment`, asignando probabilidades continuas y etiqueta discreta (`negative`, `neutral`, `positive`). En validación manual obtuvo un **Macro F1 de 0,874**.
* **Almacenamiento**: Esquema `bronze.ml_sentiment_results` con clave única `(source, source_id)`.

### 1.2. Rama 2: Reseñas de Alojamiento (Booking y TripAdvisor)
* **Naturaleza**: Reseñas estructuradas emitidas por huéspedes confirmados desde 2022. Al estar intrínsecamente ligadas a una estancia, no requieren filtro zero-shot.
* **Modelo**: `nlptown/bert-base-multilingual-uncased-sentiment` (5 clases, correspondientes a calificaciones de 1 a 5 estrellas). En validación cruzada obtuvo un **Macro F1 de 0,832**.
* **Resolución Espacial**: En el momento de la inferencia, se resuelve el identificador de celda H3 (`h3_index`) del establecimiento asociado en `silver.silver_h3_grid`.
* **Almacenamiento**: Esquema `gold.nlp_sentimiento_resenas`. Incorpora checkpoints automáticos cada 320 filas (`FILAS_POR_CHECKPOINT = 320`) para tolerancia a interrupciones.

---

## 2. Componentes del Directorio

```
analytics/sentiment/
├── batch_inference.py     # Script principal unificado de inferencia por lotes (GPU/CPU)
├── backfill_relevance.py  # Script de reprocesamiento zero-shot para comentarios pendientes
├── setup_test.py          # Verificación de dependencias (PyTorch, Transformers, CUDA)
└── README.md              # Esta documentación técnica
```

---

## 3. Instrucciones de Ejecución

El script `batch_inference.py` es totalmente incremental: consulta la base de datos y procesa exclusivamente los registros que aún no disponen de inferencia.

```bash
# Procesar únicamente comentarios de YouTube
python analytics/sentiment/batch_inference.py --source youtube

# Procesar únicamente reseñas de Booking.com
python analytics/sentiment/batch_inference.py --source booking

# Procesar únicamente opiniones de TripAdvisor
python analytics/sentiment/batch_inference.py --source tripadvisor

# Procesar todas las reseñas de alojamiento (Booking + TripAdvisor)
python analytics/sentiment/batch_inference.py --source resenas

# Procesar la totalidad de fuentes en una única ejecución
python analytics/sentiment/batch_inference.py --source todas
```

### Verificación de entorno:
```bash
python analytics/sentiment/setup_test.py
```

---

## 4. Consumo Aguas Abajo y Cruce Territorial

1. **`gold.gold_sentimiento_h3` (dbt)**:
   * Realiza la agregación zonal por hexágono H3 sobre `gold.nlp_sentimiento_resenas`.
   * Cubre exactamente **410 hexágonos H3** (15,9% de la superficie insular), que corresponden con las áreas con presencia de alojamientos reglados con reseñas de usuarios.
   * Calcula el sentimiento medio insular ponderado (**4,12 sobre 5 estrellas**) y enlaza con la `queja_principal` extraída en [`analytics/aspects/`](../aspects/README.md).

2. **`gold.nlp_topics` (BERTopic)**:
   * El script [`analytics/topics/export_general_corpus.py`](../topics/export_general_corpus.py) consulta la columna `is_relevant` de `bronze.ml_sentiment_results` para alimentar el corpus del **Modelo A (General)** de tópicos insulares.
