"""
dag_incremental_monthly.py
─────────────────────────────────────────────────────────────────────────────
DAG: incremental_monthly_pipeline
Propósito: Actualización mensual automática de las fuentes que cambian
            cada mes. Se ejecuta el día 1 de cada mes a las 06:00.

Fuentes actualizadas:
  - satélite    → sentinel2_upload_blob.py (nuevo mes de imágenes GEE)
  - ISTAC       → municipios_cifras + vivienda_vacacional (nuevos indicadores)
  - clima       → clima_realtime_upload_blob.py (acumulado del mes anterior)
  - alojamientos → alojamientos_oficiales_download.py (registro actualizado)
  - AENA        → aena_pasajeros_upload_blob.py (Excel descargado manualmente)
                  El task AENA usa un ShortCircuit que lee la Variable
                  'aena_upload_ready'. Pasos:
                    1. Descarga el Excel de AENA de su web
                    2. Cópialo a <repo>/data/aena/
                    3. En la UI de Airflow: Variables → aena_upload_ready = true
                    4. El DAG detecta la variable y ejecuta la ingesta de AENA
                    5. La variable se resetea a 'false' automáticamente

Downstream:
  - Postgres: solo las tablas afectadas
  - dbt Silver: solo los dominios afectados (espacial, istac, clima, alojamiento, movilidad)
  - Analytics: accesibilidad H3 (no ML pesado en automático)
  - dbt Gold: todos los modelos (dependen de silver actualizado)
─────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta

from airflow import DAG
from airflow.models import Variable
from airflow.operators.bash import BashOperator
from airflow.operators.python import ShortCircuitOperator, PythonOperator
from airflow.operators.empty import EmptyOperator
from airflow.utils.task_group import TaskGroup
from airflow.utils.trigger_rule import TriggerRule

# ─── Configuración base ───────────────────────────────────────────────────────

REPO_ROOT = os.environ.get("REPO_ROOT", "/opt/airflow/repo")
PYTHON = "python"
DBT_CMD = (
    f"cd {REPO_ROOT} && dbt run "
    f"--project-dir {REPO_ROOT}/dbt_project "
    f"--profiles-dir {REPO_ROOT}/dbt_project "
    f"--target dev"
)

DEFAULT_ARGS = {
    "owner": "tfm-tenerife",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=10),
    "email_on_failure": False,
}


def _check_aena_ready() -> bool:
    """
    ShortCircuit para AENA: devuelve True si el Excel ya fue subido.
    El usuario debe poner Variable 'aena_upload_ready' = 'true' en la UI
    después de copiar el Excel a data/aena/ y subirlo al blob.
    """
    return Variable.get("aena_upload_ready", default_var="false").lower() == "true"


def _reset_aena_flag(**context) -> None:
    """Resetea la variable aena_upload_ready a false tras la ingesta exitosa."""
    Variable.set("aena_upload_ready", "false")


# ─── DAG ──────────────────────────────────────────────────────────────────────

with DAG(
    dag_id="incremental_monthly_pipeline",
    description=(
        "Actualización mensual: satélite, ISTAC, clima, alojamientos + "
        "AENA (con flag manual) → postgres → dbt silver → analytics → dbt gold"
    ),
    schedule="0 6 3 * *",  # Día 3 de cada mes a las 06:00
    start_date=datetime(2024, 1, 1),
    catchup=False,
    default_args=DEFAULT_ARGS,
    tags=["incremental", "monthly", "tfm"],
    doc_md=__doc__,
    max_active_runs=1,
) as dag:

    start = EmptyOperator(task_id="start")

    # ═══════════════════════════════════════════════════════════════════════════
    # FASE 1: Ingesta incremental (dos ramas paralelas)
    # ═══════════════════════════════════════════════════════════════════════════
    with TaskGroup("fase_1_ingesta", tooltip="Ingesta incremental de fuentes actualizadas") as fase1:

        # ── Rama automática (paralela) ──────────────────────────────────────
        ingest_satelite = BashOperator(
            task_id="ingest_satelite_monthly",
            bash_command=(
                f"{PYTHON} {REPO_ROOT}/ingestion/satelite/sentinel2_upload_blob.py"
            ),
            retries=2,
            execution_timeout=timedelta(hours=3),
        )

        with TaskGroup("ingest_istac", tooltip="ISTAC — dos indicadores") as grp_istac:
            istac_muni = BashOperator(
                task_id="municipios_cifras",
                bash_command=(
                    f"{PYTHON} {REPO_ROOT}/ingestion/istac/"
                    "istac_municipios_cifras_upload_blob.py"
                ),
            )
            istac_vv = BashOperator(
                task_id="vivienda_vacacional",
                bash_command=(
                    f"{PYTHON} {REPO_ROOT}/ingestion/istac/"
                    "istac_vivienda_vacacional_upload_blob.py"
                ),
            )

        ingest_clima = BashOperator(
            task_id="ingest_clima_realtime",
            bash_command=(
                f"{PYTHON} {REPO_ROOT}/ingestion/clima/clima_realtime_upload_blob.py"
            ),
        )

        ingest_alojamientos = BashOperator(
            task_id="ingest_alojamientos",
            bash_command=(
                f"{PYTHON} {REPO_ROOT}/ingestion/alojamientos_oficiales/"
                "alojamientos_oficiales_download.py"
            ),
        )

        # ── Rama AENA (semi-manual con ShortCircuit) ────────────────────────
        # 1. Comprueba si el usuario ha subido el Excel y activado la variable
        aena_check = ShortCircuitOperator(
            task_id="aena_check_ready",
            python_callable=_check_aena_ready,
            ignore_downstream_trigger_rules=False,
        )

        # 2. Ejecuta el script de ingesta de AENA
        ingest_aena = BashOperator(
            task_id="ingest_aena",
            bash_command=(
                f"{PYTHON} {REPO_ROOT}/ingestion/aena/aena_pasajeros_upload_blob.py"
            ),
        )

        # 3. Resetea la variable para el próximo mes
        reset_aena_flag = PythonOperator(
            task_id="reset_aena_flag",
            python_callable=_reset_aena_flag,
        )

        aena_check >> ingest_aena >> reset_aena_flag

    # Join de Fase 1: continúa aunque AENA no esté lista (ShortCircuit)
    join_fase1 = EmptyOperator(
        task_id="join_fase1",
        trigger_rule=TriggerRule.NONE_FAILED_MIN_ONE_SUCCESS,
    )

    # ═══════════════════════════════════════════════════════════════════════════
    # FASE 2: Postgres — solo tablas afectadas (paralelo)
    # ═══════════════════════════════════════════════════════════════════════════
    with TaskGroup("fase_2_postgres", tooltip="Carga incremental a PostgreSQL") as fase2:

        pg_satelite = BashOperator(
            task_id="pg_satelite",
            bash_command=(
                f"{PYTHON} {REPO_ROOT}/ingestion/postgres/03_ingest_satelite_to_postgres.py"
            ),
        )
        pg_tabular = BashOperator(
            task_id="pg_tabular",
            bash_command=(
                f"{PYTHON} {REPO_ROOT}/ingestion/postgres/05_ingest_tabular_to_postgres.py"
            ),
        )
        pg_alojamientos = BashOperator(
            task_id="pg_alojamientos_geocode",
            bash_command=(
                f"{PYTHON} {REPO_ROOT}/ingestion/postgres/07_alojamientos_oficiales_geocode.py"
            ),
        )

    # ═══════════════════════════════════════════════════════════════════════════
    # FASE 3: dbt Silver — dominios afectados (paralelo)
    # ═══════════════════════════════════════════════════════════════════════════
    with TaskGroup("fase_3_dbt_silver", tooltip="dbt Silver — dominios actualizados") as fase3:

        silver_espacial = BashOperator(
            task_id="silver_espacial",
            bash_command=f"{DBT_CMD} --select silver.espacial",
        )
        silver_istac = BashOperator(
            task_id="silver_istac",
            bash_command=f"{DBT_CMD} --select silver.istac",
        )
        silver_clima = BashOperator(
            task_id="silver_clima",
            bash_command=f"{DBT_CMD} --select silver.clima",
        )
        silver_alojamiento = BashOperator(
            task_id="silver_alojamiento",
            bash_command=f"{DBT_CMD} --select silver.alojamiento",
        )
        silver_movilidad = BashOperator(
            task_id="silver_movilidad",
            bash_command=f"{DBT_CMD} --select silver.movilidad",
        )

    join_fase3 = EmptyOperator(task_id="join_fase3")

    # ═══════════════════════════════════════════════════════════════════════════
    # FASE 4: Analytics — accesibilidad (sin ML pesado en automático)
    # ═══════════════════════════════════════════════════════════════════════════
    analytics_accesibilidad = BashOperator(
        task_id="analytics_accesibilidad_h3",
        bash_command=(
            f"{PYTHON} {REPO_ROOT}/analytics/accesibilidad/gold_h3_accesibilidad.py"
        ),
        execution_timeout=timedelta(hours=2),
    )

    # ═══════════════════════════════════════════════════════════════════════════
    # FASE 5: dbt Gold — todos los modelos (paralelo)
    # ═══════════════════════════════════════════════════════════════════════════
    with TaskGroup("fase_5_dbt_gold", tooltip="dbt Gold — todos los modelos") as fase5:

        gold_aena = BashOperator(
            task_id="gold_aena_pasajeros",
            bash_command=f"{DBT_CMD} --select gold_aena_pasajeros",
        )
        gold_h3_master = BashOperator(
            task_id="gold_h3_master",
            bash_command=f"{DBT_CMD} --select gold_h3_master",
        )
        gold_municipio_anual = BashOperator(
            task_id="gold_municipio_anual",
            bash_command=f"{DBT_CMD} --select gold_municipio_anual",
        )
        gold_municipio_empleo = BashOperator(
            task_id="gold_municipio_empleo",
            bash_command=f"{DBT_CMD} --select gold_municipio_empleo",
        )
        gold_municipio_master = BashOperator(
            task_id="gold_municipio_master",
            bash_command=f"{DBT_CMD} --select gold_municipio_master",
        )
        gold_municipio_mensual = BashOperator(
            task_id="gold_municipio_mensual",
            bash_command=f"{DBT_CMD} --select gold_municipio_mensual",
        )
        gold_sentimiento_h3 = BashOperator(
            task_id="gold_sentimiento_h3",
            bash_command=f"{DBT_CMD} --select gold_sentimiento_h3",
        )
        gold_turismo_anual = BashOperator(
            task_id="gold_turismo_hotelero_anual",
            bash_command=f"{DBT_CMD} --select gold_turismo_hotelero_anual",
        )
        gold_turismo_mensual = BashOperator(
            task_id="gold_turismo_hotelero_mensual",
            bash_command=f"{DBT_CMD} --select gold_turismo_hotelero_mensual",
        )

    end = EmptyOperator(task_id="end")

    # ═══════════════════════════════════════════════════════════════════════════
    # DEPENDENCIAS GLOBALES
    # ═══════════════════════════════════════════════════════════════════════════

    [
        ingest_satelite,
        grp_istac,
        ingest_clima,
        ingest_alojamientos,
        aena_check,  # rama AENA (puede cortocircuitarse)
    ] >> join_fase1

    join_fase1 >> fase2 >> fase3

    [
        silver_espacial,
        silver_istac,
        silver_clima,
        silver_alojamiento,
        silver_movilidad,
    ] >> join_fase3

    join_fase3 >> analytics_accesibilidad >> fase5

    [
        gold_aena,
        gold_h3_master,
        gold_municipio_anual,
        gold_municipio_empleo,
        gold_municipio_master,
        gold_municipio_mensual,
        gold_sentimiento_h3,
        gold_turismo_anual,
        gold_turismo_mensual,
    ] >> end

    start >> fase1
