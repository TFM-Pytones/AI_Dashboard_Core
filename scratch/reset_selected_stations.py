import os
import sys
import json
from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv

project_dir = r"c:\Users\ROBERTO\Proyectos_Python\TFM_TUI_Tenerife\AI_Dashboard_Core"

load_dotenv(os.path.join(project_dir, ".env"), override=True)
conn_str = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
if not conn_str:
    print("[ERROR] Falta AZURE_STORAGE_CONNECTION_STRING en el .env")
    sys.exit(1)

conn_str = conn_str.strip('"').strip("'")
if "AccountName=" not in conn_str and "DefaultEndpointsProtocol=" not in conn_str:
    conn_str = f"DefaultEndpointsProtocol=https;AccountName=datalaketfmtenerife;AccountKey={conn_str};EndpointSuffix=core.windows.net"

# Estaciones con anomalía de tamaño a resetear
STATION_IDS = [9, 12, 55]

def main():
    print("=" * 70)
    print("RESETEANDO PROGRESO DE ESTACIONES INCOMPLETAS EN AZURE")
    print("=" * 70)

    blob_service_client = BlobServiceClient.from_connection_string(conn_str)
    container_client = blob_service_client.get_container_client("bronce-raw")

    # 1. Eliminar archivos parquet antiguos de Azure
    for st_id in STATION_IDS:
        blob_name = f"clima_horario_agrocabildo/estacion_{st_id}.parquet"
        print(f"Borrando archivo antiguo en Azure: {blob_name}...")
        try:
            container_client.delete_blob(blob_name)
            print("  [OK] Borrado.")
        except Exception:
            print("  [INFO] No existía el archivo o no se pudo borrar.")

    # 2. Modificar progreso remoto
    print("\nModificando el archivo de progreso backfill_progress.json...")
    progress_blob = container_client.get_blob_client("backfill_progress.json")
    
    try:
        data = progress_blob.download_blob().readall()
        progress_keys = json.loads(data)
        print(f"Total llaves actuales en Azure: {len(progress_keys)}")
    except Exception as e:
        print(f"[ERROR] No se pudo descargar el progreso de Azure: {e}")
        return

    # Filtrar llaves
    prefix_to_remove = tuple(f"{st_id}_" for st_id in STATION_IDS)
    cleaned_keys = [k for k in progress_keys if not k.startswith(prefix_to_remove)]
    
    removed_count = len(progress_keys) - len(cleaned_keys)
    print(f"Llaves eliminadas: {removed_count}")
    print(f"Total llaves limpias a subir: {len(cleaned_keys)}")

    # Subir progreso limpio
    progress_blob.upload_blob(json.dumps(cleaned_keys), overwrite=True)
    print("\n[ÉXITO] Progreso de Azure actualizado. Listo para re-descargar.")

if __name__ == "__main__":
    main()
