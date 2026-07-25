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

import sys
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup

import config
from utils.rate_limiter import wait
from utils.user_agents import get_random_user_agent
from utils.logger import get_logger
from utils.azure_storage import upload_dataframe_as_parquet

logger = get_logger(__name__, log_file=config.LOG_FILE)


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

def discover_establishment_urls(limit: int = config.MAX_ESTABLISHMENTS_PER_RUN) -> list[str]:
    """Descubre URLs de fichas de establecimiento a partir del sitemap oficial
    de Booking, filtrando por Tenerife.

    TODO:
        - Descargar/parsear config.BOOKING_HOTEL_SITEMAP (es un índice de sitemaps,
          probablemente haya que bajar un nivel más para llegar a las URLs reales).
        - Filtrar las URLs que correspondan a establecimientos en Tenerife
          (cruzar con los microdatos de zonas turísticas del issue #5, o filtrar
          por patrón de URL si Booking incluye la ubicación en el slug).
        - Respetar `limit` para no descargar de más en una sola corrida.
    """
    logger.info("Descubriendo establecimientos vía sitemap (pendiente de implementar)...")
    raise NotImplementedError("Implementar descubrimiento vía sitemap antes de correr el scraper completo")


# ---------------------------------------------------------------------------
# 2. Scraping de un establecimiento individual
# ---------------------------------------------------------------------------

def scrape_establishment(url: str) -> tuple[Establishment, list[Review]]:
    """Extrae los datos del establecimiento y sus reseñas desde una URL de ficha.

    TODO:
        - Decidir BeautifulSoup vs Selenium según si las reseñas están en el
          HTML inicial o se cargan vía JS (probar primero con requests+BS4,
          si no aparecen las reseñas, pasar a Selenium).
        - Extraer: nombre, dirección/coordenadas, tipo de establecimiento.
        - Paginar reseñas hasta config.MAX_REVIEWS_PER_ESTABLISHMENT.
        - Llamar a wait(config.MIN_DELAY_SECONDS, config.MAX_DELAY_SECONDS)
          entre cada request/página, SIEMPRE.
    """
    logger.info(f"Scrapeando establecimiento: {url}")
    raise NotImplementedError("Implementar extracción de datos por establecimiento")


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

    all_establishments: list[Establishment] = []
    all_reviews: list[Review] = []

    for i, url in enumerate(urls, start=1):
        logger.info(f"[{i}/{len(urls)}] Procesando {url}")
        try:
            establishment, reviews = scrape_establishment(url)
            all_establishments.append(establishment)
            all_reviews.extend(reviews)

            # Guardado incremental: no perder progreso si el script falla a mitad de camino
            save_and_upload([establishment], reviews)

        except Exception as e:
            logger.error(f"Error procesando {url}: {e}")
            continue

        wait(config.MIN_DELAY_SECONDS, config.MAX_DELAY_SECONDS)

    logger.info(
        f"=== Corrida finalizada: {len(all_establishments)} establecimientos, "
        f"{len(all_reviews)} reseñas en total ==="
    )


if __name__ == "__main__":
    main()
