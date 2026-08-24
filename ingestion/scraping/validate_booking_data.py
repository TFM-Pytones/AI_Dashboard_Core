"""Valida la calidad de los datos subidos a bronce-raw/booking/.

Por defecto descarga solo el último Parquet subido de establecimientos y
reseñas. Con --all agrupa y descarga TODOS los parquets de la última
corrida (cada establecimiento se guarda con su propio timestamp, no hay
un run_id explícito — ver _cluster_latest_run). Corre chequeos básicos:
campos vacíos, duplicados, fuga de datos personales, y muestra una vista
previa del contenido real.

Uso:
    python validate_booking_data.py
    python validate_booking_data.py --all
    python validate_booking_data.py --all --gap-minutes 30
"""

import argparse
import io
import re
import sys
from datetime import datetime, timedelta

import pandas as pd

from utils.azure_storage import get_container_client, list_files
from utils.logger import ensure_utf8_console

ensure_utf8_console()

_TIMESTAMP_RE = re.compile(r"_(\d{4}-\d{2}-\d{2}_\d{6})\.parquet$")


def _parse_timestamp(blob_name: str) -> datetime | None:
    match = _TIMESTAMP_RE.search(blob_name)
    if not match:
        return None
    return datetime.strptime(match.group(1), "%Y-%m-%d_%H%M%S")


def _cluster_latest_run(blob_names: list[str], gap_minutes: float) -> list[str]:
    """Agrupa los blobs más recientes que pertenecen a la misma corrida.

    No hay un run_id explícito en el nombre de archivo: cada establecimiento
    genera su propio timestamp al guardarse (save_and_upload se llama una
    vez por establecimiento, no una vez por corrida). Se infiere la corrida
    tomando, desde el archivo más reciente hacia atrás, todos los que están
    separados por menos de `gap_minutes` del siguiente — un hueco mayor a
    eso indica que se pasó a una corrida anterior.
    """
    dated = [(name, ts) for name in blob_names if (ts := _parse_timestamp(name)) is not None]
    dated.sort(key=lambda pair: pair[1], reverse=True)
    if not dated:
        return []

    gap = timedelta(minutes=gap_minutes)
    cluster = [dated[0][0]]
    for (_, prev_ts), (name, ts) in zip(dated, dated[1:]):
        if prev_ts - ts > gap:
            break
        cluster.append(name)
    return cluster


def _download_blob(name: str) -> pd.DataFrame:
    container_client = get_container_client()
    blob_client = container_client.get_blob_client(name)
    data = blob_client.download_blob().readall()
    return pd.read_parquet(io.BytesIO(data))


def _download_latest(prefix: str) -> pd.DataFrame | None:
    """Descarga el archivo más reciente de bronce-raw/booking/ que empiece
    con `prefix` (ej: "booking_establishments" o "booking_reviews")."""
    all_files = list_files(prefix=f"booking/{prefix}")
    if not all_files:
        print(f"[AVISO] No se encontró ningún archivo con prefijo 'booking/{prefix}'")
        return None

    latest = sorted(all_files)[-1]  # el timestamp en el nombre ordena cronológicamente
    print(f"Descargando: {latest}")
    return _download_blob(latest)


def _download_last_run(prefix: str, gap_minutes: float) -> pd.DataFrame | None:
    """Descarga y concatena todos los parquets de bronce-raw/booking/ que
    empiecen con `prefix` y pertenezcan a la última corrida (ver
    _cluster_latest_run)."""
    all_files = list_files(prefix=f"booking/{prefix}")
    if not all_files:
        print(f"[AVISO] No se encontró ningún archivo con prefijo 'booking/{prefix}'")
        return None

    cluster = sorted(_cluster_latest_run(all_files, gap_minutes))
    print(f"Descargando {len(cluster)} archivo(s) de la última corrida (prefijo 'booking/{prefix}'):")
    for name in cluster:
        print(f"  - {name}")

    return pd.concat([_download_blob(name) for name in cluster], ignore_index=True)


def validate_establishments(df: pd.DataFrame) -> None:
    print("\n" + "=" * 60)
    print("ESTABLECIMIENTOS")
    print("=" * 60)
    print(f"Filas: {len(df)}")
    print(f"Columnas: {list(df.columns)}")
    print("\nVista previa:")
    print(df.to_string())

    print("\n--- Chequeos ---")
    nulls = df.isnull().sum()
    for col, count in nulls.items():
        if count > 0:
            print(f"  [AVISO] {count} valor(es) nulo(s) en '{col}'")

    if df["establishment_id"].duplicated().any():
        print("  [ERROR] Hay establishment_id duplicados")
    else:
        print("  [OK] Sin establishment_id duplicados")

    if df["latitude"].isnull().any() or df["longitude"].isnull().any():
        print("  [AVISO] Falta geocodificación en al menos un establecimiento")
    else:
        print("  [OK] Todos los establecimientos tienen coordenadas")


REQUIRED_REVIEW_COLUMNS = [
    "review_id", "establishment_id", "rating", "review_text", "review_date", "reviewer_country",
]


def validate_reviews(df: pd.DataFrame, establishment_ids: set) -> None:
    print("\n" + "=" * 60)
    print("RESEÑAS")
    print("=" * 60)
    print(f"Filas: {len(df)}")
    print(f"Columnas: {list(df.columns)}")

    # Un Parquet de reseñas de una versión anterior del scraper (antes del
    # fix de save_and_upload) puede no tener columnas en absoluto cuando el
    # establecimiento no tenía reseñas — sin este chequeo, cualquier
    # df["columna"] de más abajo revienta con un KeyError sin capturar.
    missing_columns = [c for c in REQUIRED_REVIEW_COLUMNS if c not in df.columns]
    if missing_columns:
        print(f"  [ERROR] Faltan columnas esperadas: {missing_columns} — Parquet corrupto o de una versión anterior del scraper. Se omiten los chequeos de reseñas.")
        return

    if df.empty:
        print("  [AVISO] Este establecimiento no tiene reseñas (0 filas) — nada que validar.")
        return

    print("\nPrimeras 5 reseñas:")
    print(df.head(5).to_string())

    print("\n--- Chequeos ---")

    # Duplicados
    if df["review_id"].duplicated().any():
        print(f"  [ERROR] {df['review_id'].duplicated().sum()} review_id duplicados")
    else:
        print("  [OK] Sin review_id duplicados")

    # Relación con establecimientos (el join que armamos la vez pasada)
    orphan_reviews = df[~df["establishment_id"].isin(establishment_ids)]
    if len(orphan_reviews) > 0:
        print(f"  [ERROR] {len(orphan_reviews)} reseña(s) sin establecimiento correspondiente")
    else:
        print("  [OK] Todas las reseñas están correctamente vinculadas a un establecimiento")

    # Texto vacío
    empty_text = df[df["review_text"].str.strip() == ""]
    if len(empty_text) > 0:
        print(f"  [AVISO] {len(empty_text)} reseña(s) con texto vacío")
    else:
        print("  [OK] Ninguna reseña con texto vacío")

    # Rating fuera de rango esperado (Booking usa escala 1-10)
    bad_ratings = df[(df["rating"] < 1) | (df["rating"] > 10)]
    if len(bad_ratings) > 0:
        print(f"  [AVISO] {len(bad_ratings)} rating(s) fuera del rango 1-10")
    else:
        print("  [OK] Todos los ratings están en el rango esperado")

    # Chequeo de privacidad: que no se haya colado texto que parezca un nombre propio
    # en alguna columna que no debería tenerlo (chequeo simple, no exhaustivo)
    if "author" in df.columns or "username" in df.columns or "reviewer_name" in df.columns:
        print("  [ERROR CRÍTICO] Hay una columna de nombre de usuario — viola las reglas del README")
    else:
        print("  [OK] No hay columnas de nombre de usuario/autor")

    print("\nDistribución de países de reseñadores:")
    print(df["reviewer_country"].value_counts())

    print("\nEstadísticas de rating:")
    print(df["rating"].describe())


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--all",
        action="store_true",
        help="Valida todos los parquets de la última corrida, no solo el más reciente.",
    )
    parser.add_argument(
        "--gap-minutes",
        type=float,
        default=15.0,
        help="Umbral en minutos para agrupar archivos en la misma corrida (default: 15). Solo aplica con --all.",
    )
    args = parser.parse_args()

    if args.all:
        df_establishments = _download_last_run("booking_establishments", args.gap_minutes)
        df_reviews = _download_last_run("booking_reviews", args.gap_minutes)
    else:
        df_establishments = _download_latest("booking_establishments")
        df_reviews = _download_latest("booking_reviews")

    if df_establishments is None or df_reviews is None:
        print("No se pudo descargar alguno de los dos archivos. Abortando.")
        sys.exit(1)

    validate_establishments(df_establishments)
    validate_reviews(df_reviews, set(df_establishments["establishment_id"]))

    print("\n" + "=" * 60)
    print("Validación completa.")
    print("=" * 60)


if __name__ == "__main__":
    main()
