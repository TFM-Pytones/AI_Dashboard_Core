"""Genera keywords de Overpass acotadas por bounding box, una lista por
cada municipio del Grupo A (Issue #12 — priorización de descubrimiento).

Variante de build_tenerife_keywords.py (que NO se modifica, se mantiene tal
cual como generador genérico para toda la isla): en vez de un único bbox
fijo para Tenerife completa, usa un bbox específico por municipio, sacado
de la tabla real `limites_municipales` en Azure PostgreSQL — no coordenadas
inventadas a mano.

Reutiliza slugify() de build_tenerife_keywords.py (misma lógica de
bigramas), para no introducir una lógica de matching inconsistente con el
resto del pipeline.

Requiere en el .env: AZURE_DB_USER, AZURE_DB_PASSWORD, AZURE_DB_HOST,
AZURE_DB_NAME (mismas credenciales que booking_scraper_deep.py).

Uso:
    python build_priority_keywords.py
"""

import json
import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

from build_tenerife_keywords import (
    slugify,
    filter_keywords_by_specificity,
    load_discovery_cache_urls,
    SPECIFICITY_MAX_MATCHES,
)

load_dotenv()

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OUTPUT_FILE = Path(__file__).resolve().parent / "tenerife_osm_keywords_priority.json"

# Municipios del Grupo A (Issue #12): sin cobertura alguna hoy en
# config.TENERIFE_MUNICIPALITIES hasta esta tarea, y objetivo real de la
# priorización (a diferencia del Grupo B, que solo se agrega al config para
# mejorar recall general, sin este tratamiento especial de bbox/Overpass).
# slug (como en config.TENERIFE_MUNICIPALITIES) -> etiqueta real en la tabla espacial
GROUP_A_MUNICIPALITIES = {
    "la-matanza-de-acentejo": "La Matanza de Acentejo",
    "la-victoria-de-acentejo": "La Victoria de Acentejo",
    "san-juan-de-la-rambla": "San Juan de la Rambla",
    "arafo": "Arafo",
    "la-guancha": "La Guancha",
    "el-tanque": "El Tanque",
}


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


def get_group_a_bboxes() -> dict[str, tuple[float, float, float, float]]:
    """Trae el bounding box real (lat_min, lon_min, lat_max, lon_max) de
    cada municipio del Grupo A desde `limites_municipales` (esquema silver
    — la tabla con las columnas crudas `etiqueta`/`granularidad` vive ahí,
    NO en bronze; ver consultas_cruce_municipios_booking.md, sección 1).

    `geometry` está en EPSG:32628 (UTM 28N) — se transforma a 4326 (lat/lon
    estándar) antes de sacar el bbox, porque Overpass espera lat/lon.
    """
    query = text("""
        SELECT etiqueta,
               ST_XMin(ST_Transform(geometry, 4326)) AS lon_min,
               ST_YMin(ST_Transform(geometry, 4326)) AS lat_min,
               ST_XMax(ST_Transform(geometry, 4326)) AS lon_max,
               ST_YMax(ST_Transform(geometry, 4326)) AS lat_max
        FROM silver.limites_municipales
        WHERE granularidad = 'MUNICIPIOS'
          AND etiqueta = ANY(:etiquetas)
    """)
    etiquetas = list(GROUP_A_MUNICIPALITIES.values())
    engine = _get_pg_engine()
    with engine.connect() as conn:
        result = conn.execute(query, {"etiquetas": etiquetas})
        rows = {row.etiqueta: (row.lat_min, row.lon_min, row.lat_max, row.lon_max) for row in result}

    slug_by_etiqueta = {etiqueta: slug for slug, etiqueta in GROUP_A_MUNICIPALITIES.items()}
    bboxes = {}
    for etiqueta, bbox in rows.items():
        slug = slug_by_etiqueta.get(etiqueta)
        if slug:
            bboxes[slug] = bbox

    missing = set(GROUP_A_MUNICIPALITIES) - set(bboxes)
    if missing:
        print(f"[AVISO] No se encontró geometría para: {sorted(missing)} — se omiten del resultado.")

    return bboxes


def _overpass_query_for_bbox(bbox: tuple[float, float, float, float]) -> str:
    lat_min, lon_min, lat_max, lon_max = bbox
    return f"""
[out:json][timeout:60];
(
  node["tourism"~"hotel|apartment|guest_house|hostel|chalet"]({lat_min},{lon_min},{lat_max},{lon_max});
  way["tourism"~"hotel|apartment|guest_house|hostel|chalet"]({lat_min},{lon_min},{lat_max},{lon_max});
);
out center tags;
"""


def fetch_accommodation_names(bbox: tuple[float, float, float, float]) -> list[str]:
    resp = requests.post(
        OVERPASS_URL,
        data={"data": _overpass_query_for_bbox(bbox)},
        headers={"User-Agent": "TFM-Tenerife-AI-Dashboard (uso academico)"},
        timeout=90,
    )
    resp.raise_for_status()
    data = resp.json()
    return [
        element["tags"]["name"]
        for element in data.get("elements", [])
        if element.get("tags", {}).get("name")
    ]


def main():
    print("Consultando bounding boxes reales de limites_municipales (Grupo A)...")
    bboxes = get_group_a_bboxes()

    cache_urls = load_discovery_cache_urls()
    if cache_urls:
        print(f"Caché de descubrimiento cargado para el filtro de especificidad: {len(cache_urls)} URLs.")
    else:
        print(
            "[AVISO] No se encontró sitemap_discovery_cache.json — no se pudo aplicar el "
            "filtro de especificidad, se guardan todas las keywords generadas sin filtrar."
        )

    keywords_by_municipality: dict[str, list[str]] = {}

    for i, (slug, bbox) in enumerate(bboxes.items(), start=1):
        print(f"[{i}/{len(bboxes)}] {slug}: consultando Overpass API (bbox={bbox})...")
        try:
            names = fetch_accommodation_names(bbox)
        except Exception as e:
            print(f"  [AVISO] Overpass falló para {slug}: {e} — se omite este municipio.")
            keywords_by_municipality[slug] = []
            continue

        keywords = set()
        for name in names:
            for word in slugify(name):
                keywords.add(word)

        keywords_list = sorted(keywords)
        print(f"  {len(names)} alojamientos con nombre en OSM, {len(keywords_list)} keywords generadas.")

        if cache_urls:
            print(f"  Filtrando keywords de {slug} por especificidad (umbral: {SPECIFICITY_MAX_MATCHES})...")
            keywords_list = filter_keywords_by_specificity(keywords_list, cache_urls)
            print(f"  {len(keywords_list)} keywords de {slug} sobrevivieron el filtro.")

        keywords_by_municipality[slug] = keywords_list

        if i < len(bboxes):
            time.sleep(2)  # cortesía con Overpass: no golpear la API en loop sin pausas

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(keywords_by_municipality, f, indent=2, ensure_ascii=False)

    print(f"\nGuardado en: {OUTPUT_FILE}")
    print("Usar tenerife_osm_keywords_priority.json junto con --recrawl-priority en booking_scraper.py.")


if __name__ == "__main__":
    main()
