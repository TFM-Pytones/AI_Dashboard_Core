"""
istac_municipios_api.py
-----------------------
Descarga indicadores de 'Municipios en Cifras' (C00067A) del ISTAC via API,
filtra a municipios de Tenerife y convierte a formato largo (long format).

Municipios de Tenerife: codigos INE 38001 - 38999

Uso:
    .venv\\Scripts\\python scratch/istac_municipios_api.py
"""

import os
import io
import time
import logging
import requests
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ISTAC_Municipios")

BASE = "https://datos.canarias.es/api/estadisticas/indicators/v1.0"
SYSTEM_ID = "C00067A"

OUTPUT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "bronce", "tabular", "raw"
)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 31 Municipios de Tenerife (nombres exactos + variantes del ISTAC)
MUNICIPIOS_TENERIFE_NOMBRES = {
    "Adeje", "Arafo", "Arico", "Arona", "Buenavista del Norte", 
    "Candelaria", "Fasnia", "Garachico", "Granadilla de Abona", 
    "La Guancha", "Guía de Isora", "Güímar", "Icod de los Vinos", 
    "San Cristóbal de La Laguna", "La Matanza de Acentejo", "La Orotava", 
    "Puerto de la Cruz", "Los Realejos", "El Rosario", "San Juan de la Rambla", 
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
    "Superficie":                                                       "superficie_km2",
    "Población":                                                        "poblacion_total",
    "Población. De 15 a 64 años":                                       "poblacion_15_64",
    "Población. De 65 o más años":                                      "poblacion_65_mas",
    "Población. Edad media":                                            "edad_media",
    "Migraciones. Saldo migratorio":                                    "saldo_migratorio",
    "Alojamientos turísticos abiertos":                                 "alojamientos_abiertos",
    "Plazas ofertadas por alojamientos turísticos":                     "plazas_ofertadas",
    "Viajeros entrados en alojamientos turísticos":                     "viajeros_entrados",
    "Pernoctaciones en alojamientos turísticos":                        "pernoctaciones",
    "Tasa de ocupación por plazas":                                     "tasa_ocupacion_plazas",
    "Población turística equivalente en alojamientos turísticos":       "pob_turistica_equiv",
    "Empleo registrado. Hostelería":                                    "empleo_hosteleria",
    "Empleo registrado. Servicios":                                     "empleo_servicios",
    "Paro registrado":                                                  "paro_registrado",
    "Empresas inscritas en la Seguridad Social":                        "empresas_ss",
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

    # 1. Obtener todos los indicadores del sistema
    logger.info(f"Consultando sistema {SYSTEM_ID} (Municipios en Cifras)...")
    items = get_all_indicator_instances(SYSTEM_ID)
    logger.info(f"Total indicadores disponibles en la API: {len(items)}")

    # 2. Mapear titulo -> uuid
    uuid_map = {}
    for item in items:
        uuid = item.get("id", "")
        title_es = item.get("title", {}).get("es", "")
        if title_es in TITULO_A_NOMBRE:
            nombre_col = TITULO_A_NOMBRE[title_es]
            uuid_map[nombre_col] = {"uuid": uuid, "titulo": title_es}

    # Mostrar resultados del mapeo
    logger.info(f"\nIndicadores encontrados: {len(uuid_map)}/{len(TITULO_A_NOMBRE)}")
    for nombre, info in uuid_map.items():
        logger.info(f"  [{nombre}] => {info['uuid'][:8]}...")

    no_encontrados = [t for t in TITULO_A_NOMBRE if TITULO_A_NOMBRE[t] not in uuid_map]
    if no_encontrados:
        logger.warning(f"\nNO encontrados ({len(no_encontrados)}):")
        for t in no_encontrados:
            logger.warning(f"  - '{t}'")
        logger.warning("Revisa si el titulo exacto en la API es ligeramente diferente.")

    if not uuid_map:
        logger.error("Sin coincidencias. Verifica que el sistema C00067A contiene estos indicadores.")
        exit(1)

    # 3. Descargar y procesar cada indicador
    dfs = []
    for nombre_col, info in uuid_map.items():
        logger.info(f"\nDescargando: {nombre_col}...")
        df = download_as_tsv(SYSTEM_ID, info["uuid"], nombre_col)
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
                # Guardar CSV individual
                path_ind = os.path.join(OUTPUT_DIR, f"istac_mun_{nombre_col}.csv")
                df_tf.to_csv(path_ind, index=False, encoding="utf-8-sig")
                logger.info(f"    Guardado: {path_ind}")
                dfs.append(df_tf)
        time.sleep(1.0)

    # 4. Consolidar todo en un unico fichero
    if dfs:
        df_all = pd.concat(dfs, ignore_index=True)
        out = os.path.join(OUTPUT_DIR, "istac_municipios_cifras_tenerife.csv")
        df_all.to_csv(out, index=False, encoding="utf-8-sig")
        logger.info(f"\n{'='*60}")
        logger.info(f"EXITO: {len(dfs)} indicadores descargados")
        logger.info(f"Fichero consolidado: {out}")
        logger.info(f"Total filas: {len(df_all):,}")
        logger.info(f"Columnas: {list(df_all.columns)}")
        logger.info(f"Muestra de datos:\n{df_all.head(10).to_string()}")
    else:
        logger.error("No se descargo ningun indicador. Revisa la conexion y los titulos.")
