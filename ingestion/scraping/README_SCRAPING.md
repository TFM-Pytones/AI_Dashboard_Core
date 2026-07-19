# Scraping — Reseñas y puntuaciones (TripAdvisor / Booking)

**Issues relacionadas:** #12 (TripAdvisor / Booking), #13 (Google Reviews / YouTube), #14 (Reddit) **Responsables:** [tu nombre] y Guille **Estado:** 🔧 En desarrollo

## Objetivo

Extraer reseñas y puntuaciones de hoteles y restaurantes en Tenerife desde TripAdvisor y Booking.com, para alimentar el pipeline de análisis de sentimiento (NLP multilingüe) y el dashboard georreferenciado del proyecto.

## Alcance

- **Fuentes:** TripAdvisor, Booking.com
- **Datos a extraer:** nombre del establecimiento, texto de reseña, puntuación, fecha, idioma (si disponible), dirección/coordenadas del establecimiento
- **Fuera de alcance (por diseño):** información personal de los autores de reseñas (nombre de usuario, foto de perfil), contenido multimedia (fotos/vídeos)

## Stack técnico

- Python
- BeautifulSoup (contenido estático) / Selenium (contenido cargado vía JavaScript)
- Pandas para estructuración intermedia
- Carga final a Neon (PostgreSQL + PostGIS)

## ⚠️ Consideraciones legales y éticas (leer antes de programar)

Antes de desarrollar el scraper, se revisaron el archivo `robots.txt` y los Términos de Servicio de ambas plataformas. Resumen ejecutivo:

### robots.txt

- Ninguna de las dos plataformas bloquea explícitamente las páginas individuales de ficha de establecimiento (donde están las reseñas).
- Ambas bloquean el **buscador interno** (`/Search` en TripAdvisor, `/s/` en Booking) → **no usar el buscador interno para descubrir establecimientos.**
- Ambas bloquean endpoints dinámicos de tracking, mapas y paginación AJAX de reseñas.
- **Alternativa:** usar los **sitemaps XML oficiales** para descubrir URLs (`sitembk-hotel-index.xml` en Booking; sitemaps de ubicaciones en TripAdvisor).

📄 Detalle completo: ver `docs/resumen_robots_tripadvisor.md` y `docs/resumen_robots_booking.md`

### Términos de Servicio

- Ambas plataformas prohíben el scraping automatizado sin permiso escrito.
- Booking.com condiciona la prohibición principal a uso **"con fines comerciales"** — este proyecto es académico, sin fines de lucro ni republicación de contenido, lo cual es un matiz relevante (no una autorización).
- El incumplimiento de un ToS es, en general, un asunto civil (no penal), pero puede derivar en bloqueo de IP.

📄 Detalle completo: ver `docs/resumen_terminos_servicio.md`

### Reglas que seguimos en el código, sin excepción

1. ❌ No usar el buscador interno de ninguna plataforma
2. ❌ No recolectar datos personales de usuarios (username, foto, perfil)
3. ❌ No republicar el contenido extraído tal cual (solo uso interno/analítico)
4. ✅ Rate limiting generoso (pausas aleatorias, nunca peticiones simultáneas masivas)
5. ✅ User-Agent identificable y honesto (no spoofear como Googlebot u otro bot)
6. ✅ Guardado incremental (no perder el progreso si el script falla a medio camino)

## Estructura de carpetas

```
ingestion/scraping/
├── README.md                          # este archivo
├── docs/
│   ├── resumen_robots_tripadvisor.md
│   ├── resumen_robots_booking.md
│   └── resumen_terminos_servicio.md
├── tripadvisor_scraper.py
├── booking_scraper.py
├── config.py                          # constantes, rutas de salida, etc.
└── utils/
    ├── rate_limiter.py                # pausas aleatorias entre requests
    ├── user_agents.py                 # rotación de User-Agent
    └── logger.py                      # logging de progreso/errores
```

## Plan de trabajo (próximos pasos)

- [ ] Definir lista de establecimientos objetivo en Tenerife (a partir de los sitemaps o de los microdatos ya cargados en Neon)
- [ ] Prototipo mínimo: extraer reseñas de **un solo establecimiento** en TripAdvisor, validar estructura de datos
- [ ] Repetir para Booking
- [ ] Implementar rate limiting + logging
- [ ] Definir esquema de la tabla en Neon/PostGIS para reseñas (coordinar con quien lleve `sql/`)
- [ ] Escalar a la lista completa de establecimientos
- [ ] Documentar limitaciones encontradas (bloqueos, CAPTCHAs, cambios de estructura HTML) para el TFM

## Cómo ejecutar (a completar conforme se desarrolle)

```bash
python tripadvisor_scraper.py --config config.py
```

## Notas

- TripAdvisor y Booking cambian su estructura HTML con frecuencia — si el scraper deja de funcionar, lo primero es verificar si los selectores CSS/XPath siguen vigentes.
- Cualquier bloqueo, CAPTCHA o comportamiento anómalo encontrado durante el desarrollo debe registrarse aquí como nota, para la sección de limitaciones del TFM.