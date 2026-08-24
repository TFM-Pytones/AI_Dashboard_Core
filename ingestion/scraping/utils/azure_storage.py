"""Utilidad genérica de conexión a Azure Blob Storage (capa Bronce del Data Lake).

Uso típico desde cualquier script de ingestión:

    from utils.azure_storage import upload_dataframe_as_parquet

    upload_dataframe_as_parquet(df, "booking_reviews_2026-07-24.parquet", subfolder="booking")

Requiere AZURE_STORAGE_CONNECTION_STRING en el .env de la raíz del proyecto.
Acepta tanto la cadena de conexión completa como solo la AccountKey suelta
(se auto-completa si falta el resto del formato).
"""

import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient

ACCOUNT_NAME = "datalaketfmtenerife"
DEFAULT_CONTAINER = "bronce-raw"

# Carga el .env de la raíz del proyecto, sin importar desde qué subcarpeta se importe este módulo
_env_path = Path(__file__).resolve().parents[3] / ".env"
load_dotenv(_env_path, override=True)


def _get_connection_string() -> str:
    conn_str = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    if not conn_str:
        raise RuntimeError(
            "Falta AZURE_STORAGE_CONNECTION_STRING en el .env. "
            "Pide la cadena de conexión (o al menos la AccountKey) al admin de Azure del equipo."
        )

    conn_str = conn_str.strip('"').strip("'")

    # Si solo pegaron la AccountKey suelta (sin AccountName ni DefaultEndpointsProtocol),
    # completamos la cadena automáticamente.
    if "AccountName=" not in conn_str and "DefaultEndpointsProtocol=" not in conn_str:
        conn_str = (
            f"DefaultEndpointsProtocol=https;AccountName={ACCOUNT_NAME};"
            f"AccountKey={conn_str};EndpointSuffix=core.windows.net"
        )

    return conn_str


def get_container_client(container: str = DEFAULT_CONTAINER):
    """Devuelve un cliente conectado al contenedor indicado (por defecto, bronce-raw)."""
    conn_str = _get_connection_string()
    blob_service_client = BlobServiceClient.from_connection_string(conn_str)
    container_client = blob_service_client.get_container_client(container)

    if not container_client.exists():
        container_client.create_container()
        print(f"Contenedor '{container}' no existía, se creó automáticamente.")

    return container_client


def upload_dataframe_as_parquet(
    df: pd.DataFrame,
    filename: str,
    subfolder: str | None = None,
    container: str = DEFAULT_CONTAINER,
    overwrite: bool = True,
) -> str:
    """Convierte un DataFrame a Parquet y lo sube directo a Azure Blob Storage,
    sin dejar un archivo temporal en disco.

    Args:
        df: DataFrame a subir.
        filename: nombre del archivo, ej. "booking_reviews_2026-07-24.parquet"
        subfolder: prefijo lógico dentro del contenedor, ej. "booking" -> "booking/archivo.parquet"
        container: nombre del contenedor (por defecto, bronce-raw)
        overwrite: si sobreescribe un blob existente con el mismo nombre

    Returns:
        El nombre completo del blob subido (incluyendo subfolder, si aplica).
    """
    import io

    blob_name = f"{subfolder}/{filename}" if subfolder else filename

    buffer = io.BytesIO()
    df.to_parquet(buffer, compression="snappy")
    buffer.seek(0)

    container_client = get_container_client(container)
    blob_client = container_client.get_blob_client(blob_name)
    blob_client.upload_blob(buffer, overwrite=overwrite)

    print(f"[OK] Subido: {blob_name} -> contenedor '{container}' ({len(df)} filas)")
    return blob_name


def list_files(container: str = DEFAULT_CONTAINER, prefix: str | None = None) -> list[str]:
    """Lista los archivos existentes en el contenedor (opcionalmente filtrados por prefijo)."""
    container_client = get_container_client(container)
    return [b.name for b in container_client.list_blobs(name_starts_with=prefix)]


if __name__ == "__main__":
    # Test rápido: solo lista lo que ya existe en bronce-raw, no sube nada.
    print("Archivos actuales en bronce-raw:")
    for name in list_files():
        print(f"  - {name}")