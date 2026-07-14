# AI_Dashboard_Core

Repositorio general para el TFM **AI-Dashboard para la Gestión de la oferta turística georreferenciada e integración con datos abiertos externos de la isla de Tenerife**.

## Resumen ejecutivo

Tenerife vive una tensión entre la saturación de la costa turística y un interior rural infrautilizado. Este proyecto construye un dashboard TUI que cruza datos oficiales, meteorológicos, satelitales, de transporte público y de percepción turística (reviews, foros, redes) para dar visibilidad geoespacial a esa tensión y apoyar decisiones de gestión y redistribución de la demanda turística.

El índice completo del TFM está en [`docs/00_indice_tfm.md`](docs/00_indice_tfm.md).

## Arquitectura

```
Fuentes externas (AEMET, Copernicus, GTFS, Cabildo/ISTAC, scraping)
        │
        ▼
   ingestion/  (scripts Python por fuente)
        │
        ▼
   Data Warehouse (Neon / PostgreSQL + PostGIS)  ── sql/
        │  orquestado por dags/ (Airflow) + dbt_project/ (dbt)
        ▼
   analytics/  (NLP, NDVI/NDBI, clustering, isocronas, MGWR)
        │
        ▼
   llm/  (agente Text-to-SQL / generación de insights)
        │
        ▼
   app/  (dashboard Streamlit — visualización y simulador)
```

Detalle en [`docs/architecture.md`](docs/architecture.md).

## Estado actual

- ✅ Base de datos serverless en Neon con PostGIS activo
- ✅ Microdatos oficiales (Cabildo/ISTAC) y red de transporte (GTFS) ingeridos
- 🔧 En curso: despliegue del servidor, orquestación Airflow/dbt, resto de fuentes de datos (AEMET, Copernicus, scraping)
- ⏳ Pendiente: analítica avanzada, integración LLM, frontend Streamlit, validación final

Backlog completo y estado de cada tarea: [issues del repo](https://github.com/TFM-Pytones/AI_Dashboard_Core/issues).

## Equipo

- jtmn03-2002
- roberhernando
- mariorosete
- guillermoortigosa28

## Setup local

```bash
git clone https://github.com/TFM-Pytones/AI_Dashboard_Core.git
cd AI_Dashboard_Core
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Crea un archivo `.env` en la raíz del repo con estas variables (pide las credenciales a un miembro del equipo, no las subas nunca a git):

```
DB_USER=
DB_PASSWORD=
DB_HOST=
DB_NAME=
```

Verifica la conexión ejecutando `notebooks/connect_neon.ipynb`.

## Estructura del repo

```
infra/          scripts de despliegue y configuración del servidor
ingestion/       scripts de extracción por fuente de datos
dags/            DAGs de Airflow
dbt_project/     modelos dbt
sql/             diseño del Data Warehouse (esquemas, índices)
notebooks/       notebooks de exploración y prueba de conceptos
docs/            documentación y arquitectura del proyecto
```
