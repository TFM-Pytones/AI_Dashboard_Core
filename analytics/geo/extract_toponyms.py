"""Georreferenciacion por gazetteer para fuentes sin ubicacion estructurada.

Booking y TripAdvisor no necesitan esto -- ya tienen lat/lon reales por
establecimiento. Este script es para LosViajeros (y opcionalmente YouTube,
aunque ahi la cobertura es baja -- ver contexto.md): busca el nombre de un
municipio de Tenerife o de una zona/hito conocido (Teide, Anaga, Masca...)
directamente en el texto, y si no lo encuentra, prueba con el titulo del
hilo/video como respaldo.

`source_id` es un hash MD5 del texto limpio, NO `id_mensaje`. Se verifico
contra la BD real que `silver.stg_losviajeros_mensajes` (tabla creada a
mano, sin PK) reutiliza `id_mensaje` para mensajes con texto distinto: 8
valores de id repetidos entre 27 y 39 veces cada uno, 288 mensajes reales
detras de esos 8 ids. Con `id_mensaje` como clave, en cuanto UN mensaje de
un grupo tenia lugar detectado, el `ON CONFLICT (source, source_id)` hacia
invisibles a los demas mensajes del mismo grupo (~250+ mensajes). El hash
del texto no tiene ese problema, y de paso colapsa los duplicados exactos ya
conocidos (moderador re-pegando el mismo texto en varios hilos) en una sola
fila -- comportamiento correcto, no un efecto secundario a evitar.

Probado contra los datos reales antes de implementarlo (ver contexto.md):
- LosViajeros: cobertura real recalculada tras el fix de id_mensaje (ver
  salida del script, cambia respecto a la primera version).
- YouTube: solo 9.7% incluso anadiendo zonas -- la mayoria de comentarios son
  reacciones genericas sin nombrar un sitio. No se ejecuta aqui por defecto.
"""

import hashlib
import os
import re
import unicodedata
from pathlib import Path

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv(override=True)

SOURCE_LOSVIAJEROS = "losviajeros_message"

QUOTE_RE = re.compile(r".*\bEscribi[oó]:\s*", re.DOTALL)

# Alias reales tal como aparecen en el texto (municipios oficiales +
# variantes sin tilde/abreviadas). Mismo criterio que NOMBRES_CORTOS del
# notebook de TripAdvisor de Guille, pero para buscar dentro del texto en
# vez de para consultar una API.
MUNICIPIOS_ALIAS = {
    "Adeje": ["adeje"], "Arafo": ["arafo"], "Arico": ["arico"],
    "Arona": ["arona", "los cristianos", "las americas"],
    "Buenavista del Norte": ["buenavista"],
    "Candelaria": ["candelaria"], "El Rosario": ["el rosario"],
    "El Sauzal": ["sauzal"], "El Tanque": ["el tanque"], "Fasnia": ["fasnia"],
    "Garachico": ["garachico"], "Granadilla de Abona": ["granadilla"],
    "Guia de Isora": ["guia de isora"], "Guimar": ["guimar"],
    "Icod de los Vinos": ["icod"], "La Guancha": ["la guancha"],
    "La Matanza de Acentejo": ["la matanza"], "La Orotava": ["orotava"],
    "La Victoria de Acentejo": ["la victoria"], "Los Realejos": ["realejos"],
    "Los Silos": ["los silos"], "Puerto de la Cruz": ["puerto de la cruz"],
    "San Cristobal de La Laguna": ["la laguna"],
    "San Juan de la Rambla": ["san juan de la rambla"],
    "San Miguel de Abona": ["san miguel"],
    "Santa Cruz de Tenerife": ["santa cruz"],
    "Santa Ursula": ["santa ursula"], "Santiago del Teide": ["santiago del teide"],
    "Tacoronte": ["tacoronte"], "Tegueste": ["tegueste"],
    "Vilaflor de Chasna": ["vilaflor"],
}
# Hitos/zonas conocidas que NO son nombre de municipio (Teide/Anaga cruzan varios).
ZONAS_ALIAS = {
    "Parque Nacional del Teide": ["teide"],
    "Macizo de Anaga": ["anaga"],
    "Masca (Buenavista del Norte)": ["masca"],
    "Barranco del Teno": ["teno"],
    "Los Gigantes (Santiago del Teide)": ["los gigantes"],
    "El Medano (Granadilla)": ["medano"],
}


def normaliza(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode("ascii")
    return texto.lower()


ALIAS_NORM = [("municipio", nombre, [normaliza(a) for a in alias]) for nombre, alias in MUNICIPIOS_ALIAS.items()]
ZONAS_NORM = [("zona", nombre, [normaliza(a) for a in alias]) for nombre, alias in ZONAS_ALIAS.items()]


def detecta_lugar(texto: str) -> tuple[str, str] | None:
    """Devuelve (place_type, place_name) del primer lugar encontrado, o None."""
    t = normaliza(texto)
    for tipo, nombre, alias in ALIAS_NORM + ZONAS_NORM:
        if any(a in t for a in alias):
            return tipo, nombre
    return None


def strip_nested_quotes(text: str) -> str:
    match = QUOTE_RE.match(text)
    return text[match.end():].strip() if match else text.strip()


def stable_id(texto_limpio: str) -> str:
    """Hash MD5 del texto ya limpio -- ver docstring del modulo (id_mensaje no es fiable)."""
    return hashlib.md5(texto_limpio.encode("utf-8")).hexdigest()


def get_db_connection():
    return psycopg2.connect(
        user=os.getenv("AZURE_DB_USER"),
        password=os.getenv("AZURE_DB_PASSWORD"),
        host=os.getenv("AZURE_DB_HOST"),
        database=os.getenv("AZURE_DB_NAME"),
        port="5432",
        sslmode="require",
    )


def ensure_schema(conn):
    schema_path = Path(__file__).resolve().parents[2] / "sql" / "gold_geo_mentions_schema.sql"
    with conn.cursor() as cur:
        cur.execute(schema_path.read_text())
    conn.commit()


def fetch_temas_geo(conn) -> dict[int, tuple[str, str] | None]:
    """titulo del hilo -> lugar detectado (respaldo si el mensaje no menciona nada)."""
    with conn.cursor() as cur:
        cur.execute("SELECT tema_id, titulo FROM bronze.losviajeros_temas;")
        return {tema_id: detecta_lugar(titulo) for tema_id, titulo in cur.fetchall()}


def fetch_mensajes(conn) -> list[tuple[int, int, str]]:
    with conn.cursor() as cur:
        cur.execute("SELECT id_mensaje, id_tema, texto_mensaje_limpio FROM silver.stg_losviajeros_mensajes;")
        return cur.fetchall()


def save_results(conn, results: list[dict]):
    if not results:
        return
    with conn.cursor() as cur:
        psycopg2.extras.execute_batch(
            cur,
            """
            INSERT INTO gold.geo_mentions (source, source_id, place_type, place_name, method)
            VALUES (%(source)s, %(source_id)s, %(place_type)s, %(place_name)s, %(method)s)
            ON CONFLICT (source, source_id) DO NOTHING
            """,
            results,
        )
    conn.commit()


def main():
    conn = get_db_connection()
    ensure_schema(conn)

    tema_geo = fetch_temas_geo(conn)
    mensajes = fetch_mensajes(conn)

    results = []
    seen_ids: set[str] = set()
    directo = heredado = sin_geo = 0
    for id_mensaje, id_tema, texto_raw in mensajes:
        texto = strip_nested_quotes(texto_raw)
        if len(texto) < 1:
            continue
        source_id = stable_id(texto)
        if source_id in seen_ids:
            continue  # mismo texto ya procesado (duplicado exacto, ver docstring)
        seen_ids.add(source_id)

        lugar = detecta_lugar(texto)
        method = "directo"
        if not lugar:
            lugar = tema_geo.get(id_tema)
            method = "heredado_hilo"
        if lugar:
            place_type, place_name = lugar
            results.append({
                "source": SOURCE_LOSVIAJEROS,
                "source_id": source_id,
                "place_type": place_type,
                "place_name": place_name,
                "method": method,
            })
            directo += 1 if method == "directo" else 0
            heredado += 1 if method == "heredado_hilo" else 0
        else:
            sin_geo += 1

    save_results(conn, results)
    conn.close()

    total_filas = len(mensajes)
    total_unicos = len(seen_ids)
    print(f"{total_filas} filas en stg_losviajeros_mensajes ({total_unicos} mensajes con texto unico -- id_mensaje no es fiable, ver docstring).")
    print(f"  Directo en el mensaje: {directo}")
    print(f"  Heredado del titulo del hilo: {heredado}")
    print(f"  Sin lugar detectado: {sin_geo}")
    print(f"  Cobertura: {len(results)}/{total_unicos} ({100*len(results)/total_unicos:.1f}%)")
    print(f"\nGuardados {len(results)} resultados en gold.geo_mentions.")


if __name__ == "__main__":
    main()
