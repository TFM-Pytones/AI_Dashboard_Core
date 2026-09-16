import os
import io
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from azure.storage.blob import BlobServiceClient

# Cargar variables de entorno locales
load_dotenv()


# --- Configuración Azure Blob Storage (Capa Bronce / Raw) ---
AZURE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
BLOB_CONTAINER_NAME = "bronce-raw"

# --- Configuración de Ingesta Incremental (Clima) ---
INCREMENTAL_LOAD = True  # Cambiar a False para ingesta histórica completa

# --- Configuración Azure PostgreSQL (Flexible Server) ---
PG_USER = os.getenv("AZURE_DB_USER")
PG_PASS = os.getenv("AZURE_DB_PASSWORD")
PG_HOST = os.getenv("AZURE_DB_HOST")
PG_PORT = os.getenv("AZURE_DB_PORT", "5432")
PG_DB = os.getenv("AZURE_DB_NAME")

TARGET_SCHEMA = "bronze"

def get_pg_engine():
    """Crea la conexión a Azure PostgreSQL (Capa Bronze)."""
    connection_string = f"postgresql://{PG_USER}:{PG_PASS}@{PG_HOST}:{PG_PORT}/{PG_DB}"
    return create_engine(connection_string, connect_args={'sslmode': 'require'})

def ensure_schema_exists(engine, schema_name: str = TARGET_SCHEMA):
    """Crea el esquema objetivo en PostgreSQL si no existe."""
    with engine.connect() as conn:
        conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema_name};"))
        conn.commit()

def download_blob_to_dataframe(blob_service_client, blob_name: str) -> pd.DataFrame:
    """Descarga un archivo .csv, .parquet o .geojson de Azure Blob Storage a un DataFrame de Pandas."""
    blob_client = blob_service_client.get_blob_client(container=BLOB_CONTAINER_NAME, blob=blob_name)
    download_stream = blob_client.download_blob()
    content_bytes = download_stream.readall()
    
    if blob_name.endswith('.csv'):
        return pd.read_csv(io.BytesIO(content_bytes))
    elif blob_name.endswith('.parquet'):
        return pd.read_parquet(io.BytesIO(content_bytes))
    elif blob_name.endswith('.geojson'):
        import json
        geojson_dict = json.loads(content_bytes.decode('utf-8'))
        records = []
        for feature in geojson_dict.get('features', []):
            props = feature.get('properties', {})
            geom = feature.get('geometry', {})
            if geom and geom.get('type') == 'Point':
                coords = geom.get('coordinates', [])
                if len(coords) == 2:
                    props['lon'] = coords[0]
                    props['lat'] = coords[1]
            records.append(props)
        return pd.DataFrame(records)
    elif blob_name.endswith('.json'):
        import json
        try:
            return pd.read_json(io.BytesIO(content_bytes))
        except Exception:
            data = json.loads(content_bytes.decode('utf-8'))
            return pd.DataFrame.from_dict(data, orient='index')
    else:
        raise ValueError(f"Formato no soportado para lectura directa en DataFrame: {blob_name}")

import csv

def psql_insert_copy(table, conn, keys, data_iter):
    """Ejecuta un COPY de PostgreSQL (100x más rápido que INSERTs)"""
    dbapi_conn = conn.connection
    with dbapi_conn.cursor() as cur:
        s_buf = io.StringIO()
        writer = csv.writer(s_buf, delimiter='\t')
        writer.writerows(data_iter)
        s_buf.seek(0)
        columns = ', '.join([f'"{k}"' for k in keys])
        table_name = f'"{table.schema}"."{table.name}"' if table.schema else f'"{table.name}"'
        sql = f"COPY {table_name} ({columns}) FROM STDIN WITH CSV DELIMITER '\t'"
        cur.copy_expert(sql=sql, file=s_buf)

def ingest_to_postgres(df: pd.DataFrame, table_name: str, engine, if_exists: str = "replace"):
    """Inserta un DataFrame en el esquema 'bronze' de PostgreSQL usando COPY."""
    print(f"  -> Cargando {len(df)} filas en '{TARGET_SCHEMA}.{table_name}' ({if_exists})...")
    df.to_sql(
        name=table_name,
        con=engine,
        schema=TARGET_SCHEMA,
        if_exists=if_exists,
        index=False,
        method=psql_insert_copy,
        chunksize=10000
    )
    print(f"  [OK] Tabla '{TARGET_SCHEMA}.{table_name}' actualizada correctamente.")

def ingest_large_blob_to_postgres(blob_service_client, blob_name: str, table_name: str, engine, if_exists: str = "replace"):
    """Descarga un blob grande, lo convierte a CSV en disco y usa COPY nativo para evitar saturar la RAM."""
    import tempfile
    import pyarrow.parquet as pq
    import pyarrow.csv as pacsv

    blob_client = blob_service_client.get_blob_client(container=BLOB_CONTAINER_NAME, blob=blob_name)
    _, ext = os.path.splitext(blob_name)

    print(f"  -> Descargando {blob_name} a archivo temporal...")
    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp_parquet:
        tmp_parquet_path = tmp_parquet.name
        # Descarga en trozos directamente a disco
        stream = blob_client.download_blob()
        for chunk in stream.chunks():
            tmp_parquet.write(chunk)

    parquet_file = None
    tmp_csv_path = None
    try:
        print(f"  -> Convirtiendo Parquet a CSV en disco (evitando Pandas y RAM)...")
        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp_csv:
            tmp_csv_path = tmp_csv.name
            
        parquet_file = pq.ParquetFile(tmp_parquet_path)
        
        # Obtenemos un DataFrame vacío (0 filas) para que to_sql cree la estructura de la tabla en Postgres
        dummy_df = None
        for batch in parquet_file.iter_batches(batch_size=1):
            dummy_df = batch.to_pandas().head(0)
            break
            
        if dummy_df is not None:
            dummy_df.to_sql(name=table_name, con=engine, schema=TARGET_SCHEMA, if_exists=if_exists, index=False)

        # Generar CSV en disco de forma transaccional y ligera
        with open(tmp_csv_path, 'wb') as f_out:
            for batch in parquet_file.iter_batches(batch_size=5000):
                write_options = pacsv.WriteOptions(include_header=False)
                pacsv.write_csv(batch, f_out, write_options=write_options)

        print(f"  -> CSV generado. Insertando en '{TARGET_SCHEMA}.{table_name}' usando COPY nativo...")
        columns = ', '.join([f'"{k}"' for k in parquet_file.schema.names])
        dbapi_conn = engine.raw_connection()
        try:
            with dbapi_conn.cursor() as cur:
                with open(tmp_csv_path, 'r', encoding='utf-8') as f_in:
                    table_full_name = f'"{TARGET_SCHEMA}"."{table_name}"'
                    sql = f'COPY {table_full_name} ({columns}) FROM STDIN WITH CSV'
                    cur.copy_expert(sql=sql, file=f_in)
            dbapi_conn.commit()
            print(f"  [OK] Tabla '{TARGET_SCHEMA}.{table_name}' actualizada correctamente mediante COPY.")
        finally:
            dbapi_conn.close()

    except Exception as e:
        import traceback
        print(f"  [ERROR] Fallo al procesar {blob_name}: {e}")
        traceback.print_exc()
    finally:
        if parquet_file is not None:
            parquet_file = None
        for p in [tmp_parquet_path, tmp_csv_path]:
            if p:
                try:
                    if os.path.exists(p):
                        os.remove(p)
                except OSError:
                    pass

def ingest_clima_partitions_copy(blob_service_client, clima_blobs: list, engine, is_incremental: bool = False):
    """Carga archivos Parquet de clima directamente en bronze_clima_horario_agrocabildo usando COPY nativo por streaming."""
    import io
    import pyarrow.parquet as pq

    dbapi_conn = engine.raw_connection()
    try:
        with dbapi_conn.cursor() as cur:
            if not is_incremental:
                cur.execute(f'TRUNCATE TABLE "{TARGET_SCHEMA}"."bronze_clima_horario_agrocabildo";')
                dbapi_conn.commit()

            copy_sql = (
                f'COPY "{TARGET_SCHEMA}"."bronze_clima_horario_agrocabildo" '
                f'("id_estacion", "id_sensor", "timestamp", "valor_observado", "valor_validado", "es_validado", "año", "mes") '
                f'FROM STDIN WITH (FORMAT csv, DELIMITER E\'\\t\', NULL \'\\\\N\')'
            )

            total_loaded = 0
            container_client = blob_service_client.get_container_client(BLOB_CONTAINER_NAME)

            for i, blob_name in enumerate(clima_blobs, 1):
                try:
                    blob_client = container_client.get_blob_client(blob_name)
                    data = blob_client.download_blob().readall()
                    table = pq.read_table(io.BytesIO(data))

                    st_col = table["id_estacion"].to_pylist() if "id_estacion" in table.column_names else [None] * table.num_rows
                    se_col = table["id_sensor"].to_pylist() if "id_sensor" in table.column_names else [None] * table.num_rows
                    ts_col = table["timestamp"].to_pylist() if "timestamp" in table.column_names else [None] * table.num_rows
                    vo_col = table["valor_observado"].to_pylist() if "valor_observado" in table.column_names else [None] * table.num_rows
                    vv_col = table["valor_validado"].to_pylist() if "valor_validado" in table.column_names else [None] * table.num_rows
                    ev_col = table["es_validado"].to_pylist() if "es_validado" in table.column_names else [None] * table.num_rows
                    an_col = table["año"].to_pylist() if "año" in table.column_names else [None] * table.num_rows
                    me_col = table["mes"].to_pylist() if "mes" in table.column_names else [None] * table.num_rows

                    tsv_lines = []
                    for st, se, ts, vo, vv, ev, an, me in zip(st_col, se_col, ts_col, vo_col, vv_col, ev_col, an_col, me_col):
                        ts_str = ts.isoformat() if hasattr(ts, "isoformat") else (str(ts) if ts is not None else "\\N")
                        vo_str = f"{vo:.4f}" if vo is not None else "\\N"
                        vv_str = f"{vv:.4f}" if vv is not None else "\\N"
                        ev_str = "t" if ev else "f"
                        tsv_lines.append(f"{st}\t{se}\t{ts_str}\t{vo_str}\t{vv_str}\t{ev_str}\t{an}\t{me}\n")

                    tsv_buf = io.StringIO("".join(tsv_lines))
                    cur.copy_expert(copy_sql, tsv_buf)
                    dbapi_conn.commit()
                    total_loaded += table.num_rows
                    if i % 50 == 0 or i == len(clima_blobs):
                        print(f"  [{i}/{len(clima_blobs)}] Cargadas {total_loaded:,} filas de clima mediante COPY...")
                except Exception as e:
                    print(f"  [ERROR] Fallo cargando {blob_name}: {e}")
                    dbapi_conn.rollback()

            print(f"  [OK] Ingesta de clima finalizada: {total_loaded:,} filas cargadas en 'bronze_clima_horario_agrocabildo'.")
    finally:
        dbapi_conn.close()

def main():
    if not AZURE_CONNECTION_STRING:
        print("[ERROR] AZURE_STORAGE_CONNECTION_STRING no esta definido en el archivo .env")
        return
        
    print("======================================================================")
    print("INGESTA DESDE AZURE BLOB STORAGE -> AZURE POSTGRESQL (ESQUEMA BRONZE)")
    print("======================================================================")
    
    blob_service_client = BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)
    engine = get_pg_engine()
    ensure_schema_exists(engine, TARGET_SCHEMA)

    container_client = blob_service_client.get_container_client(BLOB_CONTAINER_NAME)
    blobs = [b.name for b in container_client.list_blobs()]

    # 1. TABLAS TABULARES / ISTAC / AENA / ALOJAMIENTOS / GTFS / YOUTUBE / ESPACIALES
    # ---------------------------------------------------------------------------------
    mapping_directo = {
        # AENA
        "aena/aena_pasajeros_tenerife.parquet": "bronze_aena_pasajeros",
        # Alojamientos Oficiales (Registro Turístico)
        "alojamientos_oficiales/registro_extrahoteleros_tenerife.parquet": "bronze_registro_extrahoteleros",
        "alojamientos_oficiales/registro_hoteles_tenerife.parquet": "bronze_registro_hoteles",
        "alojamientos_oficiales/registro_viviendas_vacacionales_tenerife.parquet": "bronze_registro_viviendas_vacacionales",
        # TITSA (Tabular)
        "gtfs/gtfs_rutas_atributos.parquet": "bronze_gtfs_rutas_atributos",
        "gtfs/gtfs_viajes.parquet": "bronze_gtfs_viajes",
        "gtfs/gtfs_calendario.parquet": "bronze_gtfs_calendario",
        "gtfs/gtfs_calendario_excepciones.parquet": "bronze_gtfs_calendario_excepciones",
        "gtfs/gtfs_horarios.parquet": "bronze_gtfs_horarios",
        #Losviajeros blog
        "losviajeros/losviajeros_temas.parquet": "bronze_losviajeros_temas",
        # losviajeros_mensajes se carga aparte (bloque 4) por ser un archivo muy grande
        # YouTube
        "youtube/youtube_comments.parquet": "bronze_youtube_comments",
        "youtube/youtube_videos.parquet": "bronze_youtube_videos",
        # Metadatos Estaciones
        "clima/estaciones/estaciones_agrocabildo.parquet": "bronze_estaciones_agrocabildo",
        "clima/sensores/sensores_meteorologicos.parquet": "bronze_sensores_meteorologicos"        
    }

    # Añadir dinámicamente todos los archivos Parquet de ISTAC
    for blob in blobs:
        if blob.startswith("istac/") and blob.endswith(".parquet"):
            table_name = "bronze_" + blob.split("/")[-1].replace(".parquet", "")
            mapping_directo[blob] = table_name

    print("\n--- 1. Carga de Datasets Directos (ISTAC, AENA, Registro, TITSA, YouTube, Espaciales) ---")
    for blob_name, table_name in mapping_directo.items():
        if blob_name in blobs:
            try:
                print(f"\nProcesando Blob: {blob_name}")
                df = download_blob_to_dataframe(blob_service_client, blob_name)
                ingest_to_postgres(df, table_name, engine, if_exists="replace")
            except Exception as e:
                print(f"  [ERROR] Error procesando {blob_name}: {e}")
        else:
            print(f"  [Omitido] Blob no encontrado aun en Azure: {blob_name}")


    # 2. Carga de los archivos de clima del agrocabildo
    print("\n--- 2. Carga de lecturas particionadas de clima (capa Bronze) ---")
    clima_blobs = [b for b in blobs if b.startswith("clima/mediciones/") and b.endswith(".parquet")]
    
    if INCREMENTAL_LOAD:
        from datetime import datetime
        now = datetime.now()
        current_year = now.year
        current_month = now.month
        # Filtramos para quedarnos solo con la partición del mes y año actual
        prefix_to_find = f"año={current_year}/mes={current_month:02d}/"
        clima_blobs = [b for b in clima_blobs if prefix_to_find in b]
        print(f"Modo incremental. Filtrando por partición: {prefix_to_find}")
    else:
        print("Modo carga total. Se procesarán todas las particiones históricas.")

    if clima_blobs:
        print(f"Encontrados {len(clima_blobs)} archivos de particiones de clima.")
        ingest_clima_partitions_copy(blob_service_client, clima_blobs, engine, is_incremental=INCREMENTAL_LOAD)
    else:
        print("  [Info] No se encontraron archivos particionados para ingestar.")


    # 3. Carga de Parquets de TripAdvisor (Capa Bronce)
    print("\n--- 3. Carga de Parquets de TripAdvisor (Capa Bronce) ---")
    tripadvisor_tables = {
        "bronze_tripadvisor_ubicaciones": [
            "tripadvisor/ubicaciones_raw_reconstruccion_2026-08-27.json",
            "tripadvisor/ubicaciones_raw_5_pendientes_2026-08-28.json"
        ],
        "bronze_tripadvisor_resenas": [
            "tripadvisor/resenas_raw_reconstruccion_2026-08-27.json",
            "tripadvisor/resenas_raw_5_pendientes_2026-08-28.json"
        ]
    }
    
    for table_name, b_blobs in tripadvisor_tables.items():
        if b_blobs:
            print(f"Buscando {len(b_blobs)} archivos para {table_name}...")
            dataframes = []
            for blob_name in b_blobs:
                if blob_name in blobs:
                    try:
                        df = download_blob_to_dataframe(blob_service_client, blob_name)
                        dataframes.append(df)
                        print(f"  [OK] Descargado {blob_name}")
                    except Exception as e:
                        print(f"  [AVISO] No se pudo descargar {blob_name}: {e}")
                else:
                    print(f"  [AVISO] Archivo no encontrado en blob storage: {blob_name}")
            
            if dataframes:
                full_df = pd.concat(dataframes, ignore_index=True)
                # Parse dict/list columns as JSON strings to avoid postgres type errors
                import json
                for col in full_df.columns:
                    if full_df[col].apply(lambda x: isinstance(x, (dict, list))).any():
                        full_df[col] = full_df[col].apply(lambda x: json.dumps(x) if isinstance(x, (dict, list)) else x)
                
                ingest_to_postgres(full_df, table_name, engine, if_exists="replace")
                print(f"  [OK] Combinadas y subidas {len(full_df)} filas a {table_name}")
        else:
            print(f"  [Info] No se encontraron archivos para {table_name}.")

    # 4. Carga de Blobs Grandes (LosViajeros Mensajes)  
    print("\n--- 4. Carga de Blobs Grandes (LosViajeros Mensajes) ---")
    large_blobs = {
        "losviajeros/losviajeros_mensajes.parquet": "bronze_losviajeros_mensajes",
    }
    for blob_name, table_name in large_blobs.items():
        if blob_name in blobs:
            print(f"\nProcesando Blob grande: {blob_name}")
            ingest_large_blob_to_postgres(blob_service_client, blob_name, table_name, engine, if_exists="replace")
        else:
            print(f"  [Omitido] Blob no encontrado aun en Azure: {blob_name}")

    print("\n======================================================================")
    print("PROCESO DE INGESTA COMPLETO HACIA AZURE POSTGRESQL (SCHEMA: BRONZE)")
    print("======================================================================")

if __name__ == "__main__":
    main()
