"""Fase 3 del RAG (ver plan_rag.md) -- Recuperacion de fragmentos por
significado sobre gold.nlp_chunks.

La pregunta se convierte al mismo espacio vectorial que el corpus
(paraphrase-multilingual-mpnet-base-v2, 768 dimensiones) y se buscan los
fragmentos mas cercanos con el operador <=> de pgvector (distancia coseno).

Los filtros de metadatos se aplican en el WHERE, es decir ANTES de ordenar por
cercania: preguntar "de que se quejan en Adeje" buscando sobre los ~15.000
fragmentos de Adeje da mucha mejor precision que buscar sobre los 88.000 y
descartar despues.

Uso como libreria:
    from retriever import search
    for c in search("ruido por la noche", k=8, filters={"municipio": "Adeje"}):
        print(c.municipio, c.text[:80])
"""

import os
import re
import sys
from dataclasses import dataclass
from datetime import date

import psycopg2
from dotenv import load_dotenv

from filtros import detectar_perspectiva, normalizar

load_dotenv(override=True)

# El corpus es multilingue (hay polaco, griego, ruso...) y la consola de
# Windows viene en cp1252: sin esto, imprimir un fragmento revienta.
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

MODELO_EMBEDDINGS = "paraphrase-multilingual-mpnet-base-v2"  # el mismo con el que se indexo el corpus
DIMENSIONES = 768

# Subir ef_search mejora el recall del indice HNSW a cambio de algo de
# latencia.
EF_SEARCH = 100

# Con un WHERE de metadatos, HNSW recorre sus ef_search candidatos y filtra
# DESPUES: con "Adeje" devolvia 9 de 50 fragmentos y con "Puerto de la Cruz +
# Italia", cero. El escaneo iterativo (pgvector >= 0.8) sigue recorriendo el
# indice hasta completar el LIMIT. relaxed_order y no strict_order: strict
# llegaba a 15 s con filtros selectivos y relaxed da el mismo recall en
# milisegundos. Como relaxed puede devolver las filas algo desordenadas, las
# consultas reordenan sobre un CTE MATERIALIZED (patron de la doc de pgvector).
ITERATIVE_SCAN = "relaxed_order"

# Se piden k * MARGEN_DUPLICADOS filas para que, tras quitar duplicados, sigan
# quedando k (ver quitar_duplicados).
MARGEN_DUPLICADOS = 3

# Un nombre propio que aparece en mas fragmentos que esto (el 2% del corpus) no
# distingue nada: "Puerto", "Cruz" o "Teide" traerian cientos de coincidencias
# que solo meten ruido en la fusion.
MAX_FRAGMENTOS_TERMINO = 1760

# Palabras que van en mayuscula sin ser un nombre que buscar en el texto: las
# fuentes ya son un filtro y la isla aparece en miles de fragmentos.
NO_SON_NOMBRES = {"booking", "tripadvisor", "youtube", "losviajeros", "tenerife", "canarias", "espana"}

# Maximo de fragmentos por fuente segun de que trate la pregunta (ver
# filtros.detectar_perspectiva). Booking es el 84 % del corpus y el foro casi
# todo lo demas: sin topes, en preguntas sobre el destino copaban los ocho
# huecos y YouTube o los restaurantes de TripAdvisor no entraban aunque fueran
# pertinentes. En preguntas de alojamiento no se limita nada.
TOPES_POR_PERSPECTIVA = {
    "alojamiento": {},
    "general": {"booking_review": 5, "losviajeros_message": 5},
    "destino": {"booking_review": 2, "losviajeros_message": 5},
}
# Un fragmento solo entra por variedad si su similitud no esta mas de esto por
# debajo del mejor: variar no justifica meter algo que no viene a cuento.
MARGEN_RELEVANCIA = 0.20
N_CANDIDATOS = 40

_modelo = None


def get_modelo():
    """Se carga una sola vez y de forma perezosa: son ~1 GB y no hace falta
    para nada que no sea vectorizar la pregunta."""
    global _modelo
    if _modelo is None:
        from sentence_transformers import SentenceTransformer
        _modelo = SentenceTransformer(MODELO_EMBEDDINGS)
    return _modelo


@dataclass
class Chunk:
    chunk_id: int
    source: str
    source_id: str
    text: str
    topic_label: str | None
    municipio: str | None
    zona: str | None
    fecha: date | None
    rating: float | None
    distancia: float

    @property
    def lugar(self) -> str:
        return self.municipio or self.zona or "sin ubicacion"


def get_db_connection():
    return psycopg2.connect(
        user=os.getenv("AZURE_DB_USER"),
        password=os.getenv("AZURE_DB_PASSWORD"),
        host=os.getenv("AZURE_DB_HOST"),
        database=os.getenv("AZURE_DB_NAME"),
        port="5432",
        sslmode="require",
    )


def embed_query(texto: str) -> str:
    """Devuelve el literal '[...]' que entiende pgvector. normalize_embeddings
    igual que al indexar, si no las distancias no son comparables."""
    vector = get_modelo().encode(texto, normalize_embeddings=True)
    return "[" + ",".join(f"{v:.6f}" for v in vector) + "]"


# Filtros admitidos -> (columna, operador). Siempre con marcadores %s, nunca
# interpolando el valor en la cadena.
FILTROS_SQL = {
    "municipio": ("municipio", "="),
    "zona": ("zona", "="),
    "source": ("source", "="),
    "topic_id": ("topic_id", "="),
    "pais_resenante": ("pais_resenante", "="),
    "fecha_desde": ("fecha", ">="),
    "fecha_hasta": ("fecha", "<="),
    "rating_max": ("rating", "<="),
    "rating_min": ("rating", ">="),
}


def _como_lista(valor) -> list:
    return list(valor) if isinstance(valor, (list, tuple, set)) else [valor]


def build_where(filters: dict | None) -> tuple[str, list]:
    """Acepta listas de valores ademas de valores sueltos: un mismo municipio
    esta escrito de varias formas en la BD (ver analytics/rag/filtros.py), asi
    que filtrar por uno significa filtrar por todas sus variantes.

    Municipio y zona juntos se unen con OR, no con AND: ningun fragmento tiene
    los dos (Booking y TripAdvisor traen municipio; el foro, municipio o zona),
    asi que con AND darian siempre cero. Juntos significan "este lugar, venga
    georreferenciado como venga" (ver filtros.extraer_filtros)."""
    condiciones = ["embedding IS NOT NULL"]
    valores: list = []
    pendientes = {clave: valor for clave, valor in (filters or {}).items() if valor is not None}

    if "municipio" in pendientes and "zona" in pendientes:
        condiciones.append("(municipio = ANY(%s) OR zona = ANY(%s))")
        valores += [_como_lista(pendientes.pop("municipio")), _como_lista(pendientes.pop("zona"))]

    for clave, valor in pendientes.items():
        if clave not in FILTROS_SQL:
            raise ValueError(f"Filtro no admitido: {clave}. Validos: {sorted(FILTROS_SQL)}")
        columna, operador = FILTROS_SQL[clave]
        if isinstance(valor, (list, tuple, set)):
            if operador != "=":
                raise ValueError(f"El filtro {clave} no admite varios valores.")
            condiciones.append(f"{columna} = ANY(%s)")
            valores.append(list(valor))
        else:
            condiciones.append(f"{columna} {operador} %s")
            valores.append(valor)
    return " AND ".join(condiciones), valores


def hay_fragmentos(filters: dict | None) -> bool:
    """EXISTS y no COUNT: para saber si una combinacion de filtros deja algo
    basta con encontrar un fragmento."""
    where, valores = build_where(filters)
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(f"SELECT EXISTS (SELECT 1 FROM gold.nlp_chunks WHERE {where})", valores)
            return cur.fetchone()[0]
    finally:
        conn.close()


def quitar_duplicados(chunks: list[Chunk], k: int) -> list[Chunk]:
    """El foro tiene cientos de respuestas que citan entero el mensaje original
    sin que el recorte de citas las detecte: 1.530 grupos de fragmentos que
    empiezan igual. Sin esto, un mismo mensaje llegaba a ocupar 3 de los 8
    huecos. Se comparan los primeros 200 caracteres sin tildes, signos ni
    espacios, conservando el mejor situado."""
    vistos: set[str] = set()
    unicos: list[Chunk] = []
    for chunk in chunks:
        clave = re.sub(r"[\W_]+", "", normalizar(chunk.text))[:200]
        if clave not in vistos:
            vistos.add(clave)
            unicos.append(chunk)
        if len(unicos) == k:
            break
    return unicos


def nombres_propios(query: str) -> list[str]:
    """Palabras en mayuscula de la pregunta, que es donde van los nombres que
    la busqueda vectorial difumina ("Siam Park", "H10 Conquistador").

    La primera palabra se descarta salvo que la siguiente tambien vaya en
    mayuscula: en "Merece la pena el Loro Parque" es un verbo, en "Siam Park
    merece la pena" es parte del nombre. Limitacion asumida: un nombre escrito
    en minusculas no activa la rama lexica y se queda en la semantica."""
    palabras = re.findall(r"[^\W_]+", query)
    nombres = []
    for i, palabra in enumerate(palabras):
        if not palabra[0].isupper() or normalizar(palabra) in NO_SON_NOMBRES:
            continue
        if i == 0 and not (len(palabras) > 1 and palabras[1][0].isupper()):
            continue
        nombres.append(palabra.lower())
    return nombres


def consulta_lexica(cur, query: str, filters: dict | None = None) -> str | None:
    """Construye la tsquery de la rama lexica: los nombres propios poco
    frecuentes de la pregunta unidos con OR. None si no hay ninguno.

    El lugar que ya es filtro no se busca tambien por texto: dentro de Arona,
    premiar los fragmentos que escriben "Arona" desplazaba a la mitad de los que
    hablan del ruido preguntado. Si se buscan las localidades que no forman parte
    del nombre filtrado ("Las Teresitas" dentro de Santa Cruz).

    Antes se usaba plainto_tsquery sobre la pregunta entera, que une TODAS las
    palabras con AND ("que & dicen & los & visitantes & del & siam & park"): no
    coincidia con ningun fragmento en 20 de las 22 preguntas de evaluacion, asi
    que la busqueda "hibrida" era en la practica solo vectorial.

    Tampoco sirve un OR sobre todas las palabras con contenido: terminos como
    "aparcamiento" o "ruido" traen fragmentos que los mencionan de pasada y
    desplazan a los que de verdad tratan el tema, algo que la semantica ya
    resuelve bien por si sola."""
    del_lugar = {
        palabra
        for clave in ("municipio", "zona")
        for lugar in _como_lista((filters or {}).get(clave) or [])
        for palabra in re.findall(r"[^\W_]+", normalizar(lugar))
    }
    terminos = []
    for nombre in dict.fromkeys(nombres_propios(query)):
        if normalizar(nombre) in del_lugar:
            continue
        # El diccionario 'simple' no quita tildes: "Bahía" y "Bahia" son
        # terminos distintos en el indice, se buscan los dos.
        variantes = list(dict.fromkeys([nombre, normalizar(nombre)]))
        termino = variantes[0] if len(variantes) == 1 else f"({' | '.join(variantes)})"
        cur.execute(
            "SELECT COUNT(*) FROM (SELECT 1 FROM gold.nlp_chunks "
            "WHERE tsv @@ to_tsquery('simple', %s) LIMIT %s) x",
            [termino, MAX_FRAGMENTOS_TERMINO + 1],
        )
        if 0 < cur.fetchone()[0] <= MAX_FRAGMENTOS_TERMINO:
            terminos.append(termino)
    return " | ".join(terminos) or None


CAMPOS = "chunk_id, source, source_id, text, topic_label, municipio, zona, fecha, rating"


def _configurar_hnsw(cur):
    cur.execute(f"SET LOCAL hnsw.ef_search = {EF_SEARCH}")
    cur.execute(f"SET LOCAL hnsw.iterative_scan = {ITERATIVE_SCAN}")


def _semantica(cur, query: str, k: int, filters: dict | None) -> list[Chunk]:
    where, valores = build_where(filters)
    sql = f"""
        WITH candidatos AS MATERIALIZED (
            SELECT {CAMPOS}, embedding <=> %s::vector AS distancia
            FROM gold.nlp_chunks
            WHERE {where}
            ORDER BY distancia
            LIMIT %s
        )
        SELECT * FROM candidatos ORDER BY distancia
    """
    _configurar_hnsw(cur)
    cur.execute(sql, [embed_query(query), *valores, k * MARGEN_DUPLICADOS])
    return quitar_duplicados([Chunk(*fila) for fila in cur.fetchall()], k)


def _hibrida(cur, query: str, tsquery: str, k: int, filters: dict | None,
             candidatos: int) -> list[Chunk]:
    where, valores = build_where(filters)
    vector = embed_query(query)

    sql = f"""
        WITH semantica_cruda AS MATERIALIZED (
            SELECT chunk_id, embedding <=> %s::vector AS dist
            FROM gold.nlp_chunks
            WHERE {where}
            ORDER BY dist
            LIMIT %s
        ),
        semantica AS (
            SELECT chunk_id, ROW_NUMBER() OVER (ORDER BY dist) AS pos
            FROM semantica_cruda
        ),
        lexica AS (
            SELECT chunk_id, ROW_NUMBER() OVER (ORDER BY score DESC) AS pos
            FROM (
                -- ts_rank_cd premia que los terminos aparezcan juntos ("Siam
                -- Park"). Normalizacion 1 (log de la longitud): sin normalizar
                -- ganaban los listados largos del foro; dividiendo por la
                -- longitud entera, comentarios de dos palabras.
                SELECT chunk_id, ts_rank_cd(tsv, to_tsquery('simple', %s), 1) AS score
                FROM gold.nlp_chunks
                WHERE tsv @@ to_tsquery('simple', %s) AND {where}
                ORDER BY score DESC
                LIMIT %s
            ) l
        ),
        fusion AS (
            SELECT COALESCE(s.chunk_id, x.chunk_id) AS chunk_id,
                   COALESCE(1.0 / (60 + s.pos), 0) + COALESCE(1.0 / (60 + x.pos), 0) AS rrf
            FROM semantica s
            FULL OUTER JOIN lexica x ON x.chunk_id = s.chunk_id
        )
        SELECT {', '.join('c.' + campo for campo in CAMPOS.split(', '))},
               c.embedding <=> %s::vector AS distancia
        FROM fusion f
        JOIN gold.nlp_chunks c ON c.chunk_id = f.chunk_id
        ORDER BY f.rrf DESC
        LIMIT %s
    """

    params = [
        vector, *valores, candidatos,            # rama semantica
        tsquery, tsquery, *valores, candidatos,  # rama lexica
        vector, k * MARGEN_DUPLICADOS,           # distancia final y limite
    ]
    _configurar_hnsw(cur)
    cur.execute(sql, params)
    return quitar_duplicados([Chunk(*fila) for fila in cur.fetchall()], k)


def search_semantica(query: str, k: int = 8, filters: dict | None = None) -> list[Chunk]:
    """Solo busqueda vectorial. Se mantiene aparte de la hibrida para poder
    comparar ambas en la evaluacion de la Fase 5."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            return _semantica(cur, query, k, filters)
    finally:
        conn.close()


def search_hibrida(query: str, k: int = 8, filters: dict | None = None,
                   candidatos: int = 50) -> list[Chunk]:
    """Fusiona el ranking vectorial con el de texto completo por Reciprocal
    Rank Fusion: score = 1/(60+posicion) sumado de ambas listas.

    RRF se lleva bien con escalas incomparables -- la distancia coseno y el
    ts_rank no se pueden sumar directamente -- porque solo usa la POSICION en
    cada ranking, no la puntuacion. La constante 60 es la del articulo original
    y amortigua las diferencias entre los primeros puestos.

    La rama lexica solo entra si la pregunta nombra algo concreto y poco
    frecuente (ver consulta_lexica); si no, la busqueda es la semantica.

    Las condiciones de filtro se repiten en cada subconsulta en vez de usar un
    CTE comun: un CTE referenciado dos veces se materializa y Postgres dejaria
    de usar el indice HNSW.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            tsquery = consulta_lexica(cur, query, filters)
            if tsquery is None:
                return _semantica(cur, query, k, filters)
            return _hibrida(cur, query, tsquery, k, filters, candidatos)
    finally:
        conn.close()


def diversificar(candidatos: list[Chunk], k: int, perspectiva: str) -> list[Chunk]:
    """Elige k fragmentos respetando el orden de relevancia y los topes por
    fuente de TOPES_POR_PERSPECTIVA. Si los topes dejan huecos (por ejemplo, un
    filtro de pais solo deja reseñas de Booking), se rellenan por orden."""
    topes = TOPES_POR_PERSPECTIVA.get(perspectiva, {})
    if not topes or not candidatos:
        return candidatos[:k]
    mejor = max(1 - c.distancia for c in candidatos)
    elegidos: list[int] = []
    usados: dict[str, int] = {}
    for i, c in enumerate(candidatos):
        if len(elegidos) == k:
            break
        if usados.get(c.source, 0) < topes.get(c.source, k) and (1 - c.distancia) >= mejor - MARGEN_RELEVANCIA:
            elegidos.append(i)
            usados[c.source] = usados.get(c.source, 0) + 1
    for i in range(len(candidatos)):
        if len(elegidos) == k:
            break
        if i not in elegidos:
            elegidos.append(i)
    return [candidatos[i] for i in sorted(elegidos)]


def search(query: str, k: int = 8, filters: dict | None = None,
           hibrida: bool = True, perspectiva: str = "auto") -> list[Chunk]:
    if perspectiva == "auto":
        perspectiva = detectar_perspectiva(query)
    n = max(N_CANDIDATOS, k * 5) if TOPES_POR_PERSPECTIVA.get(perspectiva) else k
    if hibrida:
        candidatos = search_hibrida(query, k=n, filters=filters)
    else:
        candidatos = search_semantica(query, k=n, filters=filters)
    return diversificar(candidatos, k, perspectiva)


if __name__ == "__main__":
    pregunta = sys.argv[1] if len(sys.argv) > 1 else "ruido por la noche en el hotel"
    print(f"Pregunta: {pregunta!r}\n")
    for etiqueta, funcion in [("SEMANTICA", search_semantica), ("HIBRIDA", search_hibrida)]:
        print(f"--- {etiqueta} ---")
        for i, c in enumerate(funcion(pregunta, k=5), 1):
            print(f"[{i}] ({c.source}, {c.lugar}, similitud {1 - c.distancia:.0%})")
            print(f"    {c.text[:160]}")
        print()
