"""
transform_tabular_silver.py
---------------------------
Toma los datos tabulares crudos del ISTAC (Capa Bronce), 
filtra las metricas absolutas, limpia nulos y pivota el dataset
para que cada indicador sea una columna (formato ancho).

Genera el dataset 'Silver' listo para Machine Learning.
"""

import os
import pandas as pd
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("Tabular_Silver")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT_FILE = os.path.join(BASE_DIR, "data", "bronce", "tabular", "raw", "istac_municipios_cifras_tenerife.csv")

OUTPUT_DIR = os.path.join(BASE_DIR, "data", "silver", "tabular")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "tfm_dataset_tabular_silver.csv")
os.makedirs(OUTPUT_DIR, exist_ok=True)

def process_silver_tabular():
    if not os.path.exists(INPUT_FILE):
        logger.error(f"No se encuentra el archivo Bronce: {INPUT_FILE}")
        return

    logger.info("Cargando dataset consolidado del ISTAC...")
    df = pd.read_csv(INPUT_FILE)
    
    # 1. FILTRAR SOLO VALORES ABSOLUTOS
    # Esto elimina las tasas de variacion y porcentajes que ensucian OBS_VALUE
    initial_rows = len(df)
    df = df[df["MEASURE_CODE"] == "ABSOLUTE"].copy()
    logger.info(f"Filtro ABSOLUTE aplicado: de {initial_rows} a {len(df)} filas.")
    
    # 2. LIMPIAR COLUMNAS INNECESARIAS
    # Nos quedamos solo con Municipio, Año, Indicador y Valor
    df_clean = df[["GEOGRAPHICAL", "TIME", "_indicador", "OBS_VALUE"]].copy()
    
    # Renombrar columnas para estandarizar
    df_clean.rename(columns={
        "GEOGRAPHICAL": "municipio",
        "TIME": "anio",
        "OBS_VALUE": "valor"
    }, inplace=True)
    
    # 3. PIVOTAR EL DATASET (De Formato Largo a Formato Ancho)
    # Filas: municipio + anio | Columnas: cada indicador
    logger.info("Pivotando el dataset a formato ancho...")
    df_pivot = df_clean.pivot_table(
        index=["municipio", "anio"],
        columns="_indicador",
        values="valor",
        aggfunc="first" # Ya hay un solo valor por año/municipio
    ).reset_index()
    
    # 4. LIMPIEZA DE NOMBRES Y NULOS
    df_pivot.columns.name = None # Quitar nombre del indice de columnas
    
    # El ISTAC puede reportar NaN si hay "Secreto Estadistico" o no hay datos ese año
    # Para MGWR los nulos son problematicos. Dejamos el log para ver cuantos hay.
    null_counts = df_pivot.isnull().sum()
    if null_counts.sum() > 0:
        logger.warning(f"Valores nulos detectados post-pivotado:\n{null_counts[null_counts > 0]}")
    
    # Ordenar por municipio y año
    df_pivot.sort_values(by=["municipio", "anio"], inplace=True)
    
    # 5. GUARDAR EN SILVER
    df_pivot.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")
    logger.info(f"Dataset Silver guardado exitosamente: {OUTPUT_FILE}")
    logger.info(f"Formato final: {df_pivot.shape[0]} filas x {df_pivot.shape[1]} columnas")
    logger.info(f"Muestra:\n{df_pivot.head()}")

if __name__ == "__main__":
    process_silver_tabular()
