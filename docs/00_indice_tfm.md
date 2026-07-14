# Índice del Proyecto

AI-Dashboard para la Gestión oferta turista georreferenciada & integración con datos abiertos externos de la isla de Tenerife

## 1. Introducción y Contexto de Negocio
- 1.1. Resumen Ejecutivo y Alcance del Proyecto
- 1.2. El Problema de Negocio en Tenerife: Tensión entre saturación costera e interior rural infrautilizado
- 1.3. Objetivos Generales y Específicos de la Plataforma
- 1.4. Preguntas Estratégicas que Resolver (Aplicación al caso TUI)
- 1.5. Justificación del Aporte Diferencial

## 2. Configuración de Infraestructura y Adquisición de Datos
- 2.1. Aprovisionamiento de servidores en DigitalOcean y base de datos serverless en Neon.tech
- 2.2. Extracción de microdatos tabulares y espaciales (Cabildo de Tenerife, IDECanarias e ISTAC)
- 2.3. Integración de la topología de transporte público (Ficheros GTFS de TITSA y Metropolitano de Tenerife)
- 2.4. Automatización de ingesta de datos meteorológicos (AEMET API Opendata), cualitativos y de datos satelitales (Copernicus Sentinel)
- 2.5. Web scrapping para Redes Sociales y Reseñas (TripAdvisor, Booking, Google Reviews, Reddit, YouTube API)

## 3. Estructuración, Data Warehouse y Topología Geoespacial
- 3.1. Diseño del almacén de datos (Data Warehouse) espacial en PostgreSQL/PostGIS
- 3.2. Estandarización de sistemas de coordenadas espaciales (EPSG:32628) y creación de índices GIST
- 3.3. Orquestación del pipeline ETL con Apache Airflow y transformaciones en base de datos usando dbt

## 4. Analítica Avanzada e Inteligencia Espacial
- 4.1. Análisis de Sentimiento Multilingüe (NLP con inferencia por lotes con modelos transformadores Multilingual BERT)
- 4.2. Detección Espacial de Tópicos de conversación turística y Extracción de Aspectos (BERTopic y pyabsa)
- 4.3. Monitorización Ambiental por Satélite (Cálculo de NDVI, NDBI y Noches VIIRS)
- 4.4. Detección de Brechas de Mercado y Aglomeraciones (Clustering Espacial de Densidad con HDBSCAN)
- 4.5. Modelado de Accesibilidad y Enrutamiento (Isocronas con OpenRouteService / pgRouting)
- 4.6. Evaluación de Factores de Éxito Local (Regresión Geográficamente Ponderada Multiescalar - MGWR)

## 5. Integración de Inteligencia Artificial Generativa (LLM)

**Opción 1**
- 5.1. Configuración de rutinas analíticas de extracción (Python Scripts)
- 5.2. Conexión automatizada con modelos comerciales fundacionales (API de Azure OpenAI o uso de IA local Groq/Ollama)
- 5.3. Generación de informes ejecutivos narrativos e insights automáticos basados en datos (Generative AI Summarization)

**Opción 2**
- 5.1. Configuración del entorno de orquestación en DigitalOcean (Instalación del framework LangChain)
- 5.2. Conexión y autenticación con modelos comerciales (API de Azure OpenAI o uso de IA local Groq/Ollama)
- 5.3. Creación de un agente inteligente conversacional (Implementación de un Text-to-SQL Agent para transformar preguntas en consultas SQL contra PostgreSQL)

> Pendiente: decidir con el equipo qué opción se implementa antes de crear las issues de esta sección.

## 6. Productivización: Tablero Visual y Simulador de Decisiones
- 6.1. Traducción del Modelado Matemático a KPIs Estratégicos de Negocio
- 6.2. Diseño de la Plataforma Interactiva Frontend (Streamlit y renderizado acelerado)
- 6.3. Mapeo de Calor y Congestión Horaria mediante Indexación H3
- 6.4. Motor de Insights Automatizados con IA Generativa (Integración de Azure OpenAI / Ollama Local)
- 6.5. Simulador de Escenarios Gravitatorios (Redistribución de la demanda y flujos turísticos)
- 6.6. Generación de Alertas Parametrizadas

## 7. Pruebas, Validación y Documentación
- 7.1. Depuración integral del código y pruebas de estrés de los endpoints
- 7.2. Análisis empírico de los resultados territoriales extraídos de Tenerife
- 7.3. Redacción científica, conclusiones y empaquetado del Trabajo de Fin de Máster
