"""
osm_tourism_upload_blob.py
-----------------------------
Extrae alojamientos, restaurantes y atracciones de OpenStreetMap 
para la isla de Tenerife usando la API de Overpass.
Guarda los resultados como un archivo GeoJSON en la capa bronce-raw
de Azure Blob Storage.
"""

import os
import json
import logging
import requests
import geopandas as gpd
from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("OSMTenerifeDownloader")

load_dotenv()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ESPACIAL_RAW_DIR = os.path.join(BASE_DIR, "data", "bronce", "espacial", "raw")
os.makedirs(ESPACIAL_RAW_DIR, exist_ok=True)

AZURE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
BLOB_CONTAINER_NAME = "bronce-raw"
BLOB_FOLDER = "espacial/osm"

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
QUERY = """
[out:json][timeout:300];
area["name"="Tenerife"]->.isla;
(
  /* Alojamiento */
  nwr["tourism"~"hotel|hostel|guest_house|apartment|chalet|camp_site|motel|resort"](area.isla);
  
  /* Atracciones y Turismo */
  node["tourism"~"attraction|viewpoint|museum|information|theme_park|zoo"](area.isla);
  node["historic"](area.isla);
  
  /* Ocio y Naturaleza */
  node["leisure"~"nature_reserve|park|marina|golf_course"](area.isla);
  node["natural"~"beach|peak|volcano"](area.isla);
  
  /* Restauracion y Ocio Nocturno */
  node["amenity"~"restaurant|bar|cafe|fast_food|pub|nightclub|casino"](area.isla);
  
  /* Transporte y Accesibilidad */
  node["highway"="bus_stop"](area.isla);
  node["amenity"~"taxi|car_rental|parking|ferry_terminal|bicycle_rental"](area.isla);
  node["railway"="tram_stop"](area.isla);
  
  /* Servicios Basicos (Capacidad de Carga) */
  node["shop"~"supermarket|convenience|mall"](area.isla);
  node["amenity"~"hospital|clinic|pharmacy|atm|bank"](area.isla);
);
out center;
"""

def process_and_upload():
    if not AZURE_CONNECTION_STRING:
        logger.error("AZURE_STORAGE_CONNECTION_STRING no está definido.")
        return

    try:
        blob_service_client = BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)
    except Exception as e:
        logger.error(f"Error al conectar con Azure: {e}")
        return

    logger.info("Consultando la API de Overpass para Tenerife...")
    try:
        headers = {
            'User-Agent': 'TenerifeTFMApp/1.0',
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        resp = requests.post(OVERPASS_URL, data={"data": QUERY}, headers=headers, timeout=120)
        resp.raise_for_status()
        elements = resp.json().get("elements", [])
        logger.info(f"Se obtuvieron {len(elements):,} puntos de interés desde OSM.")

        # Convertir a formato GeoJSON FeatureCollection
        features = []
        for el in elements:
            lat = el.get("lat") or el.get("center", {}).get("lat")
            lon = el.get("lon") or el.get("center", {}).get("lon")
            if lat and lon:
                tags = el.get("tags", {})
                
                # Identificar el tipo exacto y asignarle un macro-grupo
                poi_type = "unknown"
                poi_group = "Otros"
                
                if "tourism" in tags:
                    poi_type = tags["tourism"]
                    if poi_type in ["hotel", "hostel", "guest_house", "apartment", "chalet", "camp_site", "motel", "resort"]:
                        poi_group = "Alojamiento"
                    else:
                        poi_group = "Atracciones_Turisticas"
                elif "amenity" in tags:
                    poi_type = tags["amenity"]
                    if poi_type in ["restaurant", "bar", "cafe", "fast_food", "pub", "nightclub", "casino"]:
                        poi_group = "Restauracion_Ocio"
                    elif poi_type in ["taxi", "car_rental", "parking", "ferry_terminal", "bicycle_rental"]:
                        poi_group = "Transporte"
                    else:
                        poi_group = "Servicios_Basicos"
                elif "leisure" in tags:
                    poi_type = tags["leisure"]
                    poi_group = "Naturaleza_Deporte"
                elif "natural" in tags:
                    poi_type = tags["natural"]
                    poi_group = "Naturaleza_Deporte"
                elif "highway" in tags:
                    poi_type = tags["highway"]
                    poi_group = "Transporte"
                elif "railway" in tags:
                    poi_type = tags["railway"]
                    poi_group = "Transporte"
                elif "shop" in tags:
                    poi_type = tags["shop"]
                    poi_group = "Servicios_Basicos"
                elif "historic" in tags:
                    poi_type = "historic_site"
                    poi_group = "Atracciones_Turisticas"
                
                feature = {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [lon, lat]
                    },
                    "properties": {
                        "osm_id": el["id"],
                        "type": poi_type,         # Ej: "restaurant", "beach", "bus_stop"
                        "group": poi_group,       # Ej: "Restauracion_Ocio", "Naturaleza_Deporte"
                        "name": tags.get("name", "Desconocido")
                    }
                }
                features.append(feature)

        # Convertir a GeoDataFrame y Parquet
        gdf = gpd.GeoDataFrame.from_features(features)
        gdf.set_crs(epsg=4326, inplace=True)
        
        parquet_filename = "osm_pois_tenerife.parquet"
        parquet_path = os.path.join(ESPACIAL_RAW_DIR, parquet_filename)
        
        gdf.to_parquet(parquet_path, index=False)
        logger.info(f"Guardado localmente en: {parquet_path}")

        # Subir a Azure
        blob_destination_path = f"{BLOB_FOLDER}/{parquet_filename}"
        blob_client = blob_service_client.get_blob_client(container=BLOB_CONTAINER_NAME, blob=blob_destination_path)
        
        logger.info(f"Subiendo a Azure Blob Storage: '{blob_destination_path}'...")
        with open(parquet_path, "rb") as data:
            blob_client.upload_blob(data, overwrite=True)
        
        logger.info("Subida completada con éxito.")

    except Exception as e:
        logger.error(f"Error durante el proceso: {e}")

if __name__ == "__main__":
    process_and_upload()
