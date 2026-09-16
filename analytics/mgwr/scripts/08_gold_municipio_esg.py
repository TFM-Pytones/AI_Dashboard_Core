"""
08_gold_municipio_esg.py
-------------------------
Bloque 5 (MGWR/PTNA) -- Subtarea 5.3, dimension mesomunicipal: crea
gold.gold_bloque5_municipio_esg_v1, el Indice ESG Territorial a nivel de
municipio (31 filas, una por municipio de Tenerife).

Complementa a gold.gold_h3_esg_v1 (07_gold_h3_esg.py, nivel hexagono H3),
pero NO es una simple agregacion de esa tabla: usa un set de variables
distinto, mas orientado a indicadores socioeconomicos municipales que solo
existen a esa escala (paro, dependencia de la hosteleria, piramide de edad,
autonomos), ademas de un subconjunto ambiental agregado desde gold_h3_master.

Fuentes (todas de solo lectura, la unica escritura de este script es
gold.gold_bloque5_municipio_esg_v1):
- gold.gold_h3_master: agregado por cod_municipio -> variables [E] y
  ratio_hoteles de [G].
- gold.gold_municipio_master: variables [S] socioeconomicas + nombre oficial
  del municipio.
- gold.gold_municipio_empleo: pct_autonomos ([G]), periodo mas reciente con
  dato completo en los 31 municipios (verificado 2026-Q2, 31/31, sin NULL).
- silver.silver_istac_anual (anio=2025, verificado 31/31 sin NULL):
  edad_media y ratio_dependencia ([S]).

Decisiones de diseno (confirmadas por el usuario tras varias rondas de
verificacion en esta investigacion, ver conversacion/docs Bloque 5 Subtarea
5.3 -- NO reabrir estas decisiones):
- Ponderacion de pilares: E=0.40, S=0.40, G=0.20 (igual que gold_h3_esg_v1).
- Dentro de cada pilar, promedio simple equal-weight de las variables
  normalizadas (a diferencia de gold_h3_esg_v1, aca no hay NULLs dentro de
  pilar -- las 31 filas tienen las 31 variables completas -- por lo que no
  hace falta la logica de AVG-ignora-NULL ni columnas *_completo).
- Normalizacion MinMax (0-1) sobre los 31 municipios, invirtiendo (1 -
  normalizado) las variables de polaridad NEGATIVA (mas crudo = peor).
- pct_area_enp se agrega ponderado por area del hexagono (SUM(pct_area_enp *
  area_km2) / SUM(area_km2)), no AVG simple -- verificado que da
  practicamente lo mismo pero es la agregacion correcta.
- dias_ola_calor_anual se capea en el p95 (calculado en la misma query con
  PERCENTILE_CONT(0.95) sobre los 31 municipios, NUNCA hardcodeado) antes de
  normalizar -- mismo patron de winsorizacion que densidad_plazas_km2 en
  gold_h3_esg_v1. Candelaria es el municipio que dispara el cap (~17.68 sin
  capear).
- ratio_hoteles = SUM(n_hoteles) / SUM(n_hoteles + n_vv) agregado por
  cod_municipio, NUNCA el promedio de los ratios por hexagono (verificado en
  ronda anterior que da resultados muy distintos, ej. El Tanque).
- ratio_dependencia = (poblacion_total - poblacion_15_64) / poblacion_15_64,
  forma simplificada y algebraicamente equivalente a
  (poblacion_0_14_proxy + poblacion_65_mas) / poblacion_15_64.
- pct_dependencia_hosteleria y plazas_por_1000_hab se mantienen ambas pese al
  VIF preexistente 11.6-16.3 entre si -- decision explicita del usuario, no
  se tocan.
- ndbi_medio, cambio_luz_nocturna_pct y pob_turistica_equiv quedaron
  descartadas explicitamente de este indice.

Uso:
    python 08_gold_municipio_esg.py
"""

import sys
import time
from pathlib import Path

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _db import get_engine, setup_logging

SCRIPT_NAME = "08_gold_municipio_esg"

DDL = """
DROP TABLE IF EXISTS gold.gold_bloque5_municipio_esg_v1;

CREATE TABLE gold.gold_bloque5_municipio_esg_v1 AS
WITH h3_agg AS (
    -- [E] y ratio_hoteles [G], agregados por municipio desde gold_h3_master.
    SELECT
        cod_municipio,
        AVG(ndvi_medio)                                            AS ndvi_medio,
        AVG(viirs_medio)                                           AS viirs_medio,
        SUM(pct_area_enp * area_km2) / NULLIF(SUM(area_km2), 0)    AS pct_area_enp,
        AVG(dias_ola_calor_anual)                                  AS dias_ola_calor_anual,
        AVG(amplitud_termica_media)                                AS amplitud_termica_media,
        SUM(n_hoteles)::numeric / NULLIF(SUM(n_hoteles + n_vv), 0) AS ratio_hoteles
    FROM gold.gold_h3_master
    GROUP BY cod_municipio
),

empleo_reciente AS (
    -- Periodo mas reciente con dato completo en los 31 municipios (verificado: 2026-Q2, 31/31, sin NULL).
    SELECT cod_municipio, pct_autonomos
    FROM gold.gold_municipio_empleo
    WHERE periodo = (SELECT MAX(periodo) FROM gold.gold_municipio_empleo)
),

istac_2025 AS (
    -- anio=2025 verificado 31/31 municipios, sin NULL en las columnas usadas.
    SELECT
        municipio_cod AS cod_municipio,
        edad_media,
        (poblacion_total - poblacion_15_64)::numeric / NULLIF(poblacion_15_64, 0) AS ratio_dependencia
    FROM silver.silver_istac_anual
    WHERE anio = 2025
),

base AS (
    SELECT
        m.cod_municipio,
        m.municipio,

        -- [E] 40% (gold_h3_master, agregado)
        h.ndvi_medio,
        h.viirs_medio,
        h.pct_area_enp,
        h.dias_ola_calor_anual,
        h.amplitud_termica_media,

        -- [S] 40% (gold_municipio_master + silver_istac_anual)
        m.pct_dependencia_hosteleria,
        m.paro_actual,
        m.var_paro_pct,
        m.plazas_por_1000_hab,
        i.edad_media,
        i.ratio_dependencia,

        -- [G] 20% (gold_municipio_empleo + gold_h3_master agregado)
        e.pct_autonomos,
        h.ratio_hoteles

    FROM gold.gold_municipio_master m
    JOIN h3_agg h          ON h.cod_municipio = m.cod_municipio
    JOIN empleo_reciente e ON e.cod_municipio = m.cod_municipio
    JOIN istac_2025 i      ON i.cod_municipio = m.cod_municipio
),

stats AS (
    SELECT
        MIN(ndvi_medio) AS ndvi_min, MAX(ndvi_medio) AS ndvi_max,
        MIN(viirs_medio) AS viirs_min, MAX(viirs_medio) AS viirs_max,
        MIN(pct_area_enp) AS enp_min, MAX(pct_area_enp) AS enp_max,
        MIN(dias_ola_calor_anual) AS ola_min, MAX(dias_ola_calor_anual) AS ola_max,
        percentile_cont(0.95) WITHIN GROUP (ORDER BY dias_ola_calor_anual) AS ola_p95,
        MIN(amplitud_termica_media) AS amp_min, MAX(amplitud_termica_media) AS amp_max,

        MIN(pct_dependencia_hosteleria) AS dep_host_min, MAX(pct_dependencia_hosteleria) AS dep_host_max,
        MIN(paro_actual) AS paro_min, MAX(paro_actual) AS paro_max,
        MIN(var_paro_pct) AS var_paro_min, MAX(var_paro_pct) AS var_paro_max,
        MIN(plazas_por_1000_hab) AS plazas_min, MAX(plazas_por_1000_hab) AS plazas_max,
        MIN(edad_media) AS edad_min, MAX(edad_media) AS edad_max,
        MIN(ratio_dependencia) AS ratiodep_min, MAX(ratio_dependencia) AS ratiodep_max,

        MIN(pct_autonomos) AS auton_min, MAX(pct_autonomos) AS auton_max,
        MIN(ratio_hoteles) AS ratiohot_min, MAX(ratio_hoteles) AS ratiohot_max
    FROM base
),

normalized AS (
    SELECT
        b.cod_municipio,
        b.municipio,

        -- crudas (trazabilidad), incluyendo dias_ola_calor_anual ya capeado en p95
        b.ndvi_medio,
        b.viirs_medio,
        b.pct_area_enp,
        LEAST(b.dias_ola_calor_anual, s.ola_p95)      AS dias_ola_calor_anual_capeado,
        b.amplitud_termica_media,
        b.pct_dependencia_hosteleria,
        b.paro_actual,
        b.var_paro_pct,
        b.plazas_por_1000_hab,
        b.edad_media,
        b.ratio_dependencia,
        b.pct_autonomos,
        b.ratio_hoteles,

        -- [E] normalizadas
        (b.ndvi_medio - s.ndvi_min) / NULLIF(s.ndvi_max - s.ndvi_min, 0)                          AS n_ndvi_medio,
        1 - (b.viirs_medio - s.viirs_min) / NULLIF(s.viirs_max - s.viirs_min, 0)                  AS n_viirs_medio,
        (b.pct_area_enp - s.enp_min) / NULLIF(s.enp_max - s.enp_min, 0)                           AS n_pct_area_enp,
        1 - (LEAST(b.dias_ola_calor_anual, s.ola_p95) - s.ola_min) / NULLIF(s.ola_p95 - s.ola_min, 0) AS n_dias_ola_calor,
        1 - (b.amplitud_termica_media - s.amp_min) / NULLIF(s.amp_max - s.amp_min, 0)             AS n_amplitud_termica,

        -- [S] normalizadas (todas invertidas)
        1 - (b.pct_dependencia_hosteleria - s.dep_host_min) / NULLIF(s.dep_host_max - s.dep_host_min, 0) AS n_dep_hosteleria,
        1 - (b.paro_actual - s.paro_min) / NULLIF(s.paro_max - s.paro_min, 0)                            AS n_paro_actual,
        1 - (b.var_paro_pct - s.var_paro_min) / NULLIF(s.var_paro_max - s.var_paro_min, 0)               AS n_var_paro,
        1 - (b.plazas_por_1000_hab - s.plazas_min) / NULLIF(s.plazas_max - s.plazas_min, 0)              AS n_plazas_1000hab,
        1 - (b.edad_media - s.edad_min) / NULLIF(s.edad_max - s.edad_min, 0)                             AS n_edad_media,
        1 - (b.ratio_dependencia - s.ratiodep_min) / NULLIF(s.ratiodep_max - s.ratiodep_min, 0)          AS n_ratio_dependencia,

        -- [G] normalizadas (ambas directas)
        (b.pct_autonomos - s.auton_min) / NULLIF(s.auton_max - s.auton_min, 0)                    AS n_pct_autonomos,
        (b.ratio_hoteles - s.ratiohot_min) / NULLIF(s.ratiohot_max - s.ratiohot_min, 0)            AS n_ratio_hoteles

    FROM base b
    CROSS JOIN stats s
)

SELECT
    cod_municipio,
    municipio,

    -- crudas [E]
    ndvi_medio,
    viirs_medio,
    pct_area_enp,
    dias_ola_calor_anual_capeado,
    amplitud_termica_media,

    -- crudas [S]
    pct_dependencia_hosteleria,
    paro_actual,
    var_paro_pct,
    plazas_por_1000_hab,
    edad_media,
    ratio_dependencia,

    -- crudas [G]
    pct_autonomos,
    ratio_hoteles,

    -- scores por pilar (0-100)
    ROUND((SELECT AVG(v) FROM unnest(ARRAY[
        n_ndvi_medio, n_viirs_medio, n_pct_area_enp, n_dias_ola_calor, n_amplitud_termica
    ]) AS v)::numeric * 100, 2) AS e_score,
    ROUND((SELECT AVG(v) FROM unnest(ARRAY[
        n_dep_hosteleria, n_paro_actual, n_var_paro, n_plazas_1000hab, n_edad_media, n_ratio_dependencia
    ]) AS v)::numeric * 100, 2) AS s_score,
    ROUND((SELECT AVG(v) FROM unnest(ARRAY[
        n_pct_autonomos, n_ratio_hoteles
    ]) AS v)::numeric * 100, 2) AS g_score,

    -- score final ponderado (0-100)
    ROUND((
        0.4 * (SELECT AVG(v) FROM unnest(ARRAY[
            n_ndvi_medio, n_viirs_medio, n_pct_area_enp, n_dias_ola_calor, n_amplitud_termica
        ]) AS v)
        + 0.4 * (SELECT AVG(v) FROM unnest(ARRAY[
            n_dep_hosteleria, n_paro_actual, n_var_paro, n_plazas_1000hab, n_edad_media, n_ratio_dependencia
        ]) AS v)
        + 0.2 * (SELECT AVG(v) FROM unnest(ARRAY[
            n_pct_autonomos, n_ratio_hoteles
        ]) AS v)
    )::numeric * 100, 2) AS esg_municipal_score

FROM normalized
ORDER BY esg_municipal_score DESC NULLS LAST;

CREATE INDEX IF NOT EXISTS idx_gold_bloque5_municipio_esg_v1_cod_municipio
    ON gold.gold_bloque5_municipio_esg_v1 (cod_municipio);
"""

VERIFY_QUERY = """
SELECT
    COUNT(*) AS n_municipios,
    COUNT(DISTINCT cod_municipio) AS n_cod_distinct,
    COUNT(*) FILTER (WHERE esg_municipal_score IS NULL) AS n_null_esg,
    COUNT(*) FILTER (WHERE e_score IS NULL) AS n_null_e,
    COUNT(*) FILTER (WHERE s_score IS NULL) AS n_null_s,
    COUNT(*) FILTER (WHERE g_score IS NULL) AS n_null_g,
    ROUND(MIN(esg_municipal_score)::numeric, 2) AS esg_min,
    ROUND(percentile_cont(0.5) WITHIN GROUP (ORDER BY esg_municipal_score)::numeric, 2) AS esg_p50,
    ROUND(MAX(esg_municipal_score)::numeric, 2) AS esg_max,
    ROUND(MIN(e_score)::numeric, 2) AS e_min, ROUND(MAX(e_score)::numeric, 2) AS e_max,
    ROUND(MIN(s_score)::numeric, 2) AS s_min, ROUND(MAX(s_score)::numeric, 2) AS s_max,
    ROUND(MIN(g_score)::numeric, 2) AS g_min, ROUND(MAX(g_score)::numeric, 2) AS g_max
FROM gold.gold_bloque5_municipio_esg_v1;
"""


def main():
    logger = setup_logging(SCRIPT_NAME)
    t0 = time.perf_counter()

    try:
        logger.info("Conectando a Postgres (Azure)...")
        engine = get_engine()

        logger.info("Creando gold.gold_bloque5_municipio_esg_v1 (DROP + CREATE TABLE AS)...")
        with engine.begin() as conn:
            for statement in DDL.strip().split(";\n\n"):
                statement = statement.strip()
                if statement:
                    conn.execute(text(statement))
        logger.info("Tabla creada OK.")

        with engine.connect() as conn:
            row = conn.execute(text(VERIFY_QUERY)).fetchone()

        elapsed = time.perf_counter() - t0
        logger.info("Script finalizado OK en %.1f s.", elapsed)

    except Exception:
        logger.exception("Fallo en %s", SCRIPT_NAME)
        print(f"\nERROR en {SCRIPT_NAME} -- ver analytics/mgwr/logs/{SCRIPT_NAME}.log para el detalle.")
        sys.exit(1)

    print("\n" + "=" * 60)
    print(f"RESUMEN -- {SCRIPT_NAME}")
    print("=" * 60)
    print(f"gold.gold_bloque5_municipio_esg_v1 creada")
    print(f"Fila/columnas verify: {row}")
    print(f"Tiempo total: {elapsed:.1f} s")
    print("=" * 60)


if __name__ == "__main__":
    main()
