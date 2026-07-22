# analytics/

Módulos de análisis del proyecto, cada uno en su propia subcarpeta:

| Subcarpeta | Issues | Qué hace |
|---|---|---|
| `sentiment/` | #16, #17, #18, #19, #20 | NLP: sentimiento, aspectos, tópicos y su georreferenciación sobre reviews/comentarios/foros |
| `ambiental/` *(pendiente)* | #21-24 | NDVI/NDBI, luminosidad nocturna (VIIRS) a partir de Sentinel/Copernicus |
| `clustering/` *(pendiente)* | #25-27 | Clustering espacial (HDBSCAN), detección de brechas de mercado |
| `isocronas/` *(pendiente)* | #28-30 | Motor de rutas, isocronas y métricas de accesibilidad |
| `mgwr/` *(pendiente)* | #31-33 | Regresión geográficamente ponderada, factores de éxito local |

Solo `sentiment/` existe por ahora — el resto se irán creando según se empiecen esos issues.

---

## sentiment/

### Estado

- ✅ **Issue #16 — Setup Entorno Hugging Face y Modelos** (`setup_test.py`) — hecho.
- ✅ **Issue #17 — Inferencia de Sentimiento por Lotes** (`batch_inference.py`) — hecho.
- ⏳ **Issue #18 — Extracción de Aspectos (pyabsa)** — pendiente.
- ⏳ **Issue #19 — Modelado de Tópicos (BERTopic)** — pendiente.
- ⏳ **Issue #20 — Georreferenciación de Tópicos y Sentimientos** — pendiente, cruza los
  resultados anteriores con ubicación geográfica para el módulo de Mapa del frontend.

### Qué hace `setup_test.py` (Issue #16)

No procesa el dataset completo (eso es el #17) — es una prueba de extremo a extremo que
demuestra que toda la cadena funciona antes de construir el pipeline batch:

```
Neon (raw_data.youtube_comments) → 5 comentarios reales al azar
      → tokenizer + modelo Hugging Face
      → predicción de sentimiento por comentario
```

### Modelo: `cardiffnlp/twitter-xlm-roberta-base-sentiment`

- **Multilingüe** (encaja con "sentimiento multilingüe" que ya anuncia el módulo del frontend) —
  entrenado sobre tuits en varios idiomas, no sobre texto formal.
- Se eligió precisamente por eso: los comentarios de YouTube son cortos, informales, con
  emojis/errores/jerga — el mismo tipo de texto para el que este modelo está entrenado, a
  diferencia de modelos de sentimiento entrenados con reseñas largas y formales.
- Da 3 clases: `positive` / `neutral` / `negative`, con un score de confianza (0-1).
- Es público y gratuito — se descarga una vez desde Hugging Face Hub (~1.1GB) y queda cacheado
  en `~/.cache/huggingface/`. **Sin API key, sin coste, sin conexión a internet en usos
  posteriores** (solo la primera vez, para descargarlo).

### Hardware

El script no fuerza ningún dispositivo — `transformers` detecta automáticamente lo mejor
disponible: GPU Apple Silicon (`mps`) en Mac, CUDA si hay GPU NVIDIA, o CPU si no hay nada de
eso. En la Mac de desarrollo usó `mps:0` sin configuración extra.

### Ejemplo real (última ejecución)

```
[positive 0.90]  Gracias por mostrarnos esta maravilla. Vivo por la zona y suelo hacer a menudo...
[ neutral 0.71]  16:49 los dragos son árboles milenarios
[positive 0.59]  La próxima vez puedes Visitar el Sur, donde hay Playas de arenas doradas...
```

### Setup

```bash
pip install -r requirements.txt   # incluye transformers, torch, sentencepiece
python analytics/sentiment/setup_test.py
```

Requiere que ya existan comentarios en `raw_data.youtube_comments` (correr antes
`ingestion/scraping/youtube.py`) y las variables `DB_*` en el `.env`.

### Qué hace `batch_inference.py` (Issue #17)

Procesa **todos** los comentarios de YouTube pendientes (no una muestra), reutilizando el mismo
modelo del #16, y guarda el resultado en `processed_data.sentiment_results` — tabla genérica
(columna `source`) pensada para admitir TripAdvisor/Booking (#12) y Reddit (#14) más adelante sin
cambiar el esquema (ver `sql/sentiment_results_schema.sql`).

- **Limpieza de texto**: quita URLs y espacios repetidos antes de pasarlo al modelo; descarta lo
  que quede con menos de 3 caracteres útiles.
- **Por lotes** (`batch_size=32`) en vez de uno a uno — mucho más rápido con miles de filas.
- **Incremental**: un `LEFT JOIN` contra `sentiment_results` filtra lo ya procesado antes de
  cargar el modelo — relanzarlo tras una nueva tanda de `ingestion/scraping/youtube.py` solo
  procesa los comentarios nuevos. Si no hay nada nuevo, ni siquiera carga el modelo (~1.1GB),
  para no perder tiempo.

```bash
python analytics/sentiment/batch_inference.py
```

#### Resultado real (última ejecución)

3.100 comentarios de YouTube → 3.071 procesados (29 quedaron vacíos tras limpiar URLs, descartados):

| Sentimiento | Nº | Score medio |
|---|---|---|
| positive | 1.198 | 0.78 |
| negative | 996 | 0.77 |
| neutral | 877 | 0.62 |

Ejemplo de predicción de alta confianza real: `negative 0.97` — *"Así está quedando benidorm un
auténtico asco"*.

### Qué haría falta para el Issue #18/#19 (siguiente paso)

- **#18 (pyabsa)**: sobre este mismo texto limpio, extraer *sobre qué* opina cada comentario
  (playas, precios, masificación...), no solo si es positivo o negativo.
- **#19 (BERTopic)**: agrupar automáticamente los comentarios por temas recurrentes.
- Ambos pueden leer directamente de `processed_data.sentiment_results` (ya tiene el texto
  limpio) en vez de repetir la limpieza desde `raw_data`.
