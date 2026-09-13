import os
import re
import time
import json
import logging
import pandas as pd
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable
from dotenv import load_dotenv
from sqlalchemy import create_engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("GeocodeRegistrosPG")

load_dotenv()

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

# --- Configuración Azure PostgreSQL ---
PG_USER = os.getenv("AZURE_DB_USER")
PG_PASS = os.getenv("AZURE_DB_PASSWORD")
PG_HOST = os.getenv("AZURE_DB_HOST")
PG_PORT = os.getenv("AZURE_DB_PORT", "5432")
PG_DB = os.getenv("AZURE_DB_NAME")

def get_pg_engine():
    connection_string = f"postgresql://{PG_USER}:{PG_PASS}@{PG_HOST}:{PG_PORT}/{PG_DB}"
    return create_engine(connection_string, connect_args={'sslmode': 'require'})

def fix_inverted_article(name):
    """Convierte 'Orotava (La)' o 'Torre, La' en 'La Orotava' / 'La Torre'"""
    name = str(name).strip()
    
    # Para formato "Orotava (La)"
    match = re.search(r'^(.*)\s\((La|El|Los|Las)\)$', name, flags=re.IGNORECASE)
    if match:
        name = f"{match.group(2)} {match.group(1)}"
        
    # Para formato "Torre, La" o "Alenes Del Mar, Los"
    match = re.search(r'^(.*),\s*(La|El|Los|Las)$', name, flags=re.IGNORECASE)
    if match:
        name = f"{match.group(2)} {match.group(1)}"
        
    # También limpiar cosas como "Playa De Las Americas (Arona)" -> "Playa De Las Americas"
    name = re.sub(r'\s*\(.*?\)', '', name)
    return name.strip()

def clean_address(row):
    addr = str(row.get('direccion', '')).strip()
    if not addr or addr == 'nan' or addr == '_U': return None
        
    # Eliminar paréntesis y su contenido en la dirección
    addr = re.sub(r'\s*\(.*?\)', '', addr)
    
    # Expandir siglas comunes al inicio o en el texto
    addr = re.sub(r'(?i)\burb\.?\b', 'Urbanización', addr)
    addr = re.sub(r'(?i)\bcl\.?\b', 'Calle', addr)
    addr = re.sub(r'(?i)\bctra\.?\b', 'Carretera', addr)
    addr = re.sub(r'(?i)\bcno\.?\b', 'Camino', addr)
    addr = re.sub(r'(?i)\bav\.?\b', 'Avenida', addr)
    addr = re.sub(r'(?i)\bavda\.?\b', 'Avenida', addr)
    addr = re.sub(r'(?i)\bpza\.?\b', 'Plaza', addr)
    addr = re.sub(r'(?i)\bplza\.?\b', 'Plaza', addr)
    
    # Eliminar "Nº", "Nº ", "nº" para que quede solo el número limpio
    addr = re.sub(r'(?i)nº\s*', ' ', addr)
    
    # Eliminar palabras típicas de apartamento/piso/bloque/edificio y todo lo que sigue
    addr = re.sub(r'(?i)[,\s-]+\b(piso|bloque|blq|puerta|pta|edf|edificio|escalera|esc|vda|vivienda|bajo|atico|local|apto|apartamento|fase|residencial|res|urb|urbanizacion)\b.*', '', addr)
    
    # Eliminar cosas tipo " - 2º", " 2º Izq", ", 3º", " 1A" (pisos con el símbolo º)
    addr = re.sub(r'[,\s-]+\d+º.*', '', addr)
    
    # Reemplazar prefijos de calles comunes (por si acaso no tenían punto)
    addr = re.sub(r'^[cC]\s*/\s*', 'Calle ', addr)
    addr = re.sub(r'^[cC]\s+', 'Calle ', addr, flags=re.IGNORECASE)
    
    match = re.search(r'^([A-Za-zñÑáéíóúÁÉÍÓÚ\s,.-]+(?:,\s*)?\d+)', addr)
    if match:
        addr = match.group(1).strip()
        
    # Quitamos comas o guiones sueltos al final
    addr = re.sub(r'[,.-]+$', '', addr).strip()
    
    if not addr: return None
    
    components = [addr]
    
    localidad = str(row.get('direccion_localidad_nombre', ''))
    if localidad and localidad not in ('nan', '_U'): 
        components.append(fix_inverted_article(localidad))
        
    municipio = str(row.get('direccion_municipio_nombre', ''))
    if municipio and municipio not in ('nan', '_U'): 
        components.append(fix_inverted_article(municipio))
        
    cp = str(row.get('direccion_codigo_postal', ''))
    if cp and cp not in ('nan', '_U'): components.append(cp)
        
    components.extend(["Santa Cruz de Tenerife", "España"])
    return ", ".join(components)

def load_cache(engine):
    cache = {}
    try:
        query = "SELECT establecimiento_id, latitud_geocoded, longitud_geocoded FROM bronze.bronze_registro_geocoding_lookup"
        df_db = pd.read_sql(query, engine)
        for _, row in df_db.iterrows():
            cache[str(row['establecimiento_id'])] = {'lat': row['latitud_geocoded'], 'lon': row['longitud_geocoded'], 'query': 'from_db'}
        logger.info(f"Cargados {len(cache)} registros cacheados desde PostgreSQL.")
    except Exception as e:
        logger.info("Aun no existe tabla en Postgres para usar de caché o está vacía.")
    return cache

def process_and_geocode():
    engine = get_pg_engine()
    geolocator = Nominatim(user_agent="TFM_Tenerife_Geocoding_App")
    cache = load_cache(engine)
    
    tables = [
        "bronze_registro_hoteles",
        "bronze_registro_extrahoteleros",
        "bronze_registro_viviendas_vacacionales"
    ]
    
    lookup_data = []
    total_geocoded_session = 0
    
    for table in tables:
        logger.info(f"--- Consultando {table} en PostgreSQL (bronze) ---")
        try:
            # Añadido establecimiento_nombre_comercial para el fallback
            query = f"SELECT establecimiento_id, establecimiento_nombre_comercial, direccion, direccion_localidad_nombre, direccion_municipio_nombre, direccion_codigo_postal, latitud FROM bronze.{table}"
            df = pd.read_sql(query, engine)
        except Exception as e:
            logger.error(f"Error leyendo tabla {table}: {e}")
            continue
            
        df['latitud'] = df['latitud'].astype(str).str.replace(',', '.')
        mask = (df['latitud'] == '0') | (df['latitud'] == '0.0') | (df['latitud'].isnull()) | (df['latitud'] == 'nan')
        
        logger.info(f"Total registros: {len(df)} | Sin coordenadas válidas: {mask.sum()}")
        
        for idx, row in df[mask].iterrows():
            id_registro = str(row['establecimiento_id'])
            
            if id_registro in cache:
                if cache[id_registro]['lat'] is not None:
                    lookup_data.append({
                        "establecimiento_id": id_registro,
                        "latitud_geocoded": cache[id_registro]['lat'],
                        "longitud_geocoded": cache[id_registro]['lon']
                    })
                continue
                
            clean_str = clean_address(row)
            location = None
            query_used = ""
            
            try:
                # 1. Intentar con la dirección normal
                if clean_str:
                    time.sleep(1.1)
                    location = geolocator.geocode(clean_str, timeout=10)
                    query_used = clean_str
                    
                # 2. Si falla la dirección (o no existe), usar fallback con Nombre Comercial en Nominatim
                if not location:
                    nombre_com = str(row.get('establecimiento_nombre_comercial', ''))
                    if nombre_com and nombre_com not in ('nan', '_U'):
                        nombre_limpio = fix_inverted_article(nombre_com)
                        
                        fallback_comp = [nombre_limpio]
                        
                        loc = str(row.get('direccion_localidad_nombre', ''))
                        if loc and loc not in ('nan', '_U'): fallback_comp.append(fix_inverted_article(loc))
                            
                        mun = str(row.get('direccion_municipio_nombre', ''))
                        if mun and mun not in ('nan', '_U'): fallback_comp.append(fix_inverted_article(mun))
                            
                        cp = str(row.get('direccion_codigo_postal', ''))
                        if cp and cp not in ('nan', '_U'): fallback_comp.append(cp)
                            
                        fallback_comp.extend(["Santa Cruz de Tenerife", "España"])
                        fallback_query = ", ".join(fallback_comp)
                        
                        logger.info(f"🔄 {table} | Intento Fallback Nominatim (Nombre Comercial): {fallback_query}")
                        time.sleep(1.1)
                        location = geolocator.geocode(fallback_query, timeout=10)
                        if location: query_used = fallback_query
                        
                # 3. PLAN C: Si Nominatim fracasa estrepitosamente, usar ArcGIS (Mucho más tolerante tipo Google Maps)
                if not location:
                    from geopy.geocoders import ArcGIS
                    geolocator_arcgis = ArcGIS(user_agent="TFM_Tenerife_Geocoding_App")
                    
                    if clean_str:
                        logger.info(f"🚀 {table} | Intento PLAN C (ArcGIS) para: {clean_str}")
                        try:
                            location = geolocator_arcgis.geocode(clean_str, timeout=10)
                            if location: query_used = clean_str + " (ArcGIS)"
                        except Exception as e:
                            logger.warning(f"Fallo en ArcGIS (Calle): {e}")
                            
                    if not location and 'fallback_query' in locals():
                        logger.info(f"🚀 {table} | Intento PLAN C (ArcGIS Nombre Comercial) para: {fallback_query}")
                        try:
                            location = geolocator_arcgis.geocode(fallback_query, timeout=10)
                            if location: query_used = fallback_query + " (ArcGIS)"
                        except Exception as e:
                            logger.warning(f"Fallo en ArcGIS (Comercial): {e}")
                
                # Resultado final
                if location:
                    logger.info(f"{table} | ÉXITO: {query_used} -> {location.latitude}, {location.longitude}")
                    cache[id_registro] = {'lat': location.latitude, 'lon': location.longitude, 'query': query_used}
                    lookup_data.append({
                        "establecimiento_id": id_registro,
                        "latitud_geocoded": location.latitude,
                        "longitud_geocoded": location.longitude
                    })
                else:
                    logger.info(f"{table} | FALLO: No se encontró {clean_str if clean_str else query_used}")
                    cache[id_registro] = {'lat': None, 'lon': None, 'query': clean_str if clean_str else query_used}
                    
            except (GeocoderTimedOut, GeocoderUnavailable) as e:
                logger.error(f"⚠️ Error de API geocodificando {id_registro}: {e}")
                break
            except Exception as e:
                logger.error(f"Error inesperado con {id_registro}: {e}")
                cache[id_registro] = {'lat': None, 'lon': None, 'query': clean_str}
            
            total_geocoded_session += 1
    
    if lookup_data:
        lookup_df = pd.DataFrame(lookup_data)
        lookup_df = lookup_df.drop_duplicates(subset=['establecimiento_id'])
        
        logger.info(f"Guardando {len(lookup_df)} registros únicos en bronze.registro_geocoding_lookup...")
        try:
            lookup_df.to_sql(
                name="bronze_registro_geocoding_lookup",
                con=engine,
                schema="bronze",
                if_exists="replace",
                index=False,
                method="multi"
            )
            logger.info("Tabla bronze.registro_geocoding_lookup actualizada correctamente.")
        except Exception as e:
            logger.error(f"Error guardando tabla en postgres: {e}")
    else:
        logger.info("No hay coordenadas nuevas que guardar en la base de datos.")

if __name__ == "__main__":
    process_and_geocode()
