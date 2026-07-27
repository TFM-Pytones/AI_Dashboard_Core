import os
import sys
import json
import io
from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient

current_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.abspath(os.path.join(current_dir, ".."))
load_dotenv(os.path.join(project_dir, ".env"), override=True)

conn_str = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
if not conn_str:
    print("[ERROR] Falta AZURE_STORAGE_CONNECTION_STRING")
    sys.exit(1)

conn_str = conn_str.strip('"').strip("'")
if "AccountName=" not in conn_str and "DefaultEndpointsProtocol=" not in conn_str:
    conn_str = f"DefaultEndpointsProtocol=https;AccountName=datalaketfmtenerife;AccountKey={conn_str};EndpointSuffix=core.windows.net"

print("Descargando backfill_progress.json desde Azure Blob...")
try:
    blob_service_client = BlobServiceClient.from_connection_string(conn_str)
    blob_client = blob_service_client.get_blob_client(container="bronce-raw", blob="backfill_progress.json")
    
    stream = blob_client.download_blob()
    progress = json.loads(stream.readall().decode("utf-8"))
    
    completed_keys = progress.get("completed_keys", [])
    print(f"Total claves en el JSON del Blob: {len(completed_keys)}")
    
    # Agrupar por estacion
    stations = {}
    for key in completed_keys:
        st_id = key.split("_")[0]
        stations[st_id] = stations.get(st_id, 0) + 1
        
    print("\nEstaciones reportadas en el JSON del Blob:")
    for st_id, count in sorted(stations.items(), key=lambda x: int(x[0])):
        print(f"  Estacion {st_id}: {count} claves completadas")
        
except Exception as e:
    print(f"Error: {e}")
