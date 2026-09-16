"""
07_gold_h3_esg.py
------------------
Bloque 5 (MGWR/PTNA) -- Subtarea 5.3, dimension microespacial: crea
gold.gold_h3_esg_v1, el Indice ESG Territorial a nivel de hexagono H3.

Independiente del pipeline MGWR/PTNA (00-06): no lee ni escribe nada de
gold.gold_h3_ptna_v3. Usa tablas ya existentes y estables: gold.gold_h3_master,
gold.gold_h3_accesibilidad, gold.nlp_sentimiento_resenas, gold.nlp_aspectos_resenas.
Detalle completo de la investigacion, las decisiones de diseno y el resultado
verificado en docs/contexto_maestro_proyecto_ptna.md, seccion 5 ("Indice ESG
H3 (microespacial) -- construido y cerrado").

Reconstruido a posteriori (17-sep-2026) porque el script original que genero
la tabla real nunca se guardo versionado -- se corrio "suelto" en una sesion
anterior. Este archivo se valido fila por fila contra gold.gold_h3_esg_v1 ya
poblada (2579/2579 filas, diferencia maxima 0.00 en esg_h3_score/e_score/
s_score/g_score y en ambas columnas de trazabilidad) antes de darlo por
definitivo -- no es una reconstruccion aproximada, reproduce exactamente lo
que ya esta en produccion.

2 huecos resueltos que explican por que el SQL no es un LEFT JOIN trivial:
- pct_quejas_ruido: gold_h3_sentimiento.queja_principal da el aspecto negativo
  MAS frecuente, no una tasa. Se agrega gold.nlp_aspectos_resenas (mismo join
  por resena_id+fuente contra nlp_sentimiento_resenas que ya usa
  00_create_sentimiento_table.py) filtrando aspecto ILIKE '%ruido%' (el dato
  real tiene 3 variantes: ruido/ruidos/ruido de obra, no un literal unico) Y
  sentimiento='Negative', sobre el total de aspectos detectados en el hexagono.
- Bienes culturales / oficina de turismo oficial: silver.silver_bienes_
  interes_culturales y silver.silver_oficinas_turismo existen pero YA estan
  fusionadas en gold_h3_master.n_pois_institucionales (= COUNT(fuente=
  'IDE_Canarias')) -- no se joinean aparte, séria redundante.
  es_zona_turistica_oficial (boolean) no existe en gold_h3_master; se usa
  pct_area_zona_turistica (continuo 0-1) como reemplazo mas preciso.

Decisiones de diseno explicitas (ver seccion 5 del doc para el detalle):
- Normalizacion MinMax (0-1) por variable, invirtiendo donde "mas crudo = peor".
- Ponderacion equal-weight DENTRO de cada pilar (E: 1/9, S: 1/4, G: 1/3) --
  asuncion explicita, el plan no especifica pesos por variable.
- Promedio que IGNORA NULL dentro de cada pilar (AVG sobre unnest, no division
  por N fijo) -- un hexagono sin alojamiento no arrastra el ratio de hoteles a
  0, uno sin resenas no arrastra pct_quejas_ruido a 0. Columnas de trazabilidad
  s_score_completo/g_score_completo (mismo espiritu que n_resenas_sentimiento
  en gold_h3_sentimiento) marcan cuando esto pasa.
- densidad_plazas_km2 capeada en el p95 (LEAST contra PERCENTILE_CONT(0.95)
  calculado en la misma query, nunca hardcodeado) antes de normalizar --
  distribucion muy sesgada (mediana 0, maximo ~14.463 plazas/km2) que sin el
  cap dejaba al 95% de los hexagonos comprimidos entre 0.98-1.0 en ese
  componente.
- Pilar G NO ajustado pese a estar casi todo en 0 (n_pois_institucionales=0 en
  98%, pct_area_zona_turistica=0 en 96%, ratio_hoteles=0 en 89% de los
  hexagonos donde existe): es escasez estructural de dato real, no un
  problema de normalizacion corregible con capeo/log -- se documenta como
  limitacion, no se fuerza una transformacion.

Uso:
    python 07_gold_h3_esg.py
"""

import sys
import time
from pathlib import Path

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _db import get_engine, setup_logging

SCRIPT_NAME = "07_gold_h3_esg"

DDL = """
DROP TABLE IF EXISTS gold.gold_h3_esg_v1;

CREATE TABLE gold.gold_h3_esg_v1 AS
WITH ruido_h3 AS (
    SELECT
        s.h3_index,
        COUNT(*) AS n_aspectos_total,
        COUNT(*) FILTER (WHERE a.aspecto ILIKE '%ruido%' AND a.sentimiento = 'Negative')::numeric
            / NULLIF(COUNT(*), 0) AS pct_quejas_ruido
    FROM gold.nlp_aspectos_resenas a
    JOIN gold.nlp_sentimiento_resenas s
      ON s.resena_id = a.resena_id AND s.fuente = a.fuente
    WHERE s.h3_index IS NOT NULL AND a.aspecto IS NOT NULL
    GROUP BY s.h3_index
),

base AS (
    SELECT
        m.h3_index,
        m.municipio,

        -- [E] 40%
        m.ndvi_medio,
        (m.ndvi_2026 - m.ndvi_2022)                              AS ndvi_delta,
        m.viirs_medio,
        m.cambio_luz_nocturna_pct,
        m.ndbi_medio,
        m.pct_area_enp,
        m.dist_costa_km,                                         -- directa: mas lejos de costa = menos presion/fragilidad litoral = mejor
        m.dias_ola_calor_anual,
        m.amplitud_termica_media,

        -- [S] 40%
        m.n_plazas_registro / NULLIF(m.area_km2, 0)              AS densidad_plazas_km2,
        a.dist_hospital_km,
        a.dist_parada_cercana_m,
        r.pct_quejas_ruido,                                      -- NULL si el hexagono no tiene resenas (~84%)

        -- [G] 20%
        m.n_hoteles::numeric / NULLIF(m.n_hoteles + m.n_vv, 0)   AS ratio_hoteles,  -- NULL si no hay alojamiento (~61%)
        m.n_pois_institucionales,
        m.pct_area_zona_turistica

    FROM gold.gold_h3_master m
    LEFT JOIN gold.gold_h3_accesibilidad a ON a.h3_index = m.h3_index
    LEFT JOIN ruido_h3 r ON r.h3_index = m.h3_index
),

stats AS (
    SELECT
        MIN(ndvi_medio) AS ndvi_medio_min, MAX(ndvi_medio) AS ndvi_medio_max,
        MIN(ndvi_delta) AS ndvi_delta_min, MAX(ndvi_delta) AS ndvi_delta_max,
        MIN(viirs_medio) AS viirs_medio_min, MAX(viirs_medio) AS viirs_medio_max,
        MIN(cambio_luz_nocturna_pct) AS cambio_luz_min, MAX(cambio_luz_nocturna_pct) AS cambio_luz_max,
        MIN(ndbi_medio) AS ndbi_medio_min, MAX(ndbi_medio) AS ndbi_medio_max,
        MIN(pct_area_enp) AS pct_area_enp_min, MAX(pct_area_enp) AS pct_area_enp_max,
        MIN(dist_costa_km) AS dist_costa_min, MAX(dist_costa_km) AS dist_costa_max,
        MIN(dias_ola_calor_anual) AS ola_calor_min, MAX(dias_ola_calor_anual) AS ola_calor_max,
        MIN(amplitud_termica_media) AS amp_termica_min, MAX(amplitud_termica_media) AS amp_termica_max,
        MIN(densidad_plazas_km2) AS dens_plazas_min, MAX(densidad_plazas_km2) AS dens_plazas_max,
        percentile_cont(0.95) WITHIN GROUP (ORDER BY densidad_plazas_km2) AS dens_plazas_p95,
        MIN(dist_hospital_km) AS dist_hosp_min, MAX(dist_hospital_km) AS dist_hosp_max,
        MIN(dist_parada_cercana_m) AS dist_parada_min, MAX(dist_parada_cercana_m) AS dist_parada_max,
        MIN(pct_quejas_ruido) AS pct_ruido_min, MAX(pct_quejas_ruido) AS pct_ruido_max,
        MIN(ratio_hoteles) AS ratio_hoteles_min, MAX(ratio_hoteles) AS ratio_hoteles_max,
        MIN(n_pois_institucionales) AS pois_inst_min, MAX(n_pois_institucionales) AS pois_inst_max,
        MIN(pct_area_zona_turistica) AS zona_tur_min, MAX(pct_area_zona_turistica) AS zona_tur_max
    FROM base
),

normalized AS (
    SELECT
        b.h3_index,
        b.municipio,
        b.ratio_hoteles,
        b.pct_quejas_ruido,

        -- [E] directas (mas alto en crudo = mejor)
        (b.ndvi_medio - s.ndvi_medio_min) / NULLIF(s.ndvi_medio_max - s.ndvi_medio_min, 0) AS n_ndvi_medio,
        (b.ndvi_delta - s.ndvi_delta_min) / NULLIF(s.ndvi_delta_max - s.ndvi_delta_min, 0) AS n_ndvi_delta,
        (b.pct_area_enp - s.pct_area_enp_min) / NULLIF(s.pct_area_enp_max - s.pct_area_enp_min, 0) AS n_pct_area_enp,
        (b.dist_costa_km - s.dist_costa_min) / NULLIF(s.dist_costa_max - s.dist_costa_min, 0) AS n_dist_costa_km,

        -- [E] invertidas (mas alto en crudo = peor)
        1 - (b.viirs_medio - s.viirs_medio_min) / NULLIF(s.viirs_medio_max - s.viirs_medio_min, 0)              AS n_viirs_medio,
        1 - (b.cambio_luz_nocturna_pct - s.cambio_luz_min) / NULLIF(s.cambio_luz_max - s.cambio_luz_min, 0)     AS n_cambio_luz,
        1 - (b.ndbi_medio - s.ndbi_medio_min) / NULLIF(s.ndbi_medio_max - s.ndbi_medio_min, 0)                  AS n_ndbi_medio,
        1 - (b.dias_ola_calor_anual - s.ola_calor_min) / NULLIF(s.ola_calor_max - s.ola_calor_min, 0)           AS n_dias_ola_calor,
        1 - (b.amplitud_termica_media - s.amp_termica_min) / NULLIF(s.amp_termica_max - s.amp_termica_min, 0)   AS n_amp_termica,

        -- [S] todas invertidas (mas alto en crudo = peor)
        -- densidad_plazas_km2 capeada en p95 antes de normalizar (winsorizacion simple: LEAST
        -- contra el p95 real de la CTE stats, no un numero hardcodeado).
        1 - (LEAST(b.densidad_plazas_km2, s.dens_plazas_p95) - s.dens_plazas_min) / NULLIF(s.dens_plazas_p95 - s.dens_plazas_min, 0) AS n_densidad_plazas,
        1 - (b.dist_hospital_km - s.dist_hosp_min) / NULLIF(s.dist_hosp_max - s.dist_hosp_min, 0)                   AS n_dist_hospital,
        1 - (b.dist_parada_cercana_m - s.dist_parada_min) / NULLIF(s.dist_parada_max - s.dist_parada_min, 0)        AS n_dist_parada,
        1 - (b.pct_quejas_ruido - s.pct_ruido_min) / NULLIF(s.pct_ruido_max - s.pct_ruido_min, 0)                   AS n_pct_quejas_ruido,

        -- [G] directas (mas alto en crudo = mejor)
        (b.ratio_hoteles - s.ratio_hoteles_min) / NULLIF(s.ratio_hoteles_max - s.ratio_hoteles_min, 0)              AS n_ratio_hoteles,
        (b.n_pois_institucionales - s.pois_inst_min) / NULLIF(s.pois_inst_max - s.pois_inst_min, 0)                 AS n_pois_institucionales,
        (b.pct_area_zona_turistica - s.zona_tur_min) / NULLIF(s.zona_tur_max - s.zona_tur_min, 0)                   AS n_zona_turistica

    FROM base b
    CROSS JOIN stats s
)

SELECT
    h3_index,
    municipio,
    ROUND((SELECT AVG(v) FROM unnest(ARRAY[
        n_ndvi_medio, n_ndvi_delta, n_viirs_medio, n_cambio_luz, n_ndbi_medio,
        n_pct_area_enp, n_dist_costa_km, n_dias_ola_calor, n_amp_termica
    ]) AS v)::numeric, 4) AS e_score,
    ROUND((SELECT AVG(v) FROM unnest(ARRAY[
        n_densidad_plazas, n_dist_hospital, n_dist_parada, n_pct_quejas_ruido
    ]) AS v)::numeric, 4) AS s_score,
    ROUND((SELECT AVG(v) FROM unnest(ARRAY[
        n_ratio_hoteles, n_pois_institucionales, n_zona_turistica
    ]) AS v)::numeric, 4) AS g_score,
    ROUND((
        0.4 * (SELECT AVG(v) FROM unnest(ARRAY[
            n_ndvi_medio, n_ndvi_delta, n_viirs_medio, n_cambio_luz, n_ndbi_medio,
            n_pct_area_enp, n_dist_costa_km, n_dias_ola_calor, n_amp_termica
        ]) AS v)
        + 0.4 * (SELECT AVG(v) FROM unnest(ARRAY[
            n_densidad_plazas, n_dist_hospital, n_dist_parada, n_pct_quejas_ruido
        ]) AS v)
        + 0.2 * (SELECT AVG(v) FROM unnest(ARRAY[
            n_ratio_hoteles, n_pois_institucionales, n_zona_turistica
        ]) AS v)
    )::numeric * 100, 2) AS esg_h3_score,
    -- Columnas informativas de trazabilidad (no afectan el calculo, mismo espiritu que
    -- n_resenas_sentimiento en gold_h3_sentimiento): marcan cuando el pilar promedio
    -- sobre menos variables de las previstas porque el dato de origen es NULL, no 0.
    (pct_quejas_ruido IS NOT NULL) AS s_score_completo,
    (ratio_hoteles IS NOT NULL)    AS g_score_completo
FROM normalized
ORDER BY esg_h3_score DESC NULLS LAST;

CREATE INDEX IF NOT EXISTS idx_gold_h3_esg_v1_h3_index
    ON gold.gold_h3_esg_v1 (h3_index);
"""

VERIFY_QUERY = """
SELECT
    COUNT(*) AS n_hexagonos,
    ROUND(MIN(esg_h3_score)::numeric, 2) AS esg_min,
    ROUND(percentile_cont(0.5) WITHIN GROUP (ORDER BY esg_h3_score)::numeric, 2) AS esg_p50,
    ROUND(percentile_cont(0.95) WITHIN GROUP (ORDER BY esg_h3_score)::numeric, 2) AS esg_p95,
    ROUND(MAX(esg_h3_score)::numeric, 2) AS esg_max,
    ROUND(AVG(esg_h3_score)::numeric, 2) AS esg_media,
    COUNT(*) FILTER (WHERE s_score_completo) AS n_s_completo,
    COUNT(*) FILTER (WHERE g_score_completo) AS n_g_completo
FROM gold.gold_h3_esg_v1;
"""


def main():
    logger = setup_logging(SCRIPT_NAME)
    t0 = time.perf_counter()

    try:
        logger.info("Conectando a Postgres (Azure)...")
        engine = get_engine()

        logger.info("Creando gold.gold_h3_esg_v1 (DROP + CREATE TABLE AS)...")
        with engine.begin() as conn:
            for statement in DDL.strip().split(";\n\n"):
                statement = statement.strip()
                if statement:
                    conn.execute(text(statement))
        logger.info("Tabla creada OK.")

        with engine.connect() as conn:
            row = conn.execute(text(VERIFY_QUERY)).fetchone()
        (n_hex, esg_min, esg_p50, esg_p95, esg_max, esg_media,
         n_s_completo, n_g_completo) = row

        elapsed = time.perf_counter() - t0
        logger.info("Script finalizado OK en %.1f s.", elapsed)

    except Exception:
        logger.exception("Fallo en %s", SCRIPT_NAME)
        print(f"\nERROR en {SCRIPT_NAME} -- ver analytics/mgwr/logs/{SCRIPT_NAME}.log para el detalle.")
        sys.exit(1)

    print("\n" + "=" * 60)
    print(f"RESUMEN -- {SCRIPT_NAME}")
    print("=" * 60)
    print(f"gold.gold_h3_esg_v1 creada con {n_hex} hexagonos")
    print(f"  esg_h3_score: min={esg_min}  p50={esg_p50}  p95={esg_p95}  max={esg_max}  media={esg_media}")
    print(f"  s_score_completo=True (con dato real de ruido): {n_s_completo}")
    print(f"  g_score_completo=True (con dato real de ratio hoteles): {n_g_completo}")
    print(f"Tiempo total: {elapsed:.1f} s")
    print("=" * 60)


if __name__ == "__main__":
    main()
