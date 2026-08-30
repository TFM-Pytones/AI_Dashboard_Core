import os
import io
import json
import pandas as pd
from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv

# Carga el archivo .env desde el directorio base
load_dotenv()

# --- Configuración Azure Blob Storage ---
AZURE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
BLOB_CONTAINER_NAME = "bronce-raw"

def main():
    if not AZURE_CONNECTION_STRING:
        print("[ERROR] AZURE_STORAGE_CONNECTION_STRING no esta definido en el archivo .env")
        return
        
    print("======================================================================")
    print("MIGRACION DE JSONs ANTIGUOS A PARQUET MAESTRO (TRIPADVISOR)")
    print("======================================================================")
    
    blob_service_client = BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)
    container_client = blob_service_client.get_container_client(BLOB_CONTAINER_NAME)
    blobs = [b.name for b in container_client.list_blobs()]

    # Buscar todos los JSON de tripadvisor
    ubicaciones_jsons = [b for b in blobs if b.startswith("tripadvisor/ubicaciones_raw") and b.endswith(".json")]
    resenas_jsons = [b for b in blobs if b.startswith("tripadvisor/resenas_raw") and b.endswith(".json")]

    print(f"Encontrados {len(ubicaciones_jsons)} JSONs de ubicaciones.")
    print(f"Encontrados {len(resenas_jsons)} JSONs de reseñas.")

    # --- 1. PROCESAR UBICACIONES ---
    if ubicaciones_jsons:
        df_ubicaciones_list = []
        for blob_name in ubicaciones_jsons:
            data = container_client.get_blob_client(blob_name).download_blob().readall()
            df = pd.read_json(io.BytesIO(data))
            df_ubicaciones_list.append(df)
        
        df_ubicaciones_full = pd.concat(df_ubicaciones_list, ignore_index=True)
        # Importante: asegurar que location_id es string para deduplicar bien
        df_ubicaciones_full['location_id'] = df_ubicaciones_full['location_id'].astype(str)
        
        # Deduplicar quedándonos con la última versión de cada location_id
        df_ubicaciones_full = df_ubicaciones_full.drop_duplicates(subset=['location_id'], keep='last')
        
        # Subir Parquet
        out_buffer = io.BytesIO()
        df_ubicaciones_full.to_parquet(out_buffer, index=False)
        target_blob = "tripadvisor/tripadvisor_ubicaciones.parquet"
        container_client.get_blob_client(target_blob).upload_blob(out_buffer.getvalue(), overwrite=True)
        print(f"[OK] Generado y subido {target_blob} con {len(df_ubicaciones_full)} filas únicas.")
        print(f"     -> Los archivos JSON originales no han sido borrados.")

    # --- 2. PROCESAR RESEÑAS ---
    if resenas_jsons:
        df_resenas_list = []
        for blob_name in resenas_jsons:
            data = container_client.get_blob_client(blob_name).download_blob().readall()
            df = pd.read_json(io.BytesIO(data))
            df_resenas_list.append(df)
        
        df_resenas_full = pd.concat(df_resenas_list, ignore_index=True)
        df_resenas_full['location_id'] = df_resenas_full['location_id'].astype(str)
        
        # Algunos jsons antiguos de reseñas pueden no tener un 'review_id' extraído a primer nivel.
        # Si no existe la columna, la creamos extrayendo el ID del JSON crudo
        if 'review_id' not in df_resenas_full.columns:
            df_resenas_full['review_id'] = df_resenas_full['resena_raw'].apply(lambda x: str(x.get('id')) if isinstance(x, dict) else str(x))
        else:
            df_resenas_full['review_id'] = df_resenas_full['review_id'].astype(str)

        # Convertir resena_raw a string JSON para que Parquet no se queje de diccionarios mixtos
        df_resenas_full['resena_raw'] = df_resenas_full['resena_raw'].apply(
            lambda x: json.dumps(x) if isinstance(x, dict) else x
        )

        df_resenas_full = df_resenas_full.drop_duplicates(subset=['review_id'], keep='last')
        
        # Subir Parquet
        out_buffer = io.BytesIO()
        df_resenas_full.to_parquet(out_buffer, index=False)
        target_blob = "tripadvisor/tripadvisor_resenas.parquet"
        container_client.get_blob_client(target_blob).upload_blob(out_buffer.getvalue(), overwrite=True)
        print(f"[OK] Generado y subido {target_blob} con {len(df_resenas_full)} reseñas únicas.")
        print(f"     -> Los archivos JSON originales no han sido borrados.")

    print("\nProceso de migración completado. Ya puedes lanzar `ingest_tabular_to_postgres.py`.")

if __name__ == "__main__":
    main()
