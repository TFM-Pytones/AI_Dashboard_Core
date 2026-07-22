import os
import sys
import psycopg2
from dotenv import load_dotenv

current_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.abspath(os.path.join(current_dir, "..", "..", ".env"))
load_dotenv(env_path, override=True)

print("Intentando conectar a Azure Database for PostgreSQL...")
print("Host:", os.getenv("AZURE_DB_HOST"))
print("Usuario:", os.getenv("AZURE_DB_USER"))
print("Base de datos:", os.getenv("AZURE_DB_NAME"))

try:
    conn = psycopg2.connect(
        host=os.getenv("AZURE_DB_HOST"),
        user=os.getenv("AZURE_DB_USER"),
        password=os.getenv("AZURE_DB_PASSWORD"),
        dbname=os.getenv("AZURE_DB_NAME"),
        port="5432",
        sslmode="require"
    )
    with conn.cursor() as cursor:
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]
        print("Conexion exitosa!")
        print("Version de PostgreSQL en Azure:", version)

        # Crear esquema silver (plata) si no existe
        print("Verificando/Creando esquema 'silver'...")
        cursor.execute("CREATE SCHEMA IF NOT EXISTS silver;")
        conn.commit()
        print("Esquema 'silver' verificado.")
        
    conn.close()
except Exception as e:
    print("Error al conectar a la base de datos de Azure:")
    print(e)
    sys.exit(1)
