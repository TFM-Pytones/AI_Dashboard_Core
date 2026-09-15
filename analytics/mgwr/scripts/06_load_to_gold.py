"""
06_load_to_gold.py
--------------------
Bloque 5 (MGWR/PTNA) -- sube el resultado final de 05_ptna_score.py a
Postgres, ademas del parquet que ya se guarda localmente.

Lee analytics/mgwr/data/processed/gold_h3_ptna_v3.parquet y lo escribe como
gold.gold_h3_ptna_v3.

Uso:
    python 06_load_to_gold.py
    python 06_load_to_gold.py --input otra_ruta.parquet --table otro_nombre
"""

import argparse
import sys
import time
from pathlib import Path

import pandas as pd
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _db import DATA_PROCESSED_DIR, get_engine, setup_logging

SCRIPT_NAME = "06_load_to_gold"
SCHEMA = "gold"
TABLE_NAME = "gold_h3_ptna_v3"


def parse_args():
    parser = argparse.ArgumentParser(description="Sube el resultado final del Bloque 5 (MGWR/PTNA) a Postgres")
    parser.add_argument(
        "--input",
        default=str(DATA_PROCESSED_DIR / "gold_h3_ptna_v3.parquet"),
        help="Parquet de entrada (default: analytics/mgwr/data/processed/gold_h3_ptna_v3.parquet)",
    )
    parser.add_argument(
        "--table",
        default=TABLE_NAME,
        help=f"Nombre de la tabla destino en el schema {SCHEMA} (default: {TABLE_NAME})",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    logger = setup_logging(SCRIPT_NAME)
    t0 = time.perf_counter()

    try:
        input_path = Path(args.input)
        if not input_path.exists():
            raise FileNotFoundError(
                f"No existe {input_path}. Correr primero 05_ptna_score.py (Fase B) antes de subir a Postgres."
            )

        logger.info("Leyendo %s", input_path)
        df = pd.read_parquet(input_path)
        n_rows = len(df)
        logger.info("Filas leidas: %d. Columnas: %s", n_rows, list(df.columns))

        if n_rows == 0:
            raise RuntimeError(
                f"{input_path} existe pero tiene 0 filas -- no se sube una tabla vacia a gold."
            )

        engine = get_engine()

        # if_exists="replace" es intencional aca: mientras el dataset de PTNA
        # siga en iteracion (variables del modelo, criterios de confianza_ptna,
        # etc. todavia sujetos a cambio -- ver docs/contexto_maestro_proyecto_ptna.md),
        # esta tabla completa se va a descartar y recrear entera cada vez que
        # se vuelva a correr 04_run_model.py / 05_ptna_score.py con ajustes.
        # No copiar este patron a un script que suba una tabla gold ya
        # "definitiva" y estable -- ahi corresponde versionar o hacer upsert,
        # no reemplazar la tabla completa
        # en cada corrida.
        logger.info("Subiendo a %s.%s (if_exists='replace')...", SCHEMA, args.table)
        df.to_sql(args.table, engine, schema=SCHEMA, if_exists="replace", index=False)
        logger.info("Subida completada.")

        logger.info("Verificando con SELECT COUNT(*) contra la tabla recien creada...")
        with engine.connect() as conn:
            count_in_db = conn.execute(text(f"SELECT COUNT(*) FROM {SCHEMA}.{args.table}")).scalar()
        logger.info("COUNT(*) en %s.%s: %d", SCHEMA, args.table, count_in_db)

        if count_in_db != n_rows:
            raise RuntimeError(
                f"Mismatch tras la subida: parquet tenia {n_rows} filas, "
                f"pero {SCHEMA}.{args.table} tiene {count_in_db}."
            )

        elapsed = time.perf_counter() - t0
        logger.info("Script finalizado OK en %.1f s.", elapsed)

    except Exception:
        logger.exception("Fallo en %s", SCRIPT_NAME)
        print(f"\nERROR en {SCRIPT_NAME} -- ver analytics/mgwr/logs/{SCRIPT_NAME}.log para el detalle.")
        sys.exit(1)

    print("\n" + "=" * 60)
    print(f"RESUMEN -- {SCRIPT_NAME}")
    print("=" * 60)
    print(f"Filas subidas: {n_rows}")
    print(f"Tabla: {SCHEMA}.{args.table}")
    print(f"Verificacion SELECT COUNT(*): {count_in_db} filas (coincide con el parquet)")
    print(f"Tiempo total: {elapsed:.1f} s")
    print("=" * 60)


if __name__ == "__main__":
    main()
