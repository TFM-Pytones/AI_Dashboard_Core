"""Issue #12 — Scraping de Booking.com (reseñas y puntuaciones de establecimientos en Tenerife).

Flujo general:
    1. Descubre URLs de establecimientos en Tenerife vía el sitemap oficial
       (NO usa el buscador interno /s/, ver docs/resumen_robots_booking.md)
    2. Para cada establecimiento, extrae reseñas y puntuaciones con Selenium
       (el contenido de reseñas se carga dinámicamente vía JS)
    3. Guarda todo como Parquet y lo sube a Azure Blob Storage, capa Bronce
       (contenedor bronce-raw, carpeta booking/)

Antes de tocar la lógica de scraping, lee:
    - README.md de esta carpeta (consideraciones legales/éticas, reglas sin excepción)
    - docs/resumen_robots_booking.md
    - docs/resumen_terminos_servicio.md

Requiere en el .env: AZURE_STORAGE_CONNECTION_STRING (ver utils/azure_storage.py)
"""

import gzip
import hashlib
import json
import os
import platform
import shutil
import subprocess
import re
import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
    ElementClickInterceptedException,
    ElementNotInteractableException,
    TimeoutException,
)
from webdriver_manager.chrome import ChromeDriverManager

import config
from utils.rate_limiter import wait
from utils.user_agents import get_random_user_agent
from utils.logger import get_logger
from utils.azure_storage import upload_dataframe_as_parquet
from utils.progress_tracker import filter_pending, mark_completed

logger = get_logger(__name__, log_file=config.LOG_FILE)


def _retry_on_stale(action, retries: int = 4, delay: float = 1.5):
    """Reintenta `action` (una función sin argumentos) ante fallos transitorios
    típicos de Selenium en sitios con re-renders dinámicos:
    - StaleElementReferenceException: el elemento quedó obsoleto tras un re-render
    - ElementClickInterceptedException: algo (ej. banner de cookies) tapa el elemento
    - ElementNotInteractableException: el elemento existe pero no está listo para interactuar
    En todos los casos, esperar un poco y reintentar (re-buscando desde cero) suele resolverlo.
    """
    last_error = None
    retry_exceptions = (
        StaleElementReferenceException,
        ElementClickInterceptedException,
        ElementNotInteractableException,
    )
    for attempt in range(1, retries + 1):
        try:
            return action()
        except retry_exceptions as e:
            last_error = e
            logger.warning(
                f"  Fallo transitorio ({type(e).__name__}), reintentando ({attempt}/{retries})..."
            )
            time.sleep(delay)
    raise last_error


class NotTenerifeError(Exception):
    """Se lanza cuando el breadcrumb de la página confirma que el
    establecimiento NO está en Tenerife (falso positivo del filtro de
    descubrimiento). Lleva el establishment_id para poder marcarlo como
    procesado y no reintentarlo en corridas futuras.
    """
    def __init__(self, establishment_id: str, message: str):
        self.establishment_id = establishment_id
        super().__init__(message)


@dataclass
class Establishment:
    """Un establecimiento (hotel/apartamento) descubierto vía sitemap."""

    establishment_id: str
    name: str
    url: str
    address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    establishment_type: str | None = None


@dataclass
class Review:
    """Una reseña individual de un establecimiento.

    Nota: NO incluye nombre de usuario, foto de perfil ni otro dato personal
    identificable del autor — solo país (si Booking lo muestra), ver README.
    """

    review_id: str
    establishment_id: str
    rating: float | None = None
    review_text: str = ""
    review_date: str | None = None
    reviewer_country: str | None = None


def get_request_headers() -> dict:
    """Headers honestos e identificables, sin spoofear como Googlebot u otro bot."""
    return {
        "User-Agent": get_random_user_agent(),
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    }


# ---------------------------------------------------------------------------
# 1. Descubrimiento de establecimientos vía sitemap (NO usar el buscador interno)
# ---------------------------------------------------------------------------

SITEMAP_NAMESPACE = {"ns": "http://www.sitemaps.org/schemas/sitemap/0.9"}
DISCOVERY_CACHE_FILE = Path(__file__).resolve().parent / "sitemap_discovery_cache.json"


def _fetch_xml(url: str) -> ET.Element:
    """Descarga y parsea un sitemap XML (soporta .xml y .xml.gz)."""
    resp = requests.get(url, headers={"User-Agent": get_random_user_agent()}, timeout=30)
    resp.raise_for_status()
    content = resp.content
    if url.endswith(".gz"):
        content = gzip.decompress(content)
    return ET.fromstring(content)


def _get_spanish_shards() -> list[str]:
    """Descarga el índice principal de sitemaps y devuelve los shards del
    idioma español (hotel-es.*.xml.gz) — ojo: es EL IDIOMA de la página,
    no el país. El filtro por país real se hace después, sobre las URLs.
    """
    root = _fetch_xml(config.BOOKING_HOTEL_SITEMAP)
    locs = [el.text for el in root.findall(".//ns:loc", SITEMAP_NAMESPACE)]
    return [loc for loc in locs if "/sitembk-hotel-es." in loc]


def _extract_country_from_url(url: str) -> str | None:
    """'.../hotel/es/alegria-barranco1.es.html' -> 'es'"""
    match = re.search(r"/hotel/([a-z]{2})/", url)
    return match.group(1) if match else None


def _load_osm_keywords() -> list[str]:
    """Carga palabras clave adicionales generadas por build_tenerife_keywords.py
    (nombres reales de alojamientos en Tenerife, vía OpenStreetMap/Overpass).
    Si el archivo no existe todavía, simplemente no se usan (solo se filtra
    por municipio) — no es un error bloqueante.

    Chequeo de seguridad: descarta cualquier palabra clave de una sola
    palabra con menos de 6 caracteres — reduce el riesgo de que un término
    turístico genérico (ej. "playa", "vista") se cuele y genere falsos
    positivos masivos en shards de otros países/regiones de España.
    """
    osm_file = Path(__file__).resolve().parent / "tenerife_osm_keywords.json"
    if not osm_file.exists():
        return []
    with open(osm_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    raw_keywords = data.get("keywords", [])

    safe_keywords = [
        kw for kw in raw_keywords
        if "-" in kw or len(kw) >= 6  # bigramas (tienen guión) o palabra larga
    ]
    dropped = len(raw_keywords) - len(safe_keywords)
    if dropped:
        logger.info(f"Se descartaron {dropped} palabras clave demasiado genéricas/cortas.")

    return safe_keywords


_OSM_KEYWORDS = _load_osm_keywords()


def _matches_tenerife(url: str) -> bool:
    """Filtra por municipios de Tenerife Y/O nombres reales de alojamientos
    (vía OSM, ver build_tenerife_keywords.py) mencionados en el slug de la URL.

    LIMITACIÓN CONOCIDA (documentar en el TFM): incluso combinando ambas
    fuentes, esto no garantiza cobertura del 100% — solo detecta
    establecimientos cuyo slug de Booking coincide textualmente con el
    nombre del municipio o con alguna palabra del nombre real del
    establecimiento según OSM. Establecimientos con slugs muy distintos a
    su nombre real, o no registrados en OSM, se pierden con este método.
    """
    url_lower = url.lower()
    if any(city in url_lower for city in config.TENERIFE_MUNICIPALITIES):
        return True
    if any(keyword in url_lower for keyword in _OSM_KEYWORDS):
        return True
    return False


def _discover_from_sitemap(limit: int) -> list[str]:
    """Recorre los shards de idioma español, filtra por país=España y
    por coincidencia de municipio de Tenerife en el slug.
    """
    if DISCOVERY_CACHE_FILE.exists():
        logger.info(f"Usando caché de descubrimiento: {DISCOVERY_CACHE_FILE}")
        with open(DISCOVERY_CACHE_FILE, "r", encoding="utf-8") as f:
            cached = json.load(f)
        return cached["urls"][:limit]

    logger.info("Descargando índice de sitemaps de Booking...")
    shards = _get_spanish_shards()
    logger.info(f"{len(shards)} shards del idioma español encontrados. Recorriendo...")

    tenerife_urls: list[str] = []
    for i, shard_url in enumerate(shards, start=1):
        try:
            root = _fetch_xml(shard_url)
        except Exception as e:
            logger.warning(f"  No se pudo descargar shard {shard_url}: {e}")
            continue

        locs = [el.text for el in root.findall(".//ns:loc", SITEMAP_NAMESPACE)]
        matches = [
            loc for loc in locs
            if _extract_country_from_url(loc) == "es" and _matches_tenerife(loc)
        ]
        tenerife_urls.extend(matches)

        logger.info(
            f"  Shard {i}/{len(shards)}: {len(locs)} URLs, "
            f"{len(matches)} coinciden con Tenerife ({len(tenerife_urls)} acumuladas)"
        )

        if len(tenerife_urls) >= limit:
            break

        time.sleep(1)  # cortesía con el CDN de sitemaps, aunque no es scraping de HTML

    # Guardar en caché para no repetir esta descarga cada corrida
    with open(DISCOVERY_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump({"urls": tenerife_urls, "generated_at": pd.Timestamp.now().isoformat()}, f, indent=2)
    logger.info(f"Descubrimiento guardado en caché: {DISCOVERY_CACHE_FILE}")

    return tenerife_urls[:limit]


def discover_establishment_urls(limit: int = config.MAX_ESTABLISHMENTS_PER_RUN) -> list[str]:
    """Descubre URLs de fichas de establecimiento en Tenerife, vía los
    sitemaps oficiales de Booking (permitido por robots.txt).

    Si config.TEST_ESTABLISHMENT_URLS tiene contenido, se usa esa lista fija
    en su lugar (útil para pruebas rápidas sin depender del sitemap).
    """
    if config.TEST_ESTABLISHMENT_URLS:
        logger.warning(
            "Usando TEST_ESTABLISHMENT_URLS (lista manual) en vez del sitemap."
        )
        return config.TEST_ESTABLISHMENT_URLS[:limit]

    return _discover_from_sitemap(limit)


# ---------------------------------------------------------------------------
# 2. Scraping de un establecimiento individual
# ---------------------------------------------------------------------------

_CACHED_DRIVER_PATH: str | None = None


def _get_driver_path() -> str:
    """Verifica/descarga el ChromeDriver UNA SOLA VEZ por corrida completa,
    no una vez por establecimiento.

    Por qué esto importa: ChromeDriverManager().install() hace una llamada
    de red cada vez que se ejecuta (verifica versión más reciente). Si esto
    corre una vez por establecimiento (cientos de veces en una corrida
    grande), cualquier hipo de conexión durante esa llamada puede colgar
    el script silenciosamente por varios minutos ANTES de que Chrome
    siquiera se abra — invisible para el manejo de timeouts normal, porque
    ocurre fuera de cualquier bloque con try/except o timeout explícito.
    """
    global _CACHED_DRIVER_PATH
    if _CACHED_DRIVER_PATH is None:
        logger.info("Verificando ChromeDriver (una sola vez para toda la corrida)...")
        _CACHED_DRIVER_PATH = ChromeDriverManager().install()
    return _CACHED_DRIVER_PATH


def _cleanup_orphaned_chrome_profiles(min_age_minutes: int = 30) -> None:
    """Borra carpetas de perfil temporal de Chrome en /tmp más viejas que
    `min_age_minutes`, sin importar el nombre exacto que Chrome/Selenium
    les haya puesto (se observó que no siempre respetan el nombre pedido
    vía --user-data-dir, ej. aparecen como 'chrome-user-data-XXXXX' en vez
    del prefijo que configuramos).

    Solo Linux (la VM) — en Windows este problema no se presenta.
    Filtra por antigüedad, no borra ciegamente todo lo que coincida con el
    patrón, para no interferir con otra instancia de Chrome que pudiera
    estar corriendo en paralelo (ej. run_continuous.py + booking_scraper_deep.py
    a la vez) en el mismo momento.

    Best-effort: cualquier error (permisos, etc.) se ignora silenciosamente,
    nunca debe romper el scraping en sí.
    """
    try:
        result = subprocess.run(
            [
                "find", "/tmp",
                "-maxdepth", "1",
                "-type", "d",
                "-name", "chrome-*",
                "-mmin", f"+{min_age_minutes}",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        orphaned_dirs = [d for d in result.stdout.strip().split("\n") if d]
        if orphaned_dirs:
            for d in orphaned_dirs:
                shutil.rmtree(d, ignore_errors=True)
            logger.info(f"  Limpieza: {len(orphaned_dirs)} perfil(es) temporal(es) de Chrome huérfano(s) eliminado(s).")
    except Exception as e:
        logger.warning(f"  No se pudo limpiar perfiles temporales de Chrome (no crítico): {e}")


def build_driver() -> webdriver.Chrome:
    """Arma el driver de Chrome, headless por defecto (ver config.HEADLESS)."""
    options = Options()
    if config.HEADLESS:
        options.add_argument("--headless=new")
    options.add_argument(f"user-agent={get_random_user_agent()}")
    options.add_argument("--lang=es-ES")
    options.add_argument("--window-size=1440,900")
    # Reduce la huella "obviamente automatizada" por defecto de Selenium
    options.add_experimental_option("excludeSwitches", ["enable-automation"])

    if platform.system() == "Linux":
        options.binary_location = "/usr/bin/google-chrome"
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument(f"--user-data-dir=/tmp/chrome-data-{os.getpid()}")

    service = Service(_get_driver_path())
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(config.PAGE_LOAD_TIMEOUT_SECONDS)
    return driver


def _dismiss_cookie_banner(driver) -> None:
    """Intenta cerrar el banner de cookies si aparece. No falla si no lo encuentra
    (best-effort) — solo evita que tape botones y cause clics fallidos."""
    try:
        button = driver.find_element(By.CSS_SELECTOR, '#onetrust-accept-btn-handler')
        driver.execute_script("arguments[0].click();", button)
        logger.info("  Banner de cookies cerrado.")
        time.sleep(1)
    except (NoSuchElementException, ElementNotInteractableException):
        pass


def _get_establishment_type(driver) -> str | None:
    """Extrae el tipo de establecimiento (Apartahotel, Hotel, Hostal, etc.)
    desde el breadcrumb de navegación — el último ítem tiene el patrón
    '...Nombre (Tipo) (País)', donde el penúltimo grupo entre paréntesis
    es siempre el tipo.
    """
    try:
        nav = driver.find_element(By.CSS_SELECTOR, '[data-testid="breadcrumb-nav"]')
        items = nav.find_elements(By.TAG_NAME, "li")
        if not items:
            return None
        last_text = items[-1].text.strip()
        # Toma todos los grupos entre paréntesis; el penúltimo es el tipo
        # (el último siempre es el país, ej: "(Apartahotel) (España)")
        matches = re.findall(r"\(([^)]+)\)", last_text)
        if len(matches) >= 2:
            return matches[-2]
        return None
    except NoSuchElementException:
        return None


def _verify_is_tenerife(driver) -> bool:
    """Verificación final anti-falsos-positivos: confirma que 'Tenerife'
    aparece explícitamente en el breadcrumb de navegación de la página.

    Esto es necesario porque el filtro de descubrimiento (municipio o
    palabra clave de OSM en el slug de la URL) puede generar falsos
    positivos con nombres de lugar ambiguos que existen en más de una
    provincia de España (ej: 'santa-cruz' coincide tanto con Santa Cruz
    de Tenerife como con el barrio de Santa Cruz en Sevilla).
    No cuesta una visita extra: usa la misma página que ya cargamos para
    sacar el resto de los datos del establecimiento.
    """
    try:
        nav = driver.find_element(By.CSS_SELECTOR, '[data-testid="breadcrumb-nav"]')
        return "tenerife" in nav.text.strip().lower()
    except NoSuchElementException:
        return False  # si no se puede confirmar, mejor descartar que arriesgar un falso positivo


def _extract_establishment_id(url: str) -> str:
    """Saca el slug del hotel de la URL, ej: 'alegria-barranco1' de
    '.../hotel/es/alegria-barranco1.es.html'."""
    match = re.search(r"/hotel/[a-z]{2}/([^./]+)", url)
    return match.group(1) if match else url


def _clean_score(raw_text: str) -> float | None:
    """'Puntuación: 6,0 6,0' -> 6.0
    'Puntuación: 10 10' -> 10.0  (Booking muestra el 10 perfecto sin decimales)
    """
    match = re.search(r"(\d+(?:[,.]\d+)?)", raw_text)
    if not match:
        return None
    return float(match.group(1).replace(",", "."))


def _geocode_address(address: str) -> tuple[float | None, float | None]:
    """Geocodifica la dirección con Nominatim (OpenStreetMap), gratis y sin API key.
    Devuelve (None, None) si falla — no debe frenar el resto del scraping.

    Nominatim suele no reconocer direcciones con "s/n" (sin número), muy
    comunes en España — si la primera búsqueda no da resultados, reintenta
    sin ese fragmento.
    """
    def _query(q: str) -> tuple[float | None, float | None] | None:
        try:
            resp = requests.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": q, "format": "json", "limit": 1},
                headers={"User-Agent": config.CONTACT_INFO},
                timeout=10,
            )
            resp.raise_for_status()
            results = resp.json()
            if results:
                return float(results[0]["lat"]), float(results[0]["lon"])
        except Exception as e:
            logger.warning(f"Error consultando Nominatim para '{q}': {e}")
        return None

    result = _query(address)
    if result:
        return result

    # Reintento sin "s/n" (con o sin espacio/coma alrededor)
    address_sin_sn = re.sub(r",?\s*s/n\.?,?\s*", ", ", address, flags=re.IGNORECASE)
    address_sin_sn = re.sub(r"\s*,\s*,\s*", ", ", address_sin_sn).strip(", ")
    if address_sin_sn != address:
        logger.info(f"  Geocodificación sin resultado, reintentando sin 's/n': '{address_sin_sn}'")
        result = _query(address_sin_sn)
        if result:
            return result

    # Último recurso: direcciones con detalles muy específicos de piso/apto
    # (ej. "1 piano 4 - Apt 408") tampoco las reconoce Nominatim. Nos
    # quedamos solo con "código postal + ciudad + país" — da coordenadas
    # del centro de la ciudad, no la puerta exacta, pero es mejor que nada
    # para clasificar zonas geográficas en el análisis.
    postal_city_match = re.search(r"(\d{4,5}\s+[A-Za-zÀ-ÿ\s]+,\s*España)", address)
    if postal_city_match:
        fallback_query = postal_city_match.group(1)
        logger.info(f"  Reintentando solo con código postal + ciudad: '{fallback_query}'")
        result = _query(fallback_query)
        if result:
            return result

    logger.warning(f"No se pudo geocodificar '{address}' (ni con variantes simplificadas)")
    return None, None


def _parse_review_card(card) -> Review | None:
    """Extrae los campos de una tarjeta de reseña ya renderizada (elemento Selenium)."""
    try:
        def safe_text(testid: str) -> str:
            try:
                return card.find_element(By.CSS_SELECTOR, f'[data-testid="{testid}"]').text.strip()
            except NoSuchElementException:
                return ""

        # IMPORTANTE: usamos hashlib (determinístico) en vez de hash() de Python
        # (aleatorizado por proceso, cambia cada vez que corres el script) —
        # así el mismo review real siempre genera el mismo review_id, sin
        # importar en qué corrida se scrapeó. Esto es lo que permite deduplicar
        # correctamente más adelante al pasar de Bronce a Silver.
        review_id = card.get_attribute("data-review-id") or hashlib.md5(
            card.text.encode("utf-8")
        ).hexdigest()

        rating = _clean_score(safe_text("review-score"))
        title = safe_text("review-title")
        positive = safe_text("review-positive-text")
        negative = safe_text("review-negative-text")
        review_text = " | ".join(t for t in [title, positive, negative] if t)
        date_raw = safe_text("review-date")  # "Fecha del comentario: 21 de julio de 2026"
        review_date = date_raw.replace("Fecha del comentario:", "").strip() or None

        # País del autor (NO se extrae el nombre, ver README - consideraciones éticas)
        # La bandera del país es un <img alt="País">; la foto de perfil (si existe)
        # siempre tiene alt="" vacío, por eso buscamos la primera con alt no vacío.
        reviewer_country = None
        try:
            avatar = card.find_element(By.CSS_SELECTOR, '[data-testid="review-avatar"]')
            flag_imgs = avatar.find_elements(By.CSS_SELECTOR, "img[alt]")
            for img in flag_imgs:
                alt_text = img.get_attribute("alt")
                if alt_text:
                    reviewer_country = alt_text
                    break
        except NoSuchElementException:
            pass

        return Review(
            review_id=review_id,
            establishment_id="",  # se completa en scrape_establishment()
            rating=rating,
            review_text=review_text,
            review_date=review_date,
            reviewer_country=reviewer_country,
        )
    except Exception as e:
        logger.warning(f"No se pudo parsear una tarjeta de reseña: {e}")
        return None


def scrape_establishment(url: str, max_reviews: int | None = None) -> tuple[Establishment, list[Review]]:
    """Extrae los datos del establecimiento y sus reseñas desde una URL de ficha.

    Selectores confirmados inspeccionando una ficha real de Booking
    (ver conversación de diseño — usan data-testid, más estables que clases CSS).

    max_reviews: si no se especifica, usa config.MAX_REVIEWS_PER_ESTABLISHMENT
    (comportamiento por defecto de siempre). Permite pedir un límite distinto
    puntualmente — ej. booking_scraper_deep.py pide 200 para establecimientos
    con mucho volumen de reseñas, sin afectar la corrida normal.
    """
    max_reviews = max_reviews or config.MAX_REVIEWS_PER_ESTABLISHMENT
    logger.info(f"Scrapeando establecimiento: {url}")
    establishment_id = _extract_establishment_id(url)

    driver = build_driver()
    reviews: list[Review] = []

    try:
        driver.get(url)
        wait_obj = WebDriverWait(driver, config.PAGE_LOAD_TIMEOUT_SECONDS)

        # Pequeña pausa para dejar que la página "se asiente" (widgets, banners,
        # precios) antes de empezar a interactuar — reduce stale elements.
        time.sleep(2.5)
        _dismiss_cookie_banner(driver)

        # --- Datos del establecimiento ---
        name = _retry_on_stale(
            lambda: wait_obj.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "h2"))
            ).text.strip()
        )

        # Verificación anti-falsos-positivos: descartar temprano si el
        # breadcrumb no confirma "Tenerife" — evita perder tiempo en
        # geocodificación/reseñas de un establecimiento que en realidad
        # está en otra provincia (ver docstring de _verify_is_tenerife).
        if not _retry_on_stale(lambda: _verify_is_tenerife(driver)):
            raise NotTenerifeError(
                establishment_id,
                f"'{name}' ({url}) no está en Tenerife según el breadcrumb — descartado.",
            )

        def _get_address():
            try:
                wrapper = driver.find_element(
                    By.CSS_SELECTOR, '[data-testid="PropertyHeaderAddressDesktop-wrapper"]'
                )
                button = wrapper.find_element(By.CSS_SELECTOR, "button")
                inner_div = button.find_element(By.CSS_SELECTOR, "div")
                # Tomamos TODO el texto del contenedor (no solo el primer nodo,
                # que a veces fragmenta la dirección en más de un nodo/elemento
                # y pierde espacios) y le restamos el texto del tooltip anidado.
                address_text = driver.execute_script(
                    """
                    const container = arguments[0];
                    const fullText = container.textContent.trim();
                    const tooltip = container.querySelector('div');
                    const tooltipText = tooltip ? tooltip.textContent.trim() : '';
                    if (tooltipText && fullText.endsWith(tooltipText)) {
                        return fullText.slice(0, fullText.length - tooltipText.length).trim();
                    }
                    return fullText;
                    """,
                    inner_div,
                )
                return address_text or None
            except NoSuchElementException:
                return None

        address = _retry_on_stale(_get_address)

        latitude, longitude = (None, None)
        if address:
            latitude, longitude = _geocode_address(address)
            wait(config.MIN_DELAY_SECONDS, config.MAX_DELAY_SECONDS)  # respeta rate limit de Nominatim también

        establishment_type = _retry_on_stale(lambda: _get_establishment_type(driver))

        establishment = Establishment(
            establishment_id=establishment_id,
            name=name,
            url=url,
            address=address,
            latitude=latitude,
            longitude=longitude,
            establishment_type=establishment_type,
        )

        # --- Abrir el panel de reseñas ---
        def _click_read_all():
            # Reintenta cerrar el banner de cookies justo antes del clic —
            # a veces reaparece o tarda en cerrarse después del primer intento
            # al inicio de la función, y termina tapando este botón.
            _dismiss_cookie_banner(driver)

            button = wait_obj.until(
                EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, '[data-testid="fr-read-all-reviews"]')
                )
            )
            # Clic vía JavaScript en vez de un clic simulado de mouse: no
            # depende de que el botón esté visualmente libre de superposición
            # (evita el error "element click intercepted" cuando el banner
            # de cookies u otro elemento se solapa momentáneamente).
            driver.execute_script("arguments[0].click();", button)

        _retry_on_stale(_click_read_all)
        wait(config.MIN_DELAY_SECONDS, config.MAX_DELAY_SECONDS)

        # --- Paginar reseñas ---
        page = 1
        while len(reviews) < max_reviews:
            def _get_cards():
                wait_obj.until(
                    EC.presence_of_all_elements_located(
                        (By.CSS_SELECTOR, '[data-testid="review-card"]')
                    )
                )
                return driver.find_elements(By.CSS_SELECTOR, '[data-testid="review-card"]')

            cards = _retry_on_stale(_get_cards)

            for card in cards:
                try:
                    review = _parse_review_card(card)
                except StaleElementReferenceException:
                    continue  # esta tarjeta puntual quedó obsoleta, se omite y se sigue
                if review:
                    review.establishment_id = establishment_id
                    reviews.append(review)

            logger.info(f"  Página {page}: {len(cards)} reseñas ({len(reviews)} acumuladas)")

            if len(reviews) >= max_reviews:
                break

            try:
                next_button = driver.find_element(
                    By.CSS_SELECTOR, 'button[aria-label="Página siguiente"]'
                )
                if not next_button.is_enabled():
                    break

                def _click_next():
                    btn = driver.find_element(
                        By.CSS_SELECTOR, 'button[aria-label="Página siguiente"]'
                    )
                    driver.execute_script("arguments[0].click();", btn)

                _retry_on_stale(_click_next)
                page += 1
                wait(config.MIN_DELAY_SECONDS, config.MAX_DELAY_SECONDS)
            except NoSuchElementException:
                logger.info("  No hay más páginas de reseñas.")
                break

    except TimeoutException as e:
        logger.error(f"Timeout esperando elementos en {url}: {e}")
        raise
    finally:
        driver.quit()
        if platform.system() == "Linux":
            _cleanup_orphaned_chrome_profiles()

    return establishment, reviews[:max_reviews]


# ---------------------------------------------------------------------------
# 3. Guardado (local temporal + subida a Azure Blob / capa Bronce)
# ---------------------------------------------------------------------------

def save_and_upload(establishments: list[Establishment], reviews: list[Review]) -> None:
    """Convierte listas de dataclasses a DataFrames y los sube a bronce-raw."""
    if not establishments and not reviews:
        logger.warning("No hay datos para guardar en esta corrida.")
        return

    df_establishments = pd.DataFrame([vars(e) for e in establishments])
    df_reviews = pd.DataFrame([vars(r) for r in reviews])

    timestamp = pd.Timestamp.now().strftime("%Y-%m-%d_%H%M%S")

    upload_dataframe_as_parquet(
        df_establishments,
        filename=f"booking_establishments_{timestamp}.parquet",
        subfolder=config.AZURE_SUBFOLDER,
    )
    upload_dataframe_as_parquet(
        df_reviews,
        filename=f"booking_reviews_{timestamp}.parquet",
        subfolder=config.AZURE_SUBFOLDER,
    )

    logger.info(
        f"Guardado completo: {len(df_establishments)} establecimientos, "
        f"{len(df_reviews)} reseñas."
    )


# ---------------------------------------------------------------------------
# 4. Orquestación principal
# ---------------------------------------------------------------------------

def main():
    logger.info("=== Iniciando scraper de Booking.com ===")

    try:
        urls = discover_establishment_urls()
    except NotImplementedError as e:
        logger.error(f"Descubrimiento no implementado todavía: {e}")
        sys.exit(1)

    # Filtra los establecimientos que ya se scrapearon en una corrida anterior,
    # para poder cortar y retomar sin duplicar trabajo (ver utils/progress_tracker.py)
    pending_urls = filter_pending(urls, _extract_establishment_id)
    skipped = len(urls) - len(pending_urls)
    if skipped:
        logger.info(f"{skipped} establecimiento(s) ya completados en corridas anteriores, se omiten.")

    if not pending_urls:
        logger.info("No hay establecimientos pendientes. Nada que hacer.")
        return

    all_establishments: list[Establishment] = []
    all_reviews: list[Review] = []
    rejected_count = 0

    for i, url in enumerate(pending_urls, start=1):
        logger.info(f"[{i}/{len(pending_urls)}] Procesando {url}")
        try:
            establishment, reviews = scrape_establishment(url)
            all_establishments.append(establishment)
            all_reviews.extend(reviews)

            # Guardado incremental: no perder progreso si el script falla a mitad de camino
            save_and_upload([establishment], reviews)
            mark_completed(establishment.establishment_id)

        except NotTenerifeError as e:
            # Falso positivo del descubrimiento (ver _verify_is_tenerife).
            # No se guarda ningún dato, pero SÍ se marca como completado
            # para no volver a visitarlo en corridas futuras.
            logger.warning(f"  Descartado (no es Tenerife): {e}")
            mark_completed(e.establishment_id)
            rejected_count += 1

        except Exception as e:
            logger.error(f"Error procesando {url}: {e}")
            continue

        wait(config.MIN_DELAY_SECONDS, config.MAX_DELAY_SECONDS)

    logger.info(
        f"=== Corrida finalizada: {len(all_establishments)} establecimientos, "
        f"{len(all_reviews)} reseñas en total ({rejected_count} descartados por no ser de Tenerife) ==="
    )


if __name__ == "__main__":
    main()
