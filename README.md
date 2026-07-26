# AI-Dashboard: Gestión de Oferta Turística Georreferenciada e Integración de Datos Abiertos de Tenerife

Este repositorio contiene el código fuente y la documentación para el Trabajo de Fin de Máster (TFM): **AI-Dashboard para la Gestión de la oferta turística georreferenciada e integración con datos abiertos externos de la isla de Tenerife**.

---

## 📋 Estructura del Proyecto (Índice de Desarrollo)

### 1. Introducción y Contexto de Negocio
* **1.1. Resumen Ejecutivo y Alcance del Proyecto**: Visión global de la plataforma para resolver las necesidades del turismo en Tenerife.
* **1.2. El Problema de Negocio en Tenerife**: Tensión entre la saturación costera y el interior rural infrautilizado.
* **1.3. Objetivos Generales y Específicos de la Plataforma**: Definición de metas e hitos de entrega.
* **1.4. Preguntas Estratégicas que Resolver (Caso TUI)**: Respuestas dinámicas y analíticas basadas en el flujo turístico.
* **1.5. Justificación del Aporte Diferencial**: Uso de analítica avanzada espacial y modelos predictivos sobre las soluciones tradicionales.

### 2. Configuración de Infraestructura y Adquisición de Datos
* **2.1. Arquitectura Medallón en Azure**:
  - **Capa Bronce (Raw)**: Almacenamiento en Azure Blob Storage (contenedor `bronce-raw`) en formato particionado optimizado por estación.
  - **Capas Plata y Oro**: Servidor Flexible de Azure Database for PostgreSQL con extensión espacial PostGIS.
* **2.2. Aprovisionamiento de Máquina Virtual (Azure VM)**: Servidor Linux/Windows para la ejecución periódica de ingestas, web scraping y alojamiento del dashboard.
* **2.3. Extracción de Microdatos Tabulares y Espaciales**:
  - **Datos Espaciales**: Límites municipales, Espacios Naturales Protegidos, Zonas Turísticas y Modelo Digital del Terreno (MDT) de Tenerife (fuentes IDECanarias e ISTAC).
  - **Datos Tabulares**: Estadísticas demográficas y de oferta alojativa de Tenerife.
* **2.4. Integración de Movilidad Pública (GTFS)**: Descarga periódica y estructuración de la topología de transporte público (rutas, paradas, horarios y calendarios de TITSA y Metropolitano de Tenerife).
* **2.5. Automatización de Ingesta Ambiental y Satelital**:
  - Datos climáticos horarios e históricos en punto de la red de **Agrocabildo**.
  - Predicciones meteorológicas e históricos de validación cruzada mediante **Open-Meteo API**.
  - Datos satelitales ambientales (Copernicus Sentinel / ERA5-Land).
* **2.6. Extracción de Datos Cualitativos**:
  - Web scraping de reseñas de plataformas de alojamiento y opinión (TripAdvisor, Booking).
  - Extracción automatizada de comentarios y vídeos mediante **YouTube API** (`youtube_comments.parquet` y `youtube_videos.parquet`).

### 3. Estructuración, Data Warehouse y Topología Geoespacial
* **3.1. Diseño del Data Warehouse Espacial**: Modelado relacional en Azure Database for PostgreSQL habilitando PostGIS para soportar tipos espaciales (`GEOMETRY` / `GEOGRAPHY`).
* **3.2. Estandarización de Sistemas de Coordenadas**: Normalización global al sistema de proyección proyectado oficial de Canarias **EPSG:32628 (WGS 84 / UTM zone 28N)** y generación de índices espaciales **GIST** para consultas geográficas veloces.
* **3.3. Orquestación ETL (dbt / Apache Airflow) y Geoprocesamiento**:
  - Modelos dbt para transformación, calidad de datos y linaje.
  - Geoprocesamiento programático con `rasterio` para la extracción de Altitud, Orientación (Aspect) y Pendiente (Slope) a partir de ficheros raster (.tif) del MDT hacia la Capa Plata.

### 4. Analítica Avanzada e Inteligencia Espacial
* **4.1. Análisis de Sentimiento Multilingüe (NLP)**: Inferencia por lotes sobre reseñas turísticas utilizando transformadores de Hugging Face (`Multilingual BERT`).
* **4.2. Detección Espacial de Tópicos y Extracción de Aspectos**: Modelado de temas con `BERTopic` y extracción de aspectos clave con `pyabsa`.
* **4.3. Monitorización Ambiental por Satélite**: Cálculo de índices NDVI, NDBI y luces nocturnas VIIRS a nivel territorial.
* **4.4. Detección de Brechas de Mercado y Aglomeraciones**: Clustering de densidad geoespacial con el algoritmo `HDBSCAN`.
* **4.5. Modelado de Accesibilidad y Enrutamiento**: Cálculo de isócronas de viaje y redes de transporte mediante `OpenRouteService` y `pgRouting`.
* **4.6. Evaluación de Factores de Éxito Local (MGWR) y Calibración Topoclimática**: Ajuste dinámico térmico basado en gradientes de altitud, vientos alisios (orientación) y sombras proyectadas.

### 5. Integración de Inteligencia Artificial Generativa (LLM)
## Opción 1

* **5.1. Configuración de rutinas analíticas de extracción (Python Scripts).**
* **5.2. Conexión automatizada con modelos comerciales fundacionales (API de Azure OpenAI o uso de IA local Groq/Ollama).**
* **5.3. Generación de informes ejecutivos narrativos e insights automáticos basados en datos (Generative AI Summarization).**

## Opción 2

* **5.1. Configuración del entorno de orquestación en infraestructura de Azure (Instalación del framework LangChain).**
* **5.2. Conexión y autenticación con modelos comerciales (API de Azure OpenAI o uso de IA local Groq/Ollama).**
* **5.3. Creación de un agente inteligente conversacional (Implementación de un Text-to-SQL Agent para transformar preguntas en consultas SQL contra PostgreSQL).**


### 6. Productivización: Tablero Visual y Simulador de Decisiones
* **6.1. KPIs Estratégicos**: Consolidación de métricas de negocio para la toma de decisiones traducido del modelo matemático implementado en Python.
* **6.2. Frontend en Streamlit**: Aplicación interactiva frontend con mapas interactivos de calor y congestión turística.
* **6.3. Indexación H3**: Mapeo y agregación espacial mediante rejillas hexagonales H3 de Uber.
* **6.4. Simulador de redistribución de flujos**: Algoritmos gravitatorios para modelar el impacto de trasladar demanda turística a zonas rurales del interior.

### 7. Pruebas, Validación y Documentación
* **7.1. Depuración y Pruebas de Estrés**: Control de concurrencia y optimización de rendimiento de carga.
* **7.2. Análisis Territorial de Tenerife**: Informes de resultados.
* **7.3. Trabajo de Fin de Máster**: Documentación final y empaquetado.

---

## 📁 Organización del Repositorio

* **`infra/`**: Configuración de servidores, variables de entorno y scripts de despliegue en Azure.
* **`ingestion/`**: Pipelines de extracción incremental divididos por fuentes de datos (agrocabildo, open_meteo, microdatos, etc.).
* **`dags/`**: Flujos de trabajo de Apache Airflow para orquestar la ingesta y la analítica.
* **`dbt_project/`**: Código dbt para transformaciones de la Capa Plata y Capa Oro.
* **`sql/`**: Definición de esquemas, índices PostGIS y procedimientos almacenados.
* **`validation/`**: Scripts de validación cruzada y métricas de error.
* **`scratch/`**: Scripts auxiliares de mantenimiento y particionamiento de datos locales.
* **`docs/`**: Guías de configuración y documentación de arquitectura.