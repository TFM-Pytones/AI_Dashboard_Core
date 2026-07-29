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
LOCAL_PROGRESS_PATH = os.path.join(project_dir, "ingestion", "agrocabildo", "backfill_progress.json")

def clean_keys_list(keys):
    prefix_to_remove = tuple(f"{st_id}_" for st_id in STATION_IDS)
    return [k for k in keys if not k.startswith(prefix_to_remove)]

def main():
    print("=" * 70)
    print("RESETEANDO PROGRESO LOCAL Y REMOTO (FORMATO DICCIONARIO)")
    print("=" * 70)

    # 1. Limpiar archivo LOCAL
    if os.path.exists(LOCAL_PROGRESS_PATH):
        print("Limpiando archivo de progreso LOCAL...")
        try:
            with open(LOCAL_PROGRESS_PATH, "r", encoding="utf-8") as f:
                local_data = json.load(f)
            
            # Cuidar si viene como dict o como list
            if isinstance(local_data, dict):
                local_keys = local_data.get("completed_keys", [])
            else:
                local_keys = local_data
                
            cleaned_local = clean_keys_list(local_keys)
            
            with open(LOCAL_PROGRESS_PATH, "w", encoding="utf-8") as f:
                json.dump({"completed_keys": cleaned_local}, f, indent=2)
            print(f"  [OK] Local limpio. Quedan {len(cleaned_local)} llaves.")
        except Exception as e:
            print(f"[ERROR] No se pudo limpiar el local: {e}")
            return
    else:
        print("[INFO] No existía progreso local. Se creará al ejecutar el scraper.")

    # 2. Limpiar archivo en AZURE
    print("\nConectando a Azure Blob Storage...")
    blob_service_client = BlobServiceClient.from_connection_string(conn_str)
    container_client = blob_service_client.get_container_client("bronce-raw")
    progress_blob = container_client.get_blob_client("backfill_progress.json")

    try:
        data = progress_blob.download_blob().readall()
        remote_data = json.loads(data)
        
        if isinstance(remote_data, dict):
            remote_keys = remote_data.get("completed_keys", [])
        else:
            remote_keys = remote_data
            
        cleaned_remote = clean_keys_list(remote_keys)
        
        # Subir como diccionario
        progress_blob.upload_blob(json.dumps({"completed_keys": cleaned_remote}, indent=2), overwrite=True)
        print(f"  [OK] Azure limpio y corregido en formato dict. Quedan {len(cleaned_remote)} llaves.")
    except Exception as e:
        print(f"[ERROR] No se pudo limpiar Azure: {e}")

    print("\n[ÉXITO] Archivos corregidos. Espera a que termine la descarga actual antes de continuar.")

if __name__ == "__main__":
    main()
