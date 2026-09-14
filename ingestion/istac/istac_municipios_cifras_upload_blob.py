"""
istac_municipios_cifras_upload_blob.py
--------------------------------------
Descarga indicadores de 'Municipios en Cifras' (C00067A) del ISTAC via API,
filtra a municipios de Tenerife y convierte a formato largo (long format).

Municipios de Tenerife: codigos INE 38001 - 38999

Uso:
    python ingestion/istac/istac_municipios_cifras_upload_blob.py
"""

import os
import io
import time
import logging
import requests
import pandas as pd
from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ISTAC_Municipios")

BASE = "https://datos.canarias.es/api/estadisticas/indicators/v1.0"
SYSTEM_ID = "C00067A"

load_dotenv()
AZURE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
BLOB_CONTAINER_NAME = "bronce-raw"

# 31 Municipios de Tenerife (nombres exactos + variantes del ISTAC)
MUNICIPIOS_TENERIFE_NOMBRES = {
    "Adeje", "Arafo", "Arico", "Arona", "Buenavista del Norte", 
    "Candelaria", "Fasnia", "Garachico", "Granadilla de Abona", 
    "La Guancha", "Guía de Isora", "Güímar", "Icod de los Vinos", 
    "San Cristóbal de La Laguna", "La Matanza de Acentejo", "La Orotava", 
    "Puerto de la Cruz", "Puerto de La Cruz",  # incluye variante ISTAC (La mayúscula)
    "Los Realejos", "El Rosario", "San Juan de la Rambla", 
    "San Miguel de Abona", "Santa Cruz de Tenerife", "Santa Úrsula", 
    "Santiago del Teide", "El Sauzal", "Los Silos", "Tacoronte", 
    "El Tanque", "Tegueste", "La Victoria de Acentejo", "Vilaflor de Chasna",
    
    # Variantes / abreviaciones que usa el portal ISTAC
    "La Laguna",
    "Vilaflor",
    "Santa Cruz de Tene",
    "San Cristóbal de L",
    "Granadilla de Abor",
    "Buenavista del Nor",
    "La Matanza de Acen",
    "La Victoria de Ace",
    "San Juan de la Ram",
}


# Indicadores a descargar: titulo exacto en la API -> nombre columna
TITULO_A_NOMBRE = {
    "Población":                                                        "poblacion_total",
    "Población. De 15 a 64 años":                                       "poblacion_15_64",
    "Población. De 65 o más años":                                      "poblacion_65_mas",
    "Población. Edad media":                                            "edad_media",
    "Paro registrado":                                                  "paro_registrado",
    # Suite de Empleo y Seguridad Social (31 municipios)
    "Afiliaciones a la Seguridad Social en alta laboral según régimen. Total":                                "empleo_total",
    "Afiliaciones a la Seguridad Social en alta laboral según régimen. Régimen general":                     "empleo_asalariados",
    "Afiliaciones a la Seguridad Social en alta laboral según régimen. Régimen especial de trabajadores autónomos": "empleo_autonomos",
    "Afiliaciones a la Seguridad Social en alta laboral en el sector servicios por actividad económica (CNAE-09). Hostelería": "empleo_hosteleria",
    "Afiliaciones a la Seguridad Social en alta laboral por sectores económicos. Servicios":                 "empleo_servicios",
    "Afiliaciones a la Seguridad Social en alta laboral en el sector servicios por actividad económica (CNAE-09). Comercio al por mayor y al por menor; reparación de vehículos de motor y motocicletas": "empleo_comercio",
    "Afiliaciones a la Seguridad Social en alta laboral por sectores económicos. Construcción":              "empleo_construccion",
    "Afiliaciones a la Seguridad Social en alta laboral por sectores económicos. Industria":                 "empleo_industria",
    "Afiliaciones a la Seguridad Social en alta laboral por sectores económicos. Agricultura":               "empleo_agricultura",
    # Indicadores turísticos EOH
    "Pernoctaciones en alojamientos turísticos":                        "pernoctaciones",
    "Plazas ofertadas por alojamientos turísticos":                     "plazas_ofertadas",
    "Población turística equivalente en alojamientos turísticos":       "pob_turistica_equiv",
    "Tasa de ocupación por plazas":                                     "tasa_ocupacion_plazas",
    "Viajeros entrados en alojamientos turísticos":                     "viajeros_entrados",
}


# UUIDs verificados directamente en la API (2026-08-09 y 2026-09-12). Se usan como fuente primaria: garantizan cobertura completa
UUID_MAP_VERIFICADO = {
    # Turísticos (municipios turísticos con masa estadística en EOH/ISTAC)
    "pernoctaciones":         "503ab41f-6906-4eb1-9c7d-e49ee137ea53",
    "plazas_ofertadas":       "f7ef630f-7d4a-401c-9db8-d6c3c805a0a2",
    "pob_turistica_equiv":    "224a27c7-5682-4ae9-bf56-58ce4f5aebe6",
    "tasa_ocupacion_plazas":  "ac286c1a-f70a-4888-9679-bd973250c824",
    "viajeros_entrados":      "011c4c75-c288-4274-83b4-fe5eb68ba861",
    # Demográficos/económicos (31 municipios)
    "paro_registrado":        "9de5166a-c9d0-4e56-bf73-42a6e07f5a97",
    # Suite de Empleo (31 municipios, trimestral 1999-2026)
    "empleo_total":           "579c2c01-3219-46ba-8741-a32c6566581a",
    "empleo_asalariados":     "25c18e4f-45f1-4a1c-b7df-397c5004d1b1",
    "empleo_autonomos":       "a243a472-95af-48b5-b773-47031e3ac4a3",
    "empleo_hosteleria":      "edb35ff9-70d5-4f38-b4fd-25eaf02ff3c8",
    "empleo_servicios":       "486e46ff-788c-4dcd-845b-c16fbd5b4d82",
    "empleo_comercio":        "12aa2d29-6f23-4726-8748-e0f54b36828b",
    "empleo_construccion":    "b81f92b4-4d9a-48ad-9fde-7fcde28174a2",
    "empleo_industria":       "eb3d7390-4902-4cc0-9fa4-8c5a15933810",
    "empleo_agricultura":     "3f29230c-8680-4fd4-a06f-22a46972f078",
    # Demográficos censales (31 municipios, anuales independientes)
    "poblacion_total":        "6daf4220-c08f-431c-8383-a0a7daa87da7",
    "poblacion_15_64":        "05ac75fe-6ddf-45be-8ad6-ae8101b775dc",
    "poblacion_65_mas":       "c19aa858-484a-4d4d-a6af-9cc4b268424a",
    "edad_media":             "87f99b2c-608f-44be-8d7e-2e26681d1b45",
}


def get_all_indicator_instances(system_id: str, limit: int = 100) -> list:
    """Obtiene todos los indicadores del sistema con paginacion."""
    all_items = []
    offset = 0
    while True:
        url = f"{BASE}/indicatorsSystems/{system_id}/indicatorsInstances?limit={limit}&offset={offset}"
        try:
            resp = requests.get(url, timeout=60)
            resp.raise_for_status()
            data = resp.json()
            items = data.get("items", [])
            all_items.extend(items)
            total = data.get("total", len(items))
            logger.info(f"  Paginacion: {len(all_items)}/{total}")
            if len(all_items) >= total or not items:
                break
            offset += limit
            time.sleep(0.5)
        except Exception as e:
            logger.error(f"Error en offset={offset}: {e}")
            break
    return all_items


def download_as_tsv(system_id: str, uuid: str, nombre: str) -> pd.DataFrame:
    """
    Descarga el indicador en formato TSV y lo parsea.
    El TSV de la API del ISTAC viene en formato largo con columnas:
      GEOGRAPHICAL_AREA | TIME_PERIOD | OBS_VALUE | (otras columnas de variacion)
    """
    url = f"{BASE}/indicatorsSystems/{system_id}/indicatorsInstances/{uuid}/data.tsv"
    try:
        resp = requests.get(url, timeout=120)
        resp.raise_for_status()
        content = resp.content.decode("utf-8", errors="replace")
        df = pd.read_csv(io.StringIO(content), sep="\t")
        df["_indicador"] = nombre
        logger.info(f"  OK {nombre}: {len(df):,} filas | cols: {list(df.columns)}")
        return df
    except Exception as e:
        logger.warning(f"  FAIL TSV {nombre}: {e}")
        # Intentar CSV como fallback
        url_csv = f"{BASE}/indicatorsSystems/{system_id}/indicatorsInstances/{uuid}/data.csv"
        try:
            resp = requests.get(url_csv, timeout=120)
            resp.raise_for_status()
            content = resp.content.decode("utf-8", errors="replace")
            sep = ";" if content.count(";") > content.count(",") else ","
            df = pd.read_csv(io.StringIO(content), sep=sep)
            df["_indicador"] = nombre
            logger.info(f"  OK CSV fallback {nombre}: {len(df):,} filas")
            return df
        except Exception as e2:
            logger.warning(f"  FAIL CSV fallback {nombre}: {e2}")
            return None


def filter_tenerife(df: pd.DataFrame) -> pd.DataFrame:
    """
    Filtra el DataFrame a municipios de Tenerife.
    Busca por nombre de municipio (el portal ISTAC no incluye codigos INE).
    Acepta coincidencias parciales para cubrir abreviaciones del portal.
    """
    for col in df.columns:
        try:
            # Coincidencia exacta primero
            mask_exact = df[col].astype(str).isin(MUNICIPIOS_TENERIFE_NOMBRES)
            if mask_exact.sum() > 3:
                filtered = df[mask_exact].copy()
                logger.info(f"    Filtrado por nombre exacto en '{col}': {len(filtered)} filas")
                return filtered

            # Coincidencia parcial: la columna contiene el nombre del municipio
            mask_partial = df[col].astype(str).apply(
                lambda x: any(x.startswith(m[:10]) for m in MUNICIPIOS_TENERIFE_NOMBRES if len(m) >= 5)
            )
            if mask_partial.sum() > 3:
                filtered = df[mask_partial].copy()
                logger.info(f"    Filtrado por nombre parcial en '{col}': {len(filtered)} filas")
                return filtered
        except Exception:
            continue

    logger.warning("    No se pudo filtrar a Tenerife. Devuelve todos los datos.")
    return df


if __name__ == "__main__":
    if not AZURE_CONNECTION_STRING:
        logger.error("AZURE_STORAGE_CONNECTION_STRING no está definido.")
        exit(1)

    try:
        blob_service_client = BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)
    except Exception as e:
        logger.error(f"Error al conectar con Azure Blob Storage: {e}")
        exit(1)

    # 1. Construir uuid_map: primero desde UUIDs verificados,
    #    luego complementar con búsqueda por título para los que no están.
    logger.info(f"Consultando sistema {SYSTEM_ID} (Municipios en Cifras)...")
    items = get_all_indicator_instances(SYSTEM_ID)
    logger.info(f"Total indicadores disponibles en la API: {len(items)}")

    # Mapa final de nombre_col -> {uuid, titulo}
    uuid_map = {}

    # Prioridad 1: UUIDs verificados hardcodeados
    for nombre_col, uuid in UUID_MAP_VERIFICADO.items():
        uuid_map[nombre_col] = {"uuid": uuid, "titulo": f"[UUID verificado] {nombre_col}"}
    logger.info(f"Indicadores por UUID verificado: {len(uuid_map)}")

    # Prioridad 2: búsqueda por título (para los que no están en UUID_MAP_VERIFICADO)
    nombres_ya_cubiertos = set(uuid_map.keys())
    for item in items:
        uuid = item.get("id", "")
        title_es = item.get("title", {}).get("es", "")
        if title_es in TITULO_A_NOMBRE:
            nombre_col = TITULO_A_NOMBRE[title_es]
            if nombre_col not in nombres_ya_cubiertos:
                uuid_map[nombre_col] = {"uuid": uuid, "titulo": title_es}
                logger.info(f"  [fallback título] {nombre_col} => {uuid[:8]}...")

    logger.info(f"Total indicadores a descargar: {len(uuid_map)}/{len(TITULO_A_NOMBRE)}")
    no_encontrados = [t for t in TITULO_A_NOMBRE if TITULO_A_NOMBRE[t] not in uuid_map]
    if no_encontrados:
        logger.warning(f"NO encontrados ({len(no_encontrados)}): {no_encontrados}")

    if not uuid_map:
        logger.error("Sin coincidencias. Verifica conexión.")
        exit(1)

    # 2. Descargar cada UUID (evitar duplicados para UUIDs compartidos)
    dfs = []
    cache_uuid = {}  # uuid -> df_raw descargado
    for nombre_col, info in uuid_map.items():
        logger.info(f"\nDescargando: {nombre_col}...")
        uid = info["uuid"]
        if uid not in cache_uuid:
            df = download_as_tsv(SYSTEM_ID, uid, nombre_col)
            cache_uuid[uid] = df
            time.sleep(1.0)
        else:
            df = cache_uuid[uid]
            if df is not None:
                df = df.copy()
                df["_indicador"] = nombre_col
            logger.info(f"  Reutilizando descarga previa para {nombre_col}")

        if df is not None and not df.empty:
            df_tf = filter_tenerife(df)
            # Filtrar periodo: solo 2019-2026
            for col in df_tf.columns:
                if "time" in col.lower() or "period" in col.lower() or "fecha" in col.lower():
                    try:
                        year_mask = df_tf[col].astype(str).str[:4].astype(int).between(2019, 2026)
                        df_tf = df_tf[year_mask].copy()
                        logger.info(f"    Filtrado temporal: {len(df_tf)} filas (2019-2026)")
                        break
                    except Exception:
                        continue
            if len(df_tf) > 0:
                # Normalizar nombre Puerto de La Cruz -> Puerto de la Cruz
                geo_col = next((c for c in df_tf.columns if "GEOGRAPHICAL" in c and "CODE" not in c), None)
                if geo_col:
                    df_tf[geo_col] = df_tf[geo_col].str.replace(
                        "Puerto de La Cruz", "Puerto de la Cruz", regex=False
                    )
                
                # Forzar columnas a string para evitar fallos de PyArrow (tipos mixtos)
                for c in ["GEOGRAPHICAL_CODE", "TIME", "TIME_CODE"]:
                    if c in df_tf.columns:
                        df_tf[c] = df_tf[c].astype(str)
                # Guardar en Azure Blob directamente (Parquet)
                blob_path = f"istac/istac_mun_{nombre_col}.parquet"
                try:
                    buffer = io.BytesIO()
                    df_tf.to_parquet(buffer, index=False, compression="snappy")
                    buffer.seek(0)
                    blob_client = blob_service_client.get_blob_client(container=BLOB_CONTAINER_NAME, blob=blob_path)
                    blob_client.upload_blob(buffer, overwrite=True)
                    logger.info(f"    Subido: {blob_path}")
                except Exception as e:
                    logger.error(f"    Error subiendo {blob_path}: {e}")
                
                dfs.append(df_tf)

    # 3. Finalizar
    if dfs:
        logger.info(f"\n{'='*60}")
        logger.info(f"EXITO: {len(dfs)} indicadores descargados y subidos por separado.")
    else:
        logger.error("No se descargo ningun indicador. Revisa la conexion y los titulos.")

