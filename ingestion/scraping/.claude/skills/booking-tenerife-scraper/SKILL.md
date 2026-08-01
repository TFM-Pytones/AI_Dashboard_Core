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
