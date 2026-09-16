"""
dag_historical_full.py
─────────────────────────────────────────────────────────────────────────────
DAG: historical_full_pipeline
Propósito: Carga histórica completa desde cero.
            Se ejecuta UNA sola vez (trigger manual).

Fases:
  1. Ingesta a Azure Blob Storage (paralelo — fuentes manuales son skippables)
  2. Ingesta a PostgreSQL (secuencial, scripts numerados 01 → 07)
  3. dbt Silver (paralelo por dominio)
  4. Analytics (paralelo; tasks de ML controlados por Variable 'run_heavy_ml')
  5. dbt Gold (paralelo)

Notas:
  - Las fuentes que requieren acción manual previa (booking scraper,
    losviajeros, satélite con auth GEE) se marcan con trigger_rule especial
    para que el pipeline continúe aunque fallen / se salten.
  - Para activar las tasks de ML: set Variable 'run_heavy_ml' = 'true' en la UI.
─────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta

from airflow import DAG
from airflow.models import Variable
from airflow.operators.bash import BashOperator
from airflow.operators.python import ShortCircuitOperator
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
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
    "email_on_failure": False,
}


def _check_heavy_ml() -> bool:
    """ShortCircuit: devuelve True si run_heavy_ml está activado."""
    return Variable.get("run_heavy_ml", default_var="false").lower() == "true"


# ─── DAG ──────────────────────────────────────────────────────────────────────

with DAG(
    dag_id="historical_full_pipeline",
    description=(
        "Carga histórica completa: blob ingestion → postgres → "
        "dbt silver → analytics → dbt gold"
    ),
    schedule=None,  # Solo trigger manual
    start_date=datetime(2024, 1, 1),
    catchup=False,
    default_args=DEFAULT_ARGS,
    tags=["historical", "full-pipeline", "tfm"],
    doc_md=__doc__,
    max_active_runs=1,
) as dag:

    # ─── START ────────────────────────────────────────────────────────────────
    start = EmptyOperator(task_id="start")

    # ═══════════════════════════════════════════════════════════════════════════
    # FASE 1: Ingesta a Azure Blob Storage (paralelo)
    # ═══════════════════════════════════════════════════════════════════════════
    with TaskGroup("fase_1_ingesta_blob", tooltip="Ingesta fuentes → Azure Blob") as fase1:

        # Fuentes totalmente automáticas (API)
        ingest_aena = BashOperator(
            task_id="ingest_aena",
            bash_command=(
                f"{PYTHON} {REPO_ROOT}/ingestion/aena/aena_pasajeros_upload_blob.py"
            ),
        )

        ingest_alojamientos = BashOperator(
            task_id="ingest_alojamientos_oficiales",
            bash_command=(
                f"{PYTHON} {REPO_ROOT}/ingestion/alojamientos_oficiales/"
                "alojamientos_oficiales_download.py"
            ),
        )

        ingest_clima_metadatos = BashOperator(
            task_id="ingest_clima_metadatos",
            bash_command=(
                f"{PYTHON} {REPO_ROOT}/ingestion/clima/"
                "clima_metadatos_upload_blob.py"
            ),
        )

        ingest_clima = BashOperator(
            task_id="ingest_clima_historico",
            bash_command=(
                f"{PYTHON} {REPO_ROOT}/ingestion/clima/"
                "clima_ckan_bulk_upload_blob.py --years 2019-2026 --upload-blob --no-local"
            ),
        )

        ingest_clima_metadatos >> ingest_clima

        ingest_gtfs = BashOperator(
            task_id="ingest_gtfs",
            bash_command=(
                f"{PYTHON} {REPO_ROOT}/ingestion/gtfs/gtfs_upload_blob.py"
            ),
        )

        # ISTAC: dos scripts en paralelo dentro del grupo
        with TaskGroup("ingest_istac", tooltip="ISTAC — dos datasets") as grp_istac:
            ingest_istac_muni = BashOperator(
                task_id="municipios_cifras",
                bash_command=(
                    f"{PYTHON} {REPO_ROOT}/ingestion/istac/"
                    "istac_municipios_cifras_upload_blob.py"
                ),
            )
            ingest_istac_vv = BashOperator(
                task_id="vivienda_vacacional",
                bash_command=(
                    f"{PYTHON} {REPO_ROOT}/ingestion/istac/"
                    "istac_vivienda_vacacional_upload_blob.py"
                ),
            )

        # Espacial: cuatro scripts secuenciales (dependencias entre sí)
        with TaskGroup("ingest_espacial", tooltip="Datos espaciales (4 scripts)") as grp_espacial:
            esp_cabildo = BashOperator(
                task_id="cabildo_opendata",
                bash_command=(
                    f"{PYTHON} {REPO_ROOT}/ingestion/espacial/"
                    "cabildo_opendata_upload_blob.py"
                ),
            )
            esp_enp = BashOperator(
                task_id="enp_zonas",
                bash_command=(
                    f"{PYTHON} {REPO_ROOT}/ingestion/espacial/"
                    "enp_zonas_upload_blob.py"
                ),
            )
            esp_h3 = BashOperator(
                task_id="h3_grid",
                bash_command=(
                    f"{PYTHON} {REPO_ROOT}/ingestion/espacial/"
                    "h3_grid_upload_blob.py"
                ),
            )
            esp_osm = BashOperator(
                task_id="osm_tourism",
                bash_command=(
                    f"{PYTHON} {REPO_ROOT}/ingestion/espacial/"
                    "osm_tourism_upload_blob.py"
                ),
            )
            esp_cabildo >> esp_enp >> esp_h3 >> esp_osm

        # Fuentes semi-automáticas (pueden fallar/saltarse sin bloquear)
        # tripadvisor
        ingest_tripadvisor = BashOperator(
            task_id="ingest_tripadvisor",
            bash_command=(
                f"{PYTHON} {REPO_ROOT}/ingestion/tripadvisor/"
                "tripadvisor_upload_blob.py"
            ),
            retries=2,
        )

        # youtube
        ingest_youtube = BashOperator(
            task_id="ingest_youtube",
            bash_command=(
                f"{PYTHON} {REPO_ROOT}/ingestion/youtube/youtube_upload_blob.py"
            ),
            retries=2,
        )

        # satelite (requiere auth GEE previa: earthengine authenticate)
        ingest_satelite = BashOperator(
            task_id="ingest_satelite",
            bash_command=(
                f"{PYTHON} {REPO_ROOT}/ingestion/satelite/sentinel2_upload_blob.py"
            ),
            retries=1,
            execution_timeout=timedelta(hours=3),
        )

        # booking (scraper Selenium, puede tardar horas)
        ingest_booking = BashOperator(
            task_id="ingest_booking",
            bash_command=(
                f"{PYTHON} {REPO_ROOT}/ingestion/booking/booking_scraper.py"
            ),
            retries=0,
            execution_timeout=timedelta(hours=6),
        )

        # losviajeros (scraper de foro, supervisado)
        ingest_losviajeros = BashOperator(
            task_id="ingest_losviajeros",
            bash_command=(
                f"{PYTHON} {REPO_ROOT}/ingestion/losviajeros/losviajeros_scraper.py"
            ),
            retries=0,
            execution_timeout=timedelta(hours=2),
        )

    # Join de Fase 1: continúa aunque alguna fuente semi-manual falle
    join_fase1 = EmptyOperator(
        task_id="join_fase1",
        trigger_rule=TriggerRule.NONE_FAILED_MIN_ONE_SUCCESS,
    )

    # ═══════════════════════════════════════════════════════════════════════════
    # FASE 2: Ingesta → PostgreSQL (secuencial, orden 01 → 07)
    # ═══════════════════════════════════════════════════════════════════════════
    with TaskGroup("fase_2_postgres", tooltip="Carga datos al PostgreSQL (secuencial)") as fase2:
        pg_01 = BashOperator(
            task_id="pg_01_vector",
            bash_command=(
                f"{PYTHON} {REPO_ROOT}/ingestion/postgres/01_ingest_vector_to_postgres.py"
            ),
        )
        pg_02 = BashOperator(
            task_id="pg_02_mdt",
            bash_command=(
                f"{PYTHON} {REPO_ROOT}/ingestion/postgres/02_ingest_mdt_to_postgres.py"
            ),
        )
        pg_03 = BashOperator(
            task_id="pg_03_satelite",
            bash_command=(
                f"{PYTHON} {REPO_ROOT}/ingestion/postgres/03_ingest_satelite_to_postgres.py"
            ),
        )
        pg_04 = BashOperator(
            task_id="pg_04_booking",
            bash_command=(
                f"{PYTHON} {REPO_ROOT}/ingestion/postgres/04_ingest_booking_to_postgres.py"
            ),
        )
        pg_05 = BashOperator(
            task_id="pg_05_tabular",
            bash_command=(
                f"{PYTHON} {REPO_ROOT}/ingestion/postgres/05_ingest_tabular_to_postgres.py"
            ),
        )
        pg_06 = BashOperator(
            task_id="pg_06_geocode_booking",
            bash_command=(
                f"{PYTHON} {REPO_ROOT}/ingestion/postgres/06_geocode_booking_pg.py"
            ),
        )
        pg_07 = BashOperator(
            task_id="pg_07_alojamientos_geocode",
            bash_command=(
                f"{PYTHON} {REPO_ROOT}/ingestion/postgres/07_alojamientos_oficiales_geocode.py"
            ),
        )
        pg_01 >> pg_02 >> pg_03 >> pg_04 >> pg_05 >> pg_06 >> pg_07

    # ═══════════════════════════════════════════════════════════════════════════
    # FASE 3: dbt Silver (paralelo por dominio)
    # ═══════════════════════════════════════════════════════════════════════════
    with TaskGroup("fase_3_dbt_silver", tooltip="Transformaciones dbt Silver") as fase3:

        dbt_silver_alojamiento = BashOperator(
            task_id="silver_alojamiento",
            bash_command=f"{DBT_CMD} --select silver.alojamiento",
        )
        dbt_silver_booking = BashOperator(
            task_id="silver_booking",
            bash_command=f"{DBT_CMD} --select silver.booking",
        )
        dbt_silver_clima = BashOperator(
            task_id="silver_clima",
            bash_command=f"{DBT_CMD} --select silver.clima",
        )
        dbt_silver_espacial = BashOperator(
            task_id="silver_espacial",
            bash_command=f"{DBT_CMD} --select silver.espacial",
        )
        dbt_silver_istac = BashOperator(
            task_id="silver_istac",
            bash_command=f"{DBT_CMD} --select silver.istac",
        )
        dbt_silver_losviajeros = BashOperator(
            task_id="silver_losviajeros",
            bash_command=f"{DBT_CMD} --select silver.losviajeros",
        )
        dbt_silver_movilidad = BashOperator(
            task_id="silver_movilidad",
            bash_command=f"{DBT_CMD} --select silver.movilidad",
        )
        dbt_silver_tripadvisor = BashOperator(
            task_id="silver_tripadvisor",
            bash_command=f"{DBT_CMD} --select silver.tripadvisor",
        )
        dbt_silver_youtube = BashOperator(
            task_id="silver_youtube",
            bash_command=f"{DBT_CMD} --select silver.youtube",
        )

    join_fase3 = EmptyOperator(task_id="join_fase3")

    # ═══════════════════════════════════════════════════════════════════════════
    # FASE 4: Analytics (paralelo + ShortCircuit para tasks pesadas de ML)
    # ═══════════════════════════════════════════════════════════════════════════
    with TaskGroup("fase_4_analytics", tooltip="Scripts de analytics y ML") as fase4:

        # ShortCircuit: si run_heavy_ml=false, las tasks ML se saltan limpiamente
        check_ml = ShortCircuitOperator(
            task_id="check_ml_enabled",
            python_callable=_check_heavy_ml,
            ignore_downstream_trigger_rules=False,
        )

        # Tasks que requieren GPU / mucho tiempo (controladas por ShortCircuit)
        analytics_sentiment = BashOperator(
            task_id="sentiment_batch_inference",
            bash_command=(
                f"{PYTHON} {REPO_ROOT}/analytics/sentiment/batch_inference.py"
            ),
            execution_timeout=timedelta(hours=4),
        )
        analytics_sentiment_backfill = BashOperator(
            task_id="sentiment_backfill_relevance",
            bash_command=(
                f"{PYTHON} {REPO_ROOT}/analytics/sentiment/backfill_relevance.py"
            ),
            execution_timeout=timedelta(hours=2),
        )
        analytics_aspects = BashOperator(
            task_id="aspects_batch_inference",
            bash_command=(
                f"{PYTHON} {REPO_ROOT}/analytics/aspects/batch_inference.py"
            ),
            execution_timeout=timedelta(hours=4),
        )
        analytics_geo = BashOperator(
            task_id="geo_extract_toponyms",
            bash_command=(
                f"{PYTHON} {REPO_ROOT}/analytics/geo/extract_toponyms.py"
            ),
            execution_timeout=timedelta(hours=2),
        )
        analytics_clustering = BashOperator(
            task_id="clustering_build_features",
            bash_command=(
                f"{PYTHON} {REPO_ROOT}/analytics/clustering/build_features.py"
            ),
        )

        # Accesibilidad: no requiere GPU, siempre se ejecuta
        analytics_accesibilidad = BashOperator(
            task_id="accesibilidad_h3",
            bash_command=(
                f"{PYTHON} {REPO_ROOT}/analytics/accesibilidad/gold_h3_accesibilidad.py"
            ),
            execution_timeout=timedelta(hours=2),
        )

        # Dependencias dentro del grupo
        check_ml >> [
            analytics_sentiment,
            analytics_sentiment_backfill,
            analytics_aspects,
            analytics_geo,
            analytics_clustering,
        ]

    join_fase4 = EmptyOperator(
        task_id="join_fase4",
        trigger_rule=TriggerRule.NONE_FAILED_MIN_ONE_SUCCESS,
    )

    # ═══════════════════════════════════════════════════════════════════════════
    # FASE 5: dbt Gold (paralelo)
    # ═══════════════════════════════════════════════════════════════════════════
    with TaskGroup("fase_5_dbt_gold", tooltip="Modelos dbt Gold (capa analítica final)") as fase5:

        dbt_gold_aena = BashOperator(
            task_id="gold_aena_pasajeros",
            bash_command=f"{DBT_CMD} --select gold_aena_pasajeros",
        )
        dbt_gold_h3_master = BashOperator(
            task_id="gold_h3_master",
            bash_command=f"{DBT_CMD} --select gold_h3_master",
        )
        dbt_gold_municipio_anual = BashOperator(
            task_id="gold_municipio_anual",
            bash_command=f"{DBT_CMD} --select gold_municipio_anual",
        )
        dbt_gold_municipio_empleo = BashOperator(
            task_id="gold_municipio_empleo",
            bash_command=f"{DBT_CMD} --select gold_municipio_empleo",
        )
        dbt_gold_municipio_master = BashOperator(
            task_id="gold_municipio_master",
            bash_command=f"{DBT_CMD} --select gold_municipio_master",
        )
        dbt_gold_municipio_mensual = BashOperator(
            task_id="gold_municipio_mensual",
            bash_command=f"{DBT_CMD} --select gold_municipio_mensual",
        )
        dbt_gold_sentimiento_h3 = BashOperator(
            task_id="gold_sentimiento_h3",
            bash_command=f"{DBT_CMD} --select gold_sentimiento_h3",
        )
        dbt_gold_turismo_anual = BashOperator(
            task_id="gold_turismo_hotelero_anual",
            bash_command=f"{DBT_CMD} --select gold_turismo_hotelero_anual",
        )
        dbt_gold_turismo_mensual = BashOperator(
            task_id="gold_turismo_hotelero_mensual",
            bash_command=f"{DBT_CMD} --select gold_turismo_hotelero_mensual",
        )
        dbt_gold_topicos_h3 = BashOperator(
            task_id="gold_topicos_h3",
            bash_command=f"{DBT_CMD} --select gold_topicos_h3",
        )
        dbt_gold_topicos_municipio = BashOperator(
            task_id="gold_topicos_municipio",
            bash_command=f"{DBT_CMD} --select gold_topicos_municipio",
        )

    # ─── END ──────────────────────────────────────────────────────────────────
    end = EmptyOperator(task_id="end")

    # ═══════════════════════════════════════════════════════════════════════════
    # DEPENDENCIAS GLOBALES ENTRE FASES
    # ═══════════════════════════════════════════════════════════════════════════

    # Todos los tasks de fase1 alimentan el join
    [
        ingest_aena,
        ingest_alojamientos,
        ingest_clima,
        ingest_gtfs,
        grp_istac,
        grp_espacial,
        ingest_tripadvisor,
        ingest_youtube,
        ingest_satelite,
        ingest_booking,
        ingest_losviajeros,
    ] >> join_fase1

    join_fase1 >> fase2 >> fase3

    # Todos los tasks de silver alimentan el join
    [
        dbt_silver_alojamiento,
        dbt_silver_booking,
        dbt_silver_clima,
        dbt_silver_espacial,
        dbt_silver_istac,
        dbt_silver_losviajeros,
        dbt_silver_movilidad,
        dbt_silver_tripadvisor,
        dbt_silver_youtube,
    ] >> join_fase3

    join_fase3 >> [check_ml, analytics_accesibilidad]

    # Los tasks ML (controlados por ShortCircuit) y accesibilidad convergen en join
    [
        analytics_sentiment,
        analytics_sentiment_backfill,
        analytics_aspects,
        analytics_geo,
        analytics_clustering,
        analytics_accesibilidad,
    ] >> join_fase4

    join_fase4 >> fase5

    [
        dbt_gold_aena,
        dbt_gold_h3_master,
        dbt_gold_municipio_anual,
        dbt_gold_municipio_empleo,
        dbt_gold_municipio_master,
        dbt_gold_municipio_mensual,
        dbt_gold_sentimiento_h3,
        dbt_gold_turismo_anual,
        dbt_gold_turismo_mensual,
    ] >> end

    start >> fase1
