
**Fuente:** `https://www.booking.com/robots.txt` **Fecha de revisión:** 18 de julio de 2026

## Contexto

De forma análoga a la revisión realizada sobre TripAdvisor, se analizó el archivo `robots.txt` de Booking.com previo al desarrollo del script de scraping, con el fin de identificar las rutas restringidas para bots automatizados y diseñar la extracción de datos respetando dichas limitaciones.

## Estructura del archivo

El archivo define reglas diferenciadas por bot, además de una sección general aplicable a cualquier bot no identificado explícitamente (caso en el que entraría un scraper estándar de BeautifulSoup/Selenium).

### Bloqueo total de sitio

Los bots `psbot`, `TurnitinBot`, `NPBot` y `NPBot-1` tienen prohibido el acceso completo (`Disallow: /`). No aplican directamente al desarrollo de este proyecto.

### Reglas específicas relevantes

- **Yandex:** acceso restringido a la práctica totalidad del sitio, salvo páginas concretas en inglés, ruso y turco.
- **Applebot:** bloqueo de páginas de fotos, del flujo de reserva (`/book.html`, `/mybooking.html`, `/confirmation.html`) y de varios endpoints internos de mapas y disponibilidad.
- **AdsBot-Google / AdsBot-Google-Mobile:** bloqueo del buscador interno (`/s/`), con permiso explícito sobre páginas de landing promocionales concretas.

### Regla general (`User-agent: *`)

|Categoría|Rutas restringidas (ejemplos)|Implicación|
|---|---|---|
|Fotografías|`/photo.html` y variantes por idioma|Sin acceso a las páginas dedicadas de galería fotográfica|
|Flujo de reserva|`/book.html`, `/mybooking.html`, `/confirmation.html`|Corresponde al proceso de compra, sin relevancia para el análisis de reseñas|
|Endpoints de mapa|`/hotelsonmap.*.json`, `/markers_on_map`, `/navigation_times`|Recursos internos del mapa interactivo|
|Tracking y analítica|`/js_tracking`, `/squeak`, `/track`, `/c360/v1/track`, `/log_rt_blocks_order`|Telemetría interna del sitio|
|Comparador de habitaciones|`/srcompset.*.html`|Función interna de comparación|
|Sitemap de reseñas (recurso XML)|`/sitembk-reviews-https-index.xml`|Bloqueo del archivo de sitemap como recurso crawleable directo (no de las páginas de reseñas en sí)|
|Landing pages promocionales|`/best-price-guarantee/*`, `/free-cancellation/*`, `/deals-special-offers/*`, entre otras|Páginas de marketing sin valor analítico para el proyecto|
|Artículos por categoría/etiqueta|`/articles/tag/`, `/articles/category/`|Listados de blog, fuera del alcance del análisis|

**Observación relevante:** al igual que en TripAdvisor, las páginas individuales de ficha de alojamiento (formato `/hotel/[país]/[nombre-establecimiento].html`), que son las que contienen las reseñas y puntuaciones objeto de este estudio, **no figuran explícitamente restringidas** en la regla general. Sí está bloqueado el archivo de sitemap específico de reseñas como recurso, aunque no las páginas de reseñas propiamente dichas.

### Recursos explícitamente permitidos

El archivo declara un volumen considerable de sitemaps XML organizados por categoría (hoteles, tipo de alojamiento, ubicación, entre otros), destacando `sitembk-hotel-index.xml` y `sitembk-hotel-review-index.xml` como vías oficiales de descubrimiento de URLs de establecimientos y reseñas, en sustitución del uso del buscador interno.

## Decisiones metodológicas derivadas

1. **No se utilizará el buscador interno de Booking** (`/s/`) para la localización de establecimientos, dado que se encuentra restringido para varios bots identificados y, por consistencia de criterio, se opta por evitarlo también para el scraper propio.
2. **Se explorará el uso de los sitemaps oficiales** (`sitembk-hotel-index.xml`, `sitembk-hotel-review-index.xml`) como mecanismo de descubrimiento de URLs de establecimientos en la isla de Tenerife.
3. **Se excluirá cualquier interacción con endpoints de mapas, tracking, o flujo de reserva**, limitando el alcance del scraper a la información pública de reseñas, puntuaciones y datos descriptivos del establecimiento.
4. Se mantiene el mismo criterio aplicado a TripAdvisor: el presente análisis se documenta como evidencia de la diligencia debida realizada antes del desarrollo técnico del scraper.

## Nota metodológica

Al igual que en el caso de TripAdvisor, el cumplimiento de este archivo responde a un criterio ético y de buenas prácticas —de naturaleza voluntaria, no constitutiva de una barrera técnica—, complementario a la revisión pendiente de los Términos de Servicio de Booking.com.