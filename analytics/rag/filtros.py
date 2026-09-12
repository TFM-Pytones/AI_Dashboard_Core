"""Fase 4 del RAG (ver plan_rag.md) -- Normalizacion y extraccion automatica de
filtros a partir de la pregunta en lenguaje natural.

Dos problemas distintos que se resuelven aqui:

1. NOMBRES DE LUGAR INCONSISTENTES EN LA BD. El mismo municipio aparece escrito
   de varias formas segun la fuente que lo resolvio: Booking y TripAdvisor
   pasan por gold_h3_master (sin acentos: 'Guimar', 'Guia de Isora') y
   LosViajeros por el gazetteer de gold.geo_mentions (con acentos: 'Güímar',
   'Guía de Isora'). Filtrar por igualdad exacta dejaba fuera la mayoria de los
   fragmentos de esos municipios. Aqui se resuelve un nombre escrito por el
   usuario a TODAS sus variantes reales en la tabla.

2. FILTROS IMPLICITOS EN LA PREGUNTA. "¿de que se quejaban los alemanes en
   Adeje en 2024?" lleva dentro municipio, pais y año. Detectarlos permite
   acotar antes de buscar, que es lo que sube la precision.

La deteccion es por diccionario y no por LLM: los municipios, zonas y paises
son conjuntos cerrados y conocidos, asi que una busqueda por texto normalizado
es exacta, instantanea y gratis, mientras que un LLM podria alucinar un
municipio que no existe.
"""

import re
import unicodedata
from functools import lru_cache

# Nombres distintos en la BD que designan el mismo municipio. No es cuestion de
# acentos (eso lo cubre la normalizacion) sino de nombre oficial frente a
# nombre comun, asi que hay que declararlos a mano.
ALIAS_MUNICIPIOS = {
    "la laguna": ["La Laguna", "San Cristobal de La Laguna", "San Cristóbal de La Laguna"],
    "san cristobal de la laguna": ["La Laguna", "San Cristobal de La Laguna", "San Cristóbal de La Laguna"],
    "vilaflor": ["Vilaflor", "Vilaflor de Chasna"],
    "vilaflor de chasna": ["Vilaflor", "Vilaflor de Chasna"],
}

# Gentilicios mas habituales -> valor de pais_resenante (que la BD guarda en
# español, tal y como viene de Booking).
GENTILICIOS = {
    "aleman": "Alemania", "alemanes": "Alemania", "alemana": "Alemania", "alemanas": "Alemania",
    "britanico": "Reino Unido", "britanicos": "Reino Unido", "ingles": "Reino Unido",
    "ingleses": "Reino Unido", "britanica": "Reino Unido",
    "italiano": "Italia", "italianos": "Italia", "italiana": "Italia",
    "frances": "Francia", "franceses": "Francia", "francesa": "Francia",
    "español": "España", "españoles": "España", "española": "España", "espanol": "España",
    "polaco": "Polonia", "polacos": "Polonia",
    "irlandes": "Irlanda", "irlandeses": "Irlanda",
    "holandes": "Países Bajos", "holandeses": "Países Bajos", "neerlandes": "Países Bajos",
    "belga": "Bélgica", "belgas": "Bélgica",
    "suizo": "Suiza", "suizos": "Suiza",
    "rumano": "Rumanía", "rumanos": "Rumanía",
    "ucraniano": "Ucrania", "ucranianos": "Ucrania",
    "checo": "República Checa", "checos": "República Checa",
    "hungaro": "Hungría", "hungaros": "Hungría",
}

# Como se nombran de verdad estas zonas al preguntar. En la BD estan con el
# municipio entre parentesis ("Masca (Buenavista del Norte)"), que nadie
# escribe en una pregunta.
ALIAS_ZONAS = {
    "teide": "Parque Nacional del Teide",
    "parque nacional del teide": "Parque Nacional del Teide",
    "los gigantes": "Los Gigantes (Santiago del Teide)",
    "masca": "Masca (Buenavista del Norte)",
    "anaga": "Macizo de Anaga",
    "macizo de anaga": "Macizo de Anaga",
    "teno": "Barranco del Teno",
    "el medano": "El Medano (Granadilla)",
    "medano": "El Medano (Granadilla)",
}

FUENTES = {
    "booking": "booking_review",
    "tripadvisor": "tripadvisor_review",
    "losviajeros": "losviajeros_message",
    "foro": "losviajeros_message",
    "youtube": "youtube_comment",
}

ANYO_RE = re.compile(r"\b(20[12]\d)\b")


def normalizar(texto: str) -> str:
    """Minusculas y sin tildes ni diereses, para comparar nombres escritos de
    cualquier manera."""
    sin_tildes = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in sin_tildes if not unicodedata.combining(c))


@lru_cache(maxsize=1)
def catalogo_lugares() -> tuple[dict, dict]:
    """Lee de la BD los municipios y zonas reales y los indexa por su forma
    normalizada. Cacheado: son 37 y 6 valores que no cambian en una sesion."""
    from retriever import get_db_connection

    municipios: dict[str, list[str]] = {}
    zonas: dict[str, list[str]] = {}
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT DISTINCT municipio FROM gold.nlp_chunks WHERE municipio IS NOT NULL")
            for (valor,) in cur.fetchall():
                municipios.setdefault(normalizar(valor), []).append(valor)
            cur.execute("SELECT DISTINCT zona FROM gold.nlp_chunks WHERE zona IS NOT NULL")
            for (valor,) in cur.fetchall():
                zonas.setdefault(normalizar(valor), []).append(valor)
    finally:
        conn.close()
    return municipios, zonas


def resolver_municipio(nombre: str) -> list[str]:
    """Devuelve todas las variantes reales en la BD del municipio pedido.
    Lanza ValueError si no existe, en vez de devolver vacio silenciosamente y
    dejar al usuario creyendo que no hay opiniones de ese sitio."""
    municipios, _ = catalogo_lugares()
    clave = normalizar(nombre)

    if clave in ALIAS_MUNICIPIOS:
        existentes = [v for v in ALIAS_MUNICIPIOS[clave] if normalizar(v) in municipios]
        if existentes:
            return existentes

    if clave in municipios:
        return municipios[clave]

    parciales = [v for k, vs in municipios.items() if clave in k for v in vs]
    if parciales:
        return parciales

    disponibles = sorted({v for vs in municipios.values() for v in vs})
    raise ValueError(f"Municipio no encontrado: {nombre!r}. Disponibles: {', '.join(disponibles)}")


@lru_cache(maxsize=1)
def rango_fechas_corpus() -> tuple:
    """Primera y ultima fecha con dato en el corpus. Solo Booking y TripAdvisor
    tienen fecha; LosViajeros y YouTube no."""
    from retriever import get_db_connection

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT MIN(fecha), MAX(fecha) FROM gold.nlp_chunks WHERE fecha IS NOT NULL")
            return cur.fetchone()
    finally:
        conn.close()


def resolver_zona(nombre: str) -> list[str]:
    _, zonas = catalogo_lugares()
    clave = normalizar(nombre)
    if clave in zonas:
        return zonas[clave]
    parciales = [v for k, vs in zonas.items() if clave in k for v in vs]
    if parciales:
        return parciales
    disponibles = sorted({v for vs in zonas.values() for v in vs})
    raise ValueError(f"Zona no encontrada: {nombre!r}. Disponibles: {', '.join(disponibles)}")


def extraer_filtros(pregunta: str) -> dict:
    """Detecta municipio, zona, pais, fuente y año mencionados en la pregunta.

    Solo se usa para lo que el usuario NO haya pasado explicitamente por la
    linea de comandos: un filtro escrito a mano siempre manda sobre uno
    adivinado."""
    texto = normalizar(pregunta)
    filtros: dict = {}

    municipios, zonas = catalogo_lugares()

    # Del nombre mas largo al mas corto: asi "San Miguel de Abona" no se queda
    # en un match parcial de otro municipio mas corto contenido en el.
    for clave in sorted(municipios, key=len, reverse=True):
        if re.search(rf"\b{re.escape(clave)}\b", texto):
            filtros["municipio"] = municipios[clave]
            break

    # Municipio y zona son excluyentes: ningun fragmento tiene los dos a la vez
    # (Booking/TripAdvisor traen municipio, LosViajeros una cosa o la otra), asi
    # que activar ambos filtraria a cero. Si ya hay municipio, no se busca zona
    # -- ademas evita que "Santiago del Teide" dispare tambien el Teide.
    if "municipio" not in filtros:
        for alias in sorted(ALIAS_ZONAS, key=len, reverse=True):
            if re.search(rf"\b{re.escape(alias)}\b", texto):
                real = ALIAS_ZONAS[alias]
                if normalizar(real) in zonas:
                    filtros["zona"] = zonas[normalizar(real)]
                break

    for gentilicio, pais in GENTILICIOS.items():
        if re.search(rf"\b{re.escape(normalizar(gentilicio))}\b", texto):
            filtros["pais_resenante"] = pais
            break

    for palabra, fuente in FUENTES.items():
        if re.search(rf"\b{palabra}\b", texto):
            filtros["source"] = fuente
            break

    # Un año suelto en la pregunta no siempre es un filtro de fecha ("el
    # mundial de 2022"). Se aplica solo si el rango pedido se solapa con el
    # periodo que cubre el corpus; si no, filtrar daria cero resultados y el
    # usuario creeria que no hay opiniones, cuando lo que pasa es que el corpus
    # no llega ahi.
    anyos = ANYO_RE.findall(pregunta)
    if anyos:
        desde, hasta = f"{min(anyos)}-01-01", f"{max(anyos)}-12-31"
        primera, ultima = rango_fechas_corpus()
        if primera and ultima and desde <= ultima.isoformat() and hasta >= primera.isoformat():
            filtros["fecha_desde"] = desde
            filtros["fecha_hasta"] = hasta

    return filtros
