# ingestion/scraping/

Extracción de reseñas y menciones sobre Tenerife en plataformas externas.

**Issues relacionadas:**
- **Issue #12** — Scraping de plataformas de reservas (Booking.com). ✅ *Funcional, corriendo en producción (laptop + VM)*
- **Issue #13** — Integración API de YouTube (`youtube.py`). ✅ *completado*
- **Issue #14** — Extracción de foros (Reddit vía PRAW).

---

## 🔍 Booking.com (Issue #12)

### Objetivo

Extraer establecimientos y reseñas de Booking.com en Tenerife, para alimentar el análisis de sentimiento y el dashboard geolocalizado del proyecto.

### Estado actual

- **Descubrimiento**: automático, vía sitemaps oficiales de Booking (`sitembk-hotel-es.*.xml.gz`), filtrado por país (`/hotel/es/`) + palabras clave de OpenStreetMap (Overpass API) para identificar Tenerife.
- **Extracción**: Selenium headless, con manejo robusto de errores (reintentos ante elementos obsoletos, clics vía JavaScript, banner de cookies y de Google One Tap, establecimientos sin reseñas).
- **Almacenamiento**: Parquet en Azure Blob Storage (`bronce-raw/booking/`), capa Bronce del Data Lakehouse.
- **Ejecución**: en paralelo desde laptop y VM Azure (`mv-orquestador-tfm`), cada una con su propio `scraping_progress.json` para evitar reprocesar.
- **Pipeline hacia Silver**: `ingest_booking_to_postgres.py` → Postgres esquema `bronze` → modelos dbt → esquema `silver`, con deduplicación y tests de calidad automatizados.

### Volumen actual (referencia, ver `docs/hallazgo_establecimientos_sin_resenas.md` para detalle metodológico)
Cientos de establecimientos y miles de reseñas acumuladas — número creciendo con cada corrida de `run_continuous.py`.

### Consideraciones legales y éticas

Ver documentación completa en:
- `docs/resumen_robots_tripadvisor.md`
- `docs/resumen_robots_booking.md`
- `docs/resumen_terminos_servicio.md`

Resumen de reglas seguidas sin excepción:
1. ❌ No se usa el buscador interno de Booking — descubrimiento vía sitemaps oficiales
2. ❌ No se recolecta ningún dato personal del autor de reseñas (solo país, extraído de la bandera del avatar)
3. ❌ No se republica el contenido extraído tal cual (solo uso interno/analítico para el TFM)
4. ✅ Rate limiting con pausas aleatorias entre requests
5. ✅ User-Agent identificable y rotado, sin spoofear bots conocidos
6. ✅ Guardado incremental (cada establecimiento se sube apenas termina)

### Estructura de archivos

```
ingestion/scraping/
├── README.md
├── config.py                      # límites, pausas, credenciales de contacto
├── booking_scraper.py             # scraper principal
├── run_continuous.py              # wrapper para corridas largas por lotes
├── ingest_booking_to_postgres.py  # puente Bronce -> Postgres (bronze)
├── validate_booking_data.py       # validación de calidad post-scraping
├── build_tenerife_keywords.py     # genera palabras clave desde OSM/Overpass
├── docs/
│   ├── resumen_robots_tripadvisor.md
│   ├── resumen_robots_booking.md
│   ├── resumen_terminos_servicio.md
│   ├── hallazgo_establecimientos_sin_resenas.md
│   └── booking_scraper.log        # log persistente, acumula todas las corridas
├── .claude/skills/booking-tenerife-scraper/
│   └── SKILL.md                   # conocimiento técnico acumulado (selectores,
│                                    # bugs conocidos y sus arreglos, patrones)
└── utils/
    ├── azure_storage.py
    ├── rate_limiter.py
    ├── user_agents.py
    ├── logger.py
    └── progress_tracker.py
```

### Cómo ejecutar

**Corrida única (pruebas cortas):**
```bash
python booking_scraper.py
```

**Corrida continua por lotes (producción, laptop o VM):**
```bash
python run_continuous.py
```
Configurar `MAX_ESTABLISHMENTS_PER_RUN` (config.py) y `PAUSE_BETWEEN_BATCHES_SECONDS` (run_continuous.py) según los recursos disponibles — ver nota de RAM abajo.

**Validar calidad de los datos scrapeados:**
```bash
python validate_booking_data.py --all --gap-minutes 600
```

**Subir Bronce a Postgres:**
```bash
python ingest_booking_to_postgres.py
```

**Transformar a Silver (desde `dbt_project/`):**
```bash
dbt run --select tag:booking
dbt test --select tag:booking
```

### Ejecución en la VM Azure (`mv-orquestador-tfm`)

Ver manual completo en Obsidian / `docs/manual_vm_tmux.md` — resumen:
- La VM tiene RAM muy limitada (~842 MiB) — usar lotes moderados (20-100 según lo observado en `free -h`)
- Usar `tmux` para que el proceso sobreviva a desconexiones SSH
- Copiar manualmente `.env`, `scraping_progress.json` y `sitemap_discovery_cache.json` entre laptop y VM (no viajan por Git)

### Limitaciones conocidas (documentadas, no bloqueantes)

- Recall del descubrimiento limitado (~29-71% según corrida) — algunos establecimientos con slugs que no mencionan municipio ni coinciden con nombres de OSM no se descubren
- ~0.5-1% de reseñas sin rating extraído (badge no disponible en el DOM en el momento del scraping)
- Reseñas con puntuación pero sin comentario (Booking lo permite) generan `review_text` vacío — tratado como caso válido, no error
- Pequeño porcentaje de direcciones con espacios faltantes en el texto (no afecta geocodificación)
- Tabla `bronze.*` en Postgres acumula duplicados en cada corrida de `ingest_booking_to_postgres.py` (modo `append`) — la deduplicación real ocurre en el paso hacia `silver`

Para el detalle técnico completo de cada bug encontrado y su solución, ver la skill `booking-tenerife-scraper`.
