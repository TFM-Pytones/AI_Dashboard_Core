"""Configuración de logging para los scrapers.

Registra tanto en consola como en archivo, para poder revisar después
qué bloqueos, CAPTCHAs o errores aparecieron durante una corrida larga
(esto alimenta la sección de "limitaciones encontradas" del TFM).
"""

import logging
import sys
from pathlib import Path

_console_reconfigured = False


def ensure_utf8_console() -> None:
    """Reconfigura stdout/stderr a UTF-8 explícito.

    En Windows la consola usa cp1252 por defecto, que no puede imprimir
    emojis ni varios caracteres especiales que aparecen en reseñas reales
    (rompe con UnicodeEncodeError en vez de solo mostrar el texto mal).
    """
    global _console_reconfigured
    if _console_reconfigured:
        return
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name)
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    _console_reconfigured = True


def get_logger(name: str, log_file: str = "scraper.log") -> logging.Logger:
    ensure_utf8_console()

    logger = logging.getLogger(name)

    if logger.handlers:
        # Evita duplicar handlers si get_logger() se llama más de una vez
        return logger

    logger.setLevel(logging.INFO)

    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(log_path, mode="a", encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger
