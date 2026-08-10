---
name: booking-tenerife-scraper
description: Conocimiento acumulado para desarrollar o depurar scrapers de Booking.com con Selenium en el proyecto TFM AI Dashboard Tenerife (issue #12). Usar SIEMPRE que se trabaje en booking_scraper.py, en scrapers similares para otras plataformas de reservas (TripAdvisor, etc.), o cuando aparezcan errores de Selenium como "stale element", "click intercepted", "element not interactable", o problemas de geocodificación con Nominatim. También aplica al diseñar el descubrimiento de URLs vía sitemap, al filtrar candidatos por ubicación geográfica, o al definir el esquema de datos para establecimientos/reseñas turísticas.
---

# Scraper de Booking.com para Tenerife (TFM AI Dashboard)

Conocimiento reutilizable extraído del desarrollo real del scraper de Booking (issue #12). Antes de reinventar algo aquí descrito, usa lo ya confirmado.

## Contexto del proyecto

- Objetivo: extraer establecimientos y reseñas de Booking.com en Tenerife.
- Stack: Python + Selenium (contenido dinámico vía JS) + Azure Blob Storage (capa Bronce, Parquet).
- El destino final es un Data Lakehouse: Bronce (Parquet crudo) → Silver (Postgres, vía dbt) → Gold (KPIs).
- Repo: estructura en `ingestion/scraping/`, con `utils/` para módulos compartidos (`azure_storage.py`, `logger.py`, `rate_limiter.py`, `user_agents.py`, `progress_tracker.py`).

## Reglas éticas/legales — sin excepción

1. NO usar el buscador interno de Booking (`/s/`) — bloqueado por robots.txt. Descubrir URLs vía sitemaps oficiales (`sitembk-hotel-*.xml.gz`).
2. NO recolectar datos personales del autor de reseñas (nombre de usuario, foto). Solo país (extraído del `alt` de la imagen de bandera, NUNCA de un `<span>` suelto — ver sección de selectores).
3. Rate limiting siempre: pausas aleatorias (no fijas) entre requests/páginas.
4. User-Agent honesto e identificable, rotado entre varios reales — nunca spoofear como Googlebot.
5. Guardado incremental: subir cada establecimiento apenas termina, no esperar al final del lote completo.

## Estructura de datos confirmada

**Establishment**: `establishment_id` (slug de la URL), `name`, `url`, `address`, `latitude`, `longitude`, `establishment_type`.
**Review**: `review_id`, `establishment_id`, `rating`, `review_text`, `review_date`, `reviewer_country`. **NUNCA** agregar campo de nombre/autor.

`establishment_id` se extrae con regex del path de la URL: `r"/hotel/[a-z]{2}/([^./]+)"`.

## Selectores confirmados de Booking.com (data-testid, no clases CSS)

Las clases CSS de Booking son hashes generados (tipo `f6e3a11b0d`) que cambian con cada deploy — **nunca confiar en ellas**. Usar siempre `data-testid`, mucho más estables.

| Dato | Selector | Notas |
|---|---|---|
| Nombre del hotel | `h2` (genérico, primer h2 de la página) | — |
| Botón abrir reseñas | `[data-testid="fr-read-all-reviews"]` | Clic vía JS (ver sección de errores) |
| Contenedor de cada reseña | `[data-testid="review-card"]` | Se listan tras abrir el panel |
| Puntuación | `[data-testid="review-score"]` | Texto tipo `"Puntuación: 9,0 9,0"` — ver regex de limpieza abajo |
| Título de reseña | `[data-testid="review-title"]` | — |
| Texto positivo | `[data-testid="review-positive-text"]` | — |
| Texto negativo | `[data-testid="review-negative-text"]` | — |
| Fecha de reseña | `[data-testid="review-date"]` | Prefijo `"Fecha del comentario: "` a limpiar |
| Avatar/país | `[data-testid="review-avatar"]` | Contiene 2 `<img>`: foto de perfil (alt="") y bandera (alt="País") |
| Paginación siguiente | `button[aria-label="Página siguiente"]` | Sin data-testid propio |
| Dirección | `[data-testid="PropertyHeaderAddressDesktop-wrapper"]` | Contiene un tooltip anidado que hay que restar (ver abajo) |
| Tipo de establecimiento | `[data-testid="breadcrumb-nav"]` | Último `<li>`, patrón `"...Nombre (Tipo) (País)"` — penúltimo grupo entre paréntesis es el tipo |
| Banner de cookies | `#onetrust-accept-btn-handler` | Aparece de forma inconsistente, cerrar más de una vez |
| Banner "Iniciar sesión con Google" | `div#credential_picker_container iframe`, botón cerrar `[aria-label="Cerrar"]` DENTRO del iframe | Requiere `switch_to.frame()`/`default_content()`, ver sección de errores |
| Sin reseñas | `[data-testid="no-reviews-banner"]` | Si está presente, `fr-read-all-reviews` nunca existe — no esperar por él |

### Extraer país del reseñador (correcto)

```python
avatar = card.find_element(By.CSS_SELECTOR, '[data-testid="review-avatar"]')
flag_imgs = avatar.find_elements(By.CSS_SELECTOR, "img[alt]")
for img in flag_imgs:
    alt_text = img.get_attribute("alt")
    if alt_text:  # la foto de perfil siempre tiene alt="" vacío
        reviewer_country = alt_text
        break
```
NO iterar `<span>` sueltos buscando texto — captura basura (inicial del avatar, contador de "X comentarios").

### Limpiar puntuación (soporta 10 sin decimales)

```python
# Booking muestra "9,0 9,0" pero un 10 perfecto aparece como "10 10" (sin coma)
match = re.search(r"(\d+(?:[,.]\d+)?)", raw_text)
rating = float(match.group(1).replace(",", ".")) if match else None
```

### Extraer dirección completa (evitar el tooltip anidado)

El primer nodo de texto NO siempre contiene la dirección completa (a veces se fragmenta). Mejor: tomar todo el texto y restarle el texto del tooltip hijo.
```python
address_text = driver.execute_script("""
    const container = arguments[0];
    const fullText = container.textContent.trim();
    const tooltip = container.querySelector('div');
    const tooltipText = tooltip ? tooltip.textContent.trim() : '';
    if (tooltipText && fullText.endsWith(tooltipText)) {
        return fullText.slice(0, fullText.length - tooltipText.length).trim();
    }
    return fullText;
""", inner_div)
```
Limitación conocida, no resuelta del todo: a veces igual falta un espacio entre palabras (ej. "Puertode", "10,38260") — cosmético, no rompe la geocodificación.

## Patrones de manejo de errores de Selenium

### Reintento genérico ante fallos transitorios de DOM dinámico

Booking re-renderiza partes de la página con React — captura estos 3 tipos de excepción, re-buscando el elemento desde cero en cada intento:
```python
from selenium.common.exceptions import (
    StaleElementReferenceException,
    ElementClickInterceptedException,
    ElementNotInteractableException,
)

def _retry_on_stale(action, retries=4, delay=1.5):
    for attempt in range(1, retries + 1):
        try:
            return action()
        except (StaleElementReferenceException, ElementClickInterceptedException,
                ElementNotInteractableException) as e:
            time.sleep(delay)
    raise last_error
```

### Clics: usar SIEMPRE clic vía JavaScript, no `.click()` simulado

`.click()` de Selenium falla con "element click intercepted" cuando el banner de cookies u otro overlay tapa momentáneamente el botón. `driver.execute_script("arguments[0].click();", button)` no depende de la posición visual — evita el problema de raíz.

### Banner de cookies: cerrarlo más de una vez

No alcanza con cerrarlo solo al cargar la página — puede reaparecer o tardar en desaparecer justo antes de un clic importante. Re-intentar `_dismiss_cookie_banner()` inmediatamente antes de cada clic crítico (ej. antes de abrir el panel de reseñas).

### Timeouts de carga (`Timed out receiving message from renderer: 30.000`)

Fallo transitorio de red, no de código. Capturar con `except TimeoutException`, loggear y continuar con el siguiente establecimiento — no reintentar automáticamente dentro de la misma corrida (se reintenta solo en la próxima corrida vía el progress tracker, ver abajo).

### Interferencia nueva: banner "Iniciar sesión con Google" (One Tap), distinta al banner de cookies

Booking a veces muestra el widget nativo de Google ("Google One Tap") superpuesto a la página — aparece de forma intermitente y con carga ASÍNCRONA (tarda unos segundos en inyectarse, no está apenas carga la página). Tapa el botón "Leer todos los comentarios" y puede causar un timeout en el clic si no se cierra.

A diferencia del banner de cookies, este vive DENTRO de un `<iframe>` de `accounts.google.com` — Google no lo embebe directo en el DOM del sitio:
```html
<div id="credential_picker_container">
  <iframe title="Cuadro de diálogo Iniciar sesión con Google" src="https://accounts.google.com/gsi/iframe/select?...">
```
Botón de cerrar dentro del iframe: `[aria-label="Cerrar"]` (las clases de Google son generadas/inestables, igual que los hashes CSS de Booking — no confiar en ellas, usar el atributo semántico). Hace falta cambiar de contexto para poder clickearlo:
```python
try:
    iframe = WebDriverWait(driver, 2).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "div#credential_picker_container iframe"))
    )
except TimeoutException:
    return  # no apareció — caso más común, nada que hacer

try:
    driver.switch_to.frame(iframe)
    close_button = driver.find_element(By.CSS_SELECTOR, '[aria-label="Cerrar"]')
    driver.execute_script("arguments[0].click();", close_button)
except (NoSuchElementException, ElementNotInteractableException):
    pass
finally:
    driver.switch_to.default_content()  # SIEMPRE volver, pase lo que pase adentro
```
`switch_to.default_content()` va en un `finally` — si no se vuelve al contexto principal, todos los selectores del sitio (`h2`, `data-testid`, etc.) dejan de encontrar nada después, como si la página estuviera vacía. Llamar a esta función en los mismos dos puntos que `_dismiss_cookie_banner()`: al inicio de la página y justo antes del clic en "Leer todos los comentarios".

**Ojo con el diagnóstico**: verificado en vivo que el banner de Google SÍ aparece y SÍ se cierra bien con este código, pero en dos URLs reportadas como "cuelgan por el banner de Google" (`live-la-caleta-vista-al-mar`, `floritas-23-2`), la causa real de esos timeouts puntuales resultó ser otra cosa (ver siguiente hallazgo) — dos problemas distintos pueden producir el mismo síntoma (timeout en el clic de reseñas). No asumir causa por correlación; instrumentar con timestamps paso a paso hasta encontrar dónde se traba exactamente.

### Establecimientos sin reseñas: `no-reviews-banner`, no hay botón que esperar

Si un establecimiento no tiene ninguna reseña en Booking, el DOM nunca tiene `[data-testid="fr-read-all-reviews"]` — en su lugar aparece `[data-testid="no-reviews-banner"]`. Sin chequear esto antes de intentar el clic, el código esperaba los `PAGE_LOAD_TIMEOUT_SECONDS` completos (30s) por un botón que nunca iba a existir, tiraba `TimeoutException`, y como esa excepción se propaga fuera de `scrape_establishment()`, `main()` la atrapaba en el `except Exception` genérico del loop y **descartaba TODO el establecimiento** (ni el nombre ni la dirección quedaban guardados, no solo las reseñas).

Fix: chequear `no-reviews-banner` temprano (apenas se arma el objeto `Establishment`, antes de intentar abrir el panel) y devolver el establecimiento con `reviews=[]` de inmediato, sin esperar nada:
```python
if driver.find_elements(By.CSS_SELECTOR, '[data-testid="no-reviews-banner"]'):
    logger.info("  Sin reseñas para este establecimiento (no-reviews-banner detectado).")
    return establishment, reviews  # reviews=[] en este punto, no hace falta esperar nada más
```
`driver.find_elements` (plural) no tira excepción si no encuentra nada — no hace falta try/except acá, a diferencia de `find_element` (singular).

Verificado en vivo contra las 2 URLs de arriba: antes del fix, 52.3s y 47.4s hasta `TimeoutException` (establecimiento perdido); después, 18.3s y 14.3s, establecimiento guardado correctamente con 0 reseñas.

### Cuelgue silencioso e invisible: `ChromeDriverManager().install()` dentro del loop

Si `build_driver()` llama a `ChromeDriverManager().install()` cada vez que se construye un driver (una vez por establecimiento), cada llamada hace una consulta de red para verificar/descargar la versión correcta del binario. Un hipo de conexión ahí puede colgar el script 10-20+ minutos **sin ningún log y sin que Chrome llegue a abrirse** (confirmado: sin proceso `chrome.exe` corriendo durante el cuelgue) — invisible al manejo normal de timeouts (`TimeoutException`, `PAGE_LOAD_TIMEOUT_SECONDS`) porque ocurre ANTES de que exista un driver o una página cargando.

**Solución**: resolver la ruta del ChromeDriver una sola vez por corrida, cacheada a nivel de módulo, y que `build_driver()` reutilice esa ruta en cada llamada:
```python
_chromedriver_path: str | None = None

def _get_chromedriver_path() -> str:
    global _chromedriver_path
    if _chromedriver_path is None:
        logger.info("Resolviendo ChromeDriver (una sola vez para toda la corrida)...")
        _chromedriver_path = ChromeDriverManager().install()
    return _chromedriver_path
```
Además, llamar a `_get_chromedriver_path()` explícitamente al inicio de `main()` (antes del loop de establecimientos) para fallar rápido y con log claro ante un problema de red, en vez de que el cuelgue aparezca recién en medio de la corrida, en un establecimiento arbitrario.

## Geocodificación de direcciones (Nominatim/OpenStreetMap)

Nominatim falla con direcciones españolas específicas. Encadenar 3 niveles de fallback, del más preciso al más genérico:
1. Dirección completa tal cual
2. Sin el fragmento `"s/n"` (sin número) — muy común en España, Nominatim no lo reconoce
3. Solo `"código postal + ciudad + país"` — da coordenadas del centro de la zona, mejor que nada

```python
postal_city_match = re.search(r"(\d{4,5}\s+[A-Za-zÀ-ÿ\s]+,\s*España)", address)
```
Respetar 1 request/segundo a Nominatim (política de uso), con `User-Agent` identificable con contacto real del equipo.

## Descubrimiento de URLs vía sitemap — hallazgos importantes

1. `sitembk-hotel-index.xml` es un ÍNDICE de sitemaps, no URLs finales — hay ~3510 shards `.xml.gz` repartidos en ~45 IDIOMAS (no países). El shard `hotel-es.*` = idioma español, NO "hoteles en España".
2. Para filtrar por país real: comprobar el path de la URL (`/hotel/es/...`), no el nombre del shard.
3. **Los shards NO están mezclados al azar** — Booking parece agruparlos por bloques geográficos contiguos. En la práctica, los candidatos de España aparecieron concentrados en un rango acotado de shards (ej. 55-60 de 78), con 0 coincidencias antes y después. Vale la pena loguear el conteo por shard para detectar este patrón y no recorrer los 78 innecesariamente.
4. Filtrar por texto de municipio en el slug tiene recall limitado (muchos slugs no mencionan el municipio). Complementar con nombres reales de alojamientos vía Overpass API (OpenStreetMap) — pero usar BIGRAMAS (pares de palabras consecutivas), nunca palabras sueltas: una palabra como "playa" o "santa-cruz" es tan genérica que genera falsos positivos masivos (ej. "Santa Cruz" existe en Tenerife Y en Sevilla).

### Verificación final anti-falsos-positivos (crítica, barata)

Aunque el filtro de descubrimiento sea bueno, sigue produciendo falsos positivos (nombres de lugar ambiguos en España). Solución robusta y gratuita: el breadcrumb de cada ficha (`[data-testid="breadcrumb-nav"]`) menciona literalmente el nombre de la región/isla. Verificar esto ANTES de gastar tiempo en geocodificar/paginar reseñas — usar el mismo dato que ya se carga para sacar `establishment_type`.
```python
def _verify_is_tenerife(driver) -> bool:
    nav = driver.find_element(By.CSS_SELECTOR, '[data-testid="breadcrumb-nav"]')
    return "tenerife" in nav.text.strip().lower()
```
Si no coincide: NO guardar datos, pero SÍ marcar como completado en el progress tracker (para no re-visitarlo en corridas futuras).

## Progress tracker — evitar duplicados entre corridas

Cada corrida genera archivos Parquet con timestamp único — nunca sobreescribe. Llevar un JSON local (`scraping_progress.json`, en `.gitignore`, NUNCA subir a Git) con `establishment_id` ya procesados (completados o descartados por no-Tenerife), para poder cortar/retomar sin duplicar trabajo.

**IDs determinísticos, no aleatorios**: usar `hashlib.md5(texto.encode()).hexdigest()` para generar IDs de fallback (ej. cuando falta `data-review-id` en el HTML) — NUNCA `hash()` built-in de Python, que está aleatorizado por proceso y genera un ID distinto en cada corrida para el mismo contenido real, rompiendo la deduplicación río abajo.

## Deduplicación en Bronce → Silver

Bronce es una capa de solo-agregar (append-only) por diseño — los duplicados ahí son esperables y correctos, NO borrar archivos de Bronce para "limpiar". La deduplicación es responsabilidad de la transformación hacia Silver:
```sql
SELECT DISTINCT ON (establishment_id) * FROM staging.booking_establishments
ORDER BY establishment_id, fetched_at DESC
```

## Ejecución continua / a escala (VM sin supervisión)

- `HEADLESS = True` por defecto — no necesita pantalla.
- Es secuencial, no paralelo — a ritmo de 30s-2min por establecimiento, miles de candidatos son semanas de cómputo real, no horas. Escalar el límite gradualmente (10 → 20 → 50...), no saltar directo a "todo".
- Tasa de descarte por falsos positivos suele rondar 40-50% del caché de candidatos — cuenta como tiempo real de scraping igual, aunque no se guarde nada.
- Si aparecen 403/CAPTCHAs (no solo timeouts) al escalar, ese es el punto para retomar la necesidad de proxies (issue #3 original ya lo anticipaba).
- Para dejarlo corriendo días/semanas: un wrapper externo que relance el script en loop con pausas entre lotes, deteniéndose solo, cuando el caché de descubrimiento se agota (varios lotes seguidos sin candidatos pendientes).

## Encoding en Windows: emojis rompen la consola por defecto

La consola de Windows usa `cp1252` por defecto, no UTF-8 — un emoji en una reseña real (ej. `🥰`) puede crashear un script con `UnicodeEncodeError` al imprimir o loguear. Arreglo permanente, no workaround manual (`PYTHONIOENCODING=utf-8` puntual):

```python
# en utils/logger.py
def ensure_utf8_console():
    """Reconfigura stdout/stderr a UTF-8. Llamar una sola vez (con guard)."""
    if getattr(sys.stdout, "_utf8_reconfigured", False):
        return
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    sys.stdout._utf8_reconfigured = True
```
Llamarlo automáticamente al inicio de `get_logger()`. **Importante**: cualquier script que NO use `get_logger()` (ej. uno que solo hace `print()`, como `validate_booking_data.py`) NO queda cubierto automáticamente — necesita `from utils.logger import ensure_utf8_console; ensure_utf8_console()` explícito al inicio. Por convención del equipo, todo script nuevo debería usar `get_logger()` desde el principio para evitar este caso borde.

## `get_logger()` escribe a stderr, no a stdout — cuidado al parsear el output de un subproceso

`logging.StreamHandler()` (usado en `utils/logger.py`) usa **`sys.stderr` por defecto** si no se le pasa un stream explícito — confirmado con `logging.StreamHandler().stream is sys.stderr`. Esto significa que TODO el logging de `booking_scraper.py` (incluido cualquier marcador de texto que otro script busque en su output, ej. `"No hay establecimientos pendientes"`) sale por stderr, no por stdout.

Si otro script lanza `booking_scraper.py` como subproceso y necesita inspeccionar su output (ej. `run_continuous.py` buscando ese marcador para saber cuándo detener el loop), **hay que capturar/fusionar stderr, no solo stdout** — de lo contrario el chequeo nunca encuentra lo que busca, silenciosamente, sin ningún error. Con `subprocess.Popen`, fusionar con `stderr=subprocess.STDOUT`; con `subprocess.run`, no alcanza con revisar solo `result.stdout`.

## Streaming en tiempo real de un subproceso largo (`run_continuous.py` → `booking_scraper.py`)

`subprocess.run(..., capture_output=True)` bufferea TODO el output hasta que el proceso termina — inútil para monitorear una corrida larga sin supervisión (no se ve nada hasta el final). Usar `subprocess.Popen` con `stdout=PIPE`, `stderr=STDOUT` (ver arriba), `text=True`, `encoding="utf-8"` explícito (si no, en Windows se decodifica con cp1252 y rompe acentos) y `bufsize=1`, luego iterar `for line in process.stdout: print(line, end="")` — cada línea se entrega apenas se produce. Acumular las líneas en una lista aparte para poder buscar marcadores en el output completo después de que el proceso termine (`process.wait()`).

**Cómo probar que el streaming es real** (no solo "parece funcionar"): el caché de descubrimiento se agota rápido para límites chicos si ya se scrapearon miles de establecimientos en corridas previas (los primeros N candidatos, deterministas, ya están completados) — un lote de prueba puede terminar en segundos sin generar líneas espaciadas en el tiempo, lo cual no prueba nada. Mejor: apuntar `SCRIPT_PATH` a un script descartable que imprima líneas con `time.sleep()` entre medio (por stdout Y stderr) y confirmar con timestamps que cada línea llega a su propio momento, no todas juntas al final.



## Falsa alarma confirmada: "review_date con el país pegado al final" era un artefacto de terminal, no un bug real

Se reportó ver valores tipo `'4 de mayo de 2026España'` en `review_date` (país de `reviewer_country` pegado sin espacio). Investigado a fondo, en ningún nivel apareció el problema real:
1. Parquet leído directo de Blob (sin pasar por ninguna terminal): `review_date` y `reviewer_country` separados y limpios.
2. Barrido de las ~800 reseñas de la corrida completa del día buscando el patrón "dígito pegado a letra": cero coincidencias.
3. DOM real de Booking en vivo: `[data-testid="review-date"]` es un `<span>` aislado, sin nada anidado que pudiera arrastrar el país.

Causa real: una terminal angosta corta visualmente la línea larga de `df.to_string()` justo entre la columna `review_date` y la columna `reviewer_country`, dando la ilusión de que están concatenadas cuando en realidad son dos columnas separadas por espacios que ya no entraron en el ancho visible.

**Antes de asumir que hay un bug de scraping por algo visto en consola**: leer el valor puntual con `repr()` sobre el parquet crudo (sin pasar por un `print(df.to_string())` de una fila ancha) — si ahí aparece limpio, el problema es de visualización, no de datos. Evita "arreglar" con código especulativo un bug que no existe.

## Bug de diseño (corregido): recortar por `limit` ANTES de filtrar completados congela el "pendientes" en 0

`discover_establishment_urls()` / `_discover_from_sitemap()` recortaban el resultado a `limit` (=`config.MAX_ESTABLISHMENTS_PER_RUN`) ANTES de que `main()` aplicara `filter_pending()`. Efecto: cada corrida nueva volvía a pedir siempre los mismos primeros N candidatos del caché (`cached["urls"][:limit]`), nunca avanzaba a las posiciones siguientes. Una vez que esos primeros N quedaban `mark_completed()`, cualquier corrida futura con el mismo límite filtraba esos N a 0 pendientes y terminaba ahí — **aunque el caché tuviera miles de candidatos más sin tocar**. Silencioso: no tira error, solo logea "No hay establecimientos pendientes. Nada que hacer." y listo.

Por qué no se notó antes: una corrida larga en un solo proceso (`python booking_scraper.py` corriendo horas con `MAX_ESTABLISHMENTS_PER_RUN` alto) no lo sufre — el filtrado pasa una sola vez al arrancar y el loop interno de esa misma llamada sí avanza célula por célula, completando de a uno genuino. El bug solo aparece entre invocaciones SEPARADAS del proceso con el mismo límite (exactamente el caso de `run_continuous.py`, que relanza `booking_scraper.py` como subproceso nuevo en cada lote) — ahí es donde de verdad importa, porque es la forma pensada para corridas largas sin supervisión.

**Fix**: `discover_establishment_urls()` (y `_discover_from_sitemap()`) devuelven TODOS los candidatos disponibles, sin recortar. `main()` aplica `filter_pending()` sobre la lista completa y recién DESPUÉS recorta a `config.MAX_ESTABLISHMENTS_PER_RUN`:
```python
pending_urls = filter_pending(urls, _extract_establishment_id)  # sobre la lista completa
...
pending_urls = pending_urls[: config.MAX_ESTABLISHMENTS_PER_RUN]  # recién acá se recorta
```
Excepción a propósito: `config.TEST_ESTABLISHMENT_URLS` (lista manual chica para pruebas rápidas) SÍ sigue recortando por `limit` dentro de `discover_establishment_urls()`, sin este cambio — no tiene el problema de fondo (no es un caché de miles de candidatos) y se quiere que siga devolviendo siempre la misma sublista fija.

**Verificado contra el caché real** (20.941 candidatos, 953 ya completados): antes del fix, pedir un lote con `MAX_ESTABLISHMENTS_PER_RUN=2` daba 0 pendientes (los primeros 2 raw del caché ya estaban hechos). Después del fix, el mismo caso trae 2 candidatos genuinamente nuevos, y un chequeo de solapamiento confirma 0 IDs del lote nuevo presentes en `scraping_progress.json`.

## Validación de una corrida completa (no solo el último archivo)

`booking_scraper.py` genera un archivo Parquet independiente por establecimiento (timestamp único cada vez) — no hay un `run_id` explícito que agrupe "todo lo de esta corrida". `validate_booking_data.py --all` infiere los límites de una corrida agrupando desde el archivo más reciente hacia atrás, cortando cuando el hueco entre dos guardados consecutivos supera `--gap-minutes` (default 15).

**Limitación conocida**: si se corre el scraper dos veces seguidas con poca pausa entre una y otra, el agrupamiento por hueco puede fusionar ambas corridas en una sola sin avisar. Mejora futura (no implementada aún): agregar un `run_id` real, generado una vez al inicio de `main()`, e incluirlo en el nombre de archivo o como columna del Parquet — eliminaría la necesidad de heurística.



## `build_driver()` multiplataforma: Windows (laptop) vs Linux (VM de Azure)

En la VM de Azure (Ubuntu) Chrome necesita flags que en Windows no hacen falta. Detectar con `platform.system() == "Linux"` y aplicarlos condicionalmente, dejando el resto de `build_driver()` idéntico:

```python
if platform.system() == "Linux":
    options.binary_location = "/usr/bin/google-chrome"
    options.add_argument("--no-sandbox")           # la VM suele correr el proceso como root
    options.add_argument("--disable-dev-shm-usage") # /dev/shm es chico por defecto en muchas VMs, Chrome crashea sin esto
    options.add_argument("--disable-gpu")           # sin GPU real en el servidor
    options.add_argument(f"--user-data-dir=/tmp/chrome-user-data-{os.getpid()}")  # único por proceso, permite correr instancias en paralelo
```

### Trampa: Chrome vía Snap falla con Selenium en Ubuntu

Si Chrome/Chromium se instaló vía `snap install chromium` (el default en Ubuntu Desktop reciente), Selenium falla al arrancar el driver con:
```
session not created: probably user data directory is already in use, or Chrome failed to start
Message: unknown error: DevToolsActivePort file doesn't exist
```
Causa: el sandboxing de Snap interfiere con cómo Chrome expone el puerto de DevTools que Selenium necesita para conectarse — no es arreglable solo con `--no-sandbox` u otros flags.

**Solución que funcionó**: desinstalar la versión Snap e instalar `google-chrome-stable` directo del repositorio oficial de Google (`.deb`), no Chromium vía Snap:
```bash
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo apt install ./google-chrome-stable_current_amd64.deb
```
Por eso `options.binary_location` apunta a `/usr/bin/google-chrome` explícitamente en Linux — sin esto, Selenium puede intentar usar un Chromium de Snap residual si quedó instalado.

## Anti-patrón detectado: cuidado al mezclar ramas de Git con archivos README compartidos

Si más de una persona del equipo edita el mismo README de carpeta compartida en ramas distintas, un merge sin conflicto puede descartar silenciosamente el contenido de una de las dos versiones (Git no siempre detecta esto como conflicto si las líneas no se solapan exactamente). Verificar con `git log --all --oneline -- archivo` si el historial esperado está completo antes de asumir que un merge "automático sin errores" preservó todo.
