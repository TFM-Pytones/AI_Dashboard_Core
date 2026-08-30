"""
tripadvisor_upload_blob.py

Extrae ubicaciones y reseñas de hoteles y restaurantes de Tenerife usando la API
de Terra (TripAdvisor). Utiliza GeoPandas y PostGIS para asegurar que los resultados
pertenecen realmente a la isla (filtrado geográfico) antes de gastar peticiones
inútiles descargando reseñas de homónimos fuera de la isla.

Sube los resultados como JSON crudos a Azure Blob Storage (bronce-raw/tripadvisor/).
"""

import os
import time
import json
import argparse
import io

import requests
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
from sqlalchemy import create_engine
from azure.storage.blob import BlobServiceClient
from azure.core.exceptions import ResourceNotFoundError
from dotenv import load_dotenv

load_dotenv()

# --- Configuración y Conexiones ---
AZURE_DB_USER = os.getenv('AZURE_DB_USER')
AZURE_DB_PASSWORD = os.getenv('AZURE_DB_PASSWORD')
AZURE_DB_HOST = os.getenv('AZURE_DB_HOST')
AZURE_DB_NAME = os.getenv('AZURE_DB_NAME')

AZURE_STORAGE_CONNECTION_STRING = os.getenv('AZURE_STORAGE_CONNECTION_STRING')
CONTENEDOR_BRONZE = 'bronce-raw'
TRIPADVISOR_KEY = os.getenv('TRIPADVISOR_KEY')

BASE_URL = 'https://terra.tripadvisor.com/api'
HEADERS = {'X-API-Key': TRIPADVISOR_KEY}

peticiones_realizadas = 0
LIMITE_DIARIO_SEGURO = 900

NOMBRES_CORTOS = {
    'San Cristóbal de La Laguna': 'La Laguna',
    'Güímar': 'Guimar',
    'Guía de Isora': 'Guia de Isora',
    'Santa Úrsula': 'Santa Ursula',
    'Vilaflor de Chasna': 'Vilaflor',
}
TERMINO_GENERICO = {'RESTAURANT': 'restaurante'}


def get_db_engine():
    conn_str = f"postgresql://{AZURE_DB_USER}:{AZURE_DB_PASSWORD}@{AZURE_DB_HOST}:5432/{AZURE_DB_NAME}"
    return create_engine(conn_str, connect_args={"sslmode": "require"})


def peticion_con_reintentos(url, params, intentos_max=5):
    global peticiones_realizadas
    espera = 2
    codigos_reintentables = (429, 500, 502, 503, 504)
    for intento in range(intentos_max):
        peticiones_realizadas += 1
        resp = requests.get(url, headers=HEADERS, params=params, timeout=30)
        if resp.status_code not in codigos_reintentables:
            resp.raise_for_status()
            return resp
        retry_after = resp.headers.get('Retry-After')
        espera_real = int(retry_after) if retry_after else espera
        print(f"    error {resp.status_code} - esperando {espera_real} segundos (intento {intento + 1} de {intentos_max})...")
        time.sleep(espera_real)
        espera = min(espera * 2, 60)
    resp.raise_for_status()
    return resp


def nombre_busqueda(municipio):
    return NOMBRES_CORTOS.get(municipio, municipio)


def buscar_ubicaciones(municipio, categoria, max_paginas=10):
    resultados_totales = []
    pagina = 1
    usar_fallback = (categoria == 'HOTEL')
    
    while pagina <= max_paginas:
        if usar_fallback:
            params = {
                'query': nombre_busqueda(municipio),
                'category': categoria,
                'country_code': 'ES',
                'size': 20,
                'page': pagina,
            }
        else:
            params = {
                'query': TERMINO_GENERICO.get(categoria, categoria.lower()),
                'geo_name': nombre_busqueda(municipio),
                'category': categoria,
                'size': 20,
                'page': pagina,
            }
            
        try:
            resp = peticion_con_reintentos(BASE_URL + '/locations/search', params)
        except Exception as error:
            if not usar_fallback:
                print(f"    geo_name fallo ({error}), cambiando al metodo de texto para el resto de paginas...")
                usar_fallback = True
                params = {'query': nombre_busqueda(municipio), 'category': categoria, 'country_code': 'ES', 'size': 20, 'page': pagina}
                resp = peticion_con_reintentos(BASE_URL + '/locations/search', params)
            else:
                print(f"    fallo en pagina {pagina} - me quedo con lo ya conseguido en paginas anteriores")
                break
                
        resultados_pagina = resp.json().get('data', [])
        if not resultados_pagina:
            break
        resultados_totales.extend(resultados_pagina)
        if len(resultados_pagina) < 20:
            break
        pagina += 1
        time.sleep(0.5)
    return resultados_totales


def obtener_resenas(location_id, idioma='es'):
    params = {'language': idioma, 'size': 20}
    resp = peticion_con_reintentos(f"{BASE_URL}/locations/{location_id}/reviews", params)
    return resp.json().get('data', [])


def esta_en_tenerife(resultado, tenerife_union):
    coords = (resultado.get('location', {}) or {}).get('coordinates') or {}
    lat, lon = coords.get('latitude'), coords.get('longitude')
    if lat is None or lon is None:
        return False
    return Point(float(lon), float(lat)).within(tenerife_union)


def upload_to_azure(df_new: pd.DataFrame, blob_name: str, container_client, unique_key: str):
    """Descarga el parquet existente (si hay), une, elimina duplicados y resube."""
    blob_client = container_client.get_blob_client(blob_name)
    try:
        data = blob_client.download_blob().readall()
        df_old = pd.read_parquet(io.BytesIO(data))
        df_final = pd.concat([df_old, df_new], ignore_index=True)
        # Eliminamos duplicados basándonos en la clave única
        df_final = df_final.drop_duplicates(subset=[unique_key], keep='last')
        print(f"  -> Fusionado con datos existentes. Total: {len(df_final)} filas (Nuevas: {len(df_new)})")
    except ResourceNotFoundError:
        df_final = df_new
        df_final = df_final.drop_duplicates(subset=[unique_key], keep='last')
        print(f"  -> Archivo nuevo creado. Total: {len(df_final)} filas")

    out_buffer = io.BytesIO()
    df_final.to_parquet(out_buffer, index=False)
    blob_client.upload_blob(out_buffer.getvalue(), overwrite=True)
    print(f"  -> {blob_name} subido a Azure con éxito.")


def main():
    parser = argparse.ArgumentParser(description="Ingesta de TripAdvisor a Parquet (Azure Blob).")
    parser.add_argument("--dry-run", action="store_true", help="Realiza la extracción y muestra 3 filas, sin subir nada a Azure.")
    args = parser.parse_args()

    if not TRIPADVISOR_KEY:
        print("Falta TRIPADVISOR_KEY en .env")
        return

    engine = get_db_engine()
    blob_service = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
    container_client = blob_service.get_container_client(CONTENEDOR_BRONZE)

    print("Cargando geometria de Tenerife y municipios desde PostGIS...")
    tenerife_union = gpd.read_postgis(
        'SELECT ST_Union(geometry) AS geometry FROM silver.limites_municipales', engine, geom_col='geometry'
    ).to_crs(epsg=4326).geometry.iloc[0]
    
    municipios = pd.read_sql('SELECT etiqueta FROM silver.limites_municipales;', engine)['etiqueta'].tolist()
    
    # Para pruebas rápidas descomentar
    # municipios = municipios[:3]

    categorias = ['HOTEL', 'RESTAURANT']
    ubicaciones_raw = []
    resenas_raw = []
    vistos = set()
    descartados_fuera_tenerife = 0
    parar = False

    for municipio in municipios:
        if parar: break
        for categoria in categorias:
            if peticiones_realizadas >= LIMITE_DIARIO_SEGURO:
                print(f"\nLIMITE DE SEGURIDAD ALCANZADO ({peticiones_realizadas} peticiones). Parando aqui.")
                print(f"Continuar mañana desde: {municipio} - {categoria}")
                parar = True
                break

            print(f"Buscando {categoria} en {municipio}...")
            try:
                resultados = buscar_ubicaciones(municipio, categoria)
            except Exception as error:
                print(f"  aviso: fallo la busqueda - {error}")
                continue

            validos = [r for r in resultados if esta_en_tenerife(r, tenerife_union)]
            descartados_fuera_tenerife += len(resultados) - len(validos)
            print(f"  -> {len(resultados)} encontrados, {len(validos)} dentro de Tenerife")

            for resultado in validos:
                if peticiones_realizadas >= LIMITE_DIARIO_SEGURO:
                    print(f"  limite alcanzado a mitad de {municipio} {categoria} - paro aqui")
                    parar = True
                    break

                loc = resultado.get('location', {})
                location_id = loc.get('id')
                # Forzamos location_id a string para evitar problemas de tipos mixtos al guardar en parquet
                if location_id is not None:
                    location_id = str(location_id)
                
                if location_id is None or location_id in vistos:
                    continue
                vistos.add(location_id)

                registro = dict(resultado)
                registro['municipio_busqueda'] = municipio
                registro['categoria_busqueda'] = categoria
                # Serializamos el diccionario anidado a string JSON para evitar problemas con Parquet
                registro['location'] = json.dumps(registro.get('location', {}))
                
                # Extraemos el location_id al primer nivel para que Pandas lo ponga como columna y podamos deduplicar facilmente
                registro['location_id'] = location_id
                
                ubicaciones_raw.append(registro)

                time.sleep(0.5)

                try:
                    resenas = obtener_resenas(location_id)
                except Exception as error:
                    print(f"  aviso: fallaron las resenas de {location_id} - {error}")
                    resenas = []

                for resena in resenas:
                    resenas_raw.append({
                        'location_id': location_id,
                        'review_id': str(resena.get('id')),
                        'resena_raw': json.dumps(resena)
                    })

                time.sleep(0.5)
                
            if parar: break

    print(f"\nUbicaciones validas (dentro de Tenerife): {len(ubicaciones_raw)}")
    print(f"Descartadas por estar fuera de Tenerife: {descartados_fuera_tenerife}")
    print(f"Resenas: {len(resenas_raw)}")
    print(f"Peticiones usadas: {peticiones_realizadas}")

    if ubicaciones_raw and resenas_raw:
        df_ubicaciones = pd.DataFrame(ubicaciones_raw)
        df_resenas = pd.DataFrame(resenas_raw)
        
        # Nos aseguramos de que todos los IDs sean strings (por si Pandas los infiere como ints)
        df_ubicaciones['location_id'] = df_ubicaciones['location_id'].astype(str)
        df_resenas['location_id'] = df_resenas['location_id'].astype(str)
        df_resenas['review_id'] = df_resenas['review_id'].astype(str)

        if args.dry_run:
            print("\n[DRY RUN ACTIVO] No se subirá nada a Azure.")
            print("\nMuestra de ubicaciones (3 filas):")
            print(df_ubicaciones.head(3))
            print("\nMuestra de reseñas (3 filas):")
            print(df_resenas.head(3))
        else:
            print("\nSubiendo a Azure Blob Storage (formato Parquet)...")
            upload_to_azure(df_ubicaciones, "tripadvisor/tripadvisor_ubicaciones.parquet", container_client, unique_key="location_id")
            upload_to_azure(df_resenas, "tripadvisor/tripadvisor_resenas.parquet", container_client, unique_key="review_id")


if __name__ == '__main__':
    main()
