import os
import sys
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

try:
    client = BlobServiceClient.from_connection_string(conn_str)
    container = client.get_container_client("bronce-raw")
    
    print("Blobs en el contenedor 'bronce-raw':")
    print("-" * 80)
    print(f"{'Nombre':<50} | {'Tamaño (MB)':<12} | {'Ultima Modificacion'}")
    print("-" * 80)
    for blob in container.list_blobs():
        size_mb = blob.size / (1024 * 1024)
        print(f"{blob.name:<50} | {size_mb:<12.3f} | {blob.last_modified}")
    print("-" * 80)
except Exception as e:
    print(f"Error: {e}")
