"""Rotación de User-Agent para el scraper.

Usamos varios navegadores/SO reales y comunes para no parecer un patrón
único y sospechoso, pero sin spoofear como un bot conocido (Googlebot, etc.)
"""

import random

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0",
]


def get_random_user_agent() -> str:
    """Devuelve un User-Agent al azar de la lista."""
    return random.choice(USER_AGENTS)
