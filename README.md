# AI-Dashboard: Gestión de Oferta Turística Georreferenciada e Integración de Datos Abiertos de Tenerife

Este repositorio contiene el código fuente y la documentación para el Trabajo de Fin de Máster (TFM): **AI-Dashboard para la Gestión de la oferta turística georreferenciada e integración con datos abiertos externos de la isla de Tenerife**.

---

## Estructura del Proyecto (Índice de Desarrollo)

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
  - **Datos Espaciales**: Límites municipales (31), Espacios Naturales Protegidos (43 ENP), Zonas Turísticas (17), Bienes de Interés Cultural (125 BIC) y Modelo Digital del Terreno (MDT25) derivado a nivel de celda H3 (fuentes IDECanarias, Cabildo e ISTAC).
  - **Alojamiento Oficial**: Censo reglado del Gobierno de Canarias con **31.314 establecimientos** (30.589 Viviendas Vacacionales, 314 Hoteles y 411 Extrahoteleros; 263.769 plazas ofertadas), geocodificados vía Nominatim/ArcGIS.
* **2.4. Integración de Movilidad Pública (GTFS)**: Estructuración de la topología insular de transporte (TITSA y Metropolitano de Tenerife) con **3.934 paradas** físicas georreferenciadas, **873 trazados de rutas** (183 líneas comerciales) y **1,36 millones de registros de paso** horarios.
* **2.5. Automatización de Ingesta Ambiental y Satelital**:
  - **Red Agrocabildo**: 68 estaciones automáticas (378 sensores físicos) y 136,4 millones de lecturas brutas en Bronze, depuradas en Silver a 12,95 millones de registros continuos para las 57 estaciones maduras (instaladas $\le 2022$).
  - **Teledetección Espacial**: Composites trimestrales libres de nubes de **Copernicus Sentinel-2** (NDVI y NDBI a 20 m, 46.422 registros Silver) y radianza mensual de luces nocturnas **NOAA/NASA VIIRS** (241.648 observaciones).
* **2.6. Extracción de Datos Cualitativos y Reputación**:
  - **Comunidades de Viajeros**: Web scraping ético de LosViajeros.com con **248 hilos temáticos** y **167.274 mensajes brutos** (168.035 depurados en Silver).
  - **Audiovisual Turístico**: Monitorización de **41 vídeos** y extracción de **3.100 comentarios** de YouTube (2.819 opiniones en Silver del periodo 2022–2026).
  - **Plataformas de Alojamiento**: Scraping ético y API de Booking.com y TripAdvisor, consolidando **74.695 reseñas limpias y georreferenciadas** (73.888 Booking + 807 TripAdvisor) sobre 3.740 hoteles y 748 actividades turísticas.

### 3. Estructuración, Data Warehouse y Topología Geoespacial
* **3.1. Diseño del Data Warehouse Espacial**: Modelado relacional en Azure Database for PostgreSQL habilitando PostGIS para soportar tipos espaciales (`GEOMETRY` / `GEOGRAPHY`).
* **3.2. Estandarización de Sistemas de Coordenadas**: Normalización global al sistema de proyección proyectado oficial de Canarias **EPSG:32628 (WGS 84 / UTM zone 28N)** y generación de índices espaciales **GIST** para consultas geográficas veloces.
* **3.3. Orquestación ETL (dbt / Apache Airflow) y Geoprocesamiento**:
  - Orquestación automatizada de pipelines con **Apache Airflow 2.9 (Docker)**: DAG histórico completo, incremental mensual y refresco de redes sociales (guía de despliegue en [dags/README.md](file:///c:/Users/ROBERTO/Proyectos_Python/TFM_TUI_Tenerife/AI_Dashboard_Core/dags/README.md)).
  - Modelos dbt para transformación, calidad de datos y linaje.
  - Geoprocesamiento programático con `rasterio` para la extracción de Altitud, Orientación (Aspect) y Pendiente (Slope) a partir de ficheros raster (.tif) del MDT hacia la Capa Plata.

### 4. Analítica Avanzada e Inteligencia Espacial
* **4.1. Análisis de Sentimiento Multilingüe (NLP)**: Pipeline desacoplado en dos ramas (`analytics/sentiment/batch_inference.py`):
  - *Redes y Contenido Abierto (YouTube)*: Filtro de relevancia zero-shot con `MoritzLaurer/mDeBERTa-v3-base-mnli-xnli` (4 hipótesis, umbral de margen 0,25) y clasificación en 3 clases con `cardiffnlp/twitter-xlm-roberta-base-sentiment` (Macro F1 = 0,874, exactitud 88,2 %).
  - *Alojamientos (Booking y TripAdvisor)*: Inferencia continua de 1 a 5 estrellas con `nlptown/bert-base-multilingual-uncased-sentiment` persistido en `gold.nlp_sentimiento_resenas` para agregación territorial.
* **4.2. Detección Espacial de Tópicos y Minería de Aspectos**:
  - *Modelado de Tópicos*: Implementación de `BERTopic` con embeddings `paraphrase-multilingual-mpnet-base-v2` (768 dimensiones), centrado multilingüe por idioma, agrupamiento optimizado mediante PCA(50) + K-Means ($k=20$ general, $k=50$ geocodificado) con c-TF-IDF y nombrado asistido por LLM (Llama-3 / Groq).
  - *Extracción de Aspectos*: Modelo multilingüe `PyABSA-ATEPC` y normalización híbrida en `gold.aspecto_traducciones` (Google + MyMemory) estructurada en 6 dimensiones canónicas.
* **4.3. Monitorización Satelital y Climatología Analítica**:
  - Índices biofísicos trimestrales Copernicus Sentinel-2 (NDVI y NDBI a 20 m) y radianza mensual NOAA/NASA VIIRS (500 m) por celda H3.
  - Modelo topoclimático microinsular sobre 67 estaciones de Agrocabildo: IDW corregido por gradiente térmico altitudinal (-0,0065 °C/m), termorregulación costera, condensación orográfica ("mar de nubes" 800–1.500 m) y sombra de lluvia en sotavento sur.
* **4.4. Tipificación Territorial con HDBSCAN y Reglas de Experto**:
  - Pipeline oficial `analytics/clustering/run_hdbscan_clustering.py`: 8 covariables canónicas (incluyendo `pct_area_enp` y log-transformaciones en plazas y VIIRS), estandarización `StandardScaler` y reducción PCA (3 componentes, **81,5 % de varianza explicada**).
  - Algoritmo `HDBSCAN(min_cluster_size=30, min_samples=10)` complementado con reglas de experto territorial para reasignar el ruido, consolidando **6 tipologías territoriales con el 100 % de cobertura insular (2.579 hexágonos)** en `gold.h3_clusters`.
* **4.5. Modelado de Accesibilidad Multimodal e Isócronas**:
  - Matrices viales origen-destino mediante OpenRouteService (ORS API) hacia 18 polos estratégicos, derivando isócronas continuas de 15 a 60 min (`gold_isocronas_visuales.py`) y cobertura de paradas de transporte público regular GTFS TITSA a 200, 500 y 1.000 m.
* **4.6. Regresión Geográfica Ponderada Multiescala (MGWR) e Índice PTNA**:
  - Modelización local no estacionaria sobre las 2.579 celdas H3: eleva el $R^2$ global (no ajustado) de **0,5444** (OLS) a **0,8272**, reduciendo la I de Moran residual de **0,3065** ($p = 0,0010$) a **0,0355** ($p = 0,0110$, 999 permutaciones). Anchos de banda hiperlocales para NDVI (198) y altitud (138) y saturación en 9 variables (2.573) señalizada con `confianza_ptna = 'baja'` (10,0 % de celdas).
  - Cálculo del **Índice de Potencial Turístico No Aprovechado (PTNA)**: $\text{ptna\_score} = \text{predy\_MGWR} - y_{\text{observado}}$. El filtro combinado $\text{PTNA} > 0$ y $\text{ESG} > 60$ aísla **247 hexágonos de oportunidad ideal** (9,6 % de la isla) para la estrategia de descompresión turística de TUI.

### 5. Integración de Inteligencia Artificial Generativa (LLM & Chatbot)
* **5.1. Infraestructura de Inferencia de Alta Velocidad (Groq LPU)**: Conexión optimizada mediante cliente unificado (`analytics/llm/llm_client.py`) a modelos fundacionales en la nube (Groq API con `openai/gpt-oss-120b` y familia `Llama-3`), superando los 250 tokens/s sin costes de GPU dedicada en Azure.
* **5.2. Generador de Informes Ejecutivos Narrativos (`analytics/llm/report_generator.py`)**: Rutina automatizada que sintetiza los tópicos insulares de BERTopic y las métricas territoriales en diagnósticos ejecutivos de 3 párrafos persistidos en `gold.nlp_informe_global` por ámbito (general y alojamiento).
* **5.3. Agente Conversacional Inteligente Text-to-SQL (`analytics/chat/sql_agent.py`)**: Agente en lenguaje natural integrado en el frontend (`app/asistente.py`) que interpreta consultas del analista, genera y valida sentencias SQL seguras de solo lectura contra tablas maestras `gold.*`, las ejecuta en Azure PostgreSQL y redacta respuestas ejecutivas fundamentadas con contexto microespacial.

### 6. Productivización: Tablero Visual y Simulador de Decisiones (`app/`)
* **6.1. Arquitectura Multipágina en Streamlit (11 Módulos)**: Navegación nativa con vistas de Resumen Insular, Visor Cartográfico H3, Tabla Detallada, Rankings, Arquetipos TUI, Simulador What-If, Clima, Municipios, Alojamiento, Turismo y Asistente IA.
* **6.2. Motor Cartográfico Acelerado (PyDeck / Deck.gl)**: Renderizado 2D/3D con Modelo Digital del Terreno (MDT25), teselado H3 Res 8 (2.579 celdas terrestres) y capas de isócronas, GTFS, BIC y estaciones de Agrocabildo.
* **6.3. Matriz Estratégica 2D y Arquetipos TUI**: Proyección territorial en dos ejes continuos (Eje 1: Saturación Turística vs Eje 2: Potencial Rural y Sostenible / PTNA + ESG) para prescribir los 5 Arquetipos de Producto de TUI (*Sol y Playa Premium*, *Ecoturismo Rural*, *Cultural y Patrimonial*, *Turismo Activo*, *Bienestar y Salud*).
* **6.4. Simulador Territorial What-If (`app/simulador.py`)**: Proyección interactiva de intervenciones en plazas, conectividad, vegetación y equipamientos a 4 escalas (hexágono, municipio, arquetipo o clúster HDBSCAN) con recálculo en tiempo real de los índices estratégicos y gráfico radar.

### 7. Pruebas, Validación y Documentación
* **7.1. Batería de Pruebas Automatizadas con pytest (`tests/`)**: Cobertura de suites para ingesta, modelos dbt, analítica (NLP, aspectos, clustering, MGWR), asistente chatbot y componentes visuales de Streamlit.
* **7.2. Gobernanza de Datos y Reproducibilidad**: Documentación metodológica en Markdown, esquemas DDL idempotentes y memoria académica oficial del TFM en formato Word / PDF.

---

## Organización del Repositorio

* **`analytics/`**: Módulos de analítica avanzada: inferencia de sentimiento, tópicos BERTopic, aspectos PyABSA, clustering territorial HDBSCAN, accesibilidad ORS, MGWR/PTNA, RAG e integración de LLM.
* **`app/`**: Aplicación web interactiva frontend desarrollada en Streamlit con visualizaciones Pydeck (Deck.gl), Plotly y panel de detalle H3.
* **`dags/`**: Flujos de trabajo de orquestación en Apache Airflow (histórico completo, incremental mensual y refresco social).
* **`dbt_project/`**: Proyecto dbt con modelos analíticos para la transformación de capas Bronze → Silver → Gold en Azure PostgreSQL.
* **`docs/`**: Memoria técnica del TFM, índice académico, especificaciones de arquitectura y manuales de administración en Azure.
* **`ingestion/`**: Pipelines de extracción automatizada e ingesta a Azure Blob Storage (`bronce-raw`) y Azure PostgreSQL (`bronze.*`).
* **`notebooks/`**: Cuadernos Jupyter exploratorios utilizados en el diseño preliminar y validación analítica de modelos.
* **`scripts/`**: Utilidades operativas para carga de datos, verificación de tablas y generación automatizada de memorias en Word (.docx).
* **`sql/`**: Catálogo DDL centralizado de tablas, índices PostGIS y procedimientos almacenados complementarios a dbt.
* **`tests/`**: Suite integral de pruebas unitarias y de integración del sistema ejecutadas con pytest.