"""
dag_social_refresh.py
─────────────────────────────────────────────────────────────────────────────
DAG: social_refresh_pipeline
Propósito: Refresco manual del contenido social (reseñas, comentarios, foros).
            Se ejecuta SOLO mediante trigger manual desde la UI de Airflow.

Fuentes:
  - TripAdvisor   → tripadvisor_upload_blob.py (API Terra)
  - YouTube       → youtube_upload_blob.py (API Data v3)
  - Booking       → booking_scraper.py (Selenium — requiere Chrome)
  - LosViajeros   → losviajeros_scraper.py (scraper de foro)

Downstream:
  - Postgres: booking + tabular
  - dbt Silver: tripadvisor, youtube, booking, losviajeros
  - Analytics NLP: sentiment + aspects, YouTube y reseñas (si run_heavy_ml=true)
  - Analytics geo: toponyms extraction
  - dbt Gold: h3_master, sentimiento_h3, municipio_master

Consideraciones:
  - Booking usa Selenium (Chrome headless) → puede tardar horas
  - TripAdvisor y YouTube tienen cuotas de API → monitorizar en logs
  - Los tasks pueden marcarse como Skipped individualmente desde la UI
    sin que ello cancele el resto del pipeline
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
    "retry_delay": timedelta(minutes=10),
    "email_on_failure": False,
}


def _check_heavy_ml() -> bool:
    """ShortCircuit: devuelve True si run_heavy_ml está activado."""
    return Variable.get("run_heavy_ml", default_var="false").lower() == "true"


# ─── DAG ──────────────────────────────────────────────────────────────────────

with DAG(
    dag_id="social_refresh_pipeline",
    description=(
        "Refresco manual de contenido social: "
        "TripAdvisor + YouTube + Booking + LosViajeros → postgres → silver → NLP → gold"
    ),
    schedule=None,  # Solo trigger manual
    start_date=datetime(2024, 1, 1),
    catchup=False,
    default_args=DEFAULT_ARGS,
    tags=["social", "nlp", "manual", "tfm"],
    doc_md=__doc__,
    max_active_runs=1,
) as dag:

    start = EmptyOperator(task_id="start")

    # ═══════════════════════════════════════════════════════════════════════════
    # FASE 1: Ingesta de fuentes sociales (paralela)
    # ═══════════════════════════════════════════════════════════════════════════
    with TaskGroup("fase_1_ingesta_social", tooltip="Scraping y APIs de contenido social") as fase1:

        ingest_tripadvisor = BashOperator(
            task_id="ingest_tripadvisor",
            bash_command=(
                f"{PYTHON} {REPO_ROOT}/ingestion/tripadvisor/tripadvisor_upload_blob.py"
            ),
            retries=2,
            execution_timeout=timedelta(hours=2),
        )

        ingest_youtube = BashOperator(
            task_id="ingest_youtube",
            bash_command=(
                f"{PYTHON} {REPO_ROOT}/ingestion/youtube/youtube_upload_blob.py"
            ),
            retries=2,
            execution_timeout=timedelta(hours=1),
        )

        # Booking: Selenium con Chrome headless, puede tardar muchas horas
        ingest_booking = BashOperator(
            task_id="ingest_booking_scraper",
            bash_command=(
                f"{PYTHON} {REPO_ROOT}/ingestion/booking/booking_scraper.py"
            ),
            retries=0,
            execution_timeout=timedelta(hours=8),
        )

        # LosViajeros: scraper de foro, supervisado
        ingest_losviajeros = BashOperator(
            task_id="ingest_losviajeros_scraper",
            bash_command=(
                f"{PYTHON} {REPO_ROOT}/ingestion/losviajeros/losviajeros_scraper.py"
            ),
            retries=0,
            execution_timeout=timedelta(hours=3),
        )

    # Join: continúa aunque alguna fuente falle (cuota agotada, etc.)
    join_fase1 = EmptyOperator(
        task_id="join_fase1",
        trigger_rule=TriggerRule.NONE_FAILED_MIN_ONE_SUCCESS,
    )

    # ═══════════════════════════════════════════════════════════════════════════
    # FASE 2: Carga a PostgreSQL (paralela — tablas independientes)
    # ═══════════════════════════════════════════════════════════════════════════
    with TaskGroup("fase_2_postgres", tooltip="Carga de contenido social a PostgreSQL") as fase2:

        pg_booking = BashOperator(
            task_id="pg_booking",
            bash_command=(
                f"{PYTHON} {REPO_ROOT}/ingestion/postgres/04_ingest_booking_to_postgres.py"
            ),
        )
        pg_booking_geocode = BashOperator(
            task_id="pg_booking_geocode",
            bash_command=(
                f"{PYTHON} {REPO_ROOT}/ingestion/postgres/06_geocode_booking_pg.py"
            ),
        )
        pg_tabular = BashOperator(
            task_id="pg_tabular_social",
            bash_command=(
                f"{PYTHON} {REPO_ROOT}/ingestion/postgres/05_ingest_tabular_to_postgres.py"
            ),
        )
        pg_booking >> pg_booking_geocode

    # ═══════════════════════════════════════════════════════════════════════════
    # FASE 3: dbt Silver — dominios de contenido social (paralelo)
    # ═══════════════════════════════════════════════════════════════════════════
    with TaskGroup("fase_3_dbt_silver", tooltip="dbt Silver — contenido social") as fase3:

        silver_tripadvisor = BashOperator(
            task_id="silver_tripadvisor",
            bash_command=f"{DBT_CMD} --select silver.tripadvisor",
        )
        silver_youtube = BashOperator(
            task_id="silver_youtube",
            bash_command=f"{DBT_CMD} --select silver.youtube",
        )
        silver_booking = BashOperator(
            task_id="silver_booking",
            bash_command=f"{DBT_CMD} --select silver.booking",
        )
        silver_losviajeros = BashOperator(
            task_id="silver_losviajeros",
            bash_command=f"{DBT_CMD} --select silver.losviajeros",
        )

    join_fase3 = EmptyOperator(task_id="join_fase3")

    # ═══════════════════════════════════════════════════════════════════════════
    # FASE 4: Analytics NLP (ShortCircuit para tareas pesadas) + Geo
    # ═══════════════════════════════════════════════════════════════════════════
    with TaskGroup("fase_4_analytics_nlp", tooltip="Análisis NLP y extracción geográfica") as fase4:

        # ShortCircuit para tasks de GPU
        check_ml = ShortCircuitOperator(
            task_id="check_ml_enabled",
            python_callable=_check_heavy_ml,
            ignore_downstream_trigger_rules=False,
        )

        # --source explicito: el script unificado procesa todas las fuentes por
        # defecto, y aqui interesa separar YouTube (rapido) de las reseñas
        # (decenas de miles, horas de inferencia) en tasks distintas.
        analytics_sentiment = BashOperator(
            task_id="sentiment_batch_inference",
            bash_command=(
                f"{PYTHON} {REPO_ROOT}/analytics/sentiment/batch_inference.py --source youtube"
            ),
            execution_timeout=timedelta(hours=4),
        )
        # Este DAG refresca Booking y TripAdvisor y luego corre gold_sentimiento_h3:
        # sin esta task, las reseñas nuevas llegarian a Gold sin sentimiento.
        analytics_sentiment_resenas = BashOperator(
            task_id="sentiment_batch_inference_resenas",
            bash_command=(
                f"{PYTHON} {REPO_ROOT}/analytics/sentiment/batch_inference.py --source resenas"
            ),
            execution_timeout=timedelta(hours=8),
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
                f"{PYTHON} {REPO_ROOT}/analytics/aspects/batch_inference.py --source youtube"
            ),
            execution_timeout=timedelta(hours=4),
        )
        analytics_aspects_resenas = BashOperator(
            task_id="aspects_batch_inference_resenas",
            bash_command=(
                f"{PYTHON} {REPO_ROOT}/analytics/aspects/batch_inference.py --source resenas"
            ),
            execution_timeout=timedelta(hours=8),
        )

        # Extracción de topónimos — ligero, no requiere GPU
        analytics_geo = BashOperator(
            task_id="geo_extract_toponyms",
            bash_command=(
                f"{PYTHON} {REPO_ROOT}/analytics/geo/extract_toponyms.py"
            ),
            execution_timeout=timedelta(hours=1),
        )

        check_ml >> [
            analytics_sentiment,
            analytics_sentiment_resenas,
            analytics_sentiment_backfill,
            analytics_aspects,
            analytics_aspects_resenas,
        ]

    join_fase4 = EmptyOperator(
        task_id="join_fase4",
        trigger_rule=TriggerRule.NONE_FAILED_MIN_ONE_SUCCESS,
    )

    # ═══════════════════════════════════════════════════════════════════════════
    # FASE 5: dbt Gold — modelos que dependen de contenido social
    # ═══════════════════════════════════════════════════════════════════════════
    with TaskGroup("fase_5_dbt_gold", tooltip="dbt Gold — modelos con sentimiento y reseñas") as fase5:

        gold_h3_master = BashOperator(
            task_id="gold_h3_master",
            bash_command=f"{DBT_CMD} --select gold_h3_master",
        )
        gold_sentimiento_h3 = BashOperator(
            task_id="gold_sentimiento_h3",
            bash_command=f"{DBT_CMD} --select gold_sentimiento_h3",
        )
        gold_municipio_master = BashOperator(
            task_id="gold_municipio_master",
            bash_command=f"{DBT_CMD} --select gold_municipio_master",
        )
        gold_topicos_h3 = BashOperator(
            task_id="gold_topicos_h3",
            bash_command=f"{DBT_CMD} --select gold_topicos_h3",
        )
        gold_topicos_municipio = BashOperator(
            task_id="gold_topicos_municipio",
            bash_command=f"{DBT_CMD} --select gold_topicos_municipio",
        )

    end = EmptyOperator(task_id="end")

    # ═══════════════════════════════════════════════════════════════════════════
    # DEPENDENCIAS GLOBALES
    # ═══════════════════════════════════════════════════════════════════════════

    [ingest_tripadvisor, ingest_youtube, ingest_booking, ingest_losviajeros] >> join_fase1

    join_fase1 >> [pg_booking, pg_tabular]

    # Conectar las salidas de fase2 con la entrada de los modelos silver
    join_fase2 = EmptyOperator(task_id="join_fase2")
    [pg_booking_geocode, pg_tabular] >> join_fase2

    join_fase2 >> [
        silver_tripadvisor,
        silver_youtube,
        silver_booking,
        silver_losviajeros,
    ]

    [
        silver_tripadvisor,
        silver_youtube,
        silver_booking,
        silver_losviajeros,
    ] >> join_fase3

    join_fase3 >> [check_ml, analytics_geo]

    [
        analytics_sentiment,
        analytics_sentiment_backfill,
        analytics_aspects,
        analytics_geo,
    ] >> join_fase4

    join_fase4 >> fase5

    [gold_h3_master, gold_sentimiento_h3, gold_municipio_master] >> end

    start >> fase1
