# analytics/

Módulos de análisis del proyecto, cada uno en su propia subcarpeta:

| Subcarpeta | Issues | Qué hace |
|---|---|---|
| `sentiment/` | #16, #17 | Setup del modelo de sentimiento + inferencia por lotes sobre todo el corpus |
| `aspects/` | #18 | Extracción de aspectos (pyabsa): sobre qué habla cada comentario, no solo si es positivo/negativo |
| `topics/` *(pendiente)* | #19 | Modelado de tópicos (BERTopic): agrupa comentarios por temas recurrentes |
| *(pendiente)* | #20 | Georreferenciación de sentimiento/tópicos/aspectos para el módulo de Mapa |
| `ambiental/` *(pendiente)* | #21-24 | NDVI/NDBI, luminosidad nocturna (VIIRS) a partir de Sentinel/Copernicus |
| `clustering/` *(pendiente)* | #25-27 | Clustering espacial (HDBSCAN), detección de brechas de mercado |
| `isocronas/` *(pendiente)* | #28-30 | Motor de rutas, isocronas y métricas de accesibilidad |
| `mgwr/` *(pendiente)* | #31-33 | Regresión geográficamente ponderada, factores de éxito local |

---

## sentiment/

### Estado

- ✅ **Issue #16 — Setup Entorno Hugging Face y Modelos** (`setup_test.py`) — hecho.
- ✅ **Issue #17 — Inferencia de Sentimiento por Lotes** (`batch_inference.py`) — hecho.

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

---

## aspects/ (Issue #18)

### Estado

- ✅ **Issue #18 — Configuración de Extracción de Aspectos (pyabsa)** (`setup_test.py`) — hecho.
- ⏳ **Issue #19 — Modelado de Tópicos (BERTopic)** — pendiente.
- ⏳ **Issue #20 — Georreferenciación de Tópicos y Sentimientos** — pendiente, cruza los
  resultados de sentimiento/aspectos/tópicos con ubicación geográfica para el módulo de Mapa.

### Qué es "extracción de aspectos" y en qué se diferencia del #16/#17

El modelo del #16/#17 solo dice si un comentario entero es positivo/negativo/neutro. **pyabsa**
va un paso más allá: detecta **sobre qué palabra o frase concreta** opina el comentario (el
"aspecto") y el sentimiento de *esa parte en concreto*. Un mismo comentario puede tener varios
aspectos con sentimientos distintos — ej. "las playas geniales pero el tráfico horrible" →
`playas` (positivo) + `tráfico` (negativo), algo que el modelo de sentimiento general no puede
distinguir (te diría solo una etiqueta para toda la frase).

### Checkpoint: `multilingual` (ATEPC)

pyabsa no usa modelos sueltos de Hugging Face como el #16 — tiene su propio "zoo" de checkpoints
ya entrenados para la tarea ATEPC (*Aspect Term Extraction and Polarity Classification*). Se usó
el checkpoint `multilingual` (~1.1GB), el único que no está limitado a un solo idioma — igual de
importante aquí que en el #16, porque el corpus mezcla español/inglés.

### Problemas de compatibilidad encontrados y solución (dejar constancia para el equipo)

Instalar pyabsa en un entorno moderno (Python 3.13) no funcionó a la primera — dos fallos reales,
no hipotéticos, con su arreglo:

1. **`update-checker` 1.0.0 rompe `metric_visualizer`** (dependencia de pyabsa): la versión más
   reciente de `update-checker` cambió su API a argumentos solo-por-nombre, pero
   `metric_visualizer` la llama de forma posicional → `TypeError` al importar pyabsa.
   **Arreglo**: fijado `update-checker==0.18.0` en `requirements.txt` (aunque no es una
   dependencia directa del proyecto, solo transitiva de pyabsa, hay que fijarla a mano porque
   pip instalaría la 1.0.0 por defecto).
2. **`distutils` no existe en Python 3.12+** (se eliminó de la librería estándar), pero pyabsa
   todavía hace `from distutils.version import StrictVersion` internamente. **Arreglo**: importar
   `setuptools` antes que `pyabsa` en el propio script — `setuptools` registra un `distutils`
   compatible como efecto secundario de importarse.
3. **pyabsa vuelca archivos en la raíz del repo por defecto**: el checkpoint descargado
   (`checkpoints/`, 1.1GB), un `checkpoints.json`, y un `*.result.json` por cada ejecución si no
   se pasa `save_result=False`. Añadidas reglas a `.gitignore` para las tres cosas — nunca deben
   comitearse (el checkpoint es demasiado grande para git de todas formas).

### Ejemplo real (última ejecución, sobre comentarios reales de YouTube)

```
[beaches (Positive 0.99), traffic (Negative 0.98)]  The beaches are amazing but the traffic is terrible
[Hostelería (Negative 0.99), empleados (Negative 0.99)]  Incluso se ha "coqueteado" con la idea de...
[hoteles (Negative 0.74), saco (Negative 0.98)]  Pero esos hoteles desbordados de africanos no son...
```

Nota honesta: al ser comentarios públicos de YouTube sin filtrar, no todos son sobre turismo en
sentido estricto — algunos derivan a temas sociales/políticos (vivienda, inmigración) que
también mencionan hostelería/hoteles. Es una limitación de la fuente de datos, no del modelo.

### Setup

```bash
pip install -r requirements.txt   # incluye pyabsa y el pin de update-checker
python analytics/aspects/setup_test.py
```

---

## Qué haría falta para el Issue #19 (siguiente paso)

**#19 (BERTopic)**: a diferencia del #16 y el #18 (que son "setup + prueba con muestra"), este
issue pide **entrenar sobre el corpus completo** — agrupar automáticamente los 3.071 comentarios
por temas recurrentes, sin definir las categorías a mano. Puede leer directamente de
`processed_data.sentiment_results` (ya tiene el texto limpio) en vez de repetir la limpieza
desde `raw_data`.
