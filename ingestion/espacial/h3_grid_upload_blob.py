import os
import h3
import osmnx as ox
import geopandas as gpd
from shapely.geometry import Polygon
import json
from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient

def generate_h3_grid(resolution=8):
    print("Descargando polígono de Tenerife desde OSM...")
    # Fetch Tenerife boundary
    gdf_tenerife = ox.geocode_to_gdf('Tenerife, Spain')
    # Extraer el polígono principal
    geom = gdf_tenerife.geometry.iloc[0]
    
    # [SOLUCIÓN COSTA]: Añadimos un buffer de 0.01 grados (~1.1 km) al polígono.
    # Esto "engorda" la silueta de Tenerife (~4.6 radios del hexágono H3-8 de margen).
    # Así nos aseguramos de que el centro de los hexágonos costeros caiga siempre
    # dentro del polígono ampliado, cubriendo el 100% de la isla real sin huecos.
    geom = geom.buffer(0.01)
    
    if geom.geom_type == 'Polygon':
        polygons = [geom]
    elif geom.geom_type == 'MultiPolygon':
        polygons = list(geom.geoms)
    else:
        raise ValueError("La geometría devuelta no es un polígono")

    hexagons = set()
    for poly in polygons:
        # Convert shapely polygon to h3 LatLngPoly (expects lat, lng)
        outer = [(lat, lng) for lng, lat in poly.exterior.coords]
        holes = [[(lat, lng) for lng, lat in hole.coords] for hole in poly.interiors]
        
        try:
            # API h3 >= 4.0
            h3_poly = h3.LatLngPoly(outer, *holes)
            cells = h3.polygon_to_cells(h3_poly, resolution)
        except AttributeError:
            # API h3 < 4.0 (polyfill expected geo_json_conformant=True for lng, lat)
            geo_json = poly.__geo_interface__
            cells = h3.polyfill(geo_json, resolution, geo_json_conformant=True)
            
        hexagons.update(cells)
        
    print(f"Generados {len(hexagons)} hexágonos H3 (Resolución {resolution}).")
    
    # Convertir índices a Polígonos de Shapely
    records = []
    for h in hexagons:
        try:
            # API h3 >= 4.0
            boundary = h3.cell_to_boundary(h)
            # API 4.0 devuelve (lat, lng) por defecto, necesitamos (lng, lat) para Shapely
            boundary = [(lng, lat) for lat, lng in boundary]
        except AttributeError:
            # API h3 < 4.0
            boundary = h3.h3_to_geo_boundary(h, geo_json=True) # geo_json=True devuelve (lng, lat)
            
        poly = Polygon(boundary)
        records.append({'h3_index': h, 'resolution': resolution, 'geometry': poly})
        
    gdf = gpd.GeoDataFrame(records, crs="EPSG:4326")
    return gdf

def upload_to_blob(local_path, blob_name):
    load_dotenv()
    conn_str = os.getenv('AZURE_STORAGE_CONNECTION_STRING')
    if not conn_str:
        print("Falta AZURE_STORAGE_CONNECTION_STRING en .env")
        return
        
    container_name = "bronce-raw"
    client = BlobServiceClient.from_connection_string(conn_str)
    blob_client = client.get_blob_client(container=container_name, blob=blob_name)
    
    print(f"Subiendo a Azure Blob Storage: {blob_name}...")
    with open(local_path, 'rb') as f:
        blob_client.upload_blob(f, overwrite=True)
    print("¡Subida completada!")

if __name__ == "__main__":
    out_dir = os.path.join("data", "bronce", "espacial", "h3")
    os.makedirs(out_dir, exist_ok=True)
    out_file = os.path.join(out_dir, "h3_grid_tenerife_res8.parquet")
    
    gdf_h3 = generate_h3_grid(resolution=8)
    
    print(f"Guardando localmente en {out_file}...")
    gdf_h3.to_parquet(out_file, index=False)
    
    blob_path = "espacial/h3/h3_grid_tenerife_res8.parquet"
    upload_to_blob(out_file, blob_path)
