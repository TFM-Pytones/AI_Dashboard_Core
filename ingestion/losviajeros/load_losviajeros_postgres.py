import os
import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# 1. Cargar el .env desde la raíz
current_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.abspath(os.path.join(current_dir, "..", ".env"))
load_dotenv(env_path, override=True)

host = os.getenv("NEON_HOST")
user = os.getenv("NEON_USER")
password = os.getenv("NEON_PASSWORD")
dbname = os.getenv("NEON_DBNAME")

print("Conectando a Azure PostgreSQL...")

# 2. Crear el motor de conexión
engine = create_engine(f"postgresql://{user}:{password}@{host}:5432/{dbname}?sslmode=require")

# NUEVO PASO: Asegurarnos de que el esquema raw_data existe antes de inyectar nada
with engine.connect() as conn:
    conn.execute(text("CREATE SCHEMA IF NOT EXISTS bronze;"))
    conn.commit()
    print("[OK] Esquema 'raw_data' verificado/creado en la base de datos.")

# 3. Diccionario con los archivos a cargar
archivos_a_subir = {
    "losviajeros_temas": "losviajeros_temas.parquet",
    "losviajeros_mensajes": "losviajeros_mensajes.parquet"
}

try:
    for tabla, archivo in archivos_a_subir.items():
        ruta_archivo = os.path.abspath(os.path.join(current_dir, "..", archivo))
        
        if not os.path.exists(ruta_archivo):
            print(f"[ERROR] No encuentro el archivo: {ruta_archivo}")
            continue
            
        print(f"\nLeyendo {archivo}...")
        df = pd.read_parquet(ruta_archivo)
        
        print(f"Inyectando {len(df)} filas en raw_data.{tabla}...")
        df.to_sql(tabla, engine, schema="bronze", if_exists="replace", index=False)
        print(f" -> [OK] Tabla {tabla} lista en PostgreSQL.")
        
    print("\n=======================================================")
    print("CARGA A POSTGRESQL (RAW_DATA) COMPLETADA")
    print("=======================================================")

except Exception as e:
    print(f"\n[ERROR CRÍTICO]: {e}")