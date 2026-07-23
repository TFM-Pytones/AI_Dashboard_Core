import os
import sys
import time
import argparse
import logging
from datetime import datetime, timedelta

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from agrocabildo_ingestion import AgrocabildoIngestionPipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(current_dir, "agrocabildo_scheduler.log"), encoding="utf-8")
    ]
)
logger = logging.getLogger("AgrocabildoScheduler")

REFRESH_INTERVAL_HOURS = 12

def run_scheduler(once_only: bool = False, days_back: int = 2, max_stations: int = None):
    pipeline = AgrocabildoIngestionPipeline()
    logger.info(f"=== Servicio de Refresco Agrocabildo (Intervalo: {REFRESH_INTERVAL_HOURS}h) Iniciado ===")

    while True:
        cycle_start = datetime.now()
        logger.info(f"▶️ Inicio del ciclo de ingesta a las {cycle_start.strftime('%Y-%m-%d %H:%M:%S')}")
        
        try:
            df_result = pipeline.run_realtime_ingestion(days_back=days_back, max_stations=max_stations)
            logger.info(f"⏹️ Ciclo completado. Registros procesados: {len(df_result)}")
        except Exception as e:
            logger.error(f"❌ Error en el ciclo de ingesta: {e}", exc_info=True)

        if once_only:
            logger.info("Modo ejecución única (--once). Finalizando servicio.")
            break

        next_run = cycle_start + timedelta(hours=REFRESH_INTERVAL_HOURS)
        wait_seconds = (next_run - datetime.now()).total_seconds()
        
        if wait_seconds > 0:
            logger.info(f"⏳ Próximo refresco programado para: {next_run.strftime('%Y-%m-%d %H:%M:%S')} (esperando {wait_seconds/3600:.2f} horas)")
            time.sleep(wait_seconds)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Servicio de ingesta periódica para estaciones de Agrocabildo")
    parser.add_argument("--once", action="store_true", help="Ejecuta la ingesta una sola vez y finaliza")
    parser.add_argument("--days", type=int, default=2, help="Días de historial reciente a consultar")
    parser.add_argument("--max-stations", type=int, default=None, help="Número máximo de estaciones a procesar (para pruebas)")
    args = parser.parse_args()

    run_scheduler(once_only=args.once, days_back=args.days, max_stations=args.max_stations)
