"""
05_ptna_score.py
-----------------
Bloque 5 (MGWR/PTNA) -- Subtarea 5.2, cierre: calcula el indice PTNA a partir
del modelo MGWR ya ajustado (04_run_model.py) y produce el dataset final.

PTNA = Valor_esperado_por_MGWR - Valor_observado_real
     = modelo.predy - y

ptna_score > 0 -> el hexagono "deberia" tener mas plazas hoteleras segun sus
                  condiciones -> oportunidad de inversion.
ptna_score < 0 -> zona sobre-explotada -> riesgo de overtourism.

NOTA SOBRE `confianza_ptna` (diagnostico de estabilidad de coeficientes,
union de 3 criterios distintos, cada uno de una sesion de diagnostico
aparte sobre el .pkl ya generado): `ptna_score` NO cambia por ninguno de
los tres -- `confianza_ptna` es puramente informativa, para que quien lea
el top-10 sepa si algun "mejor candidato" tiene esta salvedad antes de
reportarlo como hallazgo solido sin mas contexto.

- **Criterio periferia (Hallazgo 4, dataset v1; variables actualizadas para
  v3 en la misma sesion del Hallazgo 11)**: con kernel adaptativo, un
  bandwidth chico + ubicacion geografica periferica (pocos vecinos reales,
  todos concentrados de un lado) puede producir coeficientes locales
  extremos e inestables. Se diagnosticaron los 4 coeficientes con rangos
  min/max mas amplios en el v1; de esos, 2 (`dist_costa_km`,
  `n_paradas_bus_500m`) mostraron sus extremos (percentil 1/99)
  concentrados en zonas geograficamente perifericas (borde 5% del rango
  lon/lat del dataset) -- las otras 2 (`n_pois_turisticos`, `viirs_medio`)
  mostraron sus extremos en zonas de alta actividad real (Puerto de la
  Cruz/La Orotava), no inestabilidad, y se descartaron de este criterio a
  proposito. `n_paradas_bus_500m` no existe desde el v2 (reemplazada por
  `dist_parada_cercana_m`) -- rediagnosticado contra el checkpoint v3 real
  (ver Hallazgo 11): el patron de periferia se sostiene para ambas
  variables (51 y 25 hexagonos respectivamente, union 55/2579 = 2.13%,
  comparable al 1.3%-2.0% del v1/v2), asi que se reemplaza
  `n_paradas_bus_500m` por `dist_parada_cercana_m` en la lista. Ver
  `calcular_h3_confianza_baja`.
- **Criterio cluster (Hallazgo 11, dataset v3)**: `altitud_media_m` quedo
  con VIF moderado (13.4) por correlacion con 4-5 variables geograficas
  relacionadas (costa/ENP/clima/accesibilidad) -- sus coeficientes
  extremos aparecen en 2 clusters geograficos COMPACTOS y bien poblados
  (136-137 de 138 vecinos posibles), no en el borde del mapa con pocos
  vecinos como el caso de arriba. Mismo percentil extremo, pero SIN el
  filtro de periferia (no aplica -- estos hexagonos dieron
  periferico=False). Ver `calcular_h3_confianza_baja_cluster`.
- **Criterio bandwidth casi-global (Hallazgo 12, dataset v3)**: diagnostico
  aparte (misma sesion) sobre `model["bandwidths_full"]` del checkpoint ya
  ajustado (`ptna_mgwr_model_v3_checkpoint.pkl` / `ptna_mgwr_model_v3.pkl`,
  verificado que son el mismo array) encontro que 9 de las 14 variables X
  quedaron con bandwidth optimo pegado al techo del kernel adaptativo: 2573
  vecinos sobre un techo de N=2579 (99.8% del dataset), vs. las otras 5
  variables (`ndvi_medio`=198, `altitud_media_m`=138, `n_restaurantes`=177,
  `n_naturaleza`=132, `n_cultura`=960) que quedaron con ventanas mucho mas
  chicas y genuinamente locales. Esto es DISTINTO, conceptualmente, a los
  otros 2 criterios de arriba:
    - No es "coeficiente ruidoso/inestable por pocos vecinos" (eso es lo que
      busca el criterio periferia, Hallazgo 4 -- bandwidth CHICO + pocos
      vecinos reales). Aca es lo opuesto: bandwidth casi-global, con la
      varianza del estimador GWR bajando cuanto mas grande el bandwidth (mas
      observaciones promediadas). El problema no es "estimador ruidoso", es
      "el coeficiente ya no captura variacion local genuina en esa zona -- el
      kernel adaptativo eligio tratar la variable casi como un efecto global
      constante en toda la isla para ese hexagono, indistinguible de un OLS
      global salvo por el 0.2% de vecinos mas lejanos que caen fuera de la
      ventana". El coeficiente en el percentil 1/99 no refleja una relacion
      local real, sino el residuo de que ese 0.2% de vecinos SI cambia segun
      donde este el hexagono.
    - Por eso tampoco es igual al criterio cluster (Hallazgo 11, VIF
      moderado con bandwidth chico/local de 138): alli la inestabilidad viene
      de colinealidad entre variables geograficas relacionadas, con una
      ventana local real. Aca no hay colinealidad senalada como causa -- es
      el propio proceso de seleccion de bandwidth (golden section search
      sobre AICc) el que convergio a un optimo casi-global para estas 9
      variables especificas.
    - NO se aplica filtro de periferia (`_es_periferico`) a este criterio: el
      vecindario de estas 9 variables es casi TODA la isla (2573/2579 con
      peso>0), exactamente lo opuesto de "pocos vecinos reales concentrados
      de un lado" que busca ese filtro. Exigir periferia aca no tendria
      sentido conceptual y descartaria el hallazgo por el motivo equivocado.
  Cifras de la investigacion previa (misma sesion, sobre este mismo
  checkpoint): 217/2579 hexagonos (8.4%) caen en percentil 1/99 de al menos
  una de estas 9 variables; de esos, 152 no estaban ya cubiertos por los 2
  criterios existentes (periferia + cluster) -- son los que este tercer
  criterio suma de nuevo a `confianza_ptna='baja'`. Ver
  `calcular_h3_confianza_baja_bandwidth`.

Uso:
    python 05_ptna_score.py
"""

import argparse
import logging
import pickle
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _db import DATA_INTERIM_DIR, DATA_PROCESSED_DIR, setup_logging

SCRIPT_NAME = "05_ptna_score"
TOP_N = 10

# Variables cuyos coeficientes extremos (percentil 1/99), SI ADEMAS caen en
# zona periferica, marcan el hexagono como confianza_ptna='baja'. Ver nota
# extensa arriba -- n_pois_turisticos y viirs_medio quedaron fuera a
# proposito (sus extremos son zonas de alta actividad real, no inestabilidad
# numerica). n_paradas_bus_500m (v1) -> dist_parada_cercana_m (desde v2,
# rediagnosticada contra el v3 en la sesion del Hallazgo 11: patron de
# periferia sostenido, 51 dist_costa_km + 25 dist_parada_cercana_m).
CONFIANZA_BAJA_VARIABLES = ["dist_costa_km", "dist_parada_cercana_m"]
CONFIANZA_BAJA_PERCENTILES = (1, 99)
CONFIANZA_BAJA_MARGEN_PERIFERICO = 0.05  # 5% del rango lon/lat del dataset

# Hallazgo 11 (dataset v3): altitud_media_m quedo con VIF moderado (13.4, no
# severo -- no se saca del modelo, a diferencia del Hallazgo 10) por
# correlacion con 4-5 variables geograficas relacionadas (dist_costa_km r=0.90,
# pct_area_enp r=0.74, temp_media_anual r=-0.68, dist_parada_cercana_m r=0.64,
# dist_hospital_km r=0.63) -- en Tenerife, altitud actua como proxy compuesto
# de costa/ENP/clima/accesibilidad a la vez. Sus coeficientes extremos
# (percentil 1/99) aparecen en 2 CLUSTERS GEOGRAFICOS COMPACTOS y bien
# poblados (136-137 de 138 vecinos posibles con peso > 0) -- NO en el borde
# del mapa con pocos vecinos reales como el Hallazgo 4. Por eso este criterio
# es DISTINTO al de CONFIANZA_BAJA_VARIABLES de arriba: mismo percentil
# extremo, pero SIN el filtro de periferia (_es_periferico no aplica aca --
# los hexagonos extremos de altitud_media_m dieron periferico=False en el
# diagnostico real). Ver calcular_h3_confianza_baja_cluster.
CONFIANZA_BAJA_VARIABLES_CLUSTER = ["altitud_media_m"]
CONFIANZA_BAJA_CLUSTER_PERCENTILES = (1, 99)

# Hallazgo 12 (dataset v3): diagnostico aparte de model["bandwidths_full"]
# (checkpoint ya ajustado, ptna_mgwr_model_v3_checkpoint.pkl / _v3.pkl --
# verificado que son el mismo array) encontro que estas 9 de las 14
# variables X quedaron con bandwidth optimo pegado al techo del kernel
# adaptativo (2573 vecinos sobre un techo de N=2579, 99.8% del dataset),
# a diferencia de las otras 5 (ndvi_medio=198, altitud_media_m=138,
# n_restaurantes=177, n_naturaleza=132, n_cultura=960) que quedaron con
# ventanas chicas y genuinamente locales. Con un bandwidth tan grande el
# kernel adaptativo trata la variable casi como un efecto global constante
# para casi toda la isla -- el coeficiente en percentil 1/99 no refleja
# inestabilidad del estimador (con tantos vecinos promediados la varianza
# deberia ser BAJA, al reves que en el criterio cluster de arriba), sino que
# el coeficiente no esta capturando variacion local genuina en esa zona. Por
# eso este criterio es CONCEPTUALMENTE DISTINTO a los otros 2 -- no es
# "coeficiente ruidoso por pocos vecinos" (periferia, Hallazgo 4) ni
# "coeficiente inestable por colinealidad con ventana local real" (cluster,
# Hallazgo 11) -- ver nota extensa arriba en el modulo. Tampoco se aplica
# filtro de periferia: el vecindario de estas 9 variables es casi TODA la
# isla (2573/2579 con peso>0), lo opuesto de "pocos vecinos concentrados de
# un lado" que busca ese filtro. Investigacion previa (misma sesion, sobre
# este checkpoint): 217/2579 hexagonos en percentil 1/99 de al menos una de
# estas 9 variables, de los cuales 152 no estaban cubiertos por los otros 2
# criterios. Ver calcular_h3_confianza_baja_bandwidth.
CONFIANZA_BAJA_VARIABLES_BANDWIDTH = [
    "slope_mean",
    "dist_hospital_km",
    "pct_area_enp",
    "temp_media_anual",
    "lluvia_mm_anual",
    "dist_parada_cercana_m",
    "tiempo_aeropuerto_min",
    "dist_costa_km",
    "sentimiento_medio",
]
CONFIANZA_BAJA_BANDWIDTH_PERCENTILES = (1, 99)
# Porcentaje de N (numero de hexagonos del modelo) usado para definir un
# bandwidth como "saturado"/casi-global. N=2579 en el checkpoint v3 ->
# umbral=2321.1; las 9 variables de arriba dieron bandwidth=2573 (>= umbral),
# las otras 5 dieron entre 132 y 960 (muy por debajo). Explicito aca (no
# hardcodeado en el cuerpo de la funcion) para que quede claro de donde sale
# el corte si se recalcula contra un checkpoint distinto en el futuro.
CONFIANZA_BAJA_BANDWIDTH_PCT = 0.9


def _es_periferico(lon, lat, lon_min, lon_max, lat_min, lat_max, margen_pct):
    """Un punto es 'periferico' si esta a <= margen_pct del rango total de
    lon o de lat del dataset -- mismo criterio usado en el diagnostico de
    estabilidad de coeficientes (sesion previa, sobre el mismo .pkl)."""
    rango_lon = lon_max - lon_min
    rango_lat = lat_max - lat_min
    cerca_borde_lon = (lon - lon_min) <= rango_lon * margen_pct or (lon_max - lon) <= rango_lon * margen_pct
    cerca_borde_lat = (lat - lat_min) <= rango_lat * margen_pct or (lat_max - lat) <= rango_lat * margen_pct
    return bool(cerca_borde_lon or cerca_borde_lat)


def calcular_h3_confianza_baja(df, model):
    """
    Recalcula (no hardcodea por h3_index) el conjunto de hexagonos con
    confianza_ptna='baja': union, sobre CONFIANZA_BAJA_VARIABLES, de los
    hexagonos cuyo coeficiente local esta en percentil 1 o 99 Y ADEMAS estan
    en zona periferica del dataset. Si el modelo se vuelve a correr con datos
    nuevos, este calculo se rehace solo -- no depende de una lista fija.
    """
    feature_names = model["feature_names"]
    params = model["params"]
    h3_model = model["h3_index"]

    faltantes = [v for v in CONFIANZA_BAJA_VARIABLES if v not in feature_names]
    if faltantes:
        raise RuntimeError(
            f"Las variables {faltantes} (usadas para confianza_ptna) no estan en "
            f"feature_names del modelo: {feature_names}."
        )

    coef_df = pd.DataFrame(params, columns=feature_names)
    coef_df["h3_index"] = h3_model

    lon_min, lon_max = df["centroide_lon"].min(), df["centroide_lon"].max()
    lat_min, lat_max = df["centroide_lat"].min(), df["centroide_lat"].max()
    periferico_by_h3 = {
        row.h3_index: _es_periferico(
            row.centroide_lon, row.centroide_lat, lon_min, lon_max, lat_min, lat_max,
            CONFIANZA_BAJA_MARGEN_PERIFERICO,
        )
        for row in df.itertuples()
    }

    p_bajo, p_alto = CONFIANZA_BAJA_PERCENTILES
    h3_confianza_baja = set()
    detalle_por_variable = {}
    for var in CONFIANZA_BAJA_VARIABLES:
        coef = coef_df[var].values
        p1 = np.percentile(coef, p_bajo)
        p99 = np.percentile(coef, p_alto)
        extremos = coef_df.loc[(coef <= p1) | (coef >= p99), "h3_index"]
        extremos_perifericos = [h for h in extremos if periferico_by_h3.get(h, False)]
        detalle_por_variable[var] = len(extremos_perifericos)
        h3_confianza_baja.update(extremos_perifericos)

    return h3_confianza_baja, detalle_por_variable


def calcular_h3_confianza_baja_cluster(model):
    """
    Hallazgo 11 (dataset v3): union, sobre CONFIANZA_BAJA_VARIABLES_CLUSTER, de
    los hexagonos cuyo coeficiente local esta en percentil 1 o 99 -- SIN filtro
    de periferia, a diferencia de calcular_h3_confianza_baja (Hallazgo 4).

    Motivo del criterio distinto: los extremos de altitud_media_m no estan en
    el borde del mapa con pocos vecinos reales (eso es lo que buscaba el
    filtro de periferia) -- estan en 2 clusters geograficos compactos con
    ventanas locales bien pobladas (136-137 de 138 vecinos posibles).
    La inestabilidad viene de colinealidad global moderada (VIF=13.4 contra
    4-5 variables geograficas relacionadas, ver Hallazgo 11), no de escasez
    de datos reales cerca. Exigir periferia aca descartaria estos clusters por
    el motivo equivocado -- por eso se omite ese filtro a proposito.

    Recalcula solo (no hardcodea por h3_index) -- si el modelo cambia, este
    calculo se rehace solo.
    """
    feature_names = model["feature_names"]
    params = model["params"]
    h3_model = model["h3_index"]

    faltantes = [v for v in CONFIANZA_BAJA_VARIABLES_CLUSTER if v not in feature_names]
    if faltantes:
        raise RuntimeError(
            f"Las variables {faltantes} (usadas para confianza_ptna, criterio cluster/Hallazgo 11) "
            f"no estan en feature_names del modelo: {feature_names}."
        )

    coef_df = pd.DataFrame(params, columns=feature_names)
    coef_df["h3_index"] = h3_model

    p_bajo, p_alto = CONFIANZA_BAJA_CLUSTER_PERCENTILES
    h3_confianza_baja = set()
    detalle_por_variable = {}
    for var in CONFIANZA_BAJA_VARIABLES_CLUSTER:
        coef = coef_df[var].values
        p1 = np.percentile(coef, p_bajo)
        p99 = np.percentile(coef, p_alto)
        extremos = coef_df.loc[(coef <= p1) | (coef >= p99), "h3_index"]
        detalle_por_variable[var] = len(extremos)
        h3_confianza_baja.update(extremos)

    return h3_confianza_baja, detalle_por_variable


def calcular_h3_confianza_baja_bandwidth(model):
    """
    Hallazgo 12 (dataset v3): union, sobre CONFIANZA_BAJA_VARIABLES_BANDWIDTH,
    de los hexagonos cuyo coeficiente local esta en percentil 1 o 99 -- SIN
    filtro de periferia, igual que calcular_h3_confianza_baja_cluster.

    Motivo del criterio (ver nota extensa al inicio del modulo y el comentario
    junto a CONFIANZA_BAJA_VARIABLES_BANDWIDTH): estas variables quedaron con
    bandwidth optimo pegado al techo del kernel adaptativo (~99.8% de N), por
    lo que el modelo las trata casi como efectos globales -- el coeficiente
    extremo no representa una relacion local real ni un estimador inestable
    (con tantos vecinos promediados la varianza del estimador deberia ser
    BAJA, al reves que en el criterio cluster de altitud_media_m). Es un
    mecanismo distinto a los otros 2 criterios, por eso vive en su propia
    funcion en vez de sumarse a alguna de las anteriores.

    El umbral de "saturado" (bandwidth >= CONFIANZA_BAJA_BANDWIDTH_PCT * N) se
    recalcula aca contra el N real del modelo (no se hardcodea el 2579 del
    checkpoint actual). CONFIANZA_BAJA_VARIABLES_BANDWIDTH es la lista ya
    confirmada (9 variables, ver comentario arriba) pero si en el futuro se
    corre este calculo contra un checkpoint distinto (modelo re-ajustado) y
    la lista de variables que superan el umbral cambia, se emite un warning
    para que quede documentado que el modelo cambio -- no se usa la lista
    recalculada para el filtro sin revisión manual, para no alterar el
    criterio de forma silenciosa.

    Recalcula el conjunto de hexagonos solo (no hardcodea por h3_index) -- si
    el modelo cambia, el percentil 1/99 se rehace solo sobre las variables de
    CONFIANZA_BAJA_VARIABLES_BANDWIDTH.
    """
    feature_names = model["feature_names"]
    params = model["params"]
    h3_model = model["h3_index"]
    bandwidths_full = model.get("bandwidths_full")

    faltantes = [v for v in CONFIANZA_BAJA_VARIABLES_BANDWIDTH if v not in feature_names]
    if faltantes:
        raise RuntimeError(
            f"Las variables {faltantes} (usadas para confianza_ptna, criterio bandwidth/Hallazgo 12) "
            f"no estan en feature_names del modelo: {feature_names}."
        )

    if bandwidths_full is not None:
        umbral_bandwidth = CONFIANZA_BAJA_BANDWIDTH_PCT * len(h3_model)
        bw_by_name = dict(zip(feature_names, np.asarray(bandwidths_full).flatten()))
        saturadas_recalculadas = sorted(
            v for v in feature_names if v != "intercept" and bw_by_name.get(v, 0) >= umbral_bandwidth
        )
        if sorted(CONFIANZA_BAJA_VARIABLES_BANDWIDTH) != saturadas_recalculadas:
            logging.getLogger(SCRIPT_NAME).warning(
                "El checkpoint cargado da una lista de variables con bandwidth >= %.1f%% de N "
                "distinta a CONFIANZA_BAJA_VARIABLES_BANDWIDTH (hardcodeada, confirmada sobre el "
                "checkpoint del Hallazgo 12). Esperada: %s. Recalculada: %s. El modelo probablemente "
                "cambio -- revisar si corresponde actualizar la constante.",
                CONFIANZA_BAJA_BANDWIDTH_PCT * 100,
                sorted(CONFIANZA_BAJA_VARIABLES_BANDWIDTH), saturadas_recalculadas,
            )

    coef_df = pd.DataFrame(params, columns=feature_names)
    coef_df["h3_index"] = h3_model

    p_bajo, p_alto = CONFIANZA_BAJA_BANDWIDTH_PERCENTILES
    h3_confianza_baja = set()
    detalle_por_variable = {}
    for var in CONFIANZA_BAJA_VARIABLES_BANDWIDTH:
        coef = coef_df[var].values
        p1 = np.percentile(coef, p_bajo)
        p99 = np.percentile(coef, p_alto)
        extremos = coef_df.loc[(coef <= p1) | (coef >= p99), "h3_index"]
        detalle_por_variable[var] = len(extremos)
        h3_confianza_baja.update(extremos)

    return h3_confianza_baja, detalle_por_variable


def parse_args():
    parser = argparse.ArgumentParser(description="Calcula ptna_score y produce el dataset final del Bloque 5")
    parser.add_argument(
        "--model",
        default=str(DATA_INTERIM_DIR / "ptna_mgwr_model_v3.pkl"),
        help="Pickle del modelo (default: analytics/mgwr/data/interim/ptna_mgwr_model_v3.pkl -- "
             "sufijo _v3 a proposito (Hallazgo 10), para no pisar el ptna_mgwr_model_v2.pkl -- ese "
             "primer intento sigue siendo el que se uso para diagnosticar la multicolinealidad, no "
             "se borra -- ni el ptna_mgwr_model.pkl del v1)",
    )
    parser.add_argument(
        "--dataset",
        default=str(DATA_INTERIM_DIR / "ptna_dataset_filtered_v3.parquet"),
        help="Dataset filtrado (default: analytics/mgwr/data/interim/ptna_dataset_filtered_v3.parquet -- "
             "sufijo _v3 a proposito (Hallazgo 10), para no pisar el ptna_dataset_filtered_v2.parquet "
             "ni el del v1)",
    )
    parser.add_argument(
        "--output",
        default=str(DATA_PROCESSED_DIR / "gold_h3_ptna_v3.parquet"),
        help="Parquet final de salida (default: analytics/mgwr/data/processed/gold_h3_ptna_v3.parquet -- "
             "sufijo _v3 a proposito (Hallazgo 10), para no pisar el gold_h3_ptna_v1.parquet del v1 "
             "(el v2 nunca llego a correr 05 -- no existe gold_h3_ptna_v2.parquet)",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    logger = setup_logging(SCRIPT_NAME)
    t0 = time.perf_counter()

    try:
        model_path = Path(args.model)
        dataset_path = Path(args.dataset)
        if not model_path.exists():
            raise FileNotFoundError(f"No existe {model_path}. Correr primero 04_run_model.py.")
        if not dataset_path.exists():
            raise FileNotFoundError(f"No existe {dataset_path}. Correr primero 02_filter_nan.py.")

        logger.info("Leyendo modelo %s", model_path)
        with open(model_path, "rb") as f:
            model = pickle.load(f)

        logger.info("Leyendo dataset filtrado %s", dataset_path)
        df = pd.read_parquet(dataset_path)

        required_keys = ["h3_index", "y", "predy"]
        missing_keys = [k for k in required_keys if k not in model]
        if missing_keys:
            raise RuntimeError(f"El pickle del modelo no tiene las claves esperadas: {missing_keys}.")

        if len(model["h3_index"]) != len(df):
            raise RuntimeError(
                f"El modelo tiene {len(model['h3_index'])} filas pero el dataset filtrado tiene {len(df)}. "
                f"Probablemente 02_filter_nan.py o 04_run_model.py corrieron sobre datos distintos -- "
                f"volver a correr el pipeline en orden (01 -> 02 -> 04 -> 05)."
            )

        logger.info(
            "Calculando confianza_ptna, criterio periferia/Hallazgo 4 (variables=%s, percentiles=%s, "
            "margen periferico=%.0f%%)...",
            CONFIANZA_BAJA_VARIABLES, CONFIANZA_BAJA_PERCENTILES, CONFIANZA_BAJA_MARGEN_PERIFERICO * 100,
        )
        h3_confianza_baja_periferia, detalle_confianza_periferia = calcular_h3_confianza_baja(df, model)
        for var, n in detalle_confianza_periferia.items():
            logger.info("  %s: %d hexagonos extremos (p1/p99) Y perifericos", var, n)

        logger.info(
            "Calculando confianza_ptna, criterio cluster/Hallazgo 11 (variables=%s, percentiles=%s, "
            "SIN filtro de periferia)...",
            CONFIANZA_BAJA_VARIABLES_CLUSTER, CONFIANZA_BAJA_CLUSTER_PERCENTILES,
        )
        h3_confianza_baja_cluster, detalle_confianza_cluster = calcular_h3_confianza_baja_cluster(model)
        for var, n in detalle_confianza_cluster.items():
            logger.info("  %s: %d hexagonos extremos (p1/p99), colinealidad global moderada (VIF>10)", var, n)

        logger.info(
            "Calculando confianza_ptna, criterio bandwidth casi-global/Hallazgo 12 (variables=%s, "
            "percentiles=%s, SIN filtro de periferia, umbral=%.0f%% de N)...",
            CONFIANZA_BAJA_VARIABLES_BANDWIDTH, CONFIANZA_BAJA_BANDWIDTH_PERCENTILES,
            CONFIANZA_BAJA_BANDWIDTH_PCT * 100,
        )
        h3_confianza_baja_bandwidth, detalle_confianza_bandwidth = calcular_h3_confianza_baja_bandwidth(model)
        for var, n in detalle_confianza_bandwidth.items():
            logger.info("  %s: %d hexagonos extremos (p1/p99), bandwidth casi-global", var, n)

        h3_confianza_baja = h3_confianza_baja_periferia | h3_confianza_baja_cluster | h3_confianza_baja_bandwidth
        detalle_confianza = {
            **detalle_confianza_periferia, **detalle_confianza_cluster, **detalle_confianza_bandwidth,
        }
        logger.info(
            "Total hexagonos marcados confianza_ptna='baja' (union de los 3 criterios, sin doble conteo): %d",
            len(h3_confianza_baja),
        )

        y = np.asarray(model["y"]).flatten()
        predy = np.asarray(model["predy"]).flatten()
        ptna_score = predy - y
        logger.info(
            "ptna_score calculado: %d valores, media=%.4f, std=%.4f",
            len(ptna_score), ptna_score.mean(), ptna_score.std(),
        )

        scores_by_h3 = pd.DataFrame({"h3_index": model["h3_index"], "ptna_score": ptna_score})
        result_df = df.merge(scores_by_h3, on="h3_index", how="left", validate="one_to_one")
        result_df["confianza_ptna"] = np.where(
            result_df["h3_index"].isin(h3_confianza_baja), "baja", "normal"
        )
        n_confianza_baja = int((result_df["confianza_ptna"] == "baja").sum())

        n_missing_score = int(result_df["ptna_score"].isna().sum())
        if n_missing_score > 0:
            logger.warning(
                "%d filas del dataset filtrado no encontraron match de h3_index en el modelo.",
                n_missing_score,
            )

        n_positive = int((result_df["ptna_score"] > 0).sum())
        n_negative = int((result_df["ptna_score"] < 0).sum())

        percentiles = [5, 10, 25, 50, 75, 90, 95]
        pct_values = result_df["ptna_score"].quantile([p / 100 for p in percentiles])
        logger.info("Percentiles de ptna_score:\n%s", pct_values.to_string())

        has_municipio = "municipio" in result_df.columns
        top_cols = ["h3_index"] + (["municipio"] if has_municipio else []) + ["ptna_score", "confianza_ptna"]
        top10 = result_df.sort_values("ptna_score", ascending=False).head(TOP_N)[top_cols]
        n_top10_confianza_baja = int((top10["confianza_ptna"] == "baja").sum())
        logger.info("Top %d hexagonos por ptna_score:\n%s", TOP_N, top10.to_string(index=False))
        if n_top10_confianza_baja:
            logger.warning(
                "%d de los top %d hexagonos tienen confianza_ptna='baja' -- ver detalle.",
                n_top10_confianza_baja, TOP_N,
            )
        if not has_municipio:
            logger.info(
                "Columna 'municipio' no esta presente en el dataset filtrado -- la query de "
                "01_build_dataset.py no la selecciona (no estaba en el pedido original). "
                "Top 10 reportado solo con h3_index."
            )

        DATA_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        result_df.to_parquet(output_path, index=False)
        logger.info("Dataset final guardado en %s", output_path)

        elapsed = time.perf_counter() - t0
        logger.info("Script finalizado OK en %.1f s.", elapsed)

    except Exception:
        logger.exception("Fallo en %s", SCRIPT_NAME)
        print(f"\nERROR en {SCRIPT_NAME} -- ver analytics/mgwr/logs/{SCRIPT_NAME}.log para el detalle.")
        sys.exit(1)

    print("\n" + "=" * 60)
    print(f"RESUMEN -- {SCRIPT_NAME}")
    print("=" * 60)
    print(f"Hexagonos con ptna_score > 0 (oportunidad): {n_positive}")
    print(f"Hexagonos con ptna_score < 0 (sobre-explotado): {n_negative}")
    print(
        f"Hexagonos con confianza_ptna='baja' (union de 3 criterios distintos, sin doble conteo): "
        f"{n_confianza_baja} / {len(result_df)} ({n_confianza_baja / len(result_df) * 100:.1f}%)"
    )
    print(f"  Criterio periferia (Hallazgo 4: bandwidth chico + zona periferica del mapa):")
    for var, n in detalle_confianza_periferia.items():
        print(f"    - {var}: {n} hexagonos")
    print(f"  Criterio cluster (Hallazgo 11: colinealidad global moderada, VIF>10, sin filtro de periferia):")
    for var, n in detalle_confianza_cluster.items():
        print(f"    - {var}: {n} hexagonos")
    print(f"  Criterio bandwidth casi-global (Hallazgo 12: bandwidth >= {CONFIANZA_BAJA_BANDWIDTH_PCT*100:.0f}% de N, sin filtro de periferia):")
    for var, n in detalle_confianza_bandwidth.items():
        print(f"    - {var}: {n} hexagonos")
    if n_missing_score:
        print(f"AVISO: {n_missing_score} filas sin match de h3_index entre dataset y modelo.")
    print("Percentiles de ptna_score:")
    print(pct_values.round(4).to_string())
    if not has_municipio:
        print("(municipio no disponible en el dataset -- top 10 solo con h3_index, ver detalle en el log)")
    print(f"\nTop {TOP_N} hexagonos por ptna_score:")
    print(top10.round(4).to_string(index=False))
    if n_top10_confianza_baja:
        print(
            f"\n*** AVISO: {n_top10_confianza_baja} de los top {TOP_N} tienen confianza_ptna='baja' "
            f"-- ver columna arriba antes de reportar estos como hallazgo solido. ***"
        )
    else:
        print(f"\nNinguno de los top {TOP_N} tiene confianza_ptna='baja'.")
    print(f"\nGuardado en: {output_path}")
    print(f"Tiempo total: {elapsed:.1f} s")
    print("=" * 60)


if __name__ == "__main__":
    main()
