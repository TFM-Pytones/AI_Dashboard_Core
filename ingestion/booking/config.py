"""Configuración centralizada para los scrapers de Booking / TripAdvisor (Issue #12).

Cambia estas constantes según necesites, sin tocar la lógica del scraper.
"""

# --- Alcance geográfico ---
# TODO: acotar según la zonificación ya cargada en el proyecto (issue #5 - microdatos).
ISLAND = "Tenerife"

# --- Sitemaps oficiales (permitido por robots.txt, ver docs/resumen_robots_booking.md) ---
BOOKING_HOTEL_SITEMAP = "https://www.booking.com/sitembk-hotel-index.xml"
BOOKING_REVIEW_SITEMAP = "https://www.booking.com/sitembk-hotel-review-index.xml"

# --- URLs de prueba (dejar vacía [] para usar el descubrimiento real vía sitemap) ---
TEST_ESTABLISHMENT_URLS = []

# --- Municipios de Tenerife, para filtrar URLs del sitemap por slug ---
# LIMITACIÓN CONOCIDA: solo detecta establecimientos cuyo slug de URL incluye
# el nombre del municipio (ver docstring de _matches_tenerife en booking_scraper.py)
TENERIFE_MUNICIPALITIES = [
    "tenerife",
    "santa-cruz-de-tenerife",
    "la-laguna",
    "san-cristobal-de-la-laguna",
    "puerto-de-la-cruz",
    "adeje",
    "playa-de-las-americas",
    "costa-adeje",
    "los-cristianos",
    "arona",
    "granadilla",
    "candelaria",
    "guimar",
    "icod-de-los-vinos",
    "garachico",
    "los-realejos",
    "la-orotava",
    "tacoronte",
    "el-sauzal",
    "buenavista-del-norte",
    "vilaflor",
    "fasnia",
    "arico",
    "san-miguel-de-abona",
    "santa-ursula",
    "el-rosario",
    "tegueste",
    "bajamar",
    "los-gigantes",
    "san-isidro-tenerife",
]

# --- Rate limiting ---
MIN_DELAY_SECONDS = 3.0
MAX_DELAY_SECONDS = 8.0

# --- Límites de una corrida, para no sobrecargar la infraestructura del sitio ---
# Empieza bajo para probar rápido; sube estos números cuando ya confirmes que funciona.
MAX_ESTABLISHMENTS_PER_RUN = 50
MAX_REVIEWS_PER_ESTABLISHMENT = 200

# --- User-Agent identificable y honesto (ver README: no spoofear como Googlebot u otro bot) ---
CONTACT_INFO = "TFM-Tenerife-AI-Dashboard (uso academico, contacto: equipo@tfm-tenerife.example)"

# --- Selenium ---
HEADLESS = True  # True = sin abrir ventana de navegador, False = visible
PAGE_LOAD_TIMEOUT_SECONDS = 30

# --- Salida ---
OUTPUT_DIR = "output"  # carpeta local temporal antes de subir a Azure Blob
AZURE_SUBFOLDER = "booking"  # carpeta lógica dentro de bronce-raw

# --- Logging ---
# Ruta absoluta y fija, para que el log siempre quede en el mismo lugar
# sin importar desde qué carpeta se ejecute el script. Se sube a Git (docs/)
# para que el equipo pueda ver el historial de corridas y limitaciones
# encontradas (bloqueos, CAPTCHAs, etc.) para la sección del TFM.
from pathlib import Path

LOG_FILE = str(
    Path(__file__).resolve().parent / "docs" / "booking_scraper.log"
)
