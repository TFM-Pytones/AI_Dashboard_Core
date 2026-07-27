import os
import sys
import logging
import pandas as pd
from dotenv import load_dotenv

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

# Buscar el archivo .env de forma inteligente en los directorios superiores
loaded = False
for i in range(4):
    env_path = os.path.abspath(os.path.join(current_dir, *[".."]*i, ".env"))
    if os.path.exists(env_path):
        load_dotenv(env_path, override=True)
        print(f"Cargado archivo .env para pruebas desde: {env_path}")
        loaded = True
        break

from agrocabildo_ingestion import AgrocabildoIngestionPipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("TestAzureIngestion")

def run_test():
    print("=" * 70)
    print("PRUEBA DE CONEXION E INGESTA EN AZURE BLOB STORAGE (CAPA BRONCE/RAW)")
    print("=" * 70)

    conn_str = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    if not conn_str:
        print("[ERROR] Falta 'AZURE_STORAGE_CONNECTION_STRING' en el archivo .env.")
        return

    print("Conectando a Azure Blob Storage (contenedor 'bronce-raw')...")
    pipeline = AgrocabildoIngestionPipeline()
    
    # 1. Ejecutar Ingesta de Muestra (2 Estaciones)
    print("\n1. Ejecutando ingesta de lecturas horarias en tiempo real (Muestra de 2 estaciones)...")
    df_result = pipeline.run_realtime_ingestion(days_back=2, max_stations=2)

    # 2. Descargar y verificar los archivos consolidados del Azure Blob
    print("\n2. Verificando archivos Parquet resultantes en Azure Blob Storage:")
    
    # Estaciones
    df_stations = pipeline.read_parquet_from_blob("estaciones_agrocabildo.parquet")
    if not df_stations.empty:
        print(f"   - Estaciones registradas en Azure Blob: {len(df_stations)}")
    else:
        print("   ❌ No se pudieron leer las estaciones del Blob.")

    # Lecturas particionadas
    if df_result is not None and not df_result.empty:
        stations_ingested = df_result["id_weatherstation"].unique()
        print(f"   - Estaciones ingestadas en esta prueba: {list(stations_ingested)}")
        
        for st_id in stations_ingested:
            st_id = int(st_id)
            blob_name = f"clima_horario_agrocabildo/estacion_{st_id}.parquet"
            print(f"   -> Verificando en el Blob: {blob_name}...")
            df_st_readings = pipeline.read_parquet_from_blob(blob_name)
            
            if not df_st_readings.empty:
                print(f"      [OK] Leídas {len(df_st_readings)} lecturas en Azure para estación {st_id}.")
                print("      Muestra de las últimas 3 lecturas:")
                print(df_st_readings.sort_values(by="timestamp", ascending=False).head(3).to_string(index=False))
            else:
                print(f"      ❌ No se pudo encontrar o leer {blob_name} en Azure Blob.")
                
        print("\nPrueba de Azure Blob Storage completada con éxito!")
    else:
        print("   ❌ No se generaron lecturas en la ingesta en tiempo real.")

if __name__ == "__main__":
    run_test()
