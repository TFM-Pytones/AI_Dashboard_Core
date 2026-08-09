"""Wrapper para correr booking_scraper.py de forma continua durante
varios días/semanas en la VM, sin intervención manual.

Por qué existe este archivo en vez de solo dejar booking_scraper.py:
    booking_scraper.py procesa UN lote (config.MAX_ESTABLISHMENTS_PER_RUN)
    y termina. Este wrapper lo relanza en loop, con una pausa larga entre
    lotes — así evitamos mandar miles de requests sin ningún respiro
    (más allá del rate limiting entre páginas individuales que ya existe
    dentro de cada corrida).

Uso en la VM (para que siga corriendo aunque cierres la sesión SSH):
    nohup python run_continuous.py > continuous_output.log 2>&1 &

Para detenerlo:
    Buscar el proceso (ps aux | grep run_continuous) y matarlo (kill <pid>),
    o simplemente parar la VM.
"""

import subprocess
import sys
import time
from pathlib import Path

import config
from utils.logger import get_logger

logger = get_logger("run_continuous", log_file=config.LOG_FILE)

# Pausa entre lotes (no entre establecimientos individuales — eso ya lo
# maneja config.MIN_DELAY_SECONDS/MAX_DELAY_SECONDS dentro de cada corrida).
# Un lote entero de MAX_ESTABLISHMENTS_PER_RUN ya toma tiempo real; esta
# pausa es un respiro adicional entre lotes completos.
PAUSE_BETWEEN_BATCHES_SECONDS = 1 * 60  # 15 minutos

# Si un lote entero devuelve 0 procesados 3 veces seguidas, probablemente
# se agotó el caché de candidatos (sitemap_discovery_cache.json) — no tiene
# sentido seguir relanzando en loop infinito sin nada nuevo que hacer.
MAX_EMPTY_BATCHES_BEFORE_STOP = 3

SCRIPT_PATH = Path(__file__).resolve().parent / "booking_scraper.py"


def run_one_batch() -> bool:
    """Corre una instancia de booking_scraper.py como subproceso.
    Devuelve True si el lote tuvo candidatos pendientes para procesar
    (aunque hayan fallado individualmente), False si ya no quedaba nada
    pendiente en el caché (señal de que el caché de descubrimiento se agotó).
    """
    logger.info("Lanzando un nuevo lote de booking_scraper.py...")

    # stderr=STDOUT: el logging de booking_scraper.py sale por stderr
    # (logging.StreamHandler() por defecto usa sys.stderr, no stdout) —
    # fusionar ambos streams es necesario para no perder esas líneas y para
    # que el marcador de caché agotado, más abajo, efectivamente lo detecte.
    process = subprocess.Popen(
        [sys.executable, str(SCRIPT_PATH)],
        cwd=SCRIPT_PATH.parent,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        bufsize=1,  # line-buffered: cada línea se entrega apenas se produce, sin esperar a que el proceso termine
    )

    # Mostramos cada línea en tiempo real (para poder monitorear una corrida
    # larga sin supervisión) y a la vez la acumulamos, para poder buscar el
    # marcador de "caché agotado" en el output completo al final.
    output_lines = []
    for line in process.stdout:
        print(line, end="")
        output_lines.append(line)

    process.wait()
    full_output = "".join(output_lines)

    if "No hay establecimientos pendientes" in full_output:
        return False
    return True


def main():
    logger.info("=== Iniciando corrida continua de booking_scraper.py ===")
    consecutive_empty_batches = 0
    batch_number = 0

    while True:
        batch_number += 1
        logger.info(f"--- Lote #{batch_number} ---")

        had_pending_work = run_one_batch()

        if not had_pending_work:
            consecutive_empty_batches += 1
            logger.info(
                f"Lote sin candidatos pendientes ({consecutive_empty_batches}/{MAX_EMPTY_BATCHES_BEFORE_STOP})."
            )
            if consecutive_empty_batches >= MAX_EMPTY_BATCHES_BEFORE_STOP:
                logger.info(
                    "Caché de descubrimiento agotado (sin novedades en varios lotes seguidos). "
                    "Deteniendo la corrida continua. Para seguir, ampliar "
                    "sitemap_discovery_cache.json (recorrer más shards) o subir "
                    "config.MAX_ESTABLISHMENTS_PER_RUN si aún quedan candidatos sin explorar."
                )
                break
        else:
            consecutive_empty_batches = 0  # hubo trabajo real, reiniciar el contador

        logger.info(
            f"Lote #{batch_number} finalizado. "
            f"Pausando {PAUSE_BETWEEN_BATCHES_SECONDS // 60} minutos antes del siguiente..."
        )
        time.sleep(PAUSE_BETWEEN_BATCHES_SECONDS)


if __name__ == "__main__":
    main()
