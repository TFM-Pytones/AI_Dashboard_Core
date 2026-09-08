"""
gtfs_gtfs_upload_blob.py
-------------------------
Descarga ficheros GTFS (TITSA y Metropolitano de Tenerife) desde el portal de datos
abiertos del Cabildo (CKAN).
Convierte la topología (paradas, rutas) a formato espacial (GeoParquet) y los
horarios/viajes a formato tabular (Parquet), y los sube directamente a Azure Blob Storage.
(Combina la lógica de los antiguos Notebooks 7 y 8 adaptada a la Arquitectura Medallón).

NOTA: Se leen los archivos DIRECTAMENTE del ZIP con Pandas para evitar filtrados
implícitos de librerías como partridge (que filtra por "día más ocupado" y puede
devolver DataFrames vacíos si el feed cambia de fechas).
"""

import os
import io
import zipfile
import requests
import tempfile
import html
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point, LineString
from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("GTFS_Upload")

load_dotenv()
AZURE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
BLOB_CONTAINER_NAME = "bronce-raw"
CKAN_API = 'https://datos.tenerife.es/ckan/api/action/package_show'

FUENTES_GTFS = {
    'titsa': {
        'package_id': '36c2e26f-0d18-4b5a-b214-1636168e0765',
        'operador': 'TITSA',
        'modo': 'guagua',
    },
    'metropolitano': {
        'package_id': '4b83e018-37d9-40a6-b6d1-1df2b91c8117',
        'operador': 'Metropolitano de Tenerife',
        'modo': 'tranvia',
    },
}


def obtener_recurso_gtfs(package_id):
    resp = requests.get(CKAN_API, params={'id': package_id}, timeout=30)
    resp.raise_for_status()
    recurso = resp.json()['result']['resources'][0]
    return {
        'url': recurso['url'],
        'last_modified': recurso['last_modified']
    }


def descargar_gtfs(url, temp_path):
    logger.info(f"Descargando GTFS desde {url} ...")
    resp = requests.get(url, timeout=120)
    resp.raise_for_status()
    with open(temp_path, 'wb') as f:
        f.write(resp.content)
    logger.info(f"Descargado a {temp_path}")


import gc

def leer_tabla_zip(zf_path, nombre_fichero, usecols=None):
    """Lee un fichero CSV del interior de un ZIP y fuerza los IDs a string para evitar errores"""
    with zipfile.ZipFile(zf_path) as zf:
        if nombre_fichero in zf.namelist():
            try:
                # Especificar dtype=str solo para los IDs ahorra muchísima RAM
                gtfs_ids = ['stop_id', 'route_id', 'trip_id', 'service_id', 'shape_id']
                
                # Si es muy grande (ej. stop_times), procesar en chunks
                if nombre_fichero == 'stop_times.txt':
                    chunks = []
                    for chunk in pd.read_csv(zf.open(nombre_fichero), dtype={col: str for col in gtfs_ids}, low_memory=True, chunksize=100000, usecols=usecols):
                        chunks.append(chunk)
                    df = pd.concat(chunks, ignore_index=True)
                    del chunks
                    gc.collect()
                else:
                    df = pd.read_csv(zf.open(nombre_fichero), dtype={col: str for col in gtfs_ids}, low_memory=False, usecols=usecols)
                    
                logger.info(f"  Leído {nombre_fichero}: {len(df)} filas")
                return df
            except Exception as e:
                logger.error(f"  Error leyendo {nombre_fichero}: {e}")
                return pd.DataFrame()
        else:
            logger.warning(f"  {nombre_fichero} no encontrado en el ZIP")
    return pd.DataFrame()


# ----- 1. LÓGICA ESPACIAL (basada en Notebook 7) -----

def construir_paradas(zf_path, operador, modo):
    stops = leer_tabla_zip(zf_path, 'stops.txt')
    if stops.empty:
        return None
    stops = stops.dropna(subset=['stop_lat', 'stop_lon'])
    geometry = [Point(xy) for xy in zip(stops['stop_lon'], stops['stop_lat'])]
    gdf = gpd.GeoDataFrame(stops, geometry=geometry, crs='EPSG:4326')
    gdf['operador'] = operador
    gdf['modo'] = modo
    columnas = ['stop_id', 'stop_name', 'operador', 'modo', 'geometry']
    return gdf[[c for c in columnas if c in gdf.columns]]


def construir_rutas(zf_path, operador, modo):
    shapes = leer_tabla_zip(zf_path, 'shapes.txt')
    if shapes.empty:
        return None
    trips = leer_tabla_zip(zf_path, 'trips.txt')
    routes = leer_tabla_zip(zf_path, 'routes.txt')

    # Forzar shape_id a string ANTES de cualquier operación para evitar tipos mixtos
    shapes['shape_id'] = shapes['shape_id'].astype(str)
    if 'shape_id' in trips.columns:
        trips['shape_id'] = trips['shape_id'].astype(str)

    # Cruzar trips -> routes para obtener el nombre de la línea de cada shape
    if not trips.empty and not routes.empty and 'shape_id' in trips.columns:
        trips_unicos = trips.drop_duplicates(subset='shape_id')[['shape_id', 'route_id']]
        info_rutas = trips_unicos.merge(routes, on='route_id', how='left')
        # Forzar a str las columnas que pueden tener tipos mixtos entre operadores
        for col in ['route_id', 'route_short_name', 'route_long_name', 'route_type', 'route_color']:
            if col in info_rutas.columns:
                info_rutas[col] = info_rutas[col].astype(str)
    else:
        info_rutas = pd.DataFrame()

    shapes_sorted = shapes.sort_values(['shape_id', 'shape_pt_sequence'])
    lineas = []
    for shape_id, grupo in shapes_sorted.groupby('shape_id'):
        linea = LineString(zip(grupo['shape_pt_lon'], grupo['shape_pt_lat']))
        lineas.append({'shape_id': shape_id, 'geometry': linea})

    gdf = gpd.GeoDataFrame(lineas, crs='EPSG:4326')
    if not info_rutas.empty:
        gdf = gdf.merge(info_rutas, on='shape_id', how='left')
    gdf['operador'] = operador
    gdf['modo'] = modo
    columnas = ['shape_id', 'route_short_name', 'route_long_name', 'operador', 'modo', 'geometry']
    return gdf[[c for c in columnas if c in gdf.columns]]


# ----- 2. LÓGICA TABULAR (basada en Notebook 8, sin partridge) -----

# Columnas que actúan como IDs o nombres y pueden tener tipos mixtos entre operadores
# (ej. TITSA usa IDs string "IT...", Metropolitano usa enteros; route_short_name puede
# ser inferido como int64 por TITSA y str por Metropolitano).
_COLS_ID = ['trip_id', 'route_id', 'service_id', 'shape_id', 'stop_id',
            'route_short_name', 'route_long_name', 'route_type', 'route_color']

def _castear_ids(df: pd.DataFrame) -> pd.DataFrame:
    """Fuerza a str las columnas ID que existan en el DataFrame para evitar
    errores de tipo mixto al concatenar operadores y serializar a Parquet."""
    for col in _COLS_ID:
        if col in df.columns:
            df[col] = df[col].astype(str)
    return df


def _a_segundos(valor):
    """Convierte HH:MM:SS (que puede superar 24h en GTFS) a segundos enteros."""
    if pd.isna(valor):
        return None
    if isinstance(valor, str):
        partes = valor.strip().split(':')
        h, m, s = int(partes[0]), int(partes[1]), int(partes[2])
        return h * 3600 + m * 60 + s
    return int(valor)


def procesar_tablas_zip(zf_path, operador):
    """
    Lee directamente del ZIP todas las tablas relacionales del GTFS.
    No usa partridge para evitar filtrados implícitos por fecha.
    """
    resultado = {}

    # RUTAS ATRIBUTOS (routes.txt)
    routes = leer_tabla_zip(zf_path, 'routes.txt')
    if not routes.empty:
        routes = _castear_ids(routes)
        routes['operador'] = operador
        if 'route_long_name' in routes.columns:
            routes['route_long_name'] = routes['route_long_name'].apply(
                lambda x: html.unescape(x).strip() if isinstance(x, str) else x
            )
        cols = ['route_id', 'route_short_name', 'route_long_name', 'route_type', 'operador', 'route_color']
        resultado['gtfs_rutas_atributos'] = routes[[c for c in cols if c in routes.columns]]

    # VIAJES (trips.txt)
    trips = leer_tabla_zip(zf_path, 'trips.txt')
    if not trips.empty:
        trips = _castear_ids(trips)
        trips['operador'] = operador
        cols = ['trip_id', 'route_id', 'service_id', 'operador', 'trip_headsign', 'direction_id', 'shape_id']
        resultado['gtfs_viajes'] = trips[[c for c in cols if c in trips.columns]]

    # CALENDARIO (calendar.txt)
    cal = leer_tabla_zip(zf_path, 'calendar.txt')
    if not cal.empty:
        cal = _castear_ids(cal)
        cal = cal.rename(columns={
            'monday': 'lunes', 'tuesday': 'martes', 'wednesday': 'miercoles',
            'thursday': 'jueves', 'friday': 'viernes', 'saturday': 'sabado', 'sunday': 'domingo',
            'start_date': 'fecha_inicio', 'end_date': 'fecha_fin'
        })
        cal['operador'] = operador
        if 'fecha_inicio' in cal.columns:
            cal['fecha_inicio'] = pd.to_datetime(cal['fecha_inicio'], format='%Y%m%d', errors='coerce').astype(str)
        if 'fecha_fin' in cal.columns:
            cal['fecha_fin'] = pd.to_datetime(cal['fecha_fin'], format='%Y%m%d', errors='coerce').astype(str)
        cols = ['service_id', 'operador', 'lunes', 'martes', 'miercoles', 'jueves',
                'viernes', 'sabado', 'domingo', 'fecha_inicio', 'fecha_fin']
        resultado['gtfs_calendario'] = cal[[c for c in cols if c in cal.columns]]

    # EXCEPCIONES CALENDARIO (calendar_dates.txt)
    exc = leer_tabla_zip(zf_path, 'calendar_dates.txt')
    if not exc.empty:
        exc = _castear_ids(exc)
        exc = exc.rename(columns={'date': 'fecha', 'exception_type': 'tipo'})
        exc['fecha'] = pd.to_datetime(exc['fecha'], format='%Y%m%d', errors='coerce').astype(str)
        exc['operador'] = operador
        resultado['gtfs_calendario_excepciones'] = exc[['service_id', 'operador', 'fecha', 'tipo']]

    # HORARIOS (stop_times.txt) — puede ser muy grande
    st = leer_tabla_zip(zf_path, 'stop_times.txt', usecols=['trip_id', 'stop_id', 'stop_sequence', 'arrival_time', 'departure_time'])
    if not st.empty:
        st = _castear_ids(st)
        st['operador'] = operador
        st['arrival_seconds'] = st['arrival_time'].apply(_a_segundos)
        st['departure_seconds'] = st['departure_time'].apply(_a_segundos)
        cols = ['trip_id', 'stop_id', 'stop_sequence', 'operador', 'arrival_seconds', 'departure_seconds']
        resultado['gtfs_horarios'] = st[[c for c in cols if c in st.columns]]
        del st
        gc.collect()

    return resultado


def main():
    if not AZURE_CONNECTION_STRING:
        logger.error("AZURE_STORAGE_CONNECTION_STRING no está definido.")
        return

    blob_service_client = BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)

    # Acumuladores de DataFrames para juntar ambos operadores
    df_acumulados = {
        'gtfs_paradas': [],
        'gtfs_rutas': [],
        'gtfs_rutas_atributos': [],
        'gtfs_viajes': [],
        'gtfs_calendario': [],
        'gtfs_calendario_excepciones': [],
        'gtfs_horarios': []
    }

    with tempfile.TemporaryDirectory() as tmpdirname:
        for clave, info in FUENTES_GTFS.items():
            logger.info(f"=== Procesando {info['operador']} ===")
            try:
                recurso = obtener_recurso_gtfs(info['package_id'])
                zip_path = os.path.join(tmpdirname, f"{clave}.zip")
                descargar_gtfs(recurso['url'], zip_path)

                # 1. Procesamiento Espacial (geometrías)
                paradas_gdf = construir_paradas(zip_path, info['operador'], info['modo'])
                if paradas_gdf is not None:
                    logger.info(f"  -> {len(paradas_gdf)} paradas construidas")
                    df_acumulados['gtfs_paradas'].append(paradas_gdf)

                rutas_gdf = construir_rutas(zip_path, info['operador'], info['modo'])
                if rutas_gdf is not None:
                    logger.info(f"  -> {len(rutas_gdf)} trazados de ruta construidos")
                    df_acumulados['gtfs_rutas'].append(rutas_gdf)

                # 2. Procesamiento Tabular (directo desde ZIP, sin partridge)
                tablas = procesar_tablas_zip(zip_path, info['operador'])
                for nombre_tabla, df_tab in tablas.items():
                    if not df_tab.empty:
                        logger.info(f"  -> {nombre_tabla}: {len(df_tab)} filas")
                        df_acumulados[nombre_tabla].append(df_tab)

            except Exception as e:
                logger.error(f"Error procesando {info['operador']}: {e}", exc_info=True)

    # Unir DataFrames y subir a Blob Storage
    logger.info("=== Consolidando y subiendo a Blob Storage ===")
    for nombre_tabla, dfs in df_acumulados.items():
        if not dfs:
            logger.warning(f"Sin datos para {nombre_tabla}, se omite.")
            continue

        logger.info(f"Preparando {nombre_tabla}...")

        # Si es geoespacial se usa GeoPandas
        if nombre_tabla in ['gtfs_paradas', 'gtfs_rutas']:
            df_final = gpd.GeoDataFrame(pd.concat(dfs, ignore_index=True), crs=dfs[0].crs)
        else:
            df_final = pd.concat(dfs, ignore_index=True)

        blob_path = f"gtfs/{nombre_tabla}.parquet"
        try:
            buffer = io.BytesIO()
            df_final.to_parquet(buffer, index=False, compression="snappy")
            buffer.seek(0)
            blob_client = blob_service_client.get_blob_client(container=BLOB_CONTAINER_NAME, blob=blob_path)
            blob_client.upload_blob(buffer, overwrite=True)
            logger.info(f"ÉXITO: {blob_path} subido con {len(df_final)} filas.")
        except Exception as e:
            logger.error(f"Error subiendo {blob_path}: {e}", exc_info=True)


if __name__ == "__main__":
    main()
