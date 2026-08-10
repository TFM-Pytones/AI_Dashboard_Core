import os
import requests
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("OpenDataDownloader")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TABULAR_DIR = os.path.join(BASE_DIR, "data", "bronce", "tabular", "raw")
ESPACIAL_DIR = os.path.join(BASE_DIR, "data", "bronce", "espacial", "raw")

os.makedirs(TABULAR_DIR, exist_ok=True)
os.makedirs(ESPACIAL_DIR, exist_ok=True)

DATASETS = [
    {
        "name": "registro_hoteles.csv",
        "url": "https://datos.canarias.es/catalogos/general/dataset/429db33d-cbce-4920-b1b6-b4dde9e5f90f/resource/87741d75-2ce2-4a45-8131-ad8263257664/download/establecimientos-hoteleros-inscritos-en-el-registro-general-turistico-de-canarias.csv",
        "dir": TABULAR_DIR
    },
    {
        "name": "registro_extrahoteleros.csv",
        "url": "https://datos.canarias.es/catalogos/general/dataset/1364104c-b86c-4ab9-8ef5-12fdf399aa01/resource/d98c2617-db26-4d15-8ee4-3b2da1130bd0/download/establecimientos-extrahoteleros-sin-viviendas-vacacionales-inscritos-en-el-registro-general-turi.csv",
        "dir": TABULAR_DIR
    },
    {
        "name": "registro_viviendas_vacacionales.csv",
        "url": "https://datos.canarias.es/catalogos/general/dataset/9f4355a2-d086-4384-ba72-d8c99aa2d544/resource/8ff8cc43-c00b-4513-8f42-a5b961c579e1/download/establecimientos-extrahoteleros-de-tipologia-vivienda-vacacional-inscritos-en-el-registro-genera.csv",
        "dir": TABULAR_DIR
    },
    {
        "name": "oficinas_turismo_tenerife.geojson",
        "url": "https://datos.tenerife.es/ckan/dataset/89d42ef7-009b-4ec2-8b9b-f6ed50d19998/resource/21beb26c-9862-4b13-9170-ba72de9c739b/download/oficinas-de-informacion-turistica-de-tenerife.geojson",
        "dir": ESPACIAL_DIR
    },
    {
        "name": "bienes_interes_cultural_tenerife.geojson",
        "url": "https://datos.tenerife.es/ckan/dataset/83530250-3418-43d0-8019-18345a211271/resource/a6766279-e2a7-4cb5-b736-ff2fe028c6b9/download/bic_inmuebles_entornos.geojson",
        "dir": ESPACIAL_DIR
    }
]

def download_file(url, dest_path):
    logger.info(f"Descargando: {url}")
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        with open(dest_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        logger.info(f"✅ Guardado en: {dest_path}")
    except Exception as e:
        logger.error(f"❌ Error descargando {url}: {e}")

if __name__ == "__main__":
    logger.info("Iniciando descarga de datos abiertos (Canarias / Tenerife)...")
    for ds in DATASETS:
        dest_path = os.path.join(ds["dir"], ds["name"])
        download_file(ds["url"], dest_path)
    logger.info("¡Descargas completadas!")
