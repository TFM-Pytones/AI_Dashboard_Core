# ingestion/scraping/

Extracción de reseñas y menciones sobre Tenerife en plataformas externas:

- **Issue #12** — Scraping de plataformas de reservas (TripAdvisor, Booking) con BeautifulSoup/Selenium. Necesita proxies y un servidor 24/7 (Issue #3).
- **Issue #13** — Integración API de YouTube (`youtube.py`). Ver detalle abajo.
- **Issue #14** — Extracción de foros (Reddit vía PRAW).

Cada fuente vive en su propio archivo/subcarpeta.

---

## youtube.py (Issue #13)

Busca vídeos sobre turismo en Tenerife en YouTube y descarga sus comentarios, cargándolos en
Neon. Es la única de las tres fuentes de "percepción turística" que usa una API oficial en vez
de scraping — no necesita proxies ni el servidor del Issue #3 para funcionar.

### Por qué no se usó también "Google Reviews"

El issue original pedía Google Reviews + YouTube. Se descartó la parte de reviews:

- No existe una "API de reviews" suelta — sale de **Google Places API** (Place Details), y solo
  el nivel **Enterprise + Atmosphere** incluye reviews.
- Ese nivel exige una **cuenta de facturación de Google Cloud con tarjeta** (aunque no llegues a
  gastar), y solo da **1.000 requests gratis/mes** — muy poco margen.
- El mismo tipo de dato (opiniones/sentimiento turístico) ya lo cubren los issues **#12**
  (TripAdvisor/Booking) y **#14** (Reddit), ambos gratis y sin tarjeta.

Decisión: YouTube sí (gratis, sin tarjeta), Google Reviews no (coste + fricción sin aportar
cobertura nueva).

### Cómo funciona

1. Busca vídeos para una lista de términos (`SEARCH_TERMS` en el propio script: "Tenerife
   turismo", "Tenerife travel", "visitar Tenerife", "Tenerife vacaciones") vía `search.list`.
2. Para cada vídeo encontrado, saca el nº de visitas (`videos.list`) y pagina sus comentarios
   (`commentThreads.list`, hasta `MAX_COMMENT_PAGES_PER_VIDEO` páginas de ~100 c/u).
3. Guarda todo en `raw_data.youtube_videos` y `raw_data.youtube_comments` (esquema en
   `sql/youtube_schema.sql`) con `INSERT ... ON CONFLICT` — **es seguro volver a ejecutarlo**,
   no duplica filas, solo añade lo nuevo y actualiza contadores.

### Cuota y coste

La API de YouTube cobra en "unidades de cuota", con 10.000/día gratis por defecto y **sin
necesidad de cuenta de facturación** (a diferencia de Places):

| Llamada | Coste | Uso en el script |
|---|---|---|
| `search.list` | 100 unidades | 1 vez por término de búsqueda (4 términos → 400) |
| `videos.list` | 1 unidad | 1 vez por término, hasta 50 vídeos a la vez |
| `commentThreads.list` | 1 unidad | 1 vez por página de comentarios por vídeo |

Una ejecución completa con la configuración actual gasta **~550-600 unidades** (~5-6% de la
cuota diaria). Como el proyecto de Google Cloud no tiene facturación vinculada, si algún día se
agotara la cuota, la API simplemente devolvería error — **nunca puede generar un cargo**.

### Setup

1. Crear/activar un proyecto en [Google Cloud Console](https://console.cloud.google.com), habilitar
   **"YouTube Data API v3"**, crear una API key restringida a esa API (no requiere tarjeta).
2. Añadir al `.env` (ver `.env.example`):
   ```
   YOUTUBE_API_KEY=...
   ```
3. Ejecutar:
   ```bash
   python ingestion/scraping/youtube.py
   ```

### Última ejecución real (referencia)

41 vídeos únicos, 3.100 comentarios únicos guardados. Desglose por término de búsqueda:

| Término | Vídeos | Comentarios |
|---|---|---|
| Tenerife turismo | 15 | 1.883 |
| Tenerife travel | 14 | 599 |
| Tenerife vacaciones | 6 | 316 |
| visitar Tenerife | 6 | 302 |

### Troubleshooting

- **`403` al pedir comentarios de un vídeo concreto**: normal, significa que ese vídeo tiene los
  comentarios desactivados — el script lo salta sin fallar.
- **Error de cuota agotada**: espera al día siguiente (se resetea a medianoche hora del Pacífico)
  o reduce `MAX_VIDEOS_PER_TERM` / `MAX_COMMENT_PAGES_PER_VIDEO` en `youtube.py`.
- **`Falta YOUTUBE_API_KEY`**: revisa que el `.env` tenga la línea y que la hayas guardado.

### Siguiente paso

Los comentarios en `raw_data.youtube_comments` son el input de `analytics/sentiment/` (Issues
#16-19), donde se les aplica el modelo de sentimiento/tópicos.
