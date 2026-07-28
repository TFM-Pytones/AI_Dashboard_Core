"""Valida la calidad de los datos más recientes subidos a bronce-raw/booking/.

Descarga los últimos Parquet de establecimientos y reseñas, y corre chequeos
básicos: campos vacíos, duplicados, fuga de datos personales, y muestra
una vista previa del contenido real.

Uso:
    python validate_booking_data.py
"""

import io
import sys

import pandas as pd

from utils.azure_storage import get_container_client, list_files


def _download_latest(prefix: str) -> pd.DataFrame | None:
    """Descarga el archivo más reciente de bronce-raw/booking/ que empiece
    con `prefix` (ej: "booking_establishments" o "booking_reviews")."""
    all_files = list_files(prefix=f"booking/{prefix}")
    if not all_files:
        print(f"[AVISO] No se encontró ningún archivo con prefijo 'booking/{prefix}'")
        return None

    latest = sorted(all_files)[-1]  # el timestamp en el nombre ordena cronológicamente
    print(f"Descargando: {latest}")

    container_client = get_container_client()
    blob_client = container_client.get_blob_client(latest)
    data = blob_client.download_blob().readall()

    return pd.read_parquet(io.BytesIO(data))


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


def validate_reviews(df: pd.DataFrame, establishment_ids: set) -> None:
    print("\n" + "=" * 60)
    print("RESEÑAS")
    print("=" * 60)
    print(f"Filas: {len(df)}")
    print(f"Columnas: {list(df.columns)}")
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
