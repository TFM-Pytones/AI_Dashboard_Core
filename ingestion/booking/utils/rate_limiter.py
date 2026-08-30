"""Pausas aleatorias entre requests, para no sobrecargar el sitio y evitar
patrones de tráfico obviamente automatizados (ver consideraciones éticas
en docs/resumen_terminos_servicio.md).
"""

import random
import time


def wait(min_seconds: float, max_seconds: float) -> None:
    """Espera una cantidad aleatoria de segundos entre min_seconds y max_seconds."""
    delay = random.uniform(min_seconds, max_seconds)
    time.sleep(delay)
