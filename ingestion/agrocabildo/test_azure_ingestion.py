import os
import sys
import logging
import pandas as pd
import psycopg2
from dotenv import load_dotenv

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

load_dotenv(os.path.abspath(os.path.join(current_dir, "..", "..", ".env")), override=True)

from agrocabildo_ingestion import AgrocabildoIngestionPipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("TestAzureIngestion")

def run_test():
    print("=" * 70)
    print("PRUEBA DE CONEXION E INGESTA EN AZURE POSTGRESQL (CAPA BRONCE/RAW)")
    print("=" * 70)

    db_url = os.getenv("AZURE_DB_URL")
    print(f"Conectando a Azure Database ({os.getenv('AZURE_DB_HOST', 'Azure Flexible Server')})...")

    pipeline = AgrocabildoIngestionPipeline()
    
    # 1. Inicializar Tablas en la Base de Datos de Azure
    print("\n1. Verificando/Creando esquema de tablas en Azure DB (raw_data)...")
    pipeline.init_db()

    # 2. Ejecutar Ingesta de Muestra (2 Estaciones)
    print("\n2. Ejecutando ingesta de lecturas horarias en tiempo real (Muestra de 2 estaciones)...")
    df_result = pipeline.run_realtime_ingestion(days_back=2, max_stations=2)

    # 3. Consultar y mostrar el resultado en la base de datos de Azure
    print("\n3. Verificando registros insertados directamente en Azure DB:")
    conn = pipeline.get_db_connection()
    if conn:
        with conn.cursor() as cursor:
            # Conteo de estaciones
            cursor.execute("SELECT COUNT(*) FROM raw_data.estaciones_agrocabildo;")
            num_estaciones = cursor.fetchone()[0]
            
            # Conteo de lecturas horarias
            cursor.execute("SELECT COUNT(*) FROM raw_data.clima_horario_agrocabildo;")
            num_lecturas = cursor.fetchone()[0]
 
            print(f"   - Estaciones registradas en Azure DB: {num_estaciones}")
            print(f"   - Lecturas horarias guardadas en Azure DB: {num_lecturas}")

            if num_lecturas > 0:
                # Muestra de las últimas 5 lecturas
                print("\nMuestra de las ultimas lecturas guardadas en 'raw_data.clima_horario_agrocabildo':")
                query_sample = """
                    SELECT l.id_estacion, e.nombre, l.id_sensor, l.timestamp, l.valor_observado, l.es_validado
                    FROM raw_data.clima_horario_agrocabildo l
                    JOIN raw_data.estaciones_agrocabildo e ON l.id_estacion = e.id_estacion
                    ORDER BY l.timestamp DESC
                    LIMIT 5;
                """
                cursor.execute(query_sample)
                rows = cursor.fetchall()
                df_sample = pd.DataFrame(rows, columns=["ID Estacion", "Nombre Estacion", "ID Sensor", "Fecha/Hora", "Valor Observado", "Validado"])
                print(df_sample.to_string(index=False))

        conn.close()
        print("\nPrueba de Azure DB completada con éxito!")
    else:
        print("Error al conectar a Azure DB. Revisa las variables de entorno en el archivo .env")

if __name__ == "__main__":
    run_test()
