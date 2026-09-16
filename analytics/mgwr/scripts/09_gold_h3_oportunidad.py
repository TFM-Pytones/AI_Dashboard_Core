"""
09_gold_h3_oportunidad.py
--------------------------
Bloque 5 (MGWR/PTNA) -- Subtarea 5.3: crea gold.gold_bloque5_h3_oportunidad_v1,
el cruce final de PTNA (gold.gold_h3_ptna_v3) y el Indice ESG Territorial
(gold.gold_h3_esg_v1) que marca, a nivel de hexagono H3, cuales son "oportunidad
ideal para TUI" segun el criterio del plan.

INNER JOIN simple por h3_index. Ya verificado en investigacion previa (no se
re-verifica aca, solo se documenta y se replica): gold_h3_ptna_v3 y
gold_h3_esg_v1 tienen 2579 filas cada una, join 1:1 exacto por h3_index, sin
huerfanos ni duplicados de ningun lado. gold_h3_esg_v1 ya trae su propia
columna municipio (identica a la de gold_h3_master para las 2579 filas), asi
que se usa esa y no hace falta un join adicional contra gold_h3_master.

Sobre el umbral de "oportunidad ideal" (ver plan_final_mejorado.md, Bloque 5,
Subtarea 5.3, linea ~1062, y docs/contexto_maestro_proyecto_ptna.md seccion 5):

(a) El plan tiene DOS definiciones distintas de este filtro en dos lugares
    distintos:
      - Subtarea 5.3 (este bloque, el que construye este script):
        ptna_score > 0 AND esg_territorial_score > 75
      - Subtarea 9.2 (Bloque 9, OTRO bloque, NO aplica aca -- se menciona
        solo para dejar constancia de que existe y por que se ignora):
        ptna_score > 80 AND esg_territorial_score > 80
    Ademas el nombre de columna que usa el plan en ambos casos,
    "esg_territorial_score", no existe -- la columna real en
    gold.gold_h3_esg_v1 (confirmado contra information_schema.columns) se
    llama esg_h3_score.

(b) Ambos umbrales (>75 y >80) son matematicamente inalcanzables con los
    datos reales: el maximo real de esg_h3_score en las 2579 filas de
    gold_h3_esg_v1 es 68.55 (P50=55.08, P95=62.75). Ningun hexagono de la
    isla pasa >75 ni >80 -- el filtro tal como esta escrito en el plan
    devuelve 0 filas en cualquiera de las dos versiones.

(c) Decision explicita del usuario (confirmada en ronda previa de esta misma
    investigacion): se ajusta el umbral a esg_h3_score > 60 como valor
    ABSOLUTO fijo, no como percentil dinamico de la distribucion. Se eligio
    no usar un percentil (p.ej. "top 10%") a proposito, para que el criterio
    no se recalcule ni cambie de significado cada vez que se re-corra este
    script o el pipeline ESG cambie de version -- 60 es un numero fijo en el
    codigo, igual que el plan original fijaba 75/80. Con este umbral,
    ptna_score > 0 AND esg_h3_score > 60 da 247 hexagonos de 2579 (verificado
    en ronda previa; este script lo vuelve a verificar mas abajo).

(d) confianza_ptna='baja' (columna de gold_h3_ptna_v3, indica baja confianza
    estadistica del ajuste MGWR en ese hexagono) NO excluye filas del
    resultado -- decision explicita del usuario. La columna se incluye tal
    cual en la tabla de salida para que quien consuma
    gold_bloque5_h3_oportunidad_v1 decida si quiere filtrarla en su propio
    analisis; es_oportunidad_ideal se calcula sin tenerla en cuenta.

La tabla resultante contiene el universo COMPLETO de 2579 hexagonos (no solo
los que cumplen el criterio) -- es_oportunidad_ideal es una columna booleana
dentro de la tabla completa, no un filtro que reduce filas.

Uso:
    python 09_gold_h3_oportunidad.py
"""

import sys
import time
from pathlib import Path

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _db import get_engine, setup_logging

SCRIPT_NAME = "09_gold_h3_oportunidad"

# Umbral absoluto fijo para esg_h3_score -- ver punto (c) del docstring de
# cabecera. NO se recalcula contra percentiles de la corrida actual.
ESG_THRESHOLD = 60

DDL = f"""
DROP TABLE IF EXISTS gold.gold_bloque5_h3_oportunidad_v1;

CREATE TABLE gold.gold_bloque5_h3_oportunidad_v1 AS
SELECT
    p.h3_index,
    e.municipio,
    p.ptna_score,
    e.esg_h3_score,
    p.confianza_ptna,
    (p.ptna_score > 0 AND e.esg_h3_score > {ESG_THRESHOLD}) AS es_oportunidad_ideal
FROM gold.gold_h3_ptna_v3 p
INNER JOIN gold.gold_h3_esg_v1 e ON e.h3_index = p.h3_index;

CREATE INDEX IF NOT EXISTS idx_gold_bloque5_h3_oportunidad_v1_h3_index
    ON gold.gold_bloque5_h3_oportunidad_v1 (h3_index);
"""

VERIFY_TOTALS_QUERY = """
SELECT
    COUNT(*) AS n_total,
    COUNT(*) FILTER (WHERE es_oportunidad_ideal) AS n_oportunidad,
    COUNT(*) FILTER (WHERE es_oportunidad_ideal AND confianza_ptna = 'baja') AS n_oportunidad_confianza_baja,
    COUNT(*) FILTER (WHERE h3_index IS NULL) AS n_null_h3_index,
    COUNT(*) FILTER (WHERE ptna_score IS NULL) AS n_null_ptna_score,
    COUNT(*) FILTER (WHERE esg_h3_score IS NULL) AS n_null_esg_score,
    COUNT(*) FILTER (WHERE es_oportunidad_ideal IS NULL) AS n_null_es_oportunidad
FROM gold.gold_bloque5_h3_oportunidad_v1;
"""

VERIFY_TOP10_QUERY = """
SELECT h3_index, municipio, ptna_score, esg_h3_score, confianza_ptna
FROM gold.gold_bloque5_h3_oportunidad_v1
WHERE es_oportunidad_ideal
ORDER BY ptna_score DESC
LIMIT 10;
"""


def main():
    logger = setup_logging(SCRIPT_NAME)
    t0 = time.perf_counter()

    try:
        logger.info("Conectando a Postgres (Azure)...")
        engine = get_engine()

        logger.info("Creando gold.gold_bloque5_h3_oportunidad_v1 (DROP + CREATE TABLE AS)...")
        with engine.begin() as conn:
            for statement in DDL.strip().split(";\n\n"):
                statement = statement.strip()
                if statement:
                    conn.execute(text(statement))
        logger.info("Tabla creada OK.")

        with engine.connect() as conn:
            totals_row = conn.execute(text(VERIFY_TOTALS_QUERY)).fetchone()
            top10_rows = conn.execute(text(VERIFY_TOP10_QUERY)).fetchall()

        (n_total, n_oportunidad, n_oportunidad_confianza_baja,
         n_null_h3_index, n_null_ptna_score, n_null_esg_score,
         n_null_es_oportunidad) = totals_row

        logger.info(
            "Verificacion: n_total=%s n_oportunidad=%s n_oportunidad_confianza_baja=%s "
            "nulls(h3_index=%s ptna_score=%s esg_h3_score=%s es_oportunidad_ideal=%s)",
            n_total, n_oportunidad, n_oportunidad_confianza_baja,
            n_null_h3_index, n_null_ptna_score, n_null_esg_score, n_null_es_oportunidad,
        )

        problemas = []
        if n_total != 2579:
            problemas.append(f"n_total={n_total} (esperado 2579)")
        if n_oportunidad != 247:
            problemas.append(f"n_oportunidad={n_oportunidad} (esperado 247)")
        if any([n_null_h3_index, n_null_ptna_score, n_null_esg_score, n_null_es_oportunidad]):
            problemas.append(
                f"NULLs inesperados: h3_index={n_null_h3_index} ptna_score={n_null_ptna_score} "
                f"esg_h3_score={n_null_esg_score} es_oportunidad_ideal={n_null_es_oportunidad}"
            )

        if problemas:
            logger.error("Discrepancias en la verificacion post-construccion: %s", "; ".join(problemas))
            print("\n" + "=" * 60)
            print(f"ADVERTENCIA -- {SCRIPT_NAME}: discrepancias en verificacion")
            print("=" * 60)
            for p in problemas:
                print(f"  - {p}")
            print("La tabla fue creada pero los numeros no coinciden con lo esperado.")
            print("Revisar antes de dar el resultado por bueno.")
            print("=" * 60)

        elapsed = time.perf_counter() - t0
        logger.info("Script finalizado en %.1f s.", elapsed)

    except Exception:
        logger.exception("Fallo en %s", SCRIPT_NAME)
        print(f"\nERROR en {SCRIPT_NAME} -- ver analytics/mgwr/logs/{SCRIPT_NAME}.log para el detalle.")
        sys.exit(1)

    print("\n" + "=" * 60)
    print(f"RESUMEN -- {SCRIPT_NAME}")
    print("=" * 60)
    print(f"gold.gold_bloque5_h3_oportunidad_v1 creada con {n_total} filas (universo completo)")
    print(f"  es_oportunidad_ideal = true: {n_oportunidad} (esperado 247)")
    print(f"  de esas, confianza_ptna = 'baja': {n_oportunidad_confianza_baja} (incluidas, no excluidas)")
    print(f"  NULLs inesperados -- h3_index={n_null_h3_index} ptna_score={n_null_ptna_score} "
          f"esg_h3_score={n_null_esg_score} es_oportunidad_ideal={n_null_es_oportunidad}")
    print("\nTop 10 oportunidad ideal por ptna_score DESC:")
    print(f"  {'h3_index':<18} {'municipio':<20} {'ptna_score':>11} {'esg_h3_score':>13} confianza_ptna")
    for h3_index, municipio, ptna_score, esg_h3_score, confianza_ptna in top10_rows:
        print(f"  {h3_index:<18} {str(municipio):<20} {ptna_score:>11} {esg_h3_score:>13} {confianza_ptna}")
    print(f"\nTiempo total: {elapsed:.1f} s")
    print("=" * 60)


if __name__ == "__main__":
    main()
