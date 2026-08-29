import os
import io
import json
import geopandas as gpd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from azure.storage.blob import BlobServiceClient
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

load_dotenv()
AZURE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
BLOB_CONTAINER_NAME = "bronce-raw"

def get_pg_engine():
    load_dotenv()
    PG_USER = os.getenv("AZURE_DB_USER")
    PG_PASS = os.getenv("AZURE_DB_PASSWORD")
    PG_HOST = os.getenv("AZURE_DB_HOST")
    PG_PORT = os.getenv("AZURE_DB_PORT", "5432")
    PG_DB = os.getenv("AZURE_DB_NAME")
    
    if not all([PG_USER, PG_PASS, PG_HOST, PG_DB]):
        raise ValueError("Faltan variables de entorno para PostgreSQL (AZURE_DB_USER, etc.)")
        
    connection_string = f"postgresql://{PG_USER}:{PG_PASS}@{PG_HOST}:{PG_PORT}/{PG_DB}"
    return create_engine(connection_string, connect_args={'sslmode': 'require'})

def ensure_postgis_and_schema(engine, schema_name="bronze"):
    logging.info(f"Asegurando esquema '{schema_name}' y extensión PostGIS...")
    with engine.connect() as conn:
        conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema_name};"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
        conn.commit()

def download_geojson_to_gdf(blob_service_client, blob_name: str):
    blob_client = blob_service_client.get_blob_client(container=BLOB_CONTAINER_NAME, blob=blob_name)
    if not blob_client.exists():
        logging.warning(f"El blob {blob_name} no existe en Azure.")
        return None
        
    logging.info(f"Descargando blob: {blob_name}")
    content = blob_client.download_blob().readall()
    
    if blob_name.endswith('.parquet'):
        gdf = gpd.read_parquet(io.BytesIO(content))
    else:
        gdf = gpd.read_file(io.BytesIO(content))
    return gdf

def ingest_vector(gdf, table_name, engine, schema="bronze"):
    if gdf.crs is None:
        logging.warning("El archivo no tiene CRS definido. Asumiendo EPSG:4326")
        gdf.set_crs(epsg=4326, inplace=True)
    elif gdf.crs.to_epsg() != 4326:
        logging.info(f"Reproyectando de {gdf.crs} a EPSG:4326...")
        gdf = gdf.to_crs(epsg=4326)
        
    logging.info(f"Insertando {len(gdf)} registros en la tabla {schema}.{table_name}...")
    
    gdf.to_postgis(
        name=table_name,
        con=engine,
        schema=schema,
        if_exists="replace",
        index=False
    )
    logging.info(f"Ingesta de {table_name} completada con éxito.")

def main():
    if not AZURE_CONNECTION_STRING:
        logging.error("AZURE_STORAGE_CONNECTION_STRING no está definido en el archivo .env")
        return
        
    engine = get_pg_engine()
    ensure_postgis_and_schema(engine)
    blob_service_client = BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)
    
    spatial_datasets = {
        "espacial/h3/h3_grid_tenerife_res8.parquet": "h3_grid",
        "espacial/enp/tenerife_espacios_naturales_protegidos.parquet": "espacios_naturales",
        "espacial/zonas_turisticas/tenerife_zonas_turisticas.parquet": "zonas_turisticas",
        "espacial/limites_municipales/limites_municipales_tenerife.parquet": "limites_municipales",
        "espacial/bienes_interes_cultural/bienes_interes_cultural_tenerife.parquet": "bienes_interes_cultural",
        "espacial/oficina_turismo/oficinas_turismo_tenerife.parquet": "oficinas_turismo",
        "espacial/osm/osm_pois_tenerife.parquet": "osm_pois"
    }
    
    for blob_path, table_name in spatial_datasets.items():
        gdf = download_geojson_to_gdf(blob_service_client, blob_path)
        if gdf is not None and not gdf.empty:
            try:
                ingest_vector(gdf, table_name, engine)
            except Exception as e:
                logging.error(f"Error ingestando {table_name}: {e}")

if __name__ == "__main__":
    main()
