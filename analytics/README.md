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
- ⏳ **Issue #17 — Inferencia de Sentimiento por Lotes** — pendiente, reutilizará este setup.
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

### Qué haría falta para el Issue #17 (siguiente paso)

- Reutilizar el mismo modelo/pipeline de aquí, pero iterando sobre **todos** los comentarios
  (no una muestra de 5) — de YouTube, y más adelante Reddit (#14) y reviews (#12).
- Guardar el resultado (label + score por comentario) en una tabla de `processed_data`, para que
  el frontend (`lib/mock-data.ts` en `frontend/`) deje de usar datos simulados y consuma esto.
- Procesar por lotes (`batch_size` en el pipeline de `transformers`) en vez de uno a uno, para
  que sea rápido con miles de comentarios.
