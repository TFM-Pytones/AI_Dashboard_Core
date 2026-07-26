import os
import sys
import io
import pandas as pd
from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient

current_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.abspath(os.path.join(current_dir, ".."))
load_dotenv(os.path.join(project_dir, ".env"), override=True)

conn_str = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
if not conn_str:
    print("[ERROR] Falta AZURE_STORAGE_CONNECTION_STRING en .env.")
    sys.exit(1)

conn_str = conn_str.strip('"').strip("'")
if "AccountName=" not in conn_str and "DefaultEndpointsProtocol=" not in conn_str:
    conn_str = f"DefaultEndpointsProtocol=https;AccountName=datalaketfmtenerife;AccountKey={conn_str};EndpointSuffix=core.windows.net"

print("Descargando el archivo clima_horario_agrocabildo.parquet desde Azure Blob...")
try:
    blob_service_client = BlobServiceClient.from_connection_string(conn_str)
    blob_client = blob_service_client.get_blob_client(container="bronce-raw", blob="clima_horario_agrocabildo.parquet")
    
    # Descargar a memoria
    stream = blob_client.download_blob()
    data = io.BytesIO(stream.readall())
    df = pd.read_parquet(data)
    
    print(f"Descarga completada. Total registros en la nube: {len(df)}")
    
    # Obtener las estaciones unicas y el conteo de filas
    st_counts = df["id_estacion"].value_counts().sort_index()
    
    # Cargar metadatos del CSV local para relacionar nombres
    csv_path = os.path.join(project_dir, "data", "estaciones-meteorologicas.csv")
    if os.path.exists(csv_path):
        df_stations = pd.read_csv(csv_path)
        stations_map = dict(zip(df_stations["estacion_id"], df_stations["estacion_nombre"]))
        stations_index = {row["estacion_id"]: idx + 1 for idx, row in df_stations.iterrows()}
    else:
        stations_map = {}
        stations_index = {}
        
    print("\nEstaciones con registros reales en la nube (Azure Blob Storage):")
    print("-" * 65)
    print(f"{'Pos. Rango':<12} | {'ID Estacion':<12} | {'Nombre Estacion':<20} | {'Registros':<12}")
    print("-" * 65)
    for st_id, count in st_counts.items():
        name = stations_map.get(st_id, "Desconocida")
        pos = stations_index.get(st_id, "-")
        print(f"{pos:<12} | {st_id:<12} | {name:<20} | {count:<12}")
    print("-" * 65)
    
except Exception as e:
    print(f"[ERROR] Ocurrio un problema: {e}")
