"""Issue #12 (extensión) — Segunda pasada de scraping para establecimientos con
mucho volumen de reseñas, buscando mayor variedad temporal (estacionalidad).

Flujo:
    1. Trae desde Silver (Postgres) los establecimientos YA scrapeados.
    2. Para cada uno, visita la página y lee el TOTAL de reseñas real en Booking
       (no las que ya tenemos — el total público del establecimiento).
    3. Si el total supera DEEP_SCRAPE_THRESHOLD, re-scrapea ese establecimiento
       con un límite de reseñas más alto (DEEP_SCRAPE_MAX_REVIEWS).
    4. El orden de las reseñas NO se modifica (sigue siendo "más relevantes
       primero", el orden por defecto de Booking) — decisión consciente,
       ver docs/limitacion_orden_relevancia_deep_scrape.md para el detalle
       metodológico y el riesgo asumido.
    5. Usa un progress tracker SEPARADO (scraping_progress_deep.json) para no
       interferir con el registro de la corrida original.

review_id es un hash determinístico del texto (ver booking_scraper.py) —
cualquier reseña ya capturada antes se deduplica sola en el modelo Silver,
sin generar basura aunque se vuelva a extraer en esta segunda pasada.

Requiere las mismas variables de entorno que booking_scraper.py, más las
credenciales de Postgres (AZURE_DB_*) para leer la lista de establecimientos.
"""

import json
import os
import re
import time
from pathlib import Path

from dotenv import load_dotenv
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from sqlalchemy import create_engine, text

import config
from booking_scraper import (
    build_driver,
    scrape_establishment,
    save_and_upload,
    NotTenerifeError,
    _dismiss_cookie_banner,
    _retry_on_stale,
)
from utils.logger import get_logger

load_dotenv()

logger = get_logger("booking_scraper_deep", log_file=config.LOG_FILE)

# --- Configuración de esta segunda pasada ---
DEEP_SCRAPE_THRESHOLD = 30       # solo re-scrapear establecimientos con MÁS reseñas totales que esto
DEEP_SCRAPE_MAX_REVIEWS = 200    # límite de reseñas a extraer en la pasada profunda

# Para pruebas rápidas: pon un número (ej. 5) para probar con pocos
# establecimientos antes de lanzar la corrida completa. None = sin límite,
# recorre TODOS los establecimientos de Silver (corrida real).
TEST_LIMIT = 5

PROGRESS_FILE_DEEP = Path(__file__).resolve().parent / "scraping_progress_deep.json"


def _get_pg_engine():
    user = os.getenv("AZURE_DB_USER")
    password = os.getenv("AZURE_DB_PASSWORD")
    host = os.getenv("AZURE_DB_HOST")
    db = os.getenv("AZURE_DB_NAME")
    missing = [n for n, v in [("AZURE_DB_USER", user), ("AZURE_DB_PASSWORD", password),
                               ("AZURE_DB_HOST", host), ("AZURE_DB_NAME", db)] if not v]
    if missing:
        raise RuntimeError(f"Faltan variables en el .env: {', '.join(missing)}")
    conn_str = f"postgresql://{user}:{password}@{host}:5432/{db}"
    return create_engine(conn_str, connect_args={"sslmode": "require"})


def _load_progress_deep() -> dict:
    if not PROGRESS_FILE_DEEP.exists():
        return {"completed_establishment_ids": [], "skipped_below_threshold": []}
    with open(PROGRESS_FILE_DEEP, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_progress_deep(progress: dict) -> None:
    with open(PROGRESS_FILE_DEEP, "w", encoding="utf-8") as f:
        json.dump(progress, f, indent=2, ensure_ascii=False)


def _mark_deep_completed(establishment_id: str) -> None:
    progress = _load_progress_deep()
    if establishment_id not in progress["completed_establishment_ids"]:
        progress["completed_establishment_ids"].append(establishment_id)
    _save_progress_deep(progress)


def _mark_below_threshold(establishment_id: str) -> None:
    progress = _load_progress_deep()
    if establishment_id not in progress["skipped_below_threshold"]:
        progress["skipped_below_threshold"].append(establishment_id)
    _save_progress_deep(progress)


def get_already_scraped_establishments(test_limit: int | None = None) -> list[tuple[str, str]]:
    """Trae (establishment_id, url) desde Silver — los establecimientos
    que ya pasaron por la corrida normal.

    test_limit: si se especifica, trae solo esa cantidad (para pruebas
    rápidas antes de lanzar la corrida completa). None = sin límite.
    Se prioriza establishment_id conocido como caso de prueba grande
    (puerto-palace) primero si test_limit está activo, para confirmar
    en la misma prueba tanto el caso "se salta" como el caso "sí re-scrapea".
    """
    engine = _get_pg_engine()
    query = "SELECT establishment_id, url FROM silver.silver_booking_establishments"
    if test_limit:
        # ORDER BY para que puerto-palace (caso conocido con miles de reseñas)
        # aparezca primero, y así la prueba confirme ambas ramas del if/else
        # sin depender del azar de qué orden devuelva Postgres.
        query += " ORDER BY (establishment_id = 'puerto-palace') DESC"
        query += f" LIMIT {int(test_limit)}"
    with engine.connect() as conn:
        result = conn.execute(text(query))
        return [(row[0], row[1]) for row in result]


def get_total_reviews_count(driver) -> int:
    """Lee el total de reseñas publicado en la página (ej. '5.218 comentarios').
    Formato de Booking usa PUNTO como separador de miles, no coma.
    Devuelve 0 si no se pudo leer (best-effort, no bloquea la corrida).
    """
    try:
        score_el = driver.find_element(By.CSS_SELECTOR, '[data-testid="review-score-component"]')
        match = re.search(r"([\d.,]+)\s*comentarios?", score_el.text, re.IGNORECASE)
        if match:
            raw_number = match.group(1).replace(".", "").replace(",", "")
            return int(raw_number)
    except NoSuchElementException:
        pass
    return 0


def check_and_scrape_deep(url: str, establishment_id: str) -> bool:
    """Visita la página, lee el total de reseñas, y decide si aplica la
    pasada profunda. Devuelve True si se re-scrapeó, False si se saltó."""
    driver = build_driver()
    try:
        driver.get(url)
        time.sleep(2.5)
        _dismiss_cookie_banner(driver)

        total_reviews = _retry_on_stale(lambda: get_total_reviews_count(driver))
        logger.info(f"  {establishment_id}: {total_reviews} reseñas totales en Booking")

        if total_reviews <= DEEP_SCRAPE_THRESHOLD:
            _mark_below_threshold(establishment_id)
            return False
    finally:
        driver.quit()

    # Supera el umbral: re-scrapear con límite ampliado (nueva instancia de
    # driver, scrape_establishment maneja su propio ciclo de vida completo)
    logger.info(f"  {establishment_id}: supera {DEEP_SCRAPE_THRESHOLD}, re-scrapeando con límite {DEEP_SCRAPE_MAX_REVIEWS}")
    establishment, reviews = scrape_establishment(url, max_reviews=DEEP_SCRAPE_MAX_REVIEWS)
    save_and_upload([establishment], reviews)
    _mark_deep_completed(establishment_id)
    return True


def main():
    logger.info("=== Iniciando scraping profundo (establecimientos con mucho volumen) ===")

    candidates = get_already_scraped_establishments(test_limit=TEST_LIMIT)
    if TEST_LIMIT:
        logger.warning(f"MODO PRUEBA activo: TEST_LIMIT={TEST_LIMIT} — no es la corrida completa.")
    logger.info(f"{len(candidates)} establecimientos ya scrapeados encontrados en Silver.")

    progress = _load_progress_deep()
    already_done = set(progress["completed_establishment_ids"]) | set(progress["skipped_below_threshold"])
    pending = [(eid, url) for eid, url in candidates if eid not in already_done]
    logger.info(f"{len(pending)} pendientes de evaluar (ya se excluyeron los procesados en corridas anteriores de este script).")

    deep_scraped_count = 0
    skipped_count = 0

    for i, (establishment_id, url) in enumerate(pending, start=1):
        logger.info(f"[{i}/{len(pending)}] Evaluando {establishment_id}")
        try:
            did_deep_scrape = check_and_scrape_deep(url, establishment_id)
            if did_deep_scrape:
                deep_scraped_count += 1
            else:
                skipped_count += 1
        except NotTenerifeError as e:
            logger.warning(f"  Descartado (no es Tenerife, inesperado en re-scrape): {e}")
            _mark_deep_completed(establishment_id)
        except Exception as e:
            logger.error(f"Error procesando {establishment_id}: {e}")
            continue

    logger.info(
        f"=== Scraping profundo finalizado: {deep_scraped_count} re-scrapeados en profundidad, "
        f"{skipped_count} bajo el umbral de {DEEP_SCRAPE_THRESHOLD} reseñas ==="
    )


if __name__ == "__main__":
    main()
