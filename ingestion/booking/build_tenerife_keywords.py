"""Genera una lista de palabras clave adicionales (nombres reales de
alojamientos en Tenerife) consultando OpenStreetMap vía Overpass API.

Estas palabras clave se combinan con TENERIFE_MUNICIPALITIES en config.py
para mejorar el recall del filtro de slugs en discover_establishment_urls().

Por qué esto SÍ funciona y el filtro geográfico directo no:
    OSM ya tiene estos alojamientos geolocalizados (dentro del polígono de
    Tenerife) — no necesitamos coordenadas de Booking para esto, las
    coordenadas ya existen en OSM. Solo extraemos sus NOMBRES para usarlos
    como texto de búsqueda contra los slugs del sitemap de Booking.

LIMITACIÓN: los slugs de Booking no siempre coinciden textualmente con el
nombre real del establecimiento (pueden estar abreviados, en otro orden,
etc.) — esto mejora el recall, pero no lo garantiza al 100%.

Uso:
    python build_tenerife_keywords.py
"""

import json
import re
import time
from pathlib import Path

import requests

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OUTPUT_FILE = Path(__file__).resolve().parent / "tenerife_osm_keywords.json"
DISCOVERY_CACHE_FILE = Path(__file__).resolve().parent / "sitemap_discovery_cache.json"

# Umbral del filtro de especificidad (ver filter_keywords_by_specificity):
# una keyword que matchea más URLs que esto en el caché de descubrimiento
# existente no es un nombre propio raro, es vocabulario genérico común en
# toda España. Los 6 municipios objetivo de priorización (Issue #12) tienen
# entre 1 y 8 establecimientos reales — parámetro fácil de ajustar, no
# hardcodeado en medio de la lógica.
SPECIFICITY_MAX_MATCHES = 20

# Bounding box aproximado de Tenerife (lat_min, lon_min, lat_max, lon_max)
# Suficientemente ajustado para no traer de otras islas canarias.
TENERIFE_BBOX = (27.95, -16.95, 28.60, -16.10)

# Query de Overpass: todos los alojamientos turísticos (hoteles, apartamentos,
# hostales, casas rurales) dentro del bounding box de Tenerife.
OVERPASS_QUERY = f"""
[out:json][timeout:60];
(
  node["tourism"~"hotel|apartment|guest_house|hostel|chalet"]({TENERIFE_BBOX[0]},{TENERIFE_BBOX[1]},{TENERIFE_BBOX[2]},{TENERIFE_BBOX[3]});
  way["tourism"~"hotel|apartment|guest_house|hostel|chalet"]({TENERIFE_BBOX[0]},{TENERIFE_BBOX[1]},{TENERIFE_BBOX[2]},{TENERIFE_BBOX[3]});
);
out center tags;
"""


def slugify(name: str) -> list[str]:
    """Convierte un nombre real (ej: 'Apartamentos Playa Dorada') en
    fragmentos tipo-slug de DOS PALABRAS CONSECUTIVAS (ej: 'playa-dorada'),
    no palabras sueltas.

    Por qué pares y no palabras sueltas: una palabra sola como "playa" o
    "vista" es vocabulario turístico común en TODA España, y generaría
    falsos positivos masivos (cualquier hotel de Alicante, Málaga, etc.
    con "playa" en su slug coincidiría). Un par específico como
    "playa-dorada" es mucho más raro y preciso.
    """
    generic_words = {
        "hotel", "hoteles", "apartamento", "apartamentos", "apartment",
        "apartments", "hostal", "hostel", "casa", "rural", "villa", "the",
        "by", "and", "de", "la", "el", "los", "las", "del", "en", "con",
    }
    text = name.lower()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    words = [w for w in text.split() if w not in generic_words and len(w) > 2]

    if len(words) >= 2:
        # Pares de palabras consecutivas (bigramas) — mucho más específicos
        return [f"{words[i]}-{words[i+1]}" for i in range(len(words) - 1)]
    elif len(words) == 1 and len(words[0]) >= 6:
        # Si solo queda una palabra, exigimos que sea larga (poco común)
        # para reducir el riesgo de que sea un término genérico
        return words
    return []


def load_discovery_cache_urls() -> list[str]:
    """Carga las URLs de sitemap_discovery_cache.json — el universo
    representativo real de URLs de Booking ya descubiertas, usado por
    filter_keywords_by_specificity() para medir qué tan específica es cada
    keyword. Devuelve [] si el caché todavía no existe (no bloquea: el
    filtro de especificidad simplemente no se puede aplicar en ese caso).
    """
    if not DISCOVERY_CACHE_FILE.exists():
        return []
    with open(DISCOVERY_CACHE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)["urls"]


def filter_keywords_by_specificity(
    keywords: list[str],
    cache_urls: list[str],
    max_matches: int = SPECIFICITY_MAX_MATCHES,
) -> list[str]:
    """Descarta keywords que no son específicas, midiendo cuántas URLs del
    caché de descubrimiento ya existente las contienen como substring.

    Por qué esto en vez de una lista de palabras prohibidas a mano: ni la
    longitud (`san-juan`, `casablanca` son largas) ni ser un bigrama
    (`vivienda-vacacional` es un bigrama pero es vocabulario de categoría,
    no un nombre propio) garantizan especificidad. Medir el conteo real de
    matches contra un universo representativo (~20.941 URLs ya conocidas)
    es una señal directa: una keyword que aparece en cientos de URLs no es
    un nombre de alojamiento raro, es un término común en toda España — y
    no hace falta mantener/actualizar una lista negra a mano cada vez que
    aparece un término genérico nuevo.

    Loguea (print) cada keyword descartada junto con su conteo real, para
    poder auditar las bajas antes de confiar en el archivo resultante.
    """
    cache_urls_lower = [u.lower() for u in cache_urls]
    kept = []
    for kw in keywords:
        count = sum(1 for u in cache_urls_lower if kw in u)
        if count > max_matches:
            print(f'    "{kw}" descartada por no específica: {count} matches (umbral: {max_matches})')
        else:
            kept.append(kw)
    return kept


def fetch_tenerife_accommodation_names() -> list[str]:
    print("Consultando Overpass API (OpenStreetMap) por alojamientos en Tenerife...")
    resp = requests.post(
        OVERPASS_URL,
        data={"data": OVERPASS_QUERY},
        headers={"User-Agent": "TFM-Tenerife-AI-Dashboard (uso academico)"},
        timeout=90,
    )
    resp.raise_for_status()
    data = resp.json()

    names = []
    for element in data.get("elements", []):
        name = element.get("tags", {}).get("name")
        if name:
            names.append(name)

    print(f"Encontrados {len(names)} alojamientos con nombre en OSM dentro de Tenerife.")
    return names


def main():
    names = fetch_tenerife_accommodation_names()

    keywords = set()
    for name in names:
        for word in slugify(name):
            keywords.add(word)

    keywords_list = sorted(keywords)
    print(f"{len(keywords_list)} palabras clave únicas generadas a partir de los nombres.")

    cache_urls = load_discovery_cache_urls()
    if cache_urls:
        print(
            f"Filtrando {len(keywords_list)} keywords por especificidad contra "
            f"{len(cache_urls)} URLs del caché de descubrimiento (umbral: {SPECIFICITY_MAX_MATCHES})..."
        )
        keywords_list = filter_keywords_by_specificity(keywords_list, cache_urls)
        print(f"{len(keywords_list)} keywords sobrevivieron el filtro de especificidad.")
    else:
        print(
            "[AVISO] No se encontró sitemap_discovery_cache.json — no se pudo aplicar el "
            "filtro de especificidad, se guardan todas las keywords generadas sin filtrar."
        )

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(
            {
                "keywords": keywords_list,
                "source_names_count": len(names),
                "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            },
            f,
            indent=2,
            ensure_ascii=False,
        )

    print(f"Guardado en: {OUTPUT_FILE}")
    print("\nAgrega esto a discover_establishment_urls() para usarlo automáticamente,")
    print("o revisa manualmente el archivo antes de confiar en él ciegamente")
    print("(algunos nombres de OSM pueden ser genéricos o poco útiles como palabra clave).")


if __name__ == "__main__":
    main()
