"""
aena_pasajeros_upload_blob.py
-----------------------
Lee los archivos Excel descargados de AENA.
Debido al formato complejo de AENA (tablas de pasajeros, 
operaciones y carga en paralelo dentro de la misma hoja),
el script busca la fila "TENERIFE" en toda la hoja para 
extraer los valores.
"""

import os
import glob
import pandas as pd
import logging
import re
from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("AENA_Ingestion")

load_dotenv()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
AENA_RAW_DIR = os.path.join(BASE_DIR, "data", "aena")
os.makedirs(AENA_RAW_DIR, exist_ok=True)

AZURE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
BLOB_CONTAINER_NAME = "bronce-raw"
BLOB_FOLDER = "aena"

def extract_aena_data(filepath):
    # Intentamos leer el archivo
    try:
        # AENA a veces usa varias hojas. Descartamos carátulas técnicas y acumulados.
        xls = pd.ExcelFile(filepath)
        sheet_to_parse = None

        # 1. Prioridad: hoja explícita de "Ranking mensual" o "Ranking anual"
        for sn in xls.sheet_names:
            sn_lower = sn.lower()
            if "ranking mensual" in sn_lower or "ranking anual" in sn_lower:
                sheet_to_parse = sn
                break

        # 2. Prioridad: hoja del mes descartando carátula técnica 'Mozart Reports' y hojas de acumulado
        if not sheet_to_parse:
            candidate_sheets = [
                sn for sn in xls.sheet_names
                if "mozart" not in sn.lower() and "acumulado" not in sn.lower()
            ]
            if candidate_sheets:
                sheet_to_parse = candidate_sheets[0]
            else:
                sheet_to_parse = xls.sheet_names[0]
        
        df = pd.read_excel(filepath, sheet_name=sheet_to_parse, header=None)
    except Exception as e:
        logger.error(f"Error leyendo {filepath}: {e}")
        return []

    # Extraer el mes y año del nombre del archivo (ej: 01.Enero_Definitivo_2019.xls o 6.-Estadisticas_Junio_2026.xlsx)
    filename = os.path.basename(filepath)
    match = re.search(r'(\d{4})', filename)
    year = match.group(1) if match else "Desconocido"
    
    meses = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
    month_name = "Desconocido"
    month_num = "00"
    for i, m in enumerate(meses):
        if m in filename.lower():
            month_name = m.capitalize()
            month_num = str(i+1).zfill(2)
            break
            
    time_code = f"{year}-{month_num}"

    records = []
    
    # Buscar todas las filas/columnas donde aparezca "TENERIFE"
    for row_idx, row in df.iterrows():
        for col_idx, cell_value in enumerate(row):
            if isinstance(cell_value, str) and "TENERIFE" in cell_value.upper():
                aeropuerto = cell_value.strip().upper()
                
                # El valor total (pasajeros/operaciones/carga) siempre suele estar en la columna de la derecha (+1 o +2)
                # Buscamos en las siguientes 3 columnas a la derecha el primer número válido
                valor = None
                for offset in range(1, 4):
                    if col_idx + offset < len(row):
                        val = row[col_idx + offset]
                        if pd.notnull(val) and isinstance(val, (int, float)):
                            valor = val
                            break
                
                # Determinar si es Pasajeros, Operaciones o Carga basándose en la posición de la columna
                # Normalmente: Col 1-3 (Pasajeros), Col 5-7 (Operaciones), Col 9-11 (Carga)
                # O comparando los valores (Pasajeros son millones, Operaciones miles, Carga kilos)
                # Para ser robustos, si la columna está en el primer tercio del dataframe, es Pasajeros, etc.
                total_cols = len(row)
                categoria = "Desconocida"
                if col_idx < total_cols * 0.4:
                    categoria = "Pasajeros"
                elif col_idx < total_cols * 0.7:
                    categoria = "Operaciones"
                else:
                    categoria = "Mercancías"
                    
                if valor is not None:
                    records.append({
                        "TIME_CODE": time_code,
                        "AEROPUERTO": aeropuerto,
                        "CATEGORIA": categoria,
                        "VALOR": valor,
                        "ARCHIVO_ORIGEN": filename
                    })
                    
    return records

def process_and_upload():
    if not AZURE_CONNECTION_STRING:
        logger.error("AZURE_STORAGE_CONNECTION_STRING no está definido.")
        return

    try:
        blob_service_client = BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)
    except Exception as e:
        logger.error(f"Error al conectar con Azure: {e}")
        return

    files = glob.glob(os.path.join(AENA_RAW_DIR, "*.xlsx")) + glob.glob(os.path.join(AENA_RAW_DIR, "*.xls"))
    
    if not files:
        logger.warning(f"No se encontraron archivos Excel de AENA en: {AENA_RAW_DIR}")
        return

    all_records = []
    logger.info(f"Se encontraron {len(files)} archivos de AENA. Procesando...")
    
    for f in files:
        records = extract_aena_data(f)
        all_records.extend(records)
        logger.info(f"  - {os.path.basename(f)}: {len(records)} registros extraídos.")

    if not all_records:
        logger.warning("Ningún archivo contenía datos válidos de Tenerife.")
        return

    df_aena = pd.DataFrame(all_records)
    
    # Pivotar la tabla para tener una fila por Mes-Aeropuerto y columnas de Pasajeros, Operaciones, Carga
    df_pivot = df_aena.pivot_table(
        index=["TIME_CODE", "AEROPUERTO"], 
        columns="CATEGORIA", 
        values="VALOR",
        aggfunc="sum"
    ).reset_index()
    
    # Limpieza final de nombres
    df_pivot.columns.name = None
    
    parquet_filename = "aena_pasajeros_tenerife.parquet"
    parquet_path = os.path.join(AENA_RAW_DIR, parquet_filename)
    
    df_pivot.to_parquet(parquet_path, index=False, compression="snappy")
    logger.info(f"Archivo consolidado guardado localmente: {parquet_path} ({len(df_pivot)} filas totales).")

    # Subir a Azure
    blob_destination_path = f"{BLOB_FOLDER}/{parquet_filename}"
    blob_client = blob_service_client.get_blob_client(container=BLOB_CONTAINER_NAME, blob=blob_destination_path)
    
    logger.info(f"Subiendo a Azure Blob Storage: '{blob_destination_path}'...")
    with open(parquet_path, "rb") as data:
        blob_client.upload_blob(data, overwrite=True)
    
    logger.info("Subida completada con éxito.")

if __name__ == "__main__":
    process_and_upload()
