"""Configuración centralizada para los scrapers de Booking / TripAdvisor (Issue #12).

Cambia estas constantes según necesites, sin tocar la lógica del scraper.
"""

# --- Alcance geográfico ---
# TODO: acotar según la zonificación ya cargada en el proyecto (issue #5 - microdatos).
ISLAND = "Tenerife"

# --- Sitemaps oficiales (permitido por robots.txt, ver docs/resumen_robots_booking.md) ---
BOOKING_HOTEL_SITEMAP = "https://www.booking.com/sitembk-hotel-index.xml"
BOOKING_REVIEW_SITEMAP = "https://www.booking.com/sitembk-hotel-review-index.xml"

# --- URLs de prueba (mientras no está implementado el parser de sitemaps) ---
# Usa la URL "canónica" (sin parámetros de sesión/tracking tipo aid, sid, checkin...)
TEST_ESTABLISHMENT_URLS = [
    "https://www.booking.com/hotel/es/alegria-barranco1.es.html",
]

# --- Rate limiting ---
MIN_DELAY_SECONDS = 3.0
MAX_DELAY_SECONDS = 8.0

# --- Límites de una corrida, para no sobrecargar la infraestructura del sitio ---
# Empieza bajo para probar rápido; sube estos números cuando ya confirmes que funciona.
MAX_ESTABLISHMENTS_PER_RUN = 1
MAX_REVIEWS_PER_ESTABLISHMENT = 15

# --- User-Agent identificable y honesto (ver README: no spoofear como Googlebot u otro bot) ---
CONTACT_INFO = "TFM-Tenerife-AI-Dashboard (uso academico, contacto: equipo@tfm-tenerife.example)"

# --- Selenium ---
HEADLESS = True
PAGE_LOAD_TIMEOUT_SECONDS = 30

# --- Salida ---
OUTPUT_DIR = "output"  # carpeta local temporal antes de subir a Azure Blob
AZURE_SUBFOLDER = "booking"  # carpeta lógica dentro de bronce-raw

# --- Logging ---
LOG_FILE = "booking_scraper.log"
