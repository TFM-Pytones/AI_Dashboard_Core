import os
import sys
import shutil
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
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

container_name = "bronce-raw"
temp_dir = os.path.join(current_dir, "temp_partition")
os.makedirs(temp_dir, exist_ok=True)

temp_monolith = os.path.join(temp_dir, "monolith.parquet")
temp_dataset_dir = os.path.join(temp_dir, "dataset_partitioned")
output_partition_dir = os.path.join(temp_dir, "clima_horario_agrocabildo")
os.makedirs(output_partition_dir, exist_ok=True)

def main():
    print("=" * 70)
    print("PARTICIONAMIENTO GLOBAL STREAMING (ULTRA MEMORY-SAFE) DEL CLIMA")
    print("=" * 70)

    try:
        blob_service_client = BlobServiceClient.from_connection_string(conn_str)
        blob_client = blob_service_client.get_blob_client(container=container_name, blob="clima_horario_agrocabildo.parquet")

        print("1. Descargando el archivo clima_horario_agrocabildo.parquet monolítico a disco...")
        with open(temp_monolith, "wb") as f:
            download_stream = blob_client.download_blob()
            download_stream.readinto(f)
        print("   [OK] Archivo monolítico descargado de forma segura en disco.")

        # 2. Particionar usando PyArrow write_to_dataset bloque a bloque
        print("\n2. Dividiendo en disco por bloques de forma secuencial...")
        pf = pq.ParquetFile(temp_monolith)
        
        for i in range(pf.num_row_groups):
            print(f"     -> Procesando bloque {i+1}/{pf.num_row_groups}...")
            table = pf.read_row_group(i)
            # Guardar en estructura de dataset particionada en disco de forma automatica
            pq.write_to_dataset(
                table,
                root_path=temp_dataset_dir,
                partition_cols=["id_estacion"]
            )
            del table # liberar memoria al instante

        print("   [OK] Division en disco completada.")

        # 3. Leer y deduplicar una sola estacion a la vez
        print("\n3. Consolidando y deduplicando estaciones de forma individual...")
        # Recorrer los directorios de estaciones creados en el dataset particionado
        for item in sorted(os.listdir(temp_dataset_dir)):
            if not item.startswith("id_estacion="):
                continue
                
            st_id_str = item.split("=")[-1]
            st_id = int(st_id_str)
            station_part_path = os.path.join(temp_dataset_dir, item)
            
            print(f"   -> Procesando Estacion {st_id} desde {station_part_path}...")
            
            # Cargar unicamente los datos de esta estacion en memoria
            df_station = pq.read_table(station_part_path).to_pandas()
            # Restaurar la columna de particion (que PyArrow elimina al leer del directorio)
            df_station["id_estacion"] = st_id
            
            # Deduplicar
            df_station.drop_duplicates(subset=["id_estacion", "id_sensor", "timestamp"], keep="last", inplace=True)
            
            local_st_path = os.path.join(output_partition_dir, f"estacion_{st_id}.parquet")
            df_station.to_parquet(local_st_path, index=False, compression="snappy")
            
            # Subir a Azure
            blob_name = f"clima_horario_agrocabildo/estacion_{st_id}.parquet"
            print(f"      [Subiendo] {blob_name} ({len(df_station)} registros)...")
            st_blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)
            with open(local_st_path, "rb") as f:
                st_blob_client.upload_blob(f, overwrite=True)
                
            del df_station # liberar memoria al instante
            
        print("\n   [OK] Particionamiento completado con éxito en la nube.")

        # 4. Eliminar el archivo antiguo monolítico del Blob Storage
        print("\n4. Eliminando el archivo monolítico antiguo del Blob Storage...")
        blob_client.delete_blob()
        print("   [OK] Archivo monolítico antiguo eliminado.")
        
        # 5. Limpiar archivos temporales locales
        print("\n5. Limpiando archivos temporales de disco...")
        shutil.rmtree(temp_dir, ignore_errors=True)
        print("   [OK] Limpieza completada.")
        
        print("\n[OK] Particionamiento global optimizado completado con éxito!")

    except Exception as e:
        print(f"[ERROR] Ocurrió un problema: {e}")
        shutil.rmtree(temp_dir, ignore_errors=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
