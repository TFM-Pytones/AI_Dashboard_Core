"""Seguimiento de progreso entre corridas del scraper.

Evita volver a scrapear un establecimiento que ya se procesó exitosamente
en una corrida anterior — importante para poder cortar y retomar el scraper
sin duplicar trabajo ni generar archivos repetidos.

Guarda un archivo JSON local (no se sube a Azure, solo es control interno).
"""

import json
from pathlib import Path
from datetime import datetime

PROGRESS_FILE = Path(__file__).resolve().parents[1] / "scraping_progress.json"


def load_progress() -> dict:
    if not PROGRESS_FILE.exists():
        return {"completed_establishment_ids": [], "last_run": None}
    with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def mark_completed(establishment_id: str) -> None:
    progress = load_progress()
    if establishment_id not in progress["completed_establishment_ids"]:
        progress["completed_establishment_ids"].append(establishment_id)
    progress["last_run"] = datetime.now().isoformat()
    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump(progress, f, indent=2, ensure_ascii=False)


def is_completed(establishment_id: str) -> bool:
    progress = load_progress()
    return establishment_id in progress["completed_establishment_ids"]


def filter_pending(urls: list[str], id_extractor) -> list[str]:
    """Filtra una lista de URLs, dejando solo las que todavía no se completaron.

    id_extractor: función que saca el establishment_id de una URL
    (usa la misma lógica que _extract_establishment_id en booking_scraper.py)
    """
    progress = load_progress()
    completed = set(progress["completed_establishment_ids"])
    return [url for url in urls if id_extractor(url) not in completed]
