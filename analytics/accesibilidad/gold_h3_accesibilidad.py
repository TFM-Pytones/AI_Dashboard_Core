"""
gold_h3_accesibilidad.py
=========================
Bloque 4 — Subtareas 4.1, 4.3, 4.4
Calcula los indicadores de accesibilidad territorial para cada hexágono H3 de Tenerife:

  4.1 → ORS Matrix: Tiempos exactos de conducción a los 6 destinos estratégicos
  4.3 → PostGIS:    Paradas de bus TITSA a ≤500m del centroide de cada hexágono
  4.4 → PostGIS:    Distancia al hospital/clínica más cercana

Output: gold.h3_accesibilidad (2.396 filas, una por hexágono H3)

Uso:
    python ingestion/gold/gold_h3_accesibilidad.py

Requisitos .env:
    AZURE_DB_HOST, AZURE_DB_USER, AZURE_DB_PASSWORD, AZURE_DB_NAME
    ORS_API_KEY    (https://openrouteservice.org/dev/#/signup — plan gratuito)

Librerías:
    pip install openrouteservice pandas psycopg2-binary sqlalchemy python-dotenv
"""

import os
import io
import time
import logging
from datetime import datetime
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from azure.storage.blob import BlobServiceClient

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
    "tfs":           [-16.5726, 28.0445],  # Aeropuerto Sur
    "tfn":           [-16.3413, 28.4827],  # Aeropuerto Norte
    "capital":       [-16.2519, 28.4700],  # Santa Cruz
    "polo_sur":      [-16.7356, 28.0805],  # Costa Adeje
    "polo_norte":    [-16.5488, 28.4148],  # Puerto de la Cruz
    "teide":         [-16.6214, 28.2547],  # Teleférico base
    "la_laguna":     [-16.3155, 28.4871],  # La Laguna
    "candelaria":    [-16.3683, 28.3516],  # Candelaria
    "los_gigantes":  [-16.8415, 28.2435],  # Acantilados Oeste
    "el_medano":     [-16.5366, 28.0461],  # El Médano
    "garachico":     [-16.7645, 28.3734],  # Garachico
    "anaga":         [-16.1573, 28.5660],  # Anaga (NE)
    "masca":         [-16.8344, 28.3197],  # Masca (NO)
    "vilaflor":      [-16.6377, 28.1582],  # Vilaflor (Centro-Sur)
    "la_orotava":    [-16.5227, 28.3903],  # La Orotava
    "guimar":        [-16.4088, 28.3078],  # Pirámides de Güímar
    "buenavista":    [-16.8897, 28.3722],  # Buenavista del Norte
    "arico":         [-16.4648, 28.1655]   # Poris de Abona / Arico
}


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
# Subtarea 4.1 — ORS Matrix: Tiempos de Conducción
# ============================================================
def calcular_tiempos_ors(df_h3: pd.DataFrame, ors_api_key: str) -> pd.DataFrame:
    """
    Envía 1 petición a la API Matrix de ORS por cada destino estratégico.
    2.396 orígenes × 1 destino = 2.396 pares por petición (< límite 3.500).
    Total = 6 peticiones  <<  500 peticiones/día del plan gratuito.

    La API devuelve tiempos en segundos; convertimos a minutos.
    Si un hexágono es inaccesible por carretera, ORS devuelve null → asignamos 999.
    """
    try:
        import openrouteservice
    except ImportError:
        raise ImportError(
            "Módulo 'openrouteservice' no instalado. Ejecuta:\n"
            "  pip install openrouteservice"
        )

    client = openrouteservice.Client(key=ors_api_key, base_url=ORS_BASE_URL)
    origenes = df_h3[["centroide_lon", "centroide_lat"]].values.tolist()
    n = len(origenes)
    logging.info(f"ORS Matrix: {n} hexágonos × {len(DESTINOS)} destinos = {n * len(DESTINOS)} pares")

    # Test de conectividad con 3 hexágonos antes de lanzar el batch completo
    logging.info("Prueba de conectividad (3 hexágonos → 1 destino)...")
    primer_destino = list(DESTINOS.values())[0]
    primer_nombre  = list(DESTINOS.keys())[0]
    try:
        test = client.distance_matrix(
            locations=origenes[:3] + [primer_destino],
            sources=list(range(3)),
            destinations=[3],
            profile="driving-car",
            metrics=["duration"],
        )
        val = test["durations"][0][0]
        tiempo_test = round(val / 60, 1) if val is not None else 999.0
        logging.info(f"  ✓ Test OK → Hexágono[0] → {primer_nombre}: {tiempo_test} min")
    except Exception as e:
        raise RuntimeError(
            f"Error en el test de conectividad ORS: {e}\n"
            "Verifica que ORS_API_KEY es válida y tienes conexión a internet."
        )

    resultados = {"h3_index": df_h3["h3_index"].tolist()}

    for nombre, coords_destino in DESTINOS.items():
        logging.info(f"  Petición Matrix: todos los hexágonos → {nombre}...")

        response = None
        for intento in range(3):
            try:
                response = client.distance_matrix(
                    locations=origenes + [coords_destino],
                    sources=list(range(n)),
                    destinations=[n],
                    profile="driving-car",
                    metrics=["duration"],
                )
                break
            except Exception as e:
                if intento < 2:
                    espera = 15 * (intento + 1)
                    logging.warning(f"    Intento {intento+1} fallido ({e}). Reintentando en {espera}s...")
                    time.sleep(espera)
                else:
                    logging.error(f"    Destino '{nombre}' fallido definitivamente. Asignando 999 min.")

        if response:
            tiempos = [
                round(row[0] / 60, 1) if (row and row[0] is not None) else 999.0
                for row in response["durations"]
            ]
        else:
            tiempos = [999.0] * n

        resultados[f"tiempo_{nombre}_min"] = tiempos
        validos = [t for t in tiempos if t < 999]
        media   = round(sum(validos) / len(validos), 1) if validos else 0
        logging.info(f"    ✓ {nombre}: media={media} min | inaccesibles={n - len(validos)}")

        time.sleep(1.5)  # Pausa cortés entre peticiones

    df_acc = pd.DataFrame(resultados)

    # Columna derivada: aeropuerto más cercano
    df_acc["tiempo_aeropuerto_min"] = df_acc[["tiempo_tfs_min", "tiempo_tfn_min"]].min(axis=1)
    df_acc["aeropuerto_mas_cercano"] = df_acc.apply(
        lambda r: "TFS" if r["tiempo_tfs_min"] <= r["tiempo_tfn_min"] else "TFN",
        axis=1
    )

    validos_aer = df_acc[df_acc["tiempo_aeropuerto_min"] < 999]["tiempo_aeropuerto_min"]
    logging.info(
        f"ORS Matrix finalizado:\n"
        f"  Tiempo medio al aeropuerto más cercano: {validos_aer.mean():.1f} min\n"
        f"  Hexágonos inaccesibles por carretera:   {(df_acc['tiempo_aeropuerto_min'] == 999).sum()}"
    )
    return df_acc


# ============================================================
# Subtarea 4.3 — Paradas de Bus TITSA (múltiples umbrales)
# ============================================================
def calcular_paradas_bus(engine) -> pd.DataFrame:
    """
    Para cada hexágono, cuenta paradas de autobús TITSA a 3 umbrales:
      - 200m  (ultra-urbano, ~3 min a pie)
      - 500m  (estándar, ~7 min a pie)
      - 1000m (periurbano, ~12 min a pie)
    y calcula la distancia real a la parada más cercana (NULL si no hay
    ninguna en toda la isla — zonas sin servicio TITSA).
    Usa ::geography para que la distancia sea en metros reales, no grados.
    """
    logging.info("Calculando accesibilidad peatonal a paradas de bus (GTFS) — 3 umbrales...")

    sql = text("""
        WITH paradas_cercanas AS (
            -- Para cada hexágono, unir con todas las paradas de la isla
            -- y calcular la distancia real para obtener la más cercana
            SELECT
                h.h3_index,
                ST_Distance(
                    ST_SetSRID(ST_Centroid(h.geometry), 4326)::geography,
                    p.geometry::geography
                ) AS dist_m
            FROM silver.silver_h3_grid h
            CROSS JOIN silver.silver_gtfs_paradas p
            WHERE p.geometry IS NOT NULL
        )
        SELECT
            h.h3_index,
            -- Umbral 200m
            COUNT(DISTINCT CASE WHEN pc.dist_m <= 200 THEN pc.dist_m END)  AS n_paradas_bus_200m,
            -- Umbral 500m
            COUNT(DISTINCT CASE WHEN pc.dist_m <= 500 THEN pc.dist_m END)  AS n_paradas_bus_500m,
            -- Umbral 1000m
            COUNT(DISTINCT CASE WHEN pc.dist_m <= 1000 THEN pc.dist_m END) AS n_paradas_bus_1000m,
            -- Distancia real a la más cercana (NULL si no hay ninguna parada en la isla)
            ROUND(MIN(pc.dist_m)::numeric, 0) AS dist_parada_cercana_m
        FROM silver.silver_h3_grid h
        LEFT JOIN paradas_cercanas pc ON pc.h3_index = h.h3_index
        GROUP BY h.h3_index
    """)

    with engine.connect() as conn:
        df = pd.read_sql(sql, conn)

    sin_servicio = df["dist_parada_cercana_m"].isna().sum()
    logging.info(
        f"Paradas de bus calculadas (3 umbrales):\n"
        f"  Hexágonos con parada a ≤200m:  {(df['n_paradas_bus_200m'] > 0).sum()} "
        f"({100*(df['n_paradas_bus_200m'] > 0).mean():.0f}%)\n"
        f"  Hexágonos con parada a ≤500m:  {(df['n_paradas_bus_500m'] > 0).sum()} "
        f"({100*(df['n_paradas_bus_500m'] > 0).mean():.0f}%)\n"
        f"  Hexágonos con parada a ≤1000m: {(df['n_paradas_bus_1000m'] > 0).sum()} "
        f"({100*(df['n_paradas_bus_1000m'] > 0).mean():.0f}%)\n"
        f"  Hexágonos SIN ninguna parada TITSA (NULL): {sin_servicio} "
        f"({100*sin_servicio/len(df):.0f}%)"
    )
    return df[["h3_index", "n_paradas_bus_200m", "n_paradas_bus_500m",
               "n_paradas_bus_1000m", "dist_parada_cercana_m"]]


# ============================================================
# Subtarea 4.4 — Distancia al Hospital más Cercano (PostGIS)
# ============================================================
def calcular_dist_hospital(engine) -> pd.DataFrame:
    """
    Calcula la distancia en línea recta (km) desde el centroide de cada hexágono
    al centro hospitalario/urgencias más cercano según POIs de OpenStreetMap.
    Usa ::geography para distancias en metros reales.
    """
    logging.info("Calculando distancia al hospital más cercano (silver.silver_osm_pois)...")

    # Verificar que hay hospitales en la tabla
    with engine.connect() as conn:
        n_hosp = conn.execute(text(
            "SELECT COUNT(*) FROM silver.silver_osm_pois "
            "WHERE LOWER(poi_type) IN ('hospital','clinic','doctors','healthcare') "
            "  AND geometry IS NOT NULL"
        )).scalar()

    if n_hosp == 0:
        logging.warning(
            "No se encontraron hospitales en silver.silver_osm_pois. "
            "Comprueba que poi_type contiene los valores esperados. "
            "La columna dist_hospital_km se omitirá de la tabla final."
        )
        return pd.DataFrame()

    logging.info(f"  Hospitales/clínicas OSM encontrados: {n_hosp}")

    sql = text("""
        WITH hospitales AS (
            SELECT geometry
            FROM silver.silver_osm_pois
            WHERE LOWER(poi_type) IN ('hospital', 'clinic', 'doctors', 'healthcare')
              AND geometry IS NOT NULL
        )
        SELECT
            h.h3_index,
            ROUND(
                MIN(ST_Distance(
                    ST_SetSRID(ST_Centroid(h.geometry), 4326)::geography,
                    hosp.geometry::geography
                ))::numeric / 1000,
            2) AS dist_hospital_km
        FROM silver.silver_h3_grid h
        CROSS JOIN hospitales hosp
        GROUP BY h.h3_index
    """)

    with engine.connect() as conn:
        df = pd.read_sql(sql, conn)

    logging.info(
        f"Distancias a hospitales calculadas:\n"
        f"  Distancia media: {df['dist_hospital_km'].mean():.1f} km\n"
        f"  Distancia máxima: {df['dist_hospital_km'].max():.1f} km\n"
        f"  Hexágonos a >20 km de hospital: {(df['dist_hospital_km'] > 20).sum()}"
    )
    return df


# ============================================================
# Subtarea 4.5 — Distancia a la Costa (Litoralidad)
# ============================================================
def calcular_dist_costa(engine) -> pd.DataFrame:
    """
    Calcula la distancia en línea recta (km) desde el centroide de cada hexágono
    hasta la línea de costa (ST_Boundary de silver_limites_municipales).
    """
    logging.info("Calculando distancia a la costa (silver_limites_municipales)...")

    sql = text("""
        WITH linea_costa AS (
            SELECT ST_Boundary(ST_Union(geometry)) AS geom
            FROM silver.silver_limites_municipales
        )
        SELECT
            h.h3_index,
            ROUND(
                ST_Distance(
                    ST_SetSRID(ST_Centroid(h.geometry), 4326)::geography,
                    lc.geom::geography
                )::numeric / 1000,
            2) AS dist_costa_km
        FROM silver.silver_h3_grid h
        CROSS JOIN linea_costa lc
    """)

    with engine.connect() as conn:
        df = pd.read_sql(sql, conn)

    logging.info(
        f"Distancias a la costa calculadas:\n"
        f"  Distancia media: {df['dist_costa_km'].mean():.1f} km\n"
        f"  Distancia máxima: {df['dist_costa_km'].max():.1f} km"
    )
    return df



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
            "2. Copia tu clave y añádela al .env:\n"
            "   ORS_API_KEY=tu_clave_aqui\n"
            "3. Vuelve a ejecutar este script."
        )

    engine = get_engine()
    ensure_gold_schema(engine)

    # Cargar centroides de la malla H3
    logging.info("Cargando malla H3 desde silver.silver_h3_grid...")
    with engine.connect() as conn:
        df_h3 = pd.read_sql(
            text("SELECT h3_index, ST_X(ST_Centroid(geometry)) AS centroide_lon, ST_Y(ST_Centroid(geometry)) AS centroide_lat FROM silver.silver_h3_grid ORDER BY h3_index"),
            conn
        )
    logging.info(f"Malla H3 cargada: {len(df_h3)} hexágonos.")

    # ── 4.1 ORS Matrix ────────────────────────────────────────────────────────
    df_acc = calcular_tiempos_ors(df_h3, ors_api_key)

    # ── 4.3 Paradas de bus ────────────────────────────────────────────────────
    try:
        df_bus = calcular_paradas_bus(engine)
        df_acc = df_acc.merge(df_bus, on="h3_index", how="left")
    except Exception as e:
        logging.error(f"Subtarea 4.3 fallida: {e}")

    # ── 4.4 Hospitales ────────────────────────────────────────────────────────
    try:
        df_hosp = calcular_dist_hospital(engine)
        if not df_hosp.empty:
            df_acc = df_acc.merge(df_hosp, on="h3_index", how="left")
    except Exception as e:
        logging.error(f"Subtarea 4.4 fallida: {e}")

    # ── 4.5 Costa ─────────────────────────────────────────────────────────────
    try:
        df_costa = calcular_dist_costa(engine)
        if not df_costa.empty:
            df_acc = df_acc.merge(df_costa, on="h3_index", how="left")
    except Exception as e:
        logging.error(f"Subtarea 4.5 fallida: {e}")

    # ── Subir a gold.gold_h3_accesibilidad ────────────────────────────────────
    logging.info(f"Subiendo {len(df_acc)} filas a gold.gold_h3_accesibilidad...")
    df_acc.to_sql(
        name="gold_h3_accesibilidad",
        con=engine,
        schema="gold",
        if_exists="replace",
        index=False,
        method="multi",
        chunksize=500,
    )

    with engine.connect() as conn:
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_gold_h3_accesibilidad_h3 "
            "ON gold.gold_h3_accesibilidad (h3_index);"
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
            
            blob_name = f"gold/accesibilidad/gold_h3_accesibilidad_{datetime.now().strftime('%Y%m%d')}.parquet"
            blob_client = blob_service_client.get_blob_client(container="bronce-raw", blob=blob_name)
            
            buffer = io.BytesIO()
            df_acc.to_parquet(buffer, index=False, compression="snappy")
            buffer.seek(0)
            blob_client.upload_blob(buffer, overwrite=True)
            logging.info(f"Backup guardado con éxito en Azure Blob Storage: {blob_name}")
        else:
            logging.warning("No se encontró AZURE_STORAGE_CONNECTION_STRING. Se omite el backup en Blob Storage.")
    except Exception as e:
        logging.error(f"Error al subir backup a Azure Blob: {e}")

    logging.info(
        f"\n{'='*60}\n"
        f"BLOQUE 4 — Subtareas 4.1, 4.3, 4.4, 4.5 COMPLETADAS\n"
        f"============================================================\n"
        f"  Tabla:    gold.gold_h3_accesibilidad\n"
        f"  Filas:    {len(df_acc)}\n"
        f"  Columnas: {list(df_acc.columns)}\n"
        f"============================================================"
    )


if __name__ == "__main__":
    main()
