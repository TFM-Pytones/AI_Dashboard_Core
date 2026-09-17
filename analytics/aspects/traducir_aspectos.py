"""
analytics/aspects/traducir_aspectos.py
--------------------------------------
Traducción automática y normalización de aspectos turísticos (PyABSA).
Pasa los aspectos extraídos en su idioma original en `gold.nlp_aspectos_resenas`
a español normalizado y los guarda en la tabla de mapeo `gold.aspecto_traducciones`.

Esta tabla es consumida directamente por el modelo dbt `gold_sentimiento_h3`
para determinar la queja principal y el desglose de aspectos por hexágono H3.

Características:
  - Enfoque híbrido: Intenta primero GoogleTranslator; si falla o satura cuota,
    recurre a MyMemoryTranslator con detección de idioma vía `langdetect`.
  - Incremental: Solo procesa los aspectos que aún no existen en `gold.aspecto_traducciones`.
  - Por orden de frecuencia: Prioriza los términos más repetidos en las reseñas.
  - Persistencia segura: Guarda en lotes y resiste desconexiones o interrupciones.

Uso:
    python analytics/aspects/traducir_aspectos.py
    python analytics/aspects/traducir_aspectos.py --limit 100
    python analytics/aspects/traducir_aspectos.py --dry-run
"""

import os
import sys
import time
import argparse
import logging
from typing import Optional, Tuple

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv(override=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

MARCADORES_ERROR = [
    "error 500",
    "server error",
    "that's an error",
    "please try again later",
    "that's all we know",
    "too many requests",
]

DEFAULT_EMAIL = os.getenv("MYMEMORY_EMAIL", "tfm_tenerife_analytics@gmail.com")


def get_pg_engine():
    user = os.getenv("AZURE_DB_USER")
    password = os.getenv("AZURE_DB_PASSWORD")
    host = os.getenv("AZURE_DB_HOST")
    port = os.getenv("AZURE_DB_PORT", "5432")
    db = os.getenv("AZURE_DB_NAME")

    if not all([user, password, host, db]):
        url = os.getenv("AZURE_DB_URL_R") or os.getenv("AZURE_DB_URL")
        if url:
            return create_engine(url, pool_pre_ping=True, pool_recycle=280)
        raise ValueError("Faltan variables de entorno de base de datos en .env (AZURE_DB_USER, AZURE_DB_PASSWORD, etc.)")

    connection_string = f"postgresql://{user}:{password}@{host}:{port}/{db}?sslmode=require"
    return create_engine(connection_string, pool_pre_ping=True, pool_recycle=280)


def ensure_table(engine) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS gold.aspecto_traducciones (
                    aspecto_original text PRIMARY KEY,
                    aspecto_traducido text,
                    frecuencia integer,
                    motor text
                );
                ALTER TABLE gold.aspecto_traducciones
                ADD COLUMN IF NOT EXISTS motor text;
                """
            )
        )
    logging.info("Tabla gold.aspecto_traducciones verificada y lista.")


def fetch_pending_aspects(engine, limit: Optional[int] = None) -> pd.DataFrame:
    query = """
        SELECT a.aspecto, COUNT(*) AS frecuencia
        FROM gold.nlp_aspectos_resenas a
        WHERE a.aspecto IS NOT NULL
          AND TRIM(a.aspecto) != ''
          AND NOT EXISTS (
              SELECT 1 FROM gold.aspecto_traducciones t WHERE t.aspecto_original = a.aspecto
          )
        GROUP BY a.aspecto
        ORDER BY frecuencia DESC
    """
    if limit and limit > 0:
        query += f" LIMIT {int(limit)}"

    logging.info("Consultando aspectos pendientes en gold.nlp_aspectos_resenas...")
    df = pd.read_sql(query, engine)
    logging.info(f"Aspectos distintos pendientes de traducir: {len(df)}")
    return df


def es_traduccion_valida(texto: Optional[str]) -> bool:
    if not texto:
        return False
    if len(texto) > 200:
        return False
    texto_lower = texto.lower()
    return not any(marcador in texto_lower for marcador in MARCADORES_ERROR)


def get_translators(email: str):
    try:
        from deep_translator import GoogleTranslator, MyMemoryTranslator
        from langdetect import detect, DetectorFactory

        DetectorFactory.seed = 0
        return GoogleTranslator, MyMemoryTranslator, detect
    except ImportError:
        logging.warning("deep-translator o langdetect no instalados. Instala con: pip install deep-translator langdetect")
        return None, None, None


def traducir_aspecto(
    texto: str,
    google_cls,
    mymemory_cls,
    detect_fn,
    email: str,
    max_intentos: int = 2,
) -> Tuple[Optional[str], Optional[str]]:
    texto_clean = texto.strip()
    if not texto_clean:
        return None, None

    # 1. Intento con Google Translate
    if google_cls:
        try:
            res = google_cls(source="auto", target="es").translate(texto_clean)
            if es_traduccion_valida(res):
                return res.strip().lower(), "google"
        except Exception:
            pass

    # 2. Respaldo: MyMemory Translator
    if mymemory_cls and detect_fn:
        try:
            iso = detect_fn(texto_clean).split("-")[0].lower()
        except Exception:
            iso = "en"
        
        mapa_iso = {"en": "en-GB", "es": "es-ES", "pt": "pt-PT", "fr": "fr-FR", "de": "de-DE", "it": "it-IT"}
        lang_code = mapa_iso.get(iso, "en-GB")

        espera = 2
        for intento in range(max_intentos):
            try:
                res = mymemory_cls(source=lang_code, target="es-ES", email=email).translate(texto_clean)
                if es_traduccion_valida(res):
                    return res.strip().lower(), "mymemory"
            except Exception:
                time.sleep(espera)
                espera *= 2

    # Si todo falla, fallback al texto original en minúsculas
    return texto_clean.lower(), "original_fallback"


def ejecutar_traduccion(limit: Optional[int] = None, batch_size: int = 20, dry_run: bool = False, email: str = DEFAULT_EMAIL):
    engine = get_pg_engine()
    ensure_table(engine)

    df_pendientes = fetch_pending_aspects(engine, limit=limit)
    if df_pendientes.empty:
        logging.info("No hay aspectos pendientes de traducir. Todo al día.")
        return

    GoogleTranslator, MyMemoryTranslator, detect = get_translators(email)
    if not GoogleTranslator:
        logging.error("No se pudo inicializar deep-translator. Abortando proceso.")
        return

    total = len(df_pendientes)
    logging.info(f"Iniciando traducción de {total} aspectos...")

    buffer = []
    procesados = 0
    inicio = time.time()

    for _, fila in df_pendientes.iterrows():
        original = str(fila["aspecto"])
        frecuencia = int(fila["frecuencia"])

        traducido, motor = traducir_aspecto(
            original,
            GoogleTranslator,
            MyMemoryTranslator,
            detect,
            email=email,
        )

        buffer.append({
            "aspecto_original": original,
            "aspecto_traducido": traducido,
            "frecuencia": frecuencia,
            "motor": motor,
        })
        procesados += 1
        time.sleep(0.3)

        if len(buffer) >= batch_size or procesados == total:
            if not dry_run:
                df_batch = pd.DataFrame(buffer)
                with engine.begin() as conn:
                    for _, b_row in df_batch.iterrows():
                        conn.execute(
                            text(
                                """
                                INSERT INTO gold.aspecto_traducciones (aspecto_original, aspecto_traducido, frecuencia, motor)
                                VALUES (:orig, :trad, :frec, :mot)
                                ON CONFLICT (aspecto_original) DO UPDATE
                                SET aspecto_traducido = EXCLUDED.aspecto_traducido,
                                    frecuencia = EXCLUDED.frecuencia,
                                    motor = EXCLUDED.motor
                                """
                            ),
                            {
                                "orig": b_row["aspecto_original"],
                                "trad": b_row["aspecto_traducido"],
                                "frec": b_row["frecuencia"],
                                "mot": b_row["motor"],
                            },
                        )

            buffer = []
            transcurrido = time.time() - inicio
            velocidad = procesados / transcurrido if transcurrido > 0 else 0
            restantes = total - procesados
            eta_min = (restantes / velocidad / 60) if velocidad > 0 else 0
            logging.info(f"Progreso: {procesados}/{total} ({velocidad:.1f} aspectos/s) -- ETA restante: {eta_min:.1f} min")

    logging.info(f"¡Traducción completada con éxito! Total procesado: {procesados}")


def parse_args():
    parser = argparse.ArgumentParser(description="Traducción y normalización de aspectos turísticos a español")
    parser.add_argument("--limit", type=int, default=None, help="Límite máximo de aspectos a procesar")
    parser.add_argument("--batch-size", type=int, default=20, help="Tamaño de lote para guardado en base de datos")
    parser.add_argument("--dry-run", action="store_true", help="Simulación: no escribe en PostgreSQL")
    parser.add_argument("--email", type=str, default=DEFAULT_EMAIL, help="Email para MyMemory Translator")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    ejecutar_traduccion(
        limit=args.limit,
        batch_size=args.batch_size,
        dry_run=args.dry_run,
        email=args.email,
    )
