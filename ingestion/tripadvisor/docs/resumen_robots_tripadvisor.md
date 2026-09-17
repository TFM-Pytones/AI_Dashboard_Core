# Análisis de Restricciones Robots.txt: TripAdvisor

**Fuente:** `https://www.tripadvisor.com/robots.txt`  
**Fecha de revisión:** 18 de julio de 2026

---

## Contexto

Como parte de la metodología del proyecto, se revisó el archivo `robots.txt` de TripAdvisor previo al desarrollo del script de scraping (issue de ingesta de reseñas), con el objetivo de identificar qué rutas del sitio están explícitamente restringidas para bots automatizados y diseñar el scraper de forma respetuosa con dichas restricciones.

---

## Estructura del archivo

El archivo define reglas diferenciadas para tres grupos de user-agents:

### 1. Bloqueo total de sitio

Bots como GPTBot, ClaudeBot, CCBot, Amazonbot, entre otros —en su mayoría crawlers de entrenamiento de modelos de IA— tienen prohibido el acceso completo al sitio (`Disallow: /`). No aplica directamente a un scraper de scraping dirigido (BeautifulSoup/Selenium), pero confirma la postura general del sitio respecto a la recolección automatizada de contenido.

### 2. Regla general (`User-agent: *`)

Aplica a cualquier bot no identificado explícitamente —incluido, por defecto, un scraper estándar hecho con `requests`, `BeautifulSoup` o `Selenium`—. Restringe alrededor de 400 rutas, entre las que destacan para este proyecto:

| Categoría | Rutas restringidas (ejemplos) | Implicación |
|---|---|---|
| Buscador interno | `/Search`, `/RestaurantSearch`, `/FindRestaurants` | No se puede usar el buscador de TripAdvisor para descubrir establecimientos vía scraping |
| Endpoints de reseñas dinámicas | `/AllReviews`, `/ExpandedUserReviews`, `/ShowUserReviewsHotels`, `/ShowUserReviewsRestaurants`, `/ReviewCollect`, `/QuickReview` | Los endpoints de carga adicional/paginación de reseñas están bloqueados |
| Perfiles de usuario | `/UserPage`, `/Profile`, `/MemberProfile` | No se debe extraer información de los perfiles de los autores de reseñas |
| Multimedia | Múltiples rutas `/media/photo-*`, `/media/vr-photo-*` | Las imágenes están mayormente restringidas |

**Observación relevante:** las páginas individuales de ficha de establecimiento con reseñas (formato `Hotel_Review-*` / `Restaurant_Review-*`) no figuran explícitamente en la lista de `Disallow` de este archivo. Sí están bloqueados, en cambio, el buscador interno y los endpoints AJAX de carga/paginación de reseñas adicionales.

### 3. Reglas específicas adicionales

- `Google-Extended` (crawler de entrenamiento de IA de Google): bloqueo total del sitio.
- `PerplexityBot`: sin acceso a los foros de viajeros.
- `bingbot`: restricción sobre enlaces directos a fotos de ubicación.
- `ChatGPT-User`, `Gemini-Deep-Research`, `OAI-SearchBot`: bloqueo de patrones de URL específicos vinculados a IDs de geolocalización.

### Recursos explícitamente permitidos

El archivo declara públicamente varios **sitemaps XML** como vía oficial para el descubrimiento de URLs del sitio (incluyendo sitemaps de ubicaciones, atracciones y reseñas de usuario), lo cual representa una alternativa más alineada con las restricciones declaradas que el uso del buscador interno.

---

## Decisiones metodológicas derivadas

1. **No se utilizará el buscador interno de TripAdvisor** para la identificación de establecimientos turísticos en Tenerife; se explorará el uso de los sitemaps públicos declarados como fuente alternativa de descubrimiento de URLs.
2. **Se evitará el llamado directo a endpoints AJAX de paginación de reseñas** (`/AllReviews`, `/ExpandedUserReviews`), optando por una navegación simulada mediante Selenium que respete el flujo de carga habitual de un usuario real.
3. **Se excluirá la extracción de datos de perfiles de usuario y contenido multimedia**, limitando el alcance del scraper estrictamente a la información textual de reseñas y puntuaciones necesaria para el análisis de sentimiento.
4. El presente análisis se documenta como evidencia de la diligencia debida aplicada antes del desarrollo del scraper, en línea con las consideraciones éticas y legales del proyecto.

---

## Nota metodológica

El cumplimiento del archivo `robots.txt` es de naturaleza voluntaria (no constituye una barrera técnica), por lo que su seguimiento responde a un criterio ético y de buenas prácticas del equipo, complementario a la revisión de los Términos de Servicio del sitio.
