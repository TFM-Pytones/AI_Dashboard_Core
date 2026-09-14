import os
import re
import argparse
import numpy as np
import pandas as pd
import geopandas as gpd
import rasterio
from rasterstats import zonal_stats
from dotenv import load_dotenv
from sqlalchemy import create_engine
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Contenedor y prefijo donde viirs_upload_blob.py deja los composites mensuales
# (ver ingestion/satelite/viirs_upload_blob.py -- CONTAINER_NAME / AZURE_BLOB_PREFIX)
VIIRS_CONTAINER_NAME = "bronce-raw"
VIIRS_BLOB_PREFIX = "satelite/viirs"

# Issue #24: 2020-2021 muestran una caida artificial de radianza (~60-70%) por
# el COVID (cierre de hoteles, toque de queda). Se etiquetan pero se excluyen
# del modelo de regresion MGWR (#31) para no sesgar el VIIRS como indicador
# negativo de turismo.
VIIRS_ANOS_EXCLUIR_MODELO = {2020, 2021}

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

def process_and_ingest_sentinel2():
    engine = get_pg_engine()
    schema = "bronze"
    table_name = "bronze_satelite_stats"
    
    # 1. Cargar Malla H3 (polígonos) desde la base de datos
    logging.info(f"Cargando polígonos H3 desde PostgreSQL ({schema}.bronze_h3_grid)...")
    try:
        query = f"SELECT h3_index, geometry FROM {schema}.bronze_h3_grid"
        gdf_h3 = gpd.read_postgis(query, con=engine, geom_col='geometry')
    except Exception as e:
        logging.error(f"No se pudo cargar la malla H3 desde la base de datos: {e}")
        return
    
    tif_dir = os.path.join("data", "Satelite_Sentinel2")
    tif_files = sorted([f for f in os.listdir(tif_dir) if f.endswith('.tif')])
    
    first_file = True
    
    for tif_file in tif_files:
        logging.info(f"=== Procesando {tif_file} ===")
        
        # Extraer año y trimestre del nombre del archivo
        match = re.search(r'(\d{4})_(Q\d)', tif_file)
        if not match:
            continue
        year, quarter = match.groups()
        
        filepath = os.path.join(tif_dir, tif_file)
        
        with rasterio.open(filepath) as src:
            # Asegurar que la malla H3 esté en el mismo CRS que la imagen Satelital
            if gdf_h3.crs != src.crs:
                gdf_h3 = gdf_h3.to_crs(src.crs)
            
            # Leer las bandas de datos
            ndvi_array = src.read(1)
            ndbi_array = src.read(2)
            transform = src.transform
            
            # --- LIMPIEZA MATEMÁTICA EN MEMORIA (ON-THE-FLY) ---
            # Filtrar ruido extremo (sombras muy negras, nubes opacas, agua profunda)
            # Reemplazamos los valores < -0.5 o absurdos por NaN
            ndvi_array = np.where((ndvi_array > -0.5) & (ndvi_array <= 1.0), ndvi_array, np.nan)
            ndbi_array = np.where((ndbi_array > -0.5) & (ndbi_array <= 1.0), ndbi_array, np.nan)
            
            # --- ESTADÍSTICA ZONAL ---
            # rasterstats ignora los píxeles NaN, por lo que el mar no hundirá la media
            logging.info(f"  Calculando Zonal Stats NDVI...")
            ndvi_stats = zonal_stats(gdf_h3, ndvi_array, affine=transform, stats="mean", nodata=np.nan)
            
            logging.info(f"  Calculando Zonal Stats NDBI...")
            ndbi_stats = zonal_stats(gdf_h3, ndbi_array, affine=transform, stats="mean", nodata=np.nan)
            
            # --- PROCESAMIENTO VIIRS (Mensual a Trimestral) ---
            viirs_dir = os.path.join("data", "Satelite_VIIRS")
            quarter_to_months = {
                'Q1': ['01', '02', '03'],
                'Q2': ['04', '05', '06'],
                'Q3': ['07', '08', '09'],
                'Q4': ['10', '11', '12']
            }
            months = quarter_to_months.get(quarter, [])
            
            viirs_arrays = []
            viirs_transform = None
            
            for m in months:
                viirs_file = os.path.join(viirs_dir, f"tenerife_viirs_{year}_{m}.tif")
                if os.path.exists(viirs_file):
                    with rasterio.open(viirs_file) as v_src:
                        v_arr = v_src.read(1)
                        v_arr = np.where(v_arr >= 0, v_arr, np.nan)
                        viirs_arrays.append(v_arr)
                        viirs_transform = v_src.transform
                        if gdf_h3.crs != v_src.crs:
                            gdf_h3 = gdf_h3.to_crs(v_src.crs)
            
            if viirs_arrays:
                logging.info(f"  Promediando {len(viirs_arrays)} meses de VIIRS para el {quarter}...")
                # Promedio ignorando NaNs
                viirs_mean_array = np.nanmean(viirs_arrays, axis=0)
                logging.info(f"  Calculando Zonal Stats VIIRS...")
                viirs_stats = zonal_stats(gdf_h3, viirs_mean_array, affine=viirs_transform, stats="mean", nodata=np.nan)
                viirs_mean_list = [s['mean'] for s in viirs_stats]
            else:
                logging.warning(f"  No se encontraron archivos VIIRS para el {year}_{quarter}")
                viirs_mean_list = [np.nan] * len(gdf_h3)
            
            # --- CONSTRUIR DATAFRAME TABULAR ---
            df = pd.DataFrame({
                'h3_index': gdf_h3['h3_index'],
                'year': int(year),
                'quarter': quarter,
                'ndvi_mean': [s['mean'] for s in ndvi_stats],
                'ndbi_mean': [s['mean'] for s in ndbi_stats],
                'viirs_mean': viirs_mean_list
            })
            
            # --- INYECTAR EN POSTGRESQL ---
            mode = "replace" if first_file else "append"
            logging.info(f"  Subiendo a PostgreSQL {schema}.{table_name} ({mode})...")
            df.to_sql(table_name, con=engine, schema=schema, if_exists=mode, index=False)
            first_file = False
            
    logging.info("¡Proceso completado para todos los trimestres de Sentinel-2!")


def process_and_ingest_viirs():
    """
    Issue #24 -- Procesamiento de Noches VIIRS (Luces Nocturnas).

    Descarga cada composite mensual VIIRS (GeoTIFF de banda unica 'avg_rad',
    ya recortado a Tenerife por ingestion/satelite/viirs_upload_blob.py) desde
    Azure Blob Storage (bronce-raw/satelite/viirs/), calcula la radianza media
    por hexagono H3 con rasterstats y lo sube a bronze.viirs_stats.

    La malla H3 se lee de silver.silver_h3_grid en PostgreSQL en vez de un
    GeoJSON local (a diferencia de process_and_ingest_sentinel2) porque los
    GeoTIFF de VIIRS solo existen en Azure Blob en este entorno, no en disco.
    """
    load_dotenv()
    conn_str = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    if not conn_str:
        logging.error("Falta AZURE_STORAGE_CONNECTION_STRING en el .env")
        return

    from azure.storage.blob import BlobServiceClient

    engine = get_pg_engine()
    schema = "bronze"
    table_name = "bronze_viirs_stats"

    logging.info("Cargando malla H3 desde bronze.bronze_h3_grid (PostgreSQL)...")
    gdf_h3 = gpd.read_postgis(
        "SELECT h3_index, geometry FROM bronze.bronze_h3_grid",
        con=engine,
        geom_col="geometry",
    )

    blob_service = BlobServiceClient.from_connection_string(conn_str)
    container = blob_service.get_container_client(VIIRS_CONTAINER_NAME)

    tif_blobs = sorted(
        (b for b in container.list_blobs(name_starts_with=f"{VIIRS_BLOB_PREFIX}/") if b.name.endswith(".tif")),
        key=lambda b: b.name,
    )
    if not tif_blobs:
        logging.error(f"No se encontraron composites VIIRS en {VIIRS_CONTAINER_NAME}/{VIIRS_BLOB_PREFIX}/")
        return

    first_file = True
    gdf_h3_proj = None

    for blob in tif_blobs:
        match = re.search(r"(\d{4})_(\d{2})\.tif$", blob.name)
        if not match:
            continue
        year, month = int(match.group(1)), int(match.group(2))

        logging.info(f"=== Procesando VIIRS {year}-{month:02d} ({blob.name}) ===")
        raw_bytes = container.get_blob_client(blob.name).download_blob().readall()

        with rasterio.MemoryFile(raw_bytes) as memfile:
            with memfile.open() as src:
                if gdf_h3_proj is None or gdf_h3_proj.crs != src.crs:
                    gdf_h3_proj = gdf_h3.to_crs(src.crs)

                radiance_array = src.read(1)
                transform = src.transform

                # Limpieza: la banda avg_rad no deberia tener radiancia negativa
                # (ruido de sensor) ni valores absurdamente altos (glare/nodata).
                radiance_array = np.where(
                    (radiance_array >= 0) & (radiance_array < 1e5), radiance_array, np.nan
                )

                logging.info("  Calculando Zonal Stats VIIRS (radianza)...")
                viirs_stats = zonal_stats(
                    gdf_h3_proj, radiance_array, affine=transform, stats="mean", nodata=np.nan
                )

                df = pd.DataFrame(
                    {
                        "h3_index": gdf_h3_proj["h3_index"],
                        "anio": year,
                        "mes": month,
                        "radianza_media": [s["mean"] for s in viirs_stats],
                    }
                )
                # Issue #24: excluir 2020-2021 del modelo de regresion (caida COVID)
                df["incluir_en_modelo"] = ~df["anio"].isin(VIIRS_ANOS_EXCLUIR_MODELO)

                mode = "replace" if first_file else "append"
                logging.info(f"  Subiendo a PostgreSQL {schema}.{table_name} ({mode})...")
                df.to_sql(table_name, con=engine, schema=schema, if_exists=mode, index=False)
                first_file = False

    logging.info("¡Proceso VIIRS completado para todos los meses disponibles!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingesta de estadisticas zonales H3 desde rasters de satelite")
    parser.add_argument(
        "--source",
        choices=["sentinel2", "viirs", "all"],
        default="all",
        help="Que pipeline ejecutar (por defecto: all)",
    )
    args = parser.parse_args()

    if args.source in ("sentinel2", "all"):
        process_and_ingest_sentinel2()
    if args.source in ("viirs", "all"):
        process_and_ingest_viirs()
