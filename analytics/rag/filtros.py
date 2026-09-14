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
#
# Solo en plural: "los alemanes" casi siempre son personas, mientras que el
# singular suele ser un idioma o un adjetivo ("reseñas en inglés", "comida
# española"). Con el singular, esas preguntas acababan filtradas por pais y
# se respondian sobre otra cosa.
GENTILICIOS = {
    "alemanes": "Alemania", "alemanas": "Alemania",
    "británicos": "Reino Unido", "británicas": "Reino Unido", "ingleses": "Reino Unido",
    "inglesas": "Reino Unido", "escoceses": "Reino Unido",
    "italianos": "Italia", "italianas": "Italia",
    "franceses": "Francia", "francesas": "Francia",
    "españoles": "España", "españolas": "España",
    "polacos": "Polonia", "polacas": "Polonia",
    "irlandeses": "Irlanda", "irlandesas": "Irlanda",
    "holandeses": "Países Bajos", "holandesas": "Países Bajos", "neerlandeses": "Países Bajos",
    "belgas": "Bélgica",
    "suizos": "Suiza", "suizas": "Suiza",
    "austriacos": "Austria", "austriacas": "Austria",
    "rumanos": "Rumanía", "rumanas": "Rumanía",
    "ucranianos": "Ucrania", "ucranianas": "Ucrania",
    "checos": "República Checa", "checas": "República Checa",
    "húngaros": "Hungría", "húngaras": "Hungría",
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

# Localidades turisticas que no son municipio -> municipio(s) al que
# pertenecen. Nadie pregunta por "Arona" sino por "Los Cristianos", y sin esto
# esas preguntas se quedaban sin filtro de lugar. Playa de las Americas esta
# repartida entre Arona y Adeje, de ahi los dos.
LOCALIDADES = {
    "santa cruz": ["Santa Cruz de Tenerife"],
    "las teresitas": ["Santa Cruz de Tenerife"],
    "san andres": ["Santa Cruz de Tenerife"],
    "los cristianos": ["Arona"],
    "las americas": ["Arona", "Adeje"],
    "playa de las americas": ["Arona", "Adeje"],
    "costa del silencio": ["Arona"],
    "las galletas": ["Arona"],
    "callao salvaje": ["Adeje"],
    "playa paraiso": ["Adeje"],
    "golf del sur": ["San Miguel de Abona"],
    "san miguel": ["San Miguel de Abona"],
    "granadilla": ["Granadilla de Abona"],
    "los abrigos": ["Granadilla de Abona"],
    "puerto de santiago": ["Santiago del Teide"],
    "playa san juan": ["Guia de Isora"],
    "alcala": ["Guia de Isora"],
    "icod": ["Icod de los Vinos"],
    "bajamar": ["La Laguna"],
    "punta del hidalgo": ["La Laguna"],
    "radazul": ["El Rosario"],
    "tabaiba": ["El Rosario"],
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

    # Nombre que puede aparecer en la pregunta -> municipios a los que equivale.
    # Todos pasan por resolver_municipio para recoger cada variante escrita en
    # la BD: sin eso "La Laguna" dejaba fuera los fragmentos guardados como
    # "San Cristóbal de La Laguna".
    nombres = {clave: [clave] for clave in [*municipios, *ALIAS_MUNICIPIOS]}
    nombres.update(LOCALIDADES)

    # Del nombre mas largo al mas corto: asi "San Miguel de Abona" no se queda
    # en un match parcial de otro municipio mas corto contenido en el.
    for clave in sorted(nombres, key=len, reverse=True):
        if re.search(rf"\b{re.escape(clave)}\b", texto):
            filtros["municipio"] = _variantes_municipios(nombres[clave])
            break

    # Si ya hay municipio no se busca zona: evita que "Santiago del Teide"
    # dispare tambien el Teide.
    if "municipio" not in filtros:
        for alias in sorted(ALIAS_ZONAS, key=len, reverse=True):
            if re.search(rf"\b{re.escape(alias)}\b", texto):
                real = ALIAS_ZONAS[alias]
                if normalizar(real) in zonas:
                    filtros["zona"] = zonas[normalizar(real)]
                    # La zona solo existe en el foro. Si es una localidad de un
                    # municipio concreto ("Los Gigantes (Santiago del Teide)"),
                    # sus alojamientos estan en Booking y TripAdvisor bajo ese
                    # municipio: se buscan ambos (build_where los une con OR).
                    padre = re.search(r"\(([^)]+)\)$", real)
                    if padre:
                        filtros["municipio"] = resolver_municipio(padre.group(1))
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


def _variantes_municipios(nombres: list[str]) -> list[str]:
    variantes: list[str] = []
    for nombre in nombres:
        for variante in resolver_municipio(nombre):
            if variante not in variantes:
                variantes.append(variante)
    return variantes


# Orden en que se sueltan los filtros deducidos cuando, combinados, no dejan
# ningun fragmento. Cada fuente trae metadatos distintos (el pais solo esta en
# Booking, la fecha en Booking y TripAdvisor, la zona solo en el foro), asi que
# una pregunta razonable como "¿que dicen en Booking del Teide?" pedia un cruce
# que no existe y se respondia "no hay informacion", que es falso. El lugar no
# se suelta nunca: casi siempre es el nucleo de la pregunta.
ORDEN_RELAJACION = [
    ("pais_resenante",),
    ("fecha_desde", "fecha_hasta"),
    ("source",),
]


def relajar_filtros(filtros: dict, fijos=frozenset()) -> tuple[dict, dict]:
    """Quita filtros, por ORDEN_RELAJACION, hasta que algun fragmento cumpla
    los que quedan. Devuelve (filtros a aplicar, filtros descartados).

    Los `fijos` (los escritos a mano) no se sueltan nunca: si esa combinacion
    pedida explicitamente no existe, lo correcto es decirlo."""
    from retriever import hay_fragmentos

    aplicables = dict(filtros)
    descartados: dict = {}
    for grupo in ORDEN_RELAJACION:
        if not aplicables or hay_fragmentos(aplicables):
            break
        for clave in grupo:
            if clave in aplicables and clave not in fijos:
                descartados[clave] = aplicables.pop(clave)
    return aplicables, descartados


# De que trata la pregunta. Booking es el 84 % del corpus y habla del
# alojamiento: sin distinguirlo, "¿que hacer en Garachico?" recuperaba seis
# reseñas de apartamentos de ocho. Ver retriever.diversificar. Palabras ya
# normalizadas (sin tildes ni eñes).
PALABRAS_ALOJAMIENTO = {
    "hotel", "hoteles", "apartamento", "apartamentos", "alojamiento", "alojamientos", "habitacion",
    "habitaciones", "huesped", "huespedes", "anfitrion", "anfitriona", "piscina", "piscinas", "desayuno",
    "buffet", "check", "checkin", "recepcion", "cama", "camas", "colchon", "bano", "banos", "ducha", "wifi",
    "limpieza", "personal", "villa", "estancia", "booking",
}
PALABRAS_DESTINO = {
    "playa", "playas", "ciudad", "ciudades", "pueblo", "pueblos", "visitar", "visita", "visitas", "hacer",
    "ver", "comer", "restaurante", "restaurantes", "guachinche", "guachinches", "comida", "gastronomia",
    "transporte", "guagua", "guaguas", "autobus", "bus", "coche", "coches", "carretera", "carreteras",
    "trafico", "masificacion", "masificado", "masificada", "turismo", "turistas", "turistico", "precio",
    "precios", "caro", "cara", "barato", "ambiente", "excursion", "excursiones", "ruta", "rutas", "sendero",
    "senderos", "senderismo", "clima", "gente", "seguridad", "suciedad", "destino", "isla", "ocio", "compras",
    "cultura", "fiesta", "fiestas", "carnaval", "teide", "parque", "ballenas", "delfines", "residentes",
    "vivienda", "impacto", "nocturna",
}


def detectar_perspectiva(pregunta: str) -> str:
    """'alojamiento' si la pregunta solo habla del alojamiento, 'destino' si solo
    habla de la isla o de un lugar, y 'general' si mezcla ambas o ninguna."""
    tokens = set(re.findall(r"[a-z]+", normalizar(pregunta)))
    alojamiento = bool(tokens & PALABRAS_ALOJAMIENTO)
    destino = bool(tokens & PALABRAS_DESTINO)
    if alojamiento and not destino:
        return "alojamiento"
    if destino and not alojamiento:
        return "destino"
    return "general"
