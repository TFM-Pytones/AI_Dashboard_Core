import os
import sys
import time
import pandas as pd
import geopandas as gpd
import psycopg2
from psycopg2.extras import execute_values
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

current_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.abspath(os.path.join(current_dir, "..", ".env"))
load_dotenv(env_path, override=True)

import csv
from io import StringIO

# Configuración de conexiones
neon_conn_str = os.getenv("DB_URL")
azure_conn_str = os.getenv("AZURE_DB_URL")

if not neon_conn_str or not azure_conn_str:
    print("[ERROR] Falta DB_URL o AZURE_DB_URL en el archivo .env")
    sys.exit(1)

# Tablas a migrar: (nombre_tabla, es_espacial)
tables_to_migrate = [
    ("limites_municipales", True),
    ("zonas_turisticas", True),
    ("gtfs_paradas", True),
    ("gtfs_rutas", True),
    ("gtfs_calendario", False),
    ("gtfs_calendario_excepciones", False),
    ("gtfs_rutas_atributos", False),
    ("gtfs_viajes", False),
    ("sentiment_results", False),
    ("aspect_results", False),
    ("gtfs_horarios", False)  # La procesamos al final por ser muy grande
]

def psql_insert_copy(table, conn, keys, data_iter):
    """
    Método optimizado para subir DataFrames a PostgreSQL utilizando COPY de forma directa.
    Es hasta 100 veces más rápido que los inserts tradicionales de Pandas.
    """
    dbapi_conn = conn.connection
    with dbapi_conn.cursor() as cur:
        s_buf = StringIO()
        writer = csv.writer(s_buf)
        writer.writerows(data_iter)
        s_buf.seek(0)

        columns = ', '.join([f'"{k}"' for k in keys])
        if table.schema:
            table_name = f'"{table.schema}"."{table.name}"'
        else:
            table_name = f'"{table.name}"'

        sql = f"COPY {table_name} ({columns}) FROM STDIN WITH CSV"
        cur.copy_expert(sql=sql, file=s_buf)

def main():
    print("=======================================================")
    # 1. Habilitar PostGIS en la base de datos de Azure
    print("Conectando a Azure Database para habilitar PostGIS...")
    try:
        azure_conn = psycopg2.connect(azure_conn_str)
        with azure_conn.cursor() as cur:
            try:
                cur.execute("CREATE EXTENSION IF NOT EXISTS postgis;")
                azure_conn.commit()
                print("  -> Extensión 'postgis' habilitada con éxito.")
            except psycopg2.Error as e:
                azure_conn.rollback()
                if "not allow-listed" in str(e) or "azure.extensions" in str(e):
                    print("\n[AVISO CRÍTICO] La extensión 'postgis' no está permitida en tu base de datos de Azure.")
                    print("Por favor, sigue estos pasos rápidos en el Portal de Azure para habilitarla:")
                    print("  1. Entra a tu PostgreSQL 'db-tfm-tenerife' en el portal de Azure.")
                    print("  2. En el menú de la izquierda, entra a 'Parámetros del servidor' (Server parameters).")
                    print("  3. Busca el parámetro: 'azure.extensions'.")
                    print("  4. Marca/selecciona 'POSTGIS' en la lista de extensiones permitidas.")
                    print("  5. Haz clic en 'Guardar' (Save) arriba.")
                    print("  6. Espera 1 minuto y vuelve a ejecutar este script de migración.\n")
                    sys.exit(1)
                else:
                    raise e
            
            cur.execute("CREATE SCHEMA IF NOT EXISTS silver;")
            azure_conn.commit()
            print("  -> Esquema 'silver' listo en Azure.")
        azure_conn.close()
    except Exception as e:
        print(f"[ERROR] No se pudo habilitar PostGIS o crear el esquema 'silver' en Azure: {e}")
        sys.exit(1)

    # Crear engines de SQLAlchemy para Pandas/GeoPandas
    neon_engine = create_engine(neon_conn_str)
    azure_engine = create_engine(azure_conn_str)

    # 2. Iniciar migración de tablas
    for table_name, is_spatial in tables_to_migrate:
        print(f"\nMigrando tabla: {table_name} (Espacial: {is_spatial})...")
        start_time = time.time()

        if is_spatial:
            try:
                # Cargar GeoDataFrame desde Neon (EPSG:32628 ya estandarizado)
                print(f"  -> Leyendo de Neon (processed_data.{table_name})...")
                gdf = gpd.read_postgis(
                    f"SELECT * FROM processed_data.{table_name}",
                    neon_engine,
                    geom_col="geometry",
                    crs="EPSG:32628"
                )
                print(f"  -> Filas leídas: {len(gdf)}")

                # Guardar en Azure (esquema silver)
                print(f"  -> Escribiendo en Azure (silver.{table_name})...")
                gdf.to_postgis(
                    table_name,
                    azure_engine,
                    schema="silver",
                    if_exists="replace",
                    index=False
                )

                # Crear índice GIST de geometría
                with azure_engine.begin() as conn:
                    conn.execute(text(
                        f"CREATE INDEX IF NOT EXISTS idx_{table_name}_geom "
                        f"ON silver.{table_name} USING GIST (geometry);"
                    ))
                print(f"  -> [OK] Tabla espacial {table_name} migrada y con índice GIST listo.")
            except Exception as e:
                print(f"  -> [ERROR] Fallo al migrar tabla espacial {table_name}: {e}")

        else:
            # Caso especial: gtfs_horarios (grande, >2 millones de filas)
            if table_name == "gtfs_horarios":
                try:
                    print("  -> Leyendo muestra inicial para crear estructura en Azure...")
                    # 1. Crear la tabla en Azure usando una muestra pequeña
                    df_sample = pd.read_sql("SELECT * FROM processed_data.gtfs_horarios LIMIT 10;", neon_engine)
                    df_sample.to_sql(
                        "gtfs_horarios",
                        azure_engine,
                        schema="silver",
                        if_exists="replace",
                        index=False
                    )
                    
                    # Truncar para vaciarla
                    with azure_engine.begin() as conn:
                        conn.execute(text("TRUNCATE TABLE silver.gtfs_horarios;"))

                    print("  -> Estructura creada. Migrando datos por lotes (chunksize=100000) usando COPY...")
                    
                    total_rows = 0
                    # Leer en chunks y subir usando el método COPY rápido
                    chunks = pd.read_sql(
                        "SELECT * FROM processed_data.gtfs_horarios;",
                        neon_engine,
                        chunksize=100000
                    )
                    
                    for chunk_df in chunks:
                        chunk_df.to_sql(
                            "gtfs_horarios",
                            azure_engine,
                            schema="silver",
                            if_exists="append",
                            index=False,
                            method=psql_insert_copy
                        )
                        total_rows += len(chunk_df)
                        print(f"     -> {total_rows} filas migradas...")

                    print(f"  -> [OK] Tabla grande gtfs_horarios migrada con éxito ({total_rows} filas).")

                except Exception as e:
                    print(f"  -> [ERROR] Fallo al migrar tabla grande gtfs_horarios: {e}")

            else:
                try:
                    # Tablas estándar no espaciales
                    print(f"  -> Leyendo de Neon (processed_data.{table_name})...")
                    df = pd.read_sql(f"SELECT * FROM processed_data.{table_name}", neon_engine)
                    print(f"  -> Filas leídas: {len(df)}")

                    print(f"  -> Escribiendo en Azure (silver.{table_name})...")
                    df.to_sql(
                        table_name,
                        azure_engine,
                        schema="silver",
                        if_exists="replace",
                        index=False
                    )
                    print(f"  -> [OK] Tabla {table_name} migrada con éxito.")
                except Exception as e:
                    print(f"  -> [ERROR] Fallo al migrar tabla {table_name}: {e}")

        elapsed_time = time.time() - start_time
        print(f"Tiempo transcurrido para {table_name}: {elapsed_time:.2f} segundos.")

    print("\n=======================================================")
    print("MIGRACIÓN DE CAPA PLATA COMPLETADA CON ÉXITO")
    print("=======================================================")

if __name__ == "__main__":
    main()
