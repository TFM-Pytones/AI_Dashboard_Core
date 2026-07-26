import os
import sys
import io
import json
import pandas as pd
from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient

current_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.abspath(os.path.join(current_dir, ".."))
load_dotenv(os.path.join(project_dir, ".env"), override=True)

conn_str = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
if not conn_str:
    print("[ERROR] Falta 'AZURE_STORAGE_CONNECTION_STRING' en el archivo .env.")
    sys.exit(1)

# Limpiar posibles comillas y formatear
conn_str = conn_str.strip('"').strip("'")
if "AccountName=" not in conn_str and "DefaultEndpointsProtocol=" not in conn_str:
    conn_str = f"DefaultEndpointsProtocol=https;AccountName=datalaketfmtenerife;AccountKey={conn_str};EndpointSuffix=core.windows.net"

container_name = "bronce-raw"

def read_parquet_from_blob(blob_service_client, blob_name: str) -> pd.DataFrame:
    """Lee un archivo Parquet existente del contenedor de Azure Blob."""
    try:
        blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)
        stream = blob_client.download_blob()
        data = stream.readall()
        return pd.read_parquet(io.BytesIO(data))
    except Exception:
        return pd.DataFrame()

def write_parquet_to_blob(blob_service_client, df: pd.DataFrame, blob_name: str):
    """Sube un DataFrame como Parquet al contenedor de Azure Blob."""
    blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)
    buffer = io.BytesIO()
    df.to_parquet(buffer, index=False, compression="snappy")
    buffer.seek(0)
    blob_client.upload_blob(buffer, overwrite=True)

def main():
    print("=" * 70)
    print("MIGRACION LOCAL A CAPA BRONCE PARTICIONADA (MAQUINA VIRTUAL / TRABAJO)")
    print("=" * 70)

    # 1. Buscar el archivo local
    local_candidates = [
        os.path.join(project_dir, "data", "clima_horario_agrocabildo.parquet"),
        os.path.join(project_dir, "data", "agrocabildo_hourly.parquet"),
    ]
    
    local_path = None
    for path in local_candidates:
        if os.path.exists(path):
            local_path = path
            break
            
    if not local_path:
        print("[ERROR] No se encontro ningun archivo Parquet local en:")
        for path in local_candidates:
            print(f"  - {path}")
        print("\nAsegurate de que la descarga de datos locales ha guardado archivos en la carpeta 'data/'.")
        sys.exit(1)

    print(f"1. Cargando archivo local: {local_path}")
    try:
        df_local = pd.read_parquet(local_path)
        print(f"   [OK] Leidos {len(df_local)} registros locales.")
    except Exception as e:
        print(f"[ERROR] Error al leer el archivo local: {e}")
        sys.exit(1)

    # Normalizar columnas locales si es necesario
    col_map = {
        "id_weatherstation": "id_estacion",
        "id_weatherstationsensor": "id_sensor",
        "observation_value": "valor_observado",
        "validated_value": "valor_validado",
        "is_validated": "es_validado"
    }
    df_local.rename(columns=col_map, inplace=True)

    if "timestamp" in df_local.columns:
        df_local["timestamp"] = pd.to_datetime(df_local["timestamp"])

    # 2. Conectar a Azure Blob
    print("2. Conectando a Azure Blob Storage...")
    try:
        blob_service_client = BlobServiceClient.from_connection_string(conn_str)
    except Exception as e:
        print(f"[ERROR] No se pudo conectar a Azure: {e}")
        sys.exit(1)

    # 3. Procesar por estacion
    stations = df_local["id_estacion"].unique()
    print(f"\n3. Se detectaron {len(stations)} estaciones en el archivo local: {list(stations)}")
    
    for st_id in sorted(stations):
        st_id = int(st_id)
        blob_name = f"clima_horario_agrocabildo/estacion_{st_id}.parquet"
        
        # Filtrar datos locales de esta estacion
        df_st_local = df_local[df_local["id_estacion"] == st_id].copy()
        
        print(f"   -> Procesando Estacion {st_id} ({len(df_st_local)} registros locales)...")
        
        # Descargar existente de Azure
        df_st_existing = read_parquet_from_blob(blob_service_client, blob_name)
        
        if not df_st_existing.empty:
            df_st_existing["timestamp"] = pd.to_datetime(df_st_existing["timestamp"])
            combined = pd.concat([df_st_existing, df_st_local], ignore_index=True)
            combined.drop_duplicates(subset=["id_estacion", "id_sensor", "timestamp"], keep="last", inplace=True)
        else:
            combined = df_st_local

        # Subir el consolidado
        try:
            write_parquet_to_blob(blob_service_client, combined, blob_name)
            print(f"      [OK] Subido/Actualizado {blob_name} ({len(combined)} registros totales en Azure).")
        except Exception as e:
            print(f"      [ERROR] Fallo al subir {blob_name}: {e}")

    print("\n[OK] Proceso de sincronizacion y particionamiento completado con exito!")

if __name__ == "__main__":
    main()
