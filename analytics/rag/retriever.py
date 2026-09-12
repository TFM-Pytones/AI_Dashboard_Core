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
import sys
from dataclasses import dataclass
from datetime import date

import psycopg2
from dotenv import load_dotenv

load_dotenv(override=True)

# El corpus es multilingue (hay polaco, griego, ruso...) y la consola de
# Windows viene en cp1252: sin esto, imprimir un fragmento revienta.
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

MODELO_EMBEDDINGS = "paraphrase-multilingual-mpnet-base-v2"  # el mismo con el que se indexo el corpus
DIMENSIONES = 768

# Subir ef_search mejora el recall del indice HNSW a cambio de algo de
# latencia. Importa sobre todo al filtrar: con un WHERE selectivo, el indice
# puede quedarse corto de candidatos antes de aplicar el filtro.
EF_SEARCH = 100

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


def build_where(filters: dict | None) -> tuple[str, list]:
    """Acepta listas de valores ademas de valores sueltos: un mismo municipio
    esta escrito de varias formas en la BD (ver analytics/rag/filtros.py), asi
    que filtrar por uno significa filtrar por todas sus variantes."""
    condiciones = ["embedding IS NOT NULL"]
    valores: list = []
    for clave, valor in (filters or {}).items():
        if valor is None:
            continue
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


CAMPOS = "chunk_id, source, source_id, text, topic_label, municipio, zona, fecha, rating"


def search_semantica(query: str, k: int = 8, filters: dict | None = None) -> list[Chunk]:
    """Solo busqueda vectorial. Se mantiene aparte de la hibrida para poder
    comparar ambas en la evaluacion de la Fase 5."""
    where, valores = build_where(filters)
    vector = embed_query(query)

    sql = f"""
        SELECT {CAMPOS}, embedding <=> %s::vector AS distancia
        FROM gold.nlp_chunks
        WHERE {where}
        ORDER BY distancia
        LIMIT %s
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(f"SET LOCAL hnsw.ef_search = {EF_SEARCH}")
            cur.execute(sql, [vector, *valores, k])
            return [Chunk(*fila) for fila in cur.fetchall()]
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

    Las condiciones de filtro se repiten en cada subconsulta en vez de usar un
    CTE comun: un CTE referenciado dos veces se materializa y Postgres dejaria
    de usar el indice HNSW.
    """
    where, valores = build_where(filters)
    vector = embed_query(query)

    sql = f"""
        WITH semantica AS (
            SELECT chunk_id, ROW_NUMBER() OVER (ORDER BY dist) AS pos
            FROM (
                SELECT chunk_id, embedding <=> %s::vector AS dist
                FROM gold.nlp_chunks
                WHERE {where}
                ORDER BY dist
                LIMIT %s
            ) s
        ),
        lexica AS (
            SELECT chunk_id, ROW_NUMBER() OVER (ORDER BY score DESC) AS pos
            FROM (
                SELECT chunk_id, ts_rank(tsv, plainto_tsquery('simple', %s)) AS score
                FROM gold.nlp_chunks
                WHERE tsv @@ plainto_tsquery('simple', %s) AND {where}
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
        vector, *valores, candidatos,      # rama semantica
        query, query, *valores, candidatos,  # rama lexica
        vector, k,                          # distancia final y limite
    ]

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(f"SET LOCAL hnsw.ef_search = {EF_SEARCH}")
            cur.execute(sql, params)
            return [Chunk(*fila) for fila in cur.fetchall()]
    finally:
        conn.close()


def search(query: str, k: int = 8, filters: dict | None = None,
           hibrida: bool = True) -> list[Chunk]:
    if hibrida:
        return search_hibrida(query, k=k, filters=filters)
    return search_semantica(query, k=k, filters=filters)


if __name__ == "__main__":
    pregunta = sys.argv[1] if len(sys.argv) > 1 else "ruido por la noche en el hotel"
    print(f"Pregunta: {pregunta!r}\n")
    for etiqueta, funcion in [("SEMANTICA", search_semantica), ("HIBRIDA", search_hibrida)]:
        print(f"--- {etiqueta} ---")
        for i, c in enumerate(funcion(pregunta, k=5), 1):
            print(f"[{i}] ({c.source}, {c.lugar}, similitud {1 - c.distancia:.0%})")
            print(f"    {c.text[:160]}")
        print()
