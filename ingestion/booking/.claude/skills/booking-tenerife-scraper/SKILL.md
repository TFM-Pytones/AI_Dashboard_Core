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
| Botón abrir reseñas | `[data-testid="Property-Header-Nav-Tab-Trigger-reviews"]` | Clic vía JS (ver sección de errores). Selector viejo `fr-read-all-reviews` sigue en el DOM pero ya no es fiable (ver nota de regresión abajo) |
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

### Regresión: cambio de flujo para abrir el panel de reseñas (septiembre 2026)

Entre el 30-ago y el 6-sep de 2026, el selector `[data-testid="fr-read-all-reviews"]` empezó a
fallar de forma creciente (de ~30% a 100% de las corridas), con `StaleElementReferenceException`
al intentar clickearlo. Diagnóstico con HTML real (JS ya ejecutado) contra 3 establecimientos con
reseñas confirmó: **no fue un bloqueo de IP/WAF ni un selector eliminado** — el botón viejo sigue
presente en el DOM, pero forma parte de un componente que React re-renderiza con mucha frecuencia,
quedando obsoleto entre el `find` y el `click` casi siempre.

Booking migró el flujo a un nuevo tab de navegación del header:
`[data-testid="Property-Header-Nav-Tab-Trigger-reviews"]` (`data-component="core/sliding-panel-trigger"`,
abre un panel deslizante `hp-reviews-sliding`). Clickeando este tab (mismo patrón: `_retry_on_stale`
+ `EC.element_to_be_clickable` + clic vía JS) el panel se abrió de forma consistente en 3/3 pruebas
reales. Importante: **todos los selectores internos de cada reseña no cambiaron** — `review-card`,
`review-score`, `review-title`, `review-positive-text`, `review-negative-text`, `review-date`,
`review-avatar` y la paginación (`button[aria-label="Página siguiente"]`) siguen intactos. Fue
puramente un cambio en el disparador que abre el panel, no en la estructura de datos.

Pista útil para diagnósticos futuros: una página con `[data-testid="no-reviews-banner"]` (0 reseñas)
no sirve para validar este flujo — ahí nunca aparece ningún botón de abrir reseñas porque no hay
nada que mostrar. Probar siempre contra establecimientos con reseñas confirmadas.

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
5. **Bug de especificidad en `slugify()` (agosto 2026)**: la heurística original asumía que un
   bigrama, o una palabra suelta de ≥6 caracteres, era suficiente garantía de especificidad. Falso:
   nombres de alojamiento reales como "San Juan" o "Casablanca" son comunísimos en toda España
   (cientos de propiedades con ese nombre fuera de Tenerife) y pasaban el filtro igual. Un bigrama
   tampoco garantiza especificidad si ambas palabras son vocabulario de categoría turística en vez
   de nombre propio (ej. "vivienda-vacacional" — pasa la regla de "2+ palabras consecutivas" pero
   es una categoría genérica, no un nombre distintivo).

   **Arreglo**: filtro de especificidad por frecuencia empírica, no por longitud/forma de la
   keyword. Antes de aceptar una keyword generada por `slugify()`, contar cuántas URLs del universo
   ya conocido (`sitemap_discovery_cache.json`) la contienen como substring — si supera un umbral
   (`max_matches=20`, ajustable), descartarla y loguearla. Aplica tanto al archivo genérico de toda
   la isla (`tenerife_osm_keywords.json`) como al de prioridad por municipio (ver sección de
   priorización más abajo). Este defecto llevaba tiempo contaminando también el descubrimiento
   general (no solo el de prioridad) — no corrompía los datos guardados porque
   `_verify_is_tenerife()` los descartaba igual en el momento de scrapear, pero sí desperdiciaba
   tiempo real de scraping en establecimientos que nunca eran de Tenerife.
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

## Priorización de descubrimiento por municipio con pocos establecimientos

Motivación: un cruce SQL geoespacial (ver `docs/consultas_cruce_municipios_booking.md`) reveló que
varios municipios de Tenerife tenían menos de 10 establecimientos scrapeados. Al auditar
`config.TENERIFE_MUNICIPALITIES` contra el listado completo de los 31 municipios reales, se
confirmó que **9 municipios faltaban del filtro por completo** — nunca pudieron matchear ni por
nombre, más allá de cualquier keyword de OSM:

- **Grupo A (objetivo de priorización)**: La Matanza de Acentejo, La Victoria de Acentejo, San Juan
  de la Rambla, Arafo, La Guancha, El Tanque — todos con <10 establecimientos hoy.
- **Grupo B (colateral, sin tratamiento especial)**: Santiago del Teide, Guía de Isora, Los Silos —
  con volumen razonable, se agregaron a `TENERIFE_MUNICIPALITIES` solo para mejorar recall general.

Mecanismo para el Grupo A:

1. `build_priority_keywords.py` (nuevo, no reemplaza a `build_tenerife_keywords.py`): consulta el
   bbox real de cada municipio del Grupo A vía `ST_Envelope`/`ST_Transform` a 4326 contra
   `silver.limites_municipales`, corre Overpass acotado a cada bbox, reusa `slugify()` +
   el filtro de especificidad (ver bug arriba), y guarda `tenerife_osm_keywords_priority.json`
   como `{municipio: [keywords]}` (estructura por municipio, a diferencia del genérico que es
   lista plana).
2. Tagging: cada URL del caché combinado se testea contra las keywords de cada municipio del Grupo
   A; los matches quedan en `priority_urls.json` como `{url, municipio, establishment_id}`. Una URL
   puede matchear más de un municipio (se prioriza para todos, no bloquea).
3. `main()` separa `pending_urls_all` en prioridad + resto, filtra cada uno independientemente por
   `filter_pending`, concatena prioridad primero, y **recién ahí** aplica el corte de
   `MAX_ESTABLISHMENTS_PER_RUN` — mismo orden filtrar-antes-de-recortar del bug #5 original, no se
   reintrodujo el problema.
4. Re-descubrimiento forzado (`--recrawl-priority`, flag opt-in, no toca el comportamiento default):
   re-recorre el sitemap completo con el matcher actualizado y **une** el resultado con el caché
   existente sin destruirlo — nunca reemplaza `sitemap_discovery_cache.json`, solo lo hace crecer.

Validado en corridas reales con `MAX_ESTABLISHMENTS_PER_RUN` de 5, 20 y 50 — el log confirma el
desglose de prioridad por municipio y que los establecimientos procesados primero son
efectivamente del Grupo A (slugs con el nombre del municipio literal).

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

## VM con recursos limitados: vigilar DISCO, no solo RAM

La VM del proyecto (`mv-orquestador-tfm`) tiene 29GB de disco y ~842MiB de RAM — ambos son escasos, pero el disco es fácil de subestimar. Un `pip install -r requirements.txt` completo en la VM (en vez de instalar solo lo que el scraper necesita) puede arrastrar `torch`/`transformers`/dependencias NVIDIA/`triton`, sumando **varios GB** (`triton` solo pesa ~594MB) y dejar el disco casi lleno sin previo aviso visible en los logs del scraper.

**Síntoma que esto produce**: Selenium falla con `invalid session id: session deleted as the browser has closed the connection` — Chrome se cierra abruptamente porque no puede escribir sus archivos temporales. Este error se parece a un crash aleatorio, pero la causa real está en `df -h /`, no en el código Python ni en Booking.

**Diagnóstico correcto, en orden**:
```bash
df -h /                                                    # 1. confirmar % de uso real del disco
sudo dmesg | grep -i "oom\|killed process" | tail -20      # 2. descartar RAM (OOM-Killer) como causa
du -sh ~/AI_Dashboard_Core/.venv/lib/python*/site-packages/* 2>/dev/null | sort -rh | head -10  # 3. encontrar qué pesa
```

**Arreglo seguro** (no toca dependencias que otros módulos del equipo sí usan, como `scipy`, `sklearn`, `rasterio`, `pandas`, `pyarrow`):
```bash
pip uninstall triton torch transformers sentencepiece -y
pip list | grep -i nvidia    # confirmar residuos, pip no siempre limpia dependencias transitivas
pip uninstall nvidia-cublas-cu12 nvidia-cuda-cupti-cu12 nvidia-cuda-nvrtc-cu12 \
    nvidia-cuda-runtime-cu12 nvidia-cufft-cu12 nvidia-cufile-cu12 nvidia-curand-cu12 \
    nvidia-cusparse-cu12 nvidia-cusparselt-cu12 nvidia-nccl-cu12 nvidia-nvjitlink-cu12 \
    nvidia-nvshmem-cu12 nvidia-nvtx-cu12 -y
```

**Consecuencia en los datos, cuando esto ya pasó**: puede dejar reseñas "huérfanas" (guardadas en Bronce sin su establecimiento correspondiente, por interrupción a mitad del guardado incremental). El `INNER JOIN` en `silver_booking_reviews.sql` contra establecimientos válidos ya filtra esto automáticamente — no requiere limpieza manual en Bronce. Ver `docs/incidente_disco_lleno_vm.md` para el caso real documentado (30 reseñas huérfanas de ~9500, filtradas sin intervención).

## Encoding en Windows: emojis rompen la consola por defecto

La consola de Windows usa `cp1252` por defecto, no UTF-8 — un emoji en una reseña real (ej. ``) puede crashear un script con `UnicodeEncodeError` al imprimir o loguear. Arreglo permanente, no workaround manual (`PYTHONIOENCODING=utf-8` puntual):

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



## Anti-patrón detectado: cuidado al mezclar ramas de Git con archivos README compartidos

Si más de una persona del equipo edita el mismo README de carpeta compartida en ramas distintas, un merge sin conflicto puede descartar silenciosamente el contenido de una de las dos versiones (Git no siempre detecta esto como conflicto si las líneas no se solapan exactamente). Verificar con `git log --all --oneline -- archivo` si el historial esperado está completo antes de asumir que un merge "automático sin errores" preservó todo.
