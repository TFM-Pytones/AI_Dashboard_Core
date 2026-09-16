"""
gold_isocronas_visuales.py
===========================
Bloque 4 — Subtarea 4.2
Genera polígonos de isócronas (manchas de color) para los 6 destinos
estratégicos a 15, 30, 45 y 60 minutos en coche.
Son capas puramente visuales para el Dashboard (no entran en el modelo MGWR).

Output: gold.isocronas_visuales (72 filas: 18 destinos × 4 rangos temporales)

Uso:
    python ingestion/gold/gold_isocronas_visuales.py

Requisitos .env:
    AZURE_DB_HOST, AZURE_DB_USER, AZURE_DB_PASSWORD, AZURE_DB_NAME
    ORS_API_KEY    (https://openrouteservice.org/dev/#/signup — plan gratuito)

Librerías:
    pip install openrouteservice geopandas shapely psycopg2-binary sqlalchemy python-dotenv
"""

import os
import io
import time
import logging
from datetime import datetime
import pandas as pd
from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient
from sqlalchemy import create_engine, text

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# ============================================================
# ORS — Nueva URL base (api.openrouteservice.org deprecada el 24/08/2026)
# ============================================================
ORS_BASE_URL = "https://api.heigit.org/openrouteservice"

# ============================================================
# Destinos estratégicos [lon, lat] — ORS usa longitud primero
# ============================================================
DESTINOS = {
    "tfs":           {"coords": [-16.5726, 28.0445], "label": "Aeropuerto Sur (TFS)"},
    "tfn":           {"coords": [-16.3413, 28.4827], "label": "Aeropuerto Norte (TFN)"},
    "capital":       {"coords": [-16.2519, 28.4700], "label": "Santa Cruz (Puerto)"},
    "extremo_sur":   {"coords": [-16.7356, 28.0805], "label": "Costa Adeje (centro)"},
    "extremo_norte": {"coords": [-16.5488, 28.4148], "label": "Puerto de la Cruz (centro)"},
    "teide":         {"coords": [-16.6214, 28.2547], "label": "Teleférico del Teide (Base)"},
    "la_laguna":     {"coords": [-16.3155, 28.4871], "label": "La Laguna (Histórico)"},
    "candelaria":    {"coords": [-16.3683, 28.3516], "label": "Basílica Candelaria"},
    "los_gigantes":  {"coords": [-16.8415, 28.2435], "label": "Acantilados Oeste"},
    "el_medano":     {"coords": [-16.5366, 28.0461], "label": "El Médano (Surf)"},
    "garachico":     {"coords": [-16.7645, 28.3734], "label": "Garachico (Pueblo)"},
    "anaga":         {"coords": [-16.1573, 28.5660], "label": "Parque Rural de Anaga"},
    "masca":         {"coords": [-16.8344, 28.3197], "label": "Masca (Teno)"},
    "vilaflor":      {"coords": [-16.6377, 28.1582], "label": "Vilaflor (Interior Sur)"},
    "la_orotava":    {"coords": [-16.5227, 28.3903], "label": "La Orotava (Valle Norte)"},
    "guimar":        {"coords": [-16.4088, 28.3078], "label": "Pirámides de Güímar"},
    "buenavista":    {"coords": [-16.8897, 28.3722], "label": "Buenavista del Norte"},
    "arico":         {"coords": [-16.4648, 28.1655], "label": "Poris de Abona / Arico"}
}

# Rangos en minutos. Se calculan en ORDEN DECRECIENTE para renderizar correctamente
# en el Dashboard (los anillos interiores tapan a los exteriores)
RANGOS_MIN = [60, 45, 30, 15]


# ============================================================
# Conexión a PostgreSQL
# ============================================================
def get_engine():
    load_dotenv()
    user = os.getenv("AZURE_DB_USER")
    pw   = os.getenv("AZURE_DB_PASSWORD")
    host = os.getenv("AZURE_DB_HOST")
    port = os.getenv("AZURE_DB_PORT", "5432")
    db   = os.getenv("AZURE_DB_NAME")

    if not all([user, pw, host, db]):
        raise ValueError(
            "Faltan variables de entorno para PostgreSQL.\n"
            "Comprueba: AZURE_DB_USER, AZURE_DB_PASSWORD, AZURE_DB_HOST, AZURE_DB_NAME"
        )
    return create_engine(
        f"postgresql://{user}:{pw}@{host}:{port}/{db}",
        connect_args={"sslmode": "require"}
    )


def ensure_gold_schema(engine):
    with engine.connect() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS gold;"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
        conn.commit()
    logging.info("Esquema 'gold' y extensión PostGIS verificados.")


# ============================================================
# Subtarea 4.2 — Isócronas Visuales (ORS Isochrones API)
# ============================================================
def calcular_isocronas(ors_api_key: str):
    """
    Hace 1 petición a la API Isochrones de ORS por cada destino estratégico.
    Cada petición devuelve los 4 polígonos (15/30/45/60 min) de ese destino.
    Total: 6 peticiones.

    Devuelve un GeoDataFrame con 24 filas y columnas:
      destino, destino_label, rango_min, geometry (Polygon, EPSG:4326)
    """
    try:
        import openrouteservice
        import geopandas as gpd
        from shapely.geometry import shape
    except ImportError:
        raise ImportError(
            "Módulos no instalados. Ejecuta:\n"
            "  pip install openrouteservice geopandas shapely"
        )

    client = openrouteservice.Client(key=ors_api_key, base_url=ORS_BASE_URL)
    filas = []

    for nombre, info in DESTINOS.items():
        coords   = info["coords"]
        label    = info["label"]
        rangos_s = [m * 60 for m in RANGOS_MIN]  # ORS acepta segundos

        logging.info(f"  Calculando isócronas para: {label} ({nombre})...")

        response = None
        for intento in range(3):
            try:
                # Usamos client.request directamente para soportar avoid_features: ferries (rutas de barco)
                params = {
                    "locations": [coords],
                    "profile": "driving-car",
                    "range": rangos_s,
                    "range_type": "time",
                    "smoothing": 0.25,  # Suavizado leve para mejor aspecto visual
                    "options": {"avoid_features": ["ferries"]},
                }
                response = client.request("/v2/isochrones/driving-car", {}, post_json=params)
                break
            except Exception as e:
                if intento < 2:
                    espera = 10 * (intento + 1)
                    logging.warning(f"    Intento {intento+1} fallido ({e}). Reintentando en {espera}s...")
                    time.sleep(espera)
                else:
                    logging.error(f"    Destino '{nombre}' fallido definitivamente: {e}")

        if response is None:
            logging.error(f"  [ERROR] {nombre}: no se generaron isócronas")
            continue

        for feature in response.get("features", []):
            rango_s   = feature["properties"]["value"]
            rango_min = rango_s // 60
            geom      = shape(feature["geometry"])
            filas.append({
                "destino":       nombre,
                "destino_label": label,
                "rango_min":     rango_min,
                "geometry":      geom,
            })
            logging.info(f"    [OK] {nombre} — {rango_min} min: {geom.geom_type}")

        time.sleep(1.5)  # Pausa cortés entre peticiones

    if not filas:
        raise RuntimeError(
            "No se generaron isócronas para ningún destino. "
            "Revisa la ORS_API_KEY y la conexión a internet."
        )

    gdf = gpd.GeoDataFrame(filas, geometry="geometry", crs=4326)

    logging.info(
        f"\nIsócronas generadas:\n"
        f"  Total polígonos: {len(gdf)}\n"
        f"  Destinos:        {gdf['destino'].nunique()}\n"
        f"  Rangos (min):    {sorted(gdf['rango_min'].unique())}"
    )
    return gdf


# ============================================================
# Main
# ============================================================
def main():
    load_dotenv()

    ors_api_key = os.getenv("ORS_API_KEY")
    if not ors_api_key:
        raise ValueError(
            "ORS_API_KEY no encontrada en el archivo .env.\n"
            "1. Regístrate en https://openrouteservice.org/dev/#/signup (plan gratuito)\n"
            "2. Añade al .env:\n"
            "   ORS_API_KEY=tu_clave_aqui\n"
            "3. Vuelve a ejecutar este script."
        )

    try:
        import geopandas as gpd
    except ImportError:
        raise ImportError("Instala geopandas: pip install geopandas")

    engine = get_engine()
    ensure_gold_schema(engine)

    # ── Calcular isócronas ────────────────────────────────────────────────────
    logging.info(f"Calculando isócronas para {len(DESTINOS)} destinos × {len(RANGOS_MIN)} rangos...")
    gdf = calcular_isocronas(ors_api_key)

    # ── Recortar con el contorno insular (elimina rutas marítimas y salientes al mar) ──
    logging.info("Recortando isócronas contra el contorno insular (silver.silver_limites_municipales)...")
    try:
        isla_gdf = gpd.read_postgis(
            "SELECT ST_Union(geometry) AS geometry FROM silver.silver_limites_municipales",
            con=engine,
            geom_col="geometry"
        )
        if not isla_gdf.empty and isla_gdf.geometry.iloc[0] is not None:
            gdf = gpd.overlay(gdf, isla_gdf, how="intersection")
            logging.info(f"Isócronas recortadas a la isla con éxito: {len(gdf)} registros.")
    except Exception as e:
        logging.warning(f"No se pudo recortar con silver.silver_limites_municipales: {e}")

    # ── Subir a gold.gold_isocronas_visuales ──────────────────────────────────
    logging.info(f"Subiendo {len(gdf)} polígonos a gold.gold_isocronas_visuales...")
    gdf.to_postgis(
        name="gold_isocronas_visuales",
        con=engine,
        schema="gold",
        if_exists="replace",
        index=False,
    )

    # Índice GiST para queries espaciales rápidas desde el Dashboard
    with engine.connect() as conn:
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_isocronas_geom "
            "ON gold.gold_isocronas_visuales USING GIST (geometry);"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_isocronas_destino "
            "ON gold.gold_isocronas_visuales (destino);"
        ))
        conn.commit()

    # ── Backup en Azure Blob Storage (Parquet) ────────────────────────────────
    try:
        conn_str = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
        if conn_str:
            conn_str = conn_str.strip('"').strip("'")
            if "AccountName=" not in conn_str and "DefaultEndpointsProtocol=" not in conn_str:
                conn_str = f"DefaultEndpointsProtocol=https;AccountName=datalaketfmtenerife;AccountKey={conn_str};EndpointSuffix=core.windows.net"
            blob_service_client = BlobServiceClient.from_connection_string(conn_str)
            
            blob_name = f"gold/accesibilidad/isocronas_visuales_{datetime.now().strftime('%Y%m%d')}.parquet"
            blob_client = blob_service_client.get_blob_client(container="bronce-raw", blob=blob_name)
            
            buffer = io.BytesIO()
            # pandas to_parquet soporta geometrías si pyarrow está instalado,
            # pero por si acaso, lo guardamos como WKT para asegurar compatibilidad universal
            gdf_backup = gdf.copy()
            gdf_backup["geometry"] = gdf_backup["geometry"].apply(lambda geom: geom.wkt)
            pd.DataFrame(gdf_backup).to_parquet(buffer, index=False, compression="snappy")
            
            buffer.seek(0)
            blob_client.upload_blob(buffer, overwrite=True)
            logging.info(f"Backup guardado con éxito en Azure Blob Storage: {blob_name}")
        else:
            logging.warning("No se encontró AZURE_STORAGE_CONNECTION_STRING. Se omite el backup en Blob Storage.")
    except Exception as e:
        logging.error(f"Error al subir backup a Azure Blob: {e}")

    # ── Resumen final ─────────────────────────────────────────────────────────
    logging.info(
        f"\n{'='*60}\n"
        f"BLOQUE 4 — Subtarea 4.2 COMPLETADA\n"
        f"{'='*60}\n"
        f"  Tabla:    gold.isocronas_visuales\n"
        f"  Filas:    {len(gdf)}\n"
        f"  Uso en el Dashboard: capa toggleable por destino y rango\n"
        f"  Columnas: destino, destino_label, rango_min, geometry\n"
        f"\n"
        f"  Destinos calculados:\n"
    )
    for nombre, info in DESTINOS.items():
        n_poligonos = len(gdf[gdf["destino"] == nombre])
        status = "OK" if n_poligonos == len(RANGOS_MIN) else f"Aviso: solo {n_poligonos}"
        logging.info(f"    {status}  {nombre}: {info['label']}")

    logging.info(f"{'='*60}")


if __name__ == "__main__":
    main()