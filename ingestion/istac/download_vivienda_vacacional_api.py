import os
import io
import pandas as pd
import requests
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ISTAC_VV")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUTPUT_DIR = os.path.join(BASE_DIR, "data", "bronce", "tabular", "raw")
os.makedirs(OUTPUT_DIR, exist_ok=True)

API_URL = "https://datos.canarias.es/api/estadisticas/statistical-resources/v1.0/datasets/ISTAC/C00065A_000061/~latest.csv"

# 31 Municipios de Tenerife (nombres exactos + variantes del ISTAC)
MUNICIPIOS_TENERIFE_NOMBRES = {
    "Adeje", "Arafo", "Arico", "Arona", "Buenavista del Norte", 
    "Candelaria", "Fasnia", "Garachico", "Granadilla de Abona", 
    "La Guancha", "Guía de Isora", "Güímar", "Icod de los Vinos", 
    "San Cristóbal de La Laguna", "La Matanza de Acentejo", "La Orotava", 
    "Puerto de la Cruz", "Puerto de La Cruz",
    "Los Realejos", "El Rosario", "San Juan de la Rambla", 
    "San Miguel de Abona", "Santa Cruz de Tenerife", "Santa Úrsula", 
    "Santiago del Teide", "El Sauzal", "Los Silos", "Tacoronte", 
    "El Tanque", "Tegueste", "La Victoria de Acentejo", "Vilaflor de Chasna",
    "La Laguna", "San Cristóbal de L"
}

METRIC_MAP = {
    'Plazas disponibles': 'plazas_vv',
    'Tasa de vivienda reservada': 'tasa_ocupacion_vv',
    'Estancia media en la vivienda vacacional': 'estancia_media_vv',
    'Ingresos totales': 'ingresos_vv',
    'Viviendas vacacionales disponibles': 'alojamientos_abiertos_vv'
}

def fetch_and_process():
    logger.info(f"Descargando datos VV desde {API_URL}")
    r = requests.get(API_URL, timeout=120)
    r.raise_for_status()
    
    df = pd.read_csv(io.StringIO(r.content.decode('utf-8')))
    logger.info(f"Datos descargados. Total filas: {len(df)}")
    
    # Filtrar Tenerife
    df_tf = df[df['TERRITORIO#es'].isin(MUNICIPIOS_TENERIFE_NOMBRES)].copy()
    logger.info(f"Filas tras filtrar municipios de Tenerife: {len(df_tf)}")

    # Filtro 'Total' en Intervalos
    if 'INTERVALOS_PLAZAS#es' in df_tf.columns:
        df_tf = df_tf[df_tf['INTERVALOS_PLAZAS#es'] == 'Total'].copy()
        logger.info(f"Filas tras filtrar INTERVALOS_PLAZAS = 'Total': {len(df_tf)}")

    # Limpiar TIME_CODE (de 2019-M01 a 2019-01)
    df_tf['TIME_CODE'] = df_tf['TIME_PERIOD_CODE'].str.replace("-M", "-", regex=False)
    
    # Procesar y guardar cada métrica
    for metric_es, indicator_name in METRIC_MAP.items():
        df_metric = df_tf[df_tf['MEDIDAS#es'] == metric_es].copy()
        
        if df_metric.empty:
            logger.warning(f"No hay datos para la métrica '{metric_es}'")
            continue
            
        # Normalizar columnas para que coincida con la capa bronce actual
        df_out = pd.DataFrame()
        # Normalizar "Puerto de La Cruz" a "Puerto de la Cruz"
        df_out['GEOGRAPHICAL'] = df_metric['TERRITORIO#es'].str.replace("Puerto de La Cruz", "Puerto de la Cruz")
        df_out['GEOGRAPHICAL_CODE'] = df_metric['TERRITORIO_CODE']
        df_out['TIME'] = df_metric['TIME_PERIOD#es']
        df_out['TIME_CODE'] = df_metric['TIME_CODE']
        df_out['MEASURE_CODE'] = 'ABSOLUTE'
        df_out['OBS_VALUE'] = df_metric['OBS_VALUE']
        df_out['_indicador'] = indicator_name
        
        out_path = os.path.join(OUTPUT_DIR, f"istac_mun_{indicator_name}.csv")
        df_out.to_csv(out_path, index=False)
        logger.info(f"Guardado {out_path} con {len(df_out)} filas.")
        
if __name__ == "__main__":
    fetch_and_process()
