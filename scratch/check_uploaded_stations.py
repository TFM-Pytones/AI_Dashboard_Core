import os
import sys
import pandas as pd
from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv

project_dir = r"c:\Users\ROBERTO\Proyectos_Python\TFM_TUI_Tenerife\AI_Dashboard_Core"

# Cargar variables de entorno
env_path = os.path.join(project_dir, ".env")
load_dotenv(env_path, override=True)

conn_str = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
if not conn_str:
    print("[ERROR] AZURE_STORAGE_CONNECTION_STRING no encontrada en .env")
    sys.exit(1)

conn_str = conn_str.strip('"').strip("'")
if "AccountName=" not in conn_str and "DefaultEndpointsProtocol=" not in conn_str:
    conn_str = f"DefaultEndpointsProtocol=https;AccountName=datalaketfmtenerife;AccountKey={conn_str};EndpointSuffix=core.windows.net"

# 1. Cargar la lista completa de las 67 estaciones desde el CSV
csv_path = os.path.join(project_dir, "data", "estaciones-meteorologicas.csv")
if not os.path.exists(csv_path):
    print(f"[ERROR] No se encuentra el CSV de estaciones en: {csv_path}")
    sys.exit(1)

df_target = pd.read_csv(csv_path, encoding="utf-8-sig")
df_target.columns = [c.strip().lstrip('\ufeff') for c in df_target.columns]

# Mapeamos índice posicional (1-indexed) -> ID y Nombre
target_stations = []
for i, row in df_target.iterrows():
    target_stations.append({
        "indice": i + 1,
        "id_estacion": int(row["estacion_id"]),
        "nombre": row["estacion_nombre"]
    })

# 2. Conectar a Azure y listar blobs particionados
print("Conectando a Azure Blob Storage...")
blob_service_client = BlobServiceClient.from_connection_string(conn_str)
container_name = "bronce-raw"
container_client = blob_service_client.get_container_client(container_name)

print("Listando archivos en clima_horario_agrocabildo/ ...")
blobs = container_client.list_blobs(name_starts_with="clima_horario_agrocabildo/")

uploaded_ids = set()
for blob in blobs:
    name = blob.name
    # Esperamos el formato: clima_horario_agrocabildo/estacion_{id}.parquet
    if name.endswith(".parquet") and "estacion_" in name:
        try:
            parts = name.split("/")[-1].replace(".parquet", "").split("_")
            st_id = int(parts[1])
            uploaded_ids.add(st_id)
        except Exception as e:
            print(f"[ADVERTENCIA] No se pudo parsear el nombre del blob {name}: {e}")

print(f"Total estaciones encontradas en Azure: {len(uploaded_ids)}")

# 3. Cruzar listas para ver cuáles están y cuáles faltan
present = []
missing = []

for st in target_stations:
    st_id = st["id_estacion"]
    if st_id in uploaded_ids:
        present.append(st)
    else:
        missing.append(st)

print("\n" + "="*50)
print(f"ESTACIONES COMPLETADAS ({len(present)}/67):")
print("="*50)
for st in present:
    print(f"  [{st['indice']}] ID {st['id_estacion']}: {st['nombre']}")

print("\n" + "="*50)
print(f"ESTACIONES FALTANTES ({len(missing)}/67):")
print("="*50)
for st in missing:
    print(f"  [{st['indice']}] ID {st['id_estacion']}: {st['nombre']}")
