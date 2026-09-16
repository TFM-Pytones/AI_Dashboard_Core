"""
00_create_sentimiento_table.py
-------------------------------
Bloque 5 (MGWR/PTNA) -- prerrequisito de la Subtarea 5.1 (dataset v2): crea
gold.gold_h3_sentimiento, la tabla de sentimiento agregado por hexagono que
plan_final_mejorado.md asume como input de 5.1/5.3 pero que ningun bloque
tiene asignado explicitamente construir (ver Hallazgo 7 en
docs/contexto_maestro_proyecto_ptna.md).

Fuentes reales (verificadas contra information_schema.columns, no contra el
SQL literal del plan -- ver Hallazgo 5/6):
- gold.nlp_sentimiento_resenas: resena_id, hotel_id, score, h3_index, fuente.
  h3_index YA viene precalculado -- no hace falta ST_Contains.
- gold.nlp_aspectos_resenas: resena_id, hotel_id, aspecto, sentimiento,
  confianza, fuente. NO tiene h3_index propio -- se trae via join a
  nlp_sentimiento_resenas por (resena_id, fuente). Verificado: resena_id no
  se repite entre fuentes distintas, asi que esa clave compuesta matchea el
  100% de las filas de aspectos (182.809/182.809) contra un h3_index valido.

queja_principal: MODE() del aspecto mas frecuente, filtrado a
sentimiento='Negative' (decision tomada explicitamente -- sin el filtro, el
resultado en la practica es el aspecto mas MENCIONADO en general, casi
siempre positivo, lo cual contradice el nombre de la columna; ver Hallazgo 6
para el ejemplo real que motivo la decision). Hexagonos sin ningun aspecto
negativo detectado quedan con queja_principal=NULL a proposito -- no se
rellenan con nada.

Uso:
    python 00_create_sentimiento_table.py
"""

import sys
import time
from pathlib import Path

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _db import get_engine, setup_logging

SCRIPT_NAME = "00_create_sentimiento_table"

DDL = """
DROP TABLE IF EXISTS gold.gold_h3_sentimiento;

CREATE TABLE gold.gold_h3_sentimiento AS
WITH sent_agg AS (
    SELECT
        h3_index,
        AVG(score) AS sentimiento_medio,
        COUNT(*) AS n_resenas_sentimiento,
        COUNT(*) FILTER (WHERE fuente = 'booking')     AS n_resenas_booking,
        COUNT(*) FILTER (WHERE fuente = 'tripadvisor') AS n_resenas_tripadvisor
    FROM gold.nlp_sentimiento_resenas
    WHERE h3_index IS NOT NULL
    GROUP BY h3_index
),
aspectos_h3 AS (
    SELECT s.h3_index, a.aspecto, a.sentimiento
    FROM gold.nlp_aspectos_resenas a
    JOIN gold.nlp_sentimiento_resenas s
      ON s.resena_id = a.resena_id AND s.fuente = a.fuente
    WHERE s.h3_index IS NOT NULL AND a.aspecto IS NOT NULL
),
queja AS (
    SELECT h3_index, MODE() WITHIN GROUP (ORDER BY aspecto) AS queja_principal
    FROM aspectos_h3
    WHERE sentimiento = 'Negative'
    GROUP BY h3_index
)
SELECT sa.*, q.queja_principal
FROM sent_agg sa
LEFT JOIN queja q ON q.h3_index = sa.h3_index;

CREATE INDEX IF NOT EXISTS idx_gold_h3_sentimiento_h3_index
    ON gold.gold_h3_sentimiento (h3_index);
"""

VERIFY_QUERY = """
SELECT
    COUNT(*) AS n_hexagonos,
    COUNT(queja_principal) AS n_con_queja_principal,
    SUM(n_resenas_sentimiento) AS total_resenas,
    ROUND(AVG(sentimiento_medio)::numeric, 3) AS sentimiento_medio_global
FROM gold.gold_h3_sentimiento;
"""


def main():
    logger = setup_logging(SCRIPT_NAME)
    t0 = time.perf_counter()

    try:
        logger.info("Conectando a Postgres (Azure)...")
        engine = get_engine()

        logger.info("Creando gold.gold_h3_sentimiento (DROP + CREATE TABLE AS)...")
        with engine.begin() as conn:
            for statement in DDL.strip().split(";\n\n"):
                statement = statement.strip()
                if statement:
                    conn.execute(text(statement))
        logger.info("Tabla creada OK.")

        with engine.connect() as conn:
            row = conn.execute(text(VERIFY_QUERY)).fetchone()
        n_hexagonos, n_con_queja, total_resenas, sentimiento_global = row

        elapsed = time.perf_counter() - t0
        logger.info("Script finalizado OK en %.1f s.", elapsed)

    except Exception:
        logger.exception("Fallo en %s", SCRIPT_NAME)
        print(f"\nERROR en {SCRIPT_NAME} -- ver analytics/mgwr/logs/{SCRIPT_NAME}.log para el detalle.")
        sys.exit(1)

    print("\n" + "=" * 60)
    print(f"RESUMEN -- {SCRIPT_NAME}")
    print("=" * 60)
    print(f"gold.gold_h3_sentimiento creada con {n_hexagonos} hexagonos")
    print(f"  Con queja_principal (>=1 aspecto negativo detectado): {n_con_queja}")
    print(f"  Total de reseñas agregadas: {total_resenas}")
    print(f"  sentimiento_medio global: {sentimiento_global}")
    print(f"Tiempo total: {elapsed:.1f} s")
    print("=" * 60)


if __name__ == "__main__":
    main()
