"""
Scraper de LosViajeros.com - Foro de Tenerife (Islas Canarias)
================================================================

QUÉ HACE:
Descarga los temas e hilos del foro de Islas Canarias que LosViajeros.com
ya tiene etiquetados como "Tenerife" (usan un sistema de tags propio, cl=Tenerife),
así que no hace falta filtrar por palabras clave nosotros mismos.
URL base: https://www.losviajeros.com/foros.php?f=61&cl=Tenerife (248 temas / 8774 mensajes
en el momento de escribir esto).

POR QUÉ ESTE SITIO SÍ Y forosdeviajes.com NO:
- forosdeviajes.com bloquea acceso automatizado en su robots.txt.
- losviajeros.com NO lo bloquea, sus páginas llevan meta-robots "index, follow"
  (quieren ser indexados) y su Aviso Legal solo prohíbe la reproducción con
  FINES COMERCIALES; permite copiar/almacenar para uso personal.

BUENAS PRÁCTICAS QUE ESTE SCRIPT RESPETA (no las quites):
- User-Agent identificado con propósito + contacto (transparencia, no nos hacemos
  pasar por un navegador).
- Rate limiting entre requests (REQUEST_DELAY). No lo bajes de 1-2s: es un foro
  de una empresa pequeña (Geonis SL), no una infraestructura de big tech.
- Solo lectura. Nunca inicia sesión ni interactúa con el foro.
- Guarda username + texto para poder trazar/deduplicar, pero recuerda: si en tu
  TFM citas mensajes textualmente, anonimiza el usuario (no hace falta el nick
  para tu análisis de KPIs, y es una buena práctica ética estándar en estudios
  con contenido de foros).

⚠️ ANTES DE LANZARLO A LOS 248 TEMAS:
No tengo el HTML crudo de la página (solo pude leerla ya convertida a texto),
así que los selectores de parse_post() son mi mejor estimación para este tipo
de foro (parece un phpBB clásico). Prueba primero con UN solo hilo (ver
`if __name__ == "__main__"` al final, hay un modo debug) e imprime el HTML de
un post para confirmar los nombres de clase reales. Ajusta lo marcado # AJUSTAR.
"""

import csv
import re
import time
import random
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.losviajeros.com"
FORUM_ID = 61          # Islas Canarias
FORUM_TAG = "Tenerife"  # tag propio del sitio -> ya viene pre-filtrado

REQUEST_DELAY = (1.5, 3.0)  # segundos, rango aleatorio entre requests (min, max)
MAX_RETRIES = 3

HEADERS = {
    # Identifícate de verdad. Cambia el email/contexto por el tuyo.
    "User-Agent": (
        "Mozilla/5.0 (compatible; TFM-InteligenciaTuristicaTenerife/1.0; "
        "investigacion academica, no comercial; contacto: tu_email@tu_universidad.es)"
    )
}

session = requests.Session()
session.headers.update(HEADERS)


def fetch(url: str) -> str | None:
    """GET con reintentos y backoff. Devuelve None si falla tras MAX_RETRIES."""
    for intento in range(MAX_RETRIES):
        try:
            resp = session.get(url, timeout=15)
            if resp.status_code == 200:
                time.sleep(random.uniform(*REQUEST_DELAY))
                return resp.text
            elif resp.status_code == 429:
                print(f"  429 Too Many Requests, esperando 30s... ({url})")
                time.sleep(30)
            else:
                print(f"  HTTP {resp.status_code} en {url}")
        except requests.RequestException as e:
            print(f"  Error de red ({intento+1}/{MAX_RETRIES}): {e}")
            time.sleep(5)
    return None


def discover_threads(max_pages: int = 7) -> list[dict]:
    """
    Recorre el listado de temas ya filtrado por tag Tenerife y devuelve
    metadatos básicos de cada tema (id, título, categoría, respuestas, lecturas).
    max_pages=7 cubre las 248 temas actuales (35-40 por página); sube el número
    si el foro ha crecido cuando lo ejecutes.
    """
    temas = []
    for page in range(max_pages):
        start = page * 40
        url = (
            f"{BASE_URL}/index.php?name=Forums&file=viewforum"
            f"&f={FORUM_ID}&cl={FORUM_TAG}&topicdays=0&start={start}"
        )
        print(f"Descubriendo temas: página {page+1}/{max_pages} -> {url}")
        html = fetch(url)
        if not html:
            continue

        soup = BeautifulSoup(html, "html.parser")
        # Cada tema es un enlace a foros.php?t=NNNNN . Esto SÍ lo confirmé
        # directamente en el HTML renderizado, es fiable.
        for link in soup.find_all("a", href=re.compile(r"foros\.php\?t=\d+$")):
            m = re.search(r"t=(\d+)", link["href"])
            if not m:
                continue
            tema_id = m.group(1)
            titulo = link.get_text(strip=True)
            if not titulo or any(t["tema_id"] == tema_id for t in temas):
                continue
            temas.append({
                "tema_id": tema_id,
                "titulo": titulo,
                "url": urljoin(BASE_URL, f"/foros.php?t={tema_id}"),
            })
    print(f"-> {len(temas)} temas únicos descubiertos.")
    return temas


def parse_post_block(block_text: str) -> dict | None:
    """
    Extrae autor / fecha / texto de un bloque de post usando los marcadores
    de texto que sí confirmé (Publicado:, Registrado:, Mensajes:).
    # AJUSTAR: si tu prueba con BeautifulSoup encuentra selectores de clase
    reales (algo como .postbody / .postauthor en foros phpBB clásicos),
    usa esos en vez de esta aproximación por texto — será más robusto.
    """
    fecha_match = re.search(
        r"Publicado:\*?\*?\s*([A-Za-zé]+,?\s*\d{2}-\d{2}-\d{4}\s*\d{1,2}:\d{2})",
        block_text,
    )
    autor_match = re.search(r"\[([^\]]+)\]\(https://www\.losviajeros\.com/index\.php\?name=Your_Account&profile=\d+\)", block_text)
    if not fecha_match or not autor_match:
        return None
    return {
        "autor": autor_match.group(1),
        "fecha_publicado_raw": fecha_match.group(1),
    }


def scrape_thread(tema_id: str, titulo: str, max_posts_pages: int = 50) -> list[dict]:
    """
    Descarga todos los mensajes de un tema, paginando de 20 en 20 (start=0,20,40...)
    hasta que una página no devuelva mensajes nuevos.
    """
    mensajes = []
    start = 0
    paginas_vacias = 0

    while start < max_posts_pages * 20 and paginas_vacias < 2:
        url = (
            f"{BASE_URL}/index.php?name=Forums&file=viewtopic"
            f"&t={tema_id}&postdays=0&postorder=asc&start={start}"
        )
        html = fetch(url)
        if not html:
            break

        soup = BeautifulSoup(html, "html.parser")

        # Cada permalink de post es foros.php?p=NNNNNNN#NNNNNNN — confirmado real.
        post_links = soup.find_all("a", href=re.compile(r"foros\.php\?p=\d+#\d+$"))
        post_ids_pagina = sorted(set(re.search(r"p=(\d+)", a["href"]).group(1) for a in post_links))

        if not post_ids_pagina:
            paginas_vacias += 1
            start += 20
            continue

        texto_pagina = soup.get_text("\n")
        for post_id in post_ids_pagina:
            mensajes.append({
                "tema_id": tema_id,
                "tema_titulo": titulo,
                "mensaje_id": post_id,
                "url": f"{BASE_URL}/foros.php?p={post_id}#{post_id}",
                # Guardamos el texto completo de la página; el post individual
                # se puede aislar luego en processed_data con el propio LLM/NLP,
                # es más robusto que pelearse con el HTML de un foro de 20 años.
                "contexto_pagina_raw": texto_pagina[:20000],
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            })

        paginas_vacias = 0
        start += 20

    return mensajes


def main(max_temas: int | None = 30):
    """
    max_temas: por defecto limita a los primeros 30 temas para tu primera
    prueba (evita lanzar 248 temas x paginación sin haber validado nada antes).
    Ponlo a None para el scraping completo cuando ya hayas verificado que
    todo funciona bien.
    """
    temas = discover_threads()
    if max_temas:
        temas = temas[:max_temas]

    with open("losviajeros_temas.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["tema_id", "titulo", "url"])
        writer.writeheader()
        writer.writerows(temas)
    print(f"Guardado losviajeros_temas.csv ({len(temas)} temas)")

    todos_mensajes = []
    for i, tema in enumerate(temas):
        print(f"[{i+1}/{len(temas)}] Descargando mensajes de: {tema['titulo']}")
        mensajes = scrape_thread(tema["tema_id"], tema["titulo"])
        todos_mensajes.extend(mensajes)

    if todos_mensajes:
        with open("losviajeros_mensajes.csv", "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(todos_mensajes[0].keys()))
            writer.writeheader()
            writer.writerows(todos_mensajes)
        print(f"Guardado losviajeros_mensajes.csv ({len(todos_mensajes)} mensajes)")


if __name__ == "__main__":
    # MODO DEBUG recomendado para tu primera ejecución:
    # descubre temas, coge el primero, y te enseña el HTML crudo de la
    # primera página de mensajes para que confirmes selectores reales.
    DEBUG = False

    if DEBUG:
        temas = discover_threads(max_pages=1)
        print(temas[:5])
        if temas:
            html = fetch(temas[0]["url"])
            with open("debug_primer_hilo.html", "w", encoding="utf-8") as f:
                f.write(html or "")
            print("Guardado debug_primer_hilo.html -> inspecciona la estructura real antes de lanzar main()")
    else:
        main(max_temas=None)  # sube esto (o pon None) cuando ya lo hayas validado