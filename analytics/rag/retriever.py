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


# Filtros admitidos -> fragmento de SQL. Se construyen con marcadores %s, nunca
# interpolando el valor en la cadena.
FILTROS_SQL = {
    "municipio": "municipio = %s",
    "zona": "zona = %s",
    "source": "source = %s",
    "topic_id": "topic_id = %s",
    "pais_resenante": "pais_resenante = %s",
    "fecha_desde": "fecha >= %s",
    "fecha_hasta": "fecha <= %s",
    "rating_max": "rating <= %s",
    "rating_min": "rating >= %s",
}


def build_where(filters: dict | None) -> tuple[str, list]:
    condiciones = ["embedding IS NOT NULL"]
    valores: list = []
    for clave, valor in (filters or {}).items():
        if valor is None:
            continue
        if clave not in FILTROS_SQL:
            raise ValueError(f"Filtro no admitido: {clave}. Validos: {sorted(FILTROS_SQL)}")
        condiciones.append(FILTROS_SQL[clave])
        valores.append(valor)
    return " AND ".join(condiciones), valores


def search(query: str, k: int = 8, filters: dict | None = None) -> list[Chunk]:
    where, valores = build_where(filters)
    vector = embed_query(query)

    sql = f"""
        SELECT chunk_id, source, source_id, text, topic_label,
               municipio, zona, fecha, rating,
               embedding <=> %s::vector AS distancia
        FROM gold.nlp_chunks
        WHERE {where}
        ORDER BY embedding <=> %s::vector
        LIMIT %s
    """

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(f"SET LOCAL hnsw.ef_search = {EF_SEARCH}")
            cur.execute(sql, [vector, *valores, vector, k])
            return [Chunk(*fila) for fila in cur.fetchall()]
    finally:
        conn.close()


if __name__ == "__main__":
    pregunta = sys.argv[1] if len(sys.argv) > 1 else "ruido por la noche en el hotel"
    print(f"Pregunta: {pregunta!r}\n")
    for i, c in enumerate(search(pregunta), 1):
        print(f"[{i}] ({c.source}, {c.lugar}, dist={c.distancia:.3f})")
        print(f"    {c.text[:200]}\n")
