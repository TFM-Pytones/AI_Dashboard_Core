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
logger = logging.getLogger("GeocodeBookingPG")

load_dotenv()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CACHE_FILE = os.path.join(BASE_DIR, "scratch", "geocode_booking_cache.json")

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
    match = re.search(r'^(.*)\s\((La|El|Los|Las)\)$', name, flags=re.IGNORECASE)
    if match:
        name = f"{match.group(2)} {match.group(1)}"
    match = re.search(r'^(.*),\s*(La|El|Los|Las)$', name, flags=re.IGNORECASE)
    if match:
        name = f"{match.group(2)} {match.group(1)}"
    name = re.sub(r'\s*\(.*?\)', '', name)
    return name.strip()

def clean_address(addr_str):
    addr = str(addr_str).strip()
    if not addr or addr.lower() in ('nan', 'none', 'null', '_u'): return None
        
    # 1. Extraer el sufijo del código postal y municipio si existe (típico de Booking)
    suffix = ""
    suffix_match = re.search(r'(,\s*\d{5}.*)$', addr)
    if suffix_match:
        suffix = suffix_match.group(1)
        addr = addr.replace(suffix, '')
        
    # Eliminar paréntesis y su contenido
    addr = re.sub(r'\s*\(.*?\)', '', addr)
    
    # Eliminar s/n (sin número)
    addr = re.sub(r'(?i)[,\s-]*s/n\b', '', addr)
        
    # Expandir siglas (C. Cl. Av. etc)
    addr = re.sub(r'(?i)\bc\.\s+', 'Calle ', addr)
    addr = re.sub(r'(?i)\bcl\.?\s+', 'Calle ', addr)
    addr = re.sub(r'(?i)\burb\.?\b', 'Urbanización', addr)
    addr = re.sub(r'(?i)\bctra\.?\b', 'Carretera', addr)
    addr = re.sub(r'(?i)\bcno\.?\b', 'Camino', addr)
    addr = re.sub(r'(?i)\bav\.?\b', 'Avenida', addr)
    addr = re.sub(r'(?i)\bavda\.?\b', 'Avenida', addr)
    addr = re.sub(r'(?i)\bpza\.?\b', 'Plaza', addr)
    addr = re.sub(r'(?i)\bplza\.?\b', 'Plaza', addr)
    
    addr = re.sub(r'(?i)nº\s*', ' ', addr)
    
    # Truncar basurilla de pisos, bloques, plantas, pianos, apartamentos (Booking tiene mucha de esta)
    addr = re.sub(r'(?i)[,\s-]+\b(piso|bloque|blq|puerta|pta|edf|edificio|escalera|esc|vda|vivienda|bajo|atico|local|apto|apt|apart|apartamento|fase|residencial|res|urb|urbanizacion|piano|planta)\b.*', '', addr)
    
    addr = re.sub(r'[,\s-]+\d+º.*', '', addr)
    addr = re.sub(r'^[cC]\s*/\s*', 'Calle ', addr)
    addr = re.sub(r'^[cC]\s+', 'Calle ', addr, flags=re.IGNORECASE)
    
    match = re.search(r'^([A-Za-zñÑáéíóúÁÉÍÓÚ\s,.-]+(?:,\s*)?\d+)', addr)
    if match:
        addr = match.group(1).strip()
        
    addr = re.sub(r'[,.-]+$', '', addr).strip()
    
    # Volver a pegar el sufijo
    addr = addr + suffix
    
    if not addr: return None
    
    # Booking addresses usually contain the full address already, so we just make sure it has Tenerife/España
    if "Tenerife" not in addr and "España" not in addr and "Spain" not in addr:
        addr = f"{addr}, Santa Cruz de Tenerife, España"
        
    return addr

def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, 'r', encoding='utf-8') as f: return json.load(f)
    return {}

def save_cache(cache):
    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

def process_and_geocode():
    engine = get_pg_engine()
    geolocator = Nominatim(user_agent="TFM_Tenerife_Geocoding_Booking_App")
    cache = load_cache()
    
    lookup_data = []
    total_geocoded_session = 0
    table = "booking_establishments"
    
    logger.info(f"--- Consultando {table} en PostgreSQL (bronze) ---")
    try:
        query = f"SELECT establishment_id, name, address, latitude FROM bronze.{table}"
        df = pd.read_sql(query, engine)
    except Exception as e:
        logger.error(f"Error leyendo tabla {table}: {e}")
        return
        
    # Identificar aquellos sin latitud o donde es '0', 'None', etc.
    df['latitude'] = df['latitude'].astype(str).str.replace(',', '.')
    mask = (df['latitude'] == '0') | (df['latitude'] == '0.0') | (df['latitude'].isnull()) | (df['latitude'] == 'nan') | (df['latitude'] == 'None')
    
    logger.info(f"Total registros: {len(df)} | Sin coordenadas válidas: {mask.sum()}")
    
    for idx, row in df[mask].iterrows():
        id_registro = str(row['establishment_id'])
        
        if id_registro in cache:
            if cache[id_registro]['lat'] is not None:
                lookup_data.append({
                    "establishment_id": id_registro,
                    "latitud_geocoded": cache[id_registro]['lat'],
                    "longitud_geocoded": cache[id_registro]['lon']
                })
            continue
            
        clean_str = clean_address(row.get('address', ''))
        location = None
        query_used = ""
        
        # Preparar Fallback
        nombre_com = str(row.get('name', ''))
        fallback_query = None
        if nombre_com and nombre_com.lower() not in ('nan', 'none', 'null', '_u'):
            nombre_limpio = fix_inverted_article(nombre_com)
            fallback_query = f"{nombre_limpio}, Santa Cruz de Tenerife, España"
            
        try:
            # 1. Intentar con la dirección normal
            if clean_str:
                time.sleep(1.1)
                location = geolocator.geocode(clean_str, timeout=10)
                query_used = clean_str
                
            # 2. Si falla la dirección, usar fallback con Nombre Comercial en Nominatim
            if not location and fallback_query:
                logger.info(f"🔄 {table} | Intento Fallback Nominatim (Nombre Comercial): {fallback_query}")
                time.sleep(1.1)
                location = geolocator.geocode(fallback_query, timeout=10)
                if location: query_used = fallback_query
                    
            # 3. PLAN C: Si Nominatim fracasa, usar ArcGIS
            if not location:
                from geopy.geocoders import ArcGIS
                geolocator_arcgis = ArcGIS(user_agent="TFM_Tenerife_Geocoding_Booking_App")
                
                if clean_str:
                    logger.info(f"🚀 {table} | Intento PLAN C (ArcGIS Calle) para: {clean_str}")
                    try:
                        location = geolocator_arcgis.geocode(clean_str, timeout=10)
                        if location: query_used = clean_str + " (ArcGIS)"
                    except Exception: pass
                        
                if not location and fallback_query:
                    logger.info(f"🚀 {table} | Intento PLAN C (ArcGIS Comercial) para: {fallback_query}")
                    try:
                        location = geolocator_arcgis.geocode(fallback_query, timeout=10)
                        if location: query_used = fallback_query + " (ArcGIS)"
                    except Exception: pass
            
            # Resultado final
            if location:
                logger.info(f"✅ {table} | ÉXITO: {query_used} -> {location.latitude}, {location.longitude}")
                cache[id_registro] = {'lat': location.latitude, 'lon': location.longitude, 'query': query_used}
                lookup_data.append({
                    "establishment_id": id_registro,
                    "latitud_geocoded": location.latitude,
                    "longitud_geocoded": location.longitude
                })
            else:
                logger.info(f"❌ {table} | FALLO: No se encontró {clean_str if clean_str else query_used}")
                cache[id_registro] = {'lat': None, 'lon': None, 'query': clean_str if clean_str else query_used}
                
        except (GeocoderTimedOut, GeocoderUnavailable) as e:
            logger.error(f"⚠️ Error de API geocodificando {id_registro}: {e}")
            save_cache(cache)
            break
        except Exception as e:
            logger.error(f"Error inesperado con {id_registro}: {e}")
            cache[id_registro] = {'lat': None, 'lon': None, 'query': clean_str}
        
        total_geocoded_session += 1
        if total_geocoded_session % 50 == 0:
            save_cache(cache)
            
    save_cache(cache)
    
    if lookup_data:
        lookup_df = pd.DataFrame(lookup_data)
        lookup_df = lookup_df.drop_duplicates(subset=['establishment_id'])
        
        logger.info(f"Guardando {len(lookup_df)} registros únicos en bronze.booking_geocoding_lookup...")
        try:
            lookup_df.to_sql(
                name="booking_geocoding_lookup",
                con=engine,
                schema="bronze",
                if_exists="replace",
                index=False,
                method="multi"
            )
            logger.info("✅ Tabla bronze.booking_geocoding_lookup actualizada correctamente.")
        except Exception as e:
            logger.error(f"❌ Error guardando tabla en postgres: {e}")
    else:
        logger.info("No hay coordenadas nuevas que guardar en la base de datos.")

if __name__ == "__main__":
    process_and_geocode()
