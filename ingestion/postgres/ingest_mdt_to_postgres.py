import os
import glob
import numpy as np
import pandas as pd
import geopandas as gpd
import rasterio
from rasterstats import zonal_stats
from dotenv import load_dotenv
from sqlalchemy import create_engine
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
        raise ValueError("Faltan variables de entorno para PostgreSQL")
        
    connection_string = f"postgresql://{PG_USER}:{PG_PASS}@{PG_HOST}:{PG_PORT}/{PG_DB}"
    return create_engine(connection_string, connect_args={'sslmode': 'require'})

def derive_slope_aspect_hillshade(elevation, pixel_size_m=25.0):
    """
    Calcula Pendiente (Slope), Orientación (Aspect) e Iluminación (Hillshade)
    directamente a partir del array de elevación usando el método de Horn (1981).
    
    Args:
        elevation:    Array 2D de elevación en metros (con NaN donde hay NoData).
        pixel_size_m: Tamaño de celda en metros (25m para MDT25).
    Returns:
        slope_deg:    Pendiente en grados [0°-90°].
        aspect_deg:   Orientación en grados [0°-360°] (Norte=0°, sentido horario).
        hillshade:    Iluminación [0-255] con sol a azimut=315° (NW), elevación=45°.
    """
    # Gradientes en X e Y (filas/columnas del raster)
    dz_dy, dz_dx = np.gradient(np.where(np.isnan(elevation), 0, elevation), pixel_size_m)
    
    # Propagamos los NaN del original a los derivados
    mask_nan = np.isnan(elevation)
    dz_dx = np.where(mask_nan, np.nan, dz_dx)
    dz_dy = np.where(mask_nan, np.nan, dz_dy)
    
    # --- SLOPE (Pendiente en grados) ---
    slope_rad = np.arctan(np.sqrt(dz_dx**2 + dz_dy**2))
    slope_deg = np.degrees(slope_rad)
    
    # --- ASPECT (Orientación en grados, Norte=0°, sentido horario) ---
    # atan2 devuelve ángulo respecto al eje X (Este). Lo convertimos a Norte-sentido horario.
    aspect_math = np.degrees(np.arctan2(-dz_dy, dz_dx))
    aspect_deg  = np.where(aspect_math < 0, 90 - aspect_math, 90 - aspect_math)
    aspect_deg  = np.where(aspect_deg > 360, aspect_deg - 360, aspect_deg)
    aspect_deg  = np.where(mask_nan, np.nan, aspect_deg)
    
    # --- HILLSHADE (sol a azimut 315° NW, elevación 45°) ---
    # Útil para el Dashboard para dar sensación de relieve visual
    az_rad = np.radians(315)
    alt_rad = np.radians(45)
    hillshade_raw = (
        np.cos(alt_rad) * np.cos(slope_rad) +
        np.sin(alt_rad) * np.sin(slope_rad) * np.cos(az_rad - np.radians(aspect_deg))
    )
    hillshade = np.clip(hillshade_raw * 255, 0, 255)
    hillshade  = np.where(mask_nan, np.nan, hillshade)
    
    return slope_deg, aspect_deg, hillshade

def process_and_ingest():
    engine = get_pg_engine()
    schema = "bronze"
    table_name = "mdt_stats"
    
    # --- 1. Cargar Malla H3 ---
    h3_path = os.path.join("data", "bronce", "spatial", "h3", "h3_grid_tenerife_res8.geojson")
    if not os.path.exists(h3_path):
        logging.error("No se encontró el archivo H3.")
        return
    gdf_h3 = gpd.read_file(h3_path)
    logging.info(f"Malla H3 cargada: {len(gdf_h3)} hexágonos")
    
    # --- 2. Buscar el TIF en data/bronce/mdt/ (archivo único de GRAFCAN para toda la isla)
    tif_dir = os.path.join("data", "bronce", "mdt")
    tif_files = glob.glob(os.path.join(tif_dir, "*.tif"))
    
    if not tif_files:
        logging.error(f"No se encontró ningún .tif en {tif_dir}")
        logging.error("Asegúrate de copiar el archivo de GRAFCAN (136_MDT25_TF.tif + .tfw) en esa carpeta.")
        return
    
    if len(tif_files) > 1:
        logging.warning(f"Se encontraron {len(tif_files)} TIFs. Se usará: {tif_files[0]}")
    
    tif_path = tif_files[0]
    logging.info(f"Abriendo MDT: {tif_path}")
    
    # --- 3. Leer el raster de elevación ---
    with rasterio.open(tif_path) as src:
        tif_crs   = src.crs
        nodata_val = src.nodata
        out_trans = src.transform
        pixel_size = src.res[0]  # Tamaño de celda en unidades del CRS (metros si es UTM)
        elevation  = src.read(1).astype(np.float32)
        logging.info(f"CRS: {tif_crs}  |  NoData: {nodata_val}  |  Resolución: {pixel_size:.1f}m")
        logging.info(f"Tamaño: {src.width}x{src.height} píxeles  |  Bounds: {src.bounds}")
    
    # Enmascarar NoData → NaN
    if nodata_val is not None:
        elevation = np.where(elevation == nodata_val, np.nan, elevation)
    elevation = np.where(elevation < -500, np.nan, elevation)
    elevation = np.where(elevation > 4000, np.nan, elevation)
    
    valid_pct = np.sum(~np.isnan(elevation)) / elevation.size * 100
    logging.info(f"Píxeles de tierra válidos: {valid_pct:.1f}%")
    
    # --- 4. Derivar Slope, Aspect y Hillshade a partir de la Elevación ---
    logging.info("Calculando Slope, Aspect y Hillshade desde el MDT...")
    slope, aspect, hillshade = derive_slope_aspect_hillshade(elevation, pixel_size_m=pixel_size)
    
    # --- 5. Reproyectar H3 al CRS del MDT ---
    h3_gdf = gdf_h3.copy()
    if tif_crs and str(h3_gdf.crs) != str(tif_crs):
        logging.info(f"Reproyectando H3: {h3_gdf.crs} → {tif_crs}")
        h3_gdf = h3_gdf.to_crs(tif_crs)
    
    # --- 6. Zonal Stats para cada capa ---
    capas = {
        "elevation": elevation,
        "slope":     slope,
        "aspect":    aspect,
        "hillshade": hillshade,
    }
    
    resultados = {h3_idx: {} for h3_idx in h3_gdf['h3_index']}
    
    for nombre, array in capas.items():
        logging.info(f"Calculando Estadísticas Zonales para '{nombre}'...")
        stats = zonal_stats(h3_gdf, array, affine=out_trans, stats=["mean", "min", "max"], nodata=np.nan)
        for i, row in h3_gdf.iterrows():
            resultados[row['h3_index']][f'{nombre}_mean'] = stats[i]['mean']
            resultados[row['h3_index']][f'{nombre}_min']  = stats[i]['min']
            resultados[row['h3_index']][f'{nombre}_max']  = stats[i]['max']
        validos = sum(1 for v in resultados.values() if v.get(f'{nombre}_mean') is not None)
        logging.info(f"  -> Hexágonos válidos para {nombre}: {validos}/{len(h3_gdf)}")
    
    # --- 7. Construir DataFrame y subir a PostgreSQL ---
    df = pd.DataFrame([
        {'h3_index': h3_idx, **vals}
        for h3_idx, vals in resultados.items()
    ])
    
    logging.info(f"\nCobertura final:")
    logging.info(f"  Hexágonos con elevación: {df['elevation_mean'].notna().sum()}/{len(df)}")
    logging.info(f"  Elevación media Tenerife: {df['elevation_mean'].mean():.0f} m")
    logging.info(f"  Elevación máxima (hex): {df['elevation_max'].max():.0f} m")
    logging.info(f"  Pendiente media: {df['slope_mean'].mean():.1f}°")
    
    logging.info(f"\nSubiendo a PostgreSQL {schema}.{table_name}...")
    df.to_sql(table_name, con=engine, schema=schema, if_exists="replace", index=False)
    logging.info("🎉 ¡MDT completado: Elevation + Slope + Aspect + Hillshade por hexágono H3!")

if __name__ == "__main__":
    process_and_ingest()
