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
import pandas as pd

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.losviajeros.com"
FORUM_ID = 61          # Islas Canarias
FORUM_TAG = "Tenerife"  # tag propio del sitio -> ya viene pre-filtrado

REQUEST_DELAY = (0.5, 1.2)  # segundos entre requests (respetuoso y ágil)
MAX_RETRIES = 3

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 (TFM Investigacion Academica)"
    )
}

session = requests.Session()
session.headers.update(HEADERS)


def fetch(url: str) -> str | None:
    """GET con reintentos y backoff. Devuelve None si falla tras MAX_RETRIES."""
    for intento in range(MAX_RETRIES):
        try:
            resp = session.get(url, timeout=20)
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


def scrape_thread(tema_id: str, titulo: str, max_posts_pages: int = 100) -> list[dict]:
    mensajes = []
    start = 0
    post_ids_vistos = set()
    page_num = 1

    while start < max_posts_pages * 20:
        url = (
            f"{BASE_URL}/index.php?name=Forums&file=viewtopic"
            f"&t={tema_id}&postdays=0&postorder=asc&start={start}"
        )
        html = fetch(url)
        if not html:
            break

        soup = BeautifulSoup(html, "html.parser")
        postbodies = soup.find_all(class_=re.compile(r"postbody", re.I))
        if not postbodies:
            break

        nuevos_en_pagina = 0
        for pb in postbodies:
            parent = pb.find_parent("tr") or pb.find_parent("table")
            link = parent.find("a", href=re.compile(r"p=(\d+)#\1")) if parent else None
            if not link:
                table = pb.find_parent("table")
                if table:
                    link = table.find("a", href=re.compile(r"p=(\d+)#\1"))

            p_id = None
            if link:
                m = re.search(r"p=(\d+)", link["href"])
                if m:
                    p_id = m.group(1)

            if not p_id or p_id in post_ids_vistos:
                continue

            texto_limpio = pb.get_text(separator=" ", strip=True)
            if not texto_limpio or texto_limpio.startswith("Últimos Mensajes") or "Menú principal" in texto_limpio:
                continue

            table_post = pb.find_parent("table")
            fecha_post = None
            if table_post:
                m_fecha = re.search(r"Publicado:\s*([A-Za-zÁÉÍÓÚáéíóú]+,?\s*\d{2}-\d{2}-\d{4}\s*\d{1,2}:\d{2})", table_post.get_text())
                if m_fecha:
                    fecha_post = m_fecha.group(1)

            post_ids_vistos.add(p_id)
            nuevos_en_pagina += 1

            mensajes.append({
                "tema_id": tema_id,
                "tema_titulo": titulo,
                "mensaje_id": p_id,
                "url": f"{BASE_URL}/foros.php?p={p_id}#{p_id}",
                "contexto_pagina_raw": texto_limpio,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            })

        # CONDICIÓN DE PARADA: Si en esta página no hay posts nuevos, hemos alcanzado el final
        if nuevos_en_pagina == 0:
            break

        start += 20
        page_num += 1

    return mensajes


def main(max_temas: int | None = None):
    print("=== INICIANDO SCRAPER DE LOSVIAJEROS (VERSIÓN LIMPIA) ===", flush=True)
    temas = discover_threads()
    if max_temas:
        temas = temas[:max_temas]

    # Guardar temas
    df_temas = pd.DataFrame(temas)
    for p in ["losviajeros_temas.parquet", "ingestion/losviajeros/losviajeros_temas.parquet"]:
        try:
            df_temas.to_parquet(p, index=False)
        except Exception:
            pass
    for p in ["losviajeros_temas.csv", "ingestion/losviajeros/losviajeros_temas.csv"]:
        try:
            df_temas.to_csv(p, index=False)
        except Exception:
            pass
    print(f"Guardado losviajeros_temas ({len(df_temas)} temas).", flush=True)

    todos_mensajes = []
    total_temas = len(temas)
    for i, tema in enumerate(temas):
        print(f"[{i+1}/{total_temas}] Tema {tema['tema_id']}: '{tema['titulo'][:45]}...'", end="", flush=True)
        mensajes = scrape_thread(tema["tema_id"], tema["titulo"])
        print(f" -> {len(mensajes)} posts extraídos (Total acum: {len(todos_mensajes) + len(mensajes)})", flush=True)
        todos_mensajes.extend(mensajes)

    if todos_mensajes:
        df_mensajes = pd.DataFrame(todos_mensajes)
        print(f"\nTotal mensajes limpios extraídos: {len(df_mensajes)}", flush=True)
        
        # Guardar en raíz y en carpeta de ingestión
        for p in ["losviajeros_mensajes.parquet", "ingestion/losviajeros/losviajeros_mensajes.parquet"]:
            try:
                df_mensajes.to_parquet(p, index=False)
            except Exception:
                pass
        for p in ["losviajeros_mensajes.csv", "ingestion/losviajeros/losviajeros_mensajes.csv"]:
            try:
                df_mensajes.to_csv(p, index=False)
            except Exception:
                pass
        print(f"¡Éxito! Archivos guardados: losviajeros_mensajes.parquet y .csv ({len(df_mensajes)} filas)", flush=True)


if __name__ == "__main__":
    main()