import os
import geopandas as gpd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

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
        # Necesitamos habilitar PostGIS en la base de datos si no lo está
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
        conn.commit()

def ingest_vector(file_path, table_name, engine, schema="bronze"):
    logging.info(f"Leyendo archivo geoespacial: {file_path}")
    gdf = gpd.read_file(file_path)
    
    # Estandarizar a WGS84 (EPSG:4326) para mapas web y H3
    if gdf.crs is None:
        logging.warning("El archivo no tiene CRS definido. Asumiendo EPSG:4326")
        gdf.set_crs(epsg=4326, inplace=True)
    elif gdf.crs.to_epsg() != 4326:
        logging.info(f"Reproyectando de {gdf.crs} a EPSG:4326...")
        gdf = gdf.to_crs(epsg=4326)
        
    logging.info(f"Insertando {len(gdf)} registros en la tabla {schema}.{table_name}...")
    
    # Subir a PostGIS. Requiere geoalchemy2
    gdf.to_postgis(
        name=table_name,
        con=engine,
        schema=schema,
        if_exists="replace",
        index=False
    )
    logging.info(f"✅ Ingesta de {table_name} completada con éxito.")

if __name__ == "__main__":
    engine = get_pg_engine()
    ensure_postgis_and_schema(engine)
    
    # 1. Malla H3 (El tablero base)
    h3_path = os.path.join("data", "bronce", "spatial", "h3", "h3_grid_tenerife_res8.geojson")
    if os.path.exists(h3_path):
        ingest_vector(h3_path, "h3_grid", engine)
    else:
        logging.error(f"No se encontró el archivo {h3_path}")
        
    # 2. Espacios Naturales Protegidos (ENP)
    enp_path = os.path.join("data", "bronce", "spatial", "spatial_enp_tenerife_espacios_naturales_protegidos.geojson")
    if os.path.exists(enp_path):
        ingest_vector(enp_path, "espacios_naturales", engine)
    else:
        logging.warning(f"No se encontró el archivo {enp_path}")
