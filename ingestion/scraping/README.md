# ingestion/scraping/

Extracción de reseñas y menciones sobre Tenerife en plataformas externas:

- Issue #12 — Scraping de plataformas de reservas (TripAdvisor, Booking) con BeautifulSoup/Selenium
- Issue #13 — Integración API de YouTube (`youtube.py`). Se descartó la parte de Google Reviews
  (Places API): requiere cuenta de facturación de Google Cloud y cuota gratis muy limitada
  (1.000 requests/mes) para el nivel que incluye reviews; el mismo tipo de dato ya lo cubren
  los issues #12 (TripAdvisor/Booking) y #14 (Reddit), sin coste.
- Issue #14 — Extracción de foros (Reddit vía PRAW)

Cada fuente puede vivir en su propia subcarpeta cuando se empiece a implementar.

## youtube.py (Issue #13)

Busca vídeos sobre turismo en Tenerife y descarga sus comentarios a `raw_data.youtube_videos` /
`raw_data.youtube_comments` (Neon). Requiere `YOUTUBE_API_KEY` en el `.env` (ver `.env.example`
en la raíz del repo — sacar la key desde Google Cloud Console, API "YouTube Data API v3").

```bash
python ingestion/scraping/youtube.py
```

Crea las tablas solo si no existen (`sql/youtube_schema.sql`) y hace upsert, así que se puede
volver a ejecutar sin duplicar datos.
