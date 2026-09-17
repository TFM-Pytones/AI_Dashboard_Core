# AI Dashboard Core — TFM Data Science & Business Analytics (UCM)

**Grupo:** Grupo 4 
**Autores:** Guillermo Martínez Ortigosa, Jorge Tamirat Montes Nocete, Jaime de Vera Martín, Mario Rosete Lázaro, Juan Andrés Cabrera Taramasco, Roberto Hernando Ascaso

---

## 1. Descripción del Proyecto

Este repositorio contiene el código fuente del **AI-Dashboard para la Gestión de la oferta turística georreferenciada e integración con datos abiertos externos de la isla de Tenerife**, desarrollado como Trabajo de Fin de Máster en Data Science & Business Analytics (UCM).

El proyecto aborda el desequilibrio territorial entre la saturación de las zonas costeras de Tenerife y el interior rural infrautilizado, construyendo una plataforma analítica de apoyo a la decisión para el operador turístico **TUI**. La solución integra fuentes de datos heterogéneas (alojamiento, movilidad GTFS, clima, satélite, reseñas y redes sociales) en una arquitectura Medallón sobre Azure, aplicando modelos de analítica avanzada espacial (HDBSCAN, MGWR/PTNA) y NLP multilingüe (BERTopic, PyABSA, sentimiento), y los expone a través de un cuadro de mando interactivo Streamlit con asistente conversacional Text-to-SQL.

---

## 2. Estructura del Repositorio

```text
AI_Dashboard_Core/
├── analytics/          # Módulos analíticos: NLP, clustering, MGWR, LLM, chat
├── app/                # Dashboard Streamlit multipágina (11 módulos) + asistente IA
├── dags/               # DAGs de Apache Airflow (orquestación ETL)
├── dbt_project/        # Modelos dbt Bronze → Silver → Gold en Azure PostgreSQL
├── docs/               # Memoria técnica y especificaciones de arquitectura
├── ingestion/          # Pipelines de extracción e ingesta a Azure Blob / PostgreSQL
├── notebooks/          # Cuadernos Jupyter exploratorios y validación de modelos
├── scripts/            # Utilidades operativas y carga de datos
├── sql/                # DDL centralizado, índices PostGIS y procedimientos
├── tests/              # Suite pytest: unitarios + integración
├── .env.example        # Plantilla de variables de entorno (sin claves reales)
├── requirements.txt    # Dependencias del proyecto
└── README.md
```

---

## 3. Requisitos y Dependencias

- **Python** 3.10+
- **PostgreSQL** con extensiones **PostGIS** y **pgvector**
- **Apache Airflow** 2.9 (Docker) — ver [`dags/README.md`](dags/README.md)
- **dbt-core** + adaptador `dbt-postgres`
- Librerías principales listadas en [`requirements.txt`](requirements.txt):
  - `streamlit`, `pydeck`, `plotly`, `pandas`, `geopandas`
  - `scikit-learn`, `hdbscan`, `mgwr`, `pyabsa`, `bertopic`
  - `sentence-transformers`, `openai`, `groq`
  - `sqlalchemy`, `psycopg2`, `rasterio`, `h3`

---

## 4. Instalación y Configuración

### 4.1 Clonar el repositorio

```bash
git clone https://github.com/TFM-Pytones/AI_Dashboard_Core.git
cd AI_Dashboard_Core
```

### 4.2 Crear y activar entorno virtual

```bash
python -m venv venv
source venv/bin/activate        # En Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 4.3 Variables de Entorno

Copiar la plantilla y rellenar con las claves suministradas en el ZIP de entrega:

```bash
cp .env.example .env            # En Windows: copy .env.example .env
```

Editar `.env` con los valores reales (ver `.env.example` para referencia de todas las claves necesarias: cadena de conexión PostgreSQL, clave Groq API, credenciales Azure Blob Storage, etc.).

---

## 5. Instrucciones de Ejecución

### 5.1 Arrancar el Dashboard (recomendado para evaluación)

```bash
streamlit run app/main.py
```

Abre automáticamente `http://localhost:8501` con el cuadro de mando completo.

### 5.2 Ejecutar el pipeline analítico

```bash
# Clustering territorial HDBSCAN
python analytics/clustering/run_hdbscan_clustering.py

# Inferencia de sentimiento (batch)
python analytics/sentiment/batch_inference.py

# Modelado MGWR e índice PTNA
python analytics/geo/run_mgwr_ptna.py
```

### 5.3 Transformaciones dbt (Bronze → Silver → Gold)

```bash
cd dbt_project
dbt run
dbt test
```

### 5.4 Orquestación con Apache Airflow

Ver guía completa en [`dags/README.md`](dags/README.md).

### 5.5 Notebooks (orden recomendado)

Ejecutar en el orden indicado por el prefijo numérico de los archivos dentro de `notebooks/`.

---

## 6. Organización del Repositorio

| Carpeta | Contenido |
|---|---|
| `analytics/` | Módulos de analítica: sentimiento, BERTopic, PyABSA, HDBSCAN, ORS, MGWR/PTNA, LLM |
| `app/` | Aplicación Streamlit con PyDeck, Plotly y asistente IA |
| `dags/` | Orquestación Apache Airflow (histórico, incremental, social) |
| `dbt_project/` | Transformación Bronze → Silver → Gold en Azure PostgreSQL |
| `docs/` | Memoria técnica, arquitectura y manuales de administración |
| `ingestion/` | Pipelines de extracción e ingesta |
| `notebooks/` | Cuadernos Jupyter exploratorios y validación |
| `scripts/` | Utilidades operativas |
| `sql/` | DDL, índices PostGIS y procedimientos |
| `tests/` | Suite de pruebas unitarias e integración (pytest) |
