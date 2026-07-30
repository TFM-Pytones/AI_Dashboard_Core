import os
import sys
import logging
import pandas as pd
from dotenv import load_dotenv

current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.abspath(os.path.join(current_dir, "..", ".."))
validation_dir = os.path.abspath(os.path.join(root_dir, "validation"))

for path in [current_dir, root_dir, validation_dir]:
    if path not in sys.path:
        sys.path.append(path)

# Cargar .env
load_dotenv(os.path.abspath(os.path.join(root_dir, ".env")), override=True)

try:
    from open_meteo_ingestion import OpenMeteoBronzeIngestionPipeline
except ImportError:
    from ingestion.open_meteo.open_meteo_ingestion import OpenMeteoBronzeIngestionPipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("TestAzureOpenMeteoIngestion")


def run_test():
    print("=" * 70)
    print("PRUEBA DE INGESTA METEOROLÓGICA EN AZURE BLOB STORAGE (CAPA BRONCE/RAW)")
    print("=" * 70)

    conn_str = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    if not conn_str:
        print("⚠️ 'AZURE_STORAGE_CONNECTION_STRING' no está en .env. Se ejecutará en modo local (data/bronce).")
    else:
        print("☁️ Conectando a Azure Blob Storage (contenedor 'bronce-raw')...")

    pipeline = OpenMeteoBronzeIngestionPipeline()

    print("\n1. Ingestando datos de reanálisis ERA5-Land (Nivel 1)...")
    era5_dfs = pipeline.run_era5_ingestion(start_date="2024-01-01", end_date="2024-01-07")

    print("\n2. Verificando lecturas descargadas de Azure Blob Storage / Capa Bronce...")
    df_sample = pipeline.read_parquet_from_blob("satelite_era5land/era5land_station_2.parquet")

    if not df_sample.empty:
        print(f"   ✅ Se leyeron {len(df_sample)} registros de la estación 2 desde Capa Bronce.")
        print("\nMuestra de registros en Capa Bronce:")
        print(df_sample.head(3).to_string())
        print("\n🎉 Prueba de Capa Bronce completada con éxito!")
    else:
        print("   ❌ No se pudieron leer registros de la Capa Bronce.")


if __name__ == "__main__":
    run_test()
