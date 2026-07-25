"""Configuración de logging para los scrapers.

Registra tanto en consola como en archivo, para poder revisar después
qué bloqueos, CAPTCHAs o errores aparecieron durante una corrida larga
(esto alimenta la sección de "limitaciones encontradas" del TFM).
"""

import logging
from pathlib import Path


def get_logger(name: str, log_file: str = "scraper.log") -> logging.Logger:
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
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger
