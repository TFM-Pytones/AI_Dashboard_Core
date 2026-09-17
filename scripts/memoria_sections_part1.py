"""
memoria_sections_part1.py
Portada, Resumen Ejecutivo, Ficha Técnica, Glosario,
Capítulo 1 (Introducción y Negocio), Capítulo 2 (Infraestructura Cloud)
y Capítulo 3 (Data Lakehouse y Topología Geoespacial).
Versión compacta — cuerpo máximo 20 páginas (sin portada, índice ni anexos).
"""


def get_front_matter():
    return """# UNIVERSIDAD COMPLUTENSE DE MADRID
## FACULTAD DE ESTUDIOS ESTADÍSTICOS
### MÁSTER EN DATA SCIENCE, BIG DATA & BUSINESS ANALYTICS

---

# AI-Dashboard para la Gestión y Sostenibilidad de la Oferta Turística Georreferenciada e Integración con Datos Abiertos de la Isla de Tenerife

### Caso de Aplicación Estratégica: Desafío 3 — TUI Group

**Autores:** Juan Andrés Cabrera Taramasco · Jaime de Vera Martín · Roberto Hernando Ascaso · Guillermo Martínez Ortigosa · Jorge Tamirat Montes Nocete · Mario Rosete Lázaro

**Tutores:** Carlos J. Pérez Ortega · Santiago Mota

**Convocatoria:** Curso Académico 2025–2026

---

## Resumen Ejecutivo

Tenerife recibe más de 7,2 millones de turistas internacionales al año, pero más del 80 % de la oferta alojativa y del gasto turístico se concentra en la franja litoral del suroeste (Adeje, Arona y Santiago del Teide), mientras que los municipios del interior y del norte —con un patrimonio cultural, paisajístico y ambiental de primer orden— permanecen infrautilizados. Esta polarización ha derivado en saturación crónica de las autopistas TF-1 y TF-5, estrés hídrico, gentrificación y una creciente contestación social bajo el lema "Canarias tiene un límite".

El presente TFM responde al **Desafío 3 de TUI Group** (UCM, 2025–2026): diseñar, implementar y productivizar un sistema de inteligencia territorial que diagnostique la capacidad de carga insular, detecte zonas con potencial desaprovechado y modele escenarios de redistribución de la demanda. La plataforma integra más de diez fuentes heterogéneas en un **Data Lakehouse en Microsoft Azure** con arquitectura Medallón (Bronze, Silver y Gold), articulado sobre la **Malla Hexagonal Uber H3 Resolución 8** (2.579 celdas terrestres de ~0,85 km²) para superar el sesgo MAUP de las divisiones administrativas. Las fuentes cubren: parque alojativo oficial y más de 55.000 reseñas de Booking y TripAdvisor; red de transporte público GTFS (TITSA y Tranvía); teledetección Copernicus Sentinel-2 (NDVI y NDBI) y radianza nocturna VIIRS; modelado topoclimático sobre 67 estaciones de Agrocabildo; isócronas de accesibilidad vial hacia 18 destinos estratégicos; y corpus textual multilingüe de YouTube y LosViajeros. La analítica avanzada incluye segmentación no supervisada con HDBSCAN, regresión geográfica ponderada multiescala (MGWR), modelado de tópicos con BERTopic y análisis de sentimiento con XLM-RoBERTa. El sistema culmina en un AI-Dashboard interactivo en Streamlit/PyDeck con simulador territorial interactivo de redistribución y motor de informes narrativos vía Groq API.

**Palabras clave:** Inteligencia Territorial, Uber H3, PostGIS, Arquitectura Medallón, Topoclimatología, Teledetección, HDBSCAN, MGWR, BERTopic, RAG, TUI Group, Tenerife.

---

## Abstract

Tenerife receives over 7.2 million international visitors annually under severe spatial polarisation: more than 80% of lodging capacity concentrates in a narrow southwestern coastal strip, while inland and northern municipalities remain economically underutilised. This imbalance triggers chronic traffic gridlocks, freshwater stress, residential displacement, and growing social unrest. This Master's Thesis addresses **TUI Group's Strategic Challenge 3** by designing, deploying, and productizing an end-to-end spatial intelligence and decision-support platform on Microsoft Azure (Medallion Lakehouse architecture) over a 2,579-cell Uber H3 Resolution-8 hexagonal grid. The platform harmonises official lodging registries, 55,000+ geolocated reviews, GTFS transit data, Sentinel-2 biophysical indices, VIIRS nocturnal radiance, a high-resolution topoclimatic model from 67 weather stations, and multilingual NLP corpora. Advanced analytics include HDBSCAN spatial clustering, Multiscale GWR, BERTopic topic modelling, and XLM-RoBERTa sentiment inference. The system is productized as an interactive Streamlit dashboard with a gravity-based demand redistribution simulator and a RAG-powered Groq narrative engine.

**Keywords:** Spatial Intelligence, Uber H3, PostGIS, Medallion Architecture, Topoclimatology, HDBSCAN, MGWR, BERTopic, RAG, TUI Group, Tenerife.

---

## Ficha Técnica del Proyecto

| Parámetro | Especificación |
| :--- | :--- |
| **Entidad Colaboradora** | TUI Group (Corporate Strategic Challenges 2025–2026) |
| **Encuadre Académico** | Máster en Data Science, Big Data & Business Analytics (UCM) |
| **Ámbito Territorial** | Isla de Tenerife (2.034 km², 31 municipios) |
| **Unidad Espacial Base** | Malla Hexagonal Uber H3 Res 8 (2.579 celdas terrestres, ~0,85 km²) |
| **Ventana Temporal** | 2019–2026 (series históricas prepandemia y postpandemia) |
| **Infraestructura Cloud** | Microsoft Azure (Blob Storage Gen2, PostgreSQL Flexible Server v16 + PostGIS 3.4) |
| **Orquestación ETL** | dbt Core 1.8 (capas Bronze, Silver y Gold) |
| **Modelos de ML/IA** | HDBSCAN, MGWR, XLM-RoBERTa, BERTopic, PyABSA, Groq LPU |
| **Frontend** | Streamlit + PyDeck (renderizado WebGL) |

---

## Glosario y Acrónimos

* **AICc:** Criterio de Información de Akaike Corregido.
* **dbt:** *data build tool* — herramienta de transformación analítica SQL.
* **ENP:** Espacios Naturales Protegidos (Red Canaria).
* **GTFS:** *General Transit Feed Specification* — estándar de transporte público.
* **HDBSCAN:** *Hierarchical Density-Based Spatial Clustering of Applications with Noise*.
* **IDW:** *Inverse Distance Weighting* — interpolación por inversa de la distancia.
* **ISTAC:** Instituto Canario de Estadística.
* **MAUP:** *Modifiable Areal Unit Problem* — Problema de la Unidad de Área Modificable.
* **MGWR:** *Multiscale Geographically Weighted Regression*.
* **NDBI / NDVI:** Índice de Edificación / Vegetación Normalizado (Sentinel-2).
* **ORS:** *OpenRouteService* — motor de enrutamiento sobre OpenStreetMap.
* **PTNA:** *Potential Tourism Niche Attraction* — Índice de Potencial de Nicho Ecoturístico.
* **RAG:** *Retrieval-Augmented Generation* — generación aumentada con LLMs.
* **TITSA:** Transportes Interurbanos de Tenerife S.A.U.
* **VIIRS DNB:** *Visible Infrared Imaging Radiometer Suite Day/Night Band* — luz nocturna satelital.
"""


def get_chapter_1():
    return """# 1. Introducción y Contexto de Negocio

## 1.1. El Problema de Negocio: Saturación Costera y Vacío Rural

En 2024 Tenerife superó los 7,2 millones de turistas internacionales (+12 % interanual), consolidando una actividad que aporta el **35,5 % del PIB regional y el 39,7 % del empleo total de Canarias** (Gobierno de Canarias / IMPACTUR, 2024). Sin embargo, el problema de fondo no radica en el volumen global de visitantes, sino en su extrema asimetría territorial. Nuestros microdatos de afiliación a la Seguridad Social (ISTAC) evidencian una severa polarización laboral: mientras que la hostelería directa representa el 16,6 % del empleo insular (72.088 afiliados), en enclaves costeros como Adeje o Santiago del Teide absorbe el **57,0 % y el 49,2 % de la ocupación municipal total**, generando un monocultivo económico hipervulnerable.

Esta hiperconcentración se traslada con idéntica crudeza al mercado residencial a través de las **30.589 viviendas vacacionales registradas en el Registro General Turístico (128.419 plazas)** en la capa Bronze, de las cuales **más del 58 % (17.837 unidades)** se aglutinan en apenas cinco municipios del sur insular (Arona, Adeje, Granadilla de Abona, Santiago del Teide y San Miguel de Abona). Esta presión simultánea sobre el suelo, el agua y las infraestructuras colapsa diariamente las autopistas TF-1 y TF-5 con intensidades superiores a 90.000 vehículos/día, encajando en la definición formal de *overtourism* (Milano et al., 2019). En agudo contraste, los 25 municipios restantes de los 31 que integran la isla —medianías agrícolas y comarcas del norte— captan apenas una fracción residual de las pernoctaciones y del gasto, sufriendo despoblación, abandono agrario y una presencia nula en los canales de TUI.

## 1.2. Objetivos y Preguntas Estratégicas de TUI Group

El **objetivo general** del proyecto es diseñar, desplegar y validar una plataforma de inteligencia territorial que capacite a TUI Group para monitorizar la capacidad de carga insular y planificar la redistribución equilibrada de los flujos turísticos en los 31 municipios de Tenerife. Los objetivos específicos se articulan en torno a las siete preguntas estratégicas del briefing corporativo:

| # | Pregunta Estratégica (Briefing TUI) | Cómo la Resolvemos (Módulo del Proyecto) |
| :---: | :--- | :--- |
| **P1** | ¿Dónde se localizan con exactitud las zonas saturadas? | Malla H3 microespacial (res 8) + radiancia nocturna VIIRS |
| **P2** | ¿Qué zonas tienen alto potencial pero baja visibilidad? | Clustering HDBSCAN + Índice de Potencial Turístico (PTNA) |
| **P3** | ¿Qué comarcas rurales tienen condiciones para absorber demanda? | Modelo topoclimático + NDVI + Marco ESG ($PTNA > 0, ESG > 60$) |
| **P4** | ¿Cómo influye la accesibilidad en el éxito de zonas no costeras? | Matriz vial ORS (18 destinos) + GTFS multiumbral (200/500/1.000 m) |
| **P5** | ¿Qué áreas muestran señales de congestión? | Índice continuo de saturación: densidad de plazas + NLP + VIIRS |
| **P6** | ¿De qué se quejan los turistas en el sur y qué buscan en el interior? | Inferencia multilingüe XLM-RoBERTa + BERTopic + PyABSA |
| **P7** | ¿Qué impacto tendría redistribuir un 10–20 % de la masa turística? | Simulador territorial interactivo What-If (`simulador.py`) |

## 1.3. Propuesta de Valor y Aporte Diferencial

Frente a cuadros de mando estáticos convencionales de *Business Intelligence*, la solución articula una arquitectura *Lakehouse* continua a escala insular y resolución microterritorial, fundamentada en cinco ventajas diferenciales:

1. **Superación del sesgo MAUP (*Modifiable Areal Unit Problem*):** Sustitución de las delimitaciones municipales administrativas por una teselación hexagonal regular (Uber H3, resolución 8, celdas de 0,737 km² y 461 m de apotema), eliminando las distorsiones de escala espacial.
2. **Integración multimodal holística:** Consolidación en un único modelo espacial de doce fuentes heterogéneas: teledetección (Sentinel-2 y VIIRS), oferta reglada y vacacional geocodificada, red de transporte público (GTFS e isócronas ORS), climatología horaria y minería de texto multilingüe.
3. **Modelado físico topoclimático de precisión:** Simulación de los microclimas insulares mediante gradientes adiabáticos, inversión térmica del mar de nubes (800–1.500 m) y corrección orográfica Foehn por orientación de laderas (aspect).
4. **Machine Learning con conciencia espacial (*Spatial ML*):** Detección de patrones mediante agrupamiento por densidad jerárquica con ruido (HDBSCAN) y regresión multiescala ponderada geográficamente (MGWR) con anchos de banda locales por variable.
5. **Prescripción ejecutiva mediante RAG (*Retrieval-Augmented Generation*):** Interrogación en lenguaje natural sobre las tablas maestras *Gold* mediante inferencia ultrarrápida LPU (Groq y Llama-3), traduciendo el dato multidimensional en recomendaciones estratégicas inmediatas.
"""


def get_chapter_2():
    return """# 2. Infraestructura Cloud y Adquisición de Datos

## 2.1. Arquitectura en Microsoft Azure

La infraestructura se desplegó íntegramente en la región europea de Microsoft Azure con tres componentes principales:

* **Azure Blob Storage (Data Lake Gen2):** Repositorio primario estructurado en contenedores `bronce-raw`, `silver-processed` y `gold-analytics`. Almacena Parquet particionados, GeoTIFFs de teledetección y colecciones JSON brutas.
* **Azure Database for PostgreSQL Flexible Server v16 + PostGIS 3.4:** Motor relacional y geoespacial central (2 vCores, 8 GiB RAM, SSD Premium). Aloja las tablas del esquema `bronze` y los modelos analíticos de `silver` y `gold`. Las tablas de caché de geocodificación (`bronze_registro_geocoding_lookup` y `bronze_booking_geocoding_lookup`) centralizan en la nube todas las coordenadas resueltas, eliminando dependencias locales.
* **VM Azure Linux (Ubuntu 22.04 LTS):** Nodo orquestador de cron jobs, scrapers y ejecuciones de dbt Core 1.8.

El proyecto partió de una instancia Neon.tech para prototipado rápido y migró a Azure al incorporar el backfill histórico de Agrocabildo y los más de dos millones de registros GTFS de TITSA, que superaban las limitaciones de la capa gratuita. La migración se realizó con el protocolo binario `COPY` de PostgreSQL.

## 2.2. Extracción de Microdatos Oficiales Tabulares y Espaciales

La información territorial y socioeconómica de base se adquirió programáticamente a partir de fuentes institucionales abiertas:

* **Instituto Canario de Estadística (ISTAC):** Mediante su API REST (recurso *Municipios en Cifras* C00067A), se ingirieron quince indicadores socioeconómicos para los 31 municipios de Tenerife (códigos INE 38001 a 38052), abarcando pernoctaciones mensuales, plazas ofertadas, ocupación, población turística equivalente, paro registrado y la serie de afiliaciones a la Seguridad Social en ocho sectores.
* **Cartografía Vectorial Oficial (Cabildo de Tenerife e IDECanarias):** A través de la API CKAN del Portal de Datos Abiertos del Cabildo insular (`datos.tenerife.es`) se descargaron en GeoJSON los límites municipales, los Bienes de Interés Cultural (BIC) y las oficinas de turismo, complementados con las capas de Zonas Turísticas y Espacios Naturales Protegidos (ENP) de GRAFCAN / IDECanarias, consolidándose en Azure Blob como GeoParquet en EPSG:4326.
* **Modelo Digital del Terreno (MDT25):** Con una resolución de celda de 25 metros, se derivaron matricialmente mediante el operador de gradiente de Horn (1981) la altitud, la pendiente topográfica, la orientación de laderas (aspect) y la radiancia del sombreado (*hillshade* a 315° NW y 45° de elevación solar), agregándose sus estadísticas zonales a la geometría insular.

| Origen | Proveedor | Formato | Volumen / Cobertura |
| :--- | :--- | :--- | :--- |
| **AENA** | Ministerio de Transportes | CSV mensual | Pasajeros TFS y TFN, serie 2019–2026 |
| **Alojamiento Oficial** | Gobierno de Canarias | Open Data / API | 31.314 establecimientos (30.589 VV, 314 hoteles, 411 extrahoteleros; 263.769 plazas) |
| **Booking.com** | Plataforma comercial | Scraping ético JSON | 38.412 reseñas geolocalizadas |
| **TripAdvisor** | Plataforma comercial | Scraping ético JSON | 12.840 reseñas de hoteles y actividades |
| **LosViajeros** | Comunidad de viajeros | HTML / foros | 2.650 mensajes de debate (248 hilos) |
| **YouTube** | YouTube Data API v3 | JSON API | 1.890 comentarios de vídeos turísticos |
| **Agrocabildo** | Cabildo de Tenerife | API REST horaria | 67 estaciones agrometeorológicas insulares |
| **Copernicus Sentinel-2** | Agencia Espacial Europea | GeoTIFF L2A 20 m | Compuestos trimestrales NDVI / NDBI (2019–2026) |
| **NOAA/NASA VIIRS** | Earth Observation Group | GeoTIFF DNB 500 m | Compuestos mensuales de luz nocturna (2019–2026) |
| **GTFS TITSA / Tranvía** | Cabildo / Open Data | GTFS ZIP | 3.893 paradas, 142 líneas y 2.082.154 registros de paso |
| **Cartografía Abierta** | Cabildo / GRAFCAN | GeoJSON / WFS | 31 municipios, ENP, BIC, Oficinas Turismo, MDT25 |
| **Microdatos ISTAC** | Instituto Canario de Estadística | API REST / SDMX | 15 indicadores socioeconómicos y suite de empleo |

## 2.3. Derechos de Uso, Licencias y Marco Ético de los Datos

Todo el proceso de adquisición se rigió por un marco estricto de diligencia debida ética y legal:

1. **Datos abiertos institucionales y teledetección:** Las fuentes gubernamentales (ISTAC, IDECanarias, Cabildo y Agrocabildo) se explotan al amparo de la Directiva Europea 2019/1024 y la Ley 37/2007 de reutilización de información del sector público. Las imágenes Sentinel-2 se rigen por la política de acceso abierto de la ESA, los datos de radiancia nocturna VIIRS por la política de libre acceso a datos científicos de la NASA/NOAA, y la matriz GTFS de TITSA por la licencia abierta insular de transporte.
2. **Adquisición en plataformas sociales (Booking.com y TripAdvisor):** Previo al desarrollo de los extractores, se evaluaron los archivos `robots.txt` y los Términos de Servicio (ToS) de ambas plataformas. La sección A14 de los ToS de Booking.com y las cláusulas de TripAdvisor restringen la extracción masiva automatizada con fines comerciales sin autorización previa. Para este TFM, la recolección se circunscribió estrictamente al marco de **investigación académica sin ánimo de lucro** de la Universidad Complutense, implementando un *rate limiting* conservador (retrasos probabilísticos de 2,5–5,0 s por petición) para no sobrecargar los servidores.
3. **Privacidad y cumplimiento del RGPD:** El pipeline descarta de forma irreversible cualquier dato de carácter personal (nombres de usuario, identificadores de perfil, avatares y direcciones IP). La información extraída se limitó a texto de opinión, puntuación numérica y fecha, agregándose a nivel espacial en celdas H3 sin trazabilidad individual.
4. **Condición mandatoria para explotación comercial (TUI Group):** La arquitectura del *Lakehouse* está totalmente desacoplada de los mecanismos de ingesta. Para cualquier despliegue operativo o comercial por parte de **TUI Group**, estos extractores experimentales **deben sustituirse necesariamente por las APIs oficiales y contratos de licencia correspondientes**: *Booking Connectivity Partner API*, *TripAdvisor Content API* y *YouTube Data API Enterprise* (Google Cloud Platform).
"""


def get_chapter_3():
    return """# 3. Data Lakehouse y Topología Geoespacial

## 3.1. Arquitectura Medallón con dbt Core

El almacén analítico sigue el patrón **Medallion Lakehouse** (Armbrust et al., 2021) implementado con dbt Core 1.8 sobre Azure PostgreSQL Flexible Server v16 + PostGIS 3.4. La orquestación del pipeline se realiza con **Apache Airflow 2.x**, desplegado en contenedores Docker (`Dockerfile.airflow` + `docker-compose.yml`) sobre la VM Ubuntu de Azure. El proyecto define **tres DAGs** que cubren los distintos ciclos de vida del dato:

* **`historical_full_pipeline`** (trigger manual, una única vez): Carga histórica completa en cinco fases secuenciales con máxima paralelización interna. Un `ShortCircuitOperator` controlado por la Variable de Airflow `run_heavy_ml` activa o desactiva las tasks de inferencia NLP pesadas (sentimiento, aspectos) sin bloquear el resto del flujo. Las fuentes semimanuales (Booking scraper, satélite con autenticación GEE) se declaran con `TriggerRule.NONE_FAILED_MIN_ONE_SUCCESS` para que el pipeline continúe aunque fallen.
* **`incremental_monthly_pipeline`** (cron `0 6 1 * *`, primer día de cada mes): Refresca únicamente las fuentes que cambian mensualmente —satélite, ISTAC, clima, alojamientos y AENA (esta última con ShortCircuit que lee la Variable `aena_upload_ready`)— y regenera únicamente los dominios Silver y Gold afectados.
* **`social_refresh`** (trigger manual): Reingesta controlada de fuentes sociales (Booking, TripAdvisor, YouTube, LosViajeros) y relanza el pipeline NLP cuando se dispone de nuevas reseñas.

Las cinco fases del DAG histórico son:

```
FASE 1 — Ingesta a Azure Blob Storage (paralelo):
  ingest_aena │ ingest_alojamientos │ ingest_clima │ ingest_gtfs
  ingest_istac (2 tasks) │ ingest_espacial (4 tasks secuenciales)
  ingest_tripadvisor ⚠️ │ ingest_youtube ⚠️ │ ingest_satelite ⚠️
  ingest_booking ⚠️ │ ingest_losviajeros ⚠️
  join (none_failed_min_one_success)
FASE 2 — Carga a PostgreSQL (secuencial 01→07):
  pg_01_vector → pg_02_mdt → pg_03_satelite → pg_04_booking
  → pg_05_tabular → pg_06_geocode_booking → pg_07_alojamientos_geocode
FASE 3 — dbt Silver (paralelo por dominio: 9 dominios)
FASE 4 — Analytics (paralelo + ShortCircuit GPU):
  check_ml_enabled → sentiment_batch │ aspects_batch │ geo_toponyms │ clustering
  accesibilidad_h3 (siempre, sin GPU)
FASE 5 — dbt Gold (paralelo: 9 modelos)
```

Las tres capas del *lakehouse* que gestiona dbt son:

* **Bronze (Raw):** **48 tablas fuente** declaradas en `sources.yml`, organizadas en doce áreas temáticas. Preserva el estado original con marca temporal de ingesta; ningún dato se modifica ni elimina en esta capa.
* **Silver (Limpieza y Conformance):** **9 dominios de modelos** SQL —`alojamiento`, `booking`, `clima`, `espacial`, `istac`, `losviajeros`, `movilidad`, `tripadvisor` y `youtube`— que limpian nulos, deduplican registros mediante `ROW_NUMBER() OVER (PARTITION BY id ORDER BY fecha DESC)`, tipifican columnas y proyectan geometrías a EPSG:4326 y EPSG:32628.
* **Gold (Analítica Multidimensional):** **11 modelos materializados** listos para ML, visualización y RAG *(catálogo detallado en la sección 4.4)*:

| Modelo Gold | Granularidad | Contenido principal |
| :--- | :---: | :--- |
| `gold_h3_master` | H3 (2.579 celdas) | >60 variables biofísicas, topoclimáticas, alojativas y NLP |
| `gold_sentimiento_h3` | H3 | Polaridad media y queja modal por fuente |
| `gold_municipio_master` | Municipal (31) | KPIs ISTAC, AENA, empleo y alojamiento integrados |
| `gold_municipio_anual / mensual` | Municipal | Series temporales de pernoctaciones y ocupación |
| `gold_municipio_empleo` | Municipal | Afiliaciones SS por sector y ratio de monocultivo |
| `gold_turismo_hotelero_anual / mensual` | Municipal | RevPAR, ADR y GOP hoteleros con referencia ARIMA |
| `gold_aena_pasajeros` | Aeropuerto | Pasajeros TFS/TFN (2019–2026) |
| `gold_h3_ptna` | H3 | Índice PTNA, coeficientes MGWR locales y score ESG *(pendiente)* |
| `gold_h3_clusters` | H3 | Arquetipos HDBSCAN y probabilidad de pertenencia |

dbt gestiona automáticamente el grafo de dependencias entre modelos (`ref()`, `source()`), los materializa como tablas físicas con índices GiST/BRIN, y aplica **tests de integridad** declarativos: unicidad de `h3_index`, rangos válidos de NDVI/NDBI, ausencia de nulos en geometría y referencial entre Silver y Gold.

## 3.2. La Malla Hexagonal Uber H3 (Resolución 8) y Resolución del MAUP

En Tenerife, municipios como La Orotava abarcan desde la costa (0 m) hasta la cima del Teide (3.715 m), por lo que un promedio municipal mezcla realidades climáticas y económicas radicalmente opuestas. Para resolver el **Problema de la Unidad de Área Modificable (MAUP)** (Openshaw, 1984), el proyecto adopta como teselación primaria la **Malla Hexagonal Uber H3 en Resolución 8**:

* Hexágonos isotrópicos de **~0,85 km²** con distancia uniforme entre centroides vecinos de 990 m; la isotropía garantiza que ninguna dirección de análisis espacial recibe un sesgo sistemático de muestreo.
* El rasterizado bruto de la costa generó 2.746 celdas Bronze; tras el filtrado geoespacial estricto en `silver_h3_grid` —que descarta celdas sin datos topográficos ni satelitales— se depuraron **2.579 celdas terrestres limpias**.
* `silver_h3_grid` actúa como **tabla pivote maestra** del sistema: todos los modelos Gold se unen a ella mediante `ST_Contains(h.geometry, p.geometry)` o `ST_Intersects()`, garantizando que cualquier dato puntual o poligonal quede referenciado al mismo conjunto canónico de hexágonos.
* Las geometrías se almacenan en **EPSG:4326** (WGS84) para indexación H3 y renderizado web, y se proyectan en tiempo de consulta a **EPSG:32628** (REGCAN95 / UTM Zona 28N) para cálculos métricos reales (áreas, distancias, buffers).
* Los índices GiST sobre `geometry` y el índice único sobre `h3_index` en `gold_h3_master` permiten resolver cruces espaciales complejos en 15–45 milisegundos.

## 3.3. Geocodificación Centralizada y Control de Calidad del Dato

El Registro General Turístico de Canarias incluye numerosas entradas sin coordenadas geográficas o con topónimos en formatos no canónicos. Para normalizar estas direcciones sin coordenadas se implementó un flujo centralizado de geocodificación que opera íntegramente en la nube:

1. **Normalización Toponímica Canaria:** Corrección automática de artículos pospuestos (`"Orotava (La)"` → `"La Orotava"`), expansión de abreviaturas viales y desambiguación insular obligatoria (sufijo `, Tenerife, España` a toda solicitud de geocodificación).
2. **Caché en Base de Datos Cloud (Azure PostgreSQL):** Antes de consumir cuota de API, el pipeline consulta las tablas de lookup `bronze_registro_geocoding_lookup` y `bronze_booking_geocoding_lookup`. Solo las direcciones inéditas generan una llamada externa, y su resultado se inserta de forma inmediata en la nube para reutilización futura de cualquier miembro del equipo.
3. **Cruce Espacial en dbt:** El modelo `silver_alojamientos_oficiales.sql` genera la geometría canónica con `ST_SetSRID(ST_MakePoint(longitud, latitud), 4326)` mediante un `COALESCE` que prioriza coordenadas explícitas del registro sobre las geocodificadas *(SQL completo en Anexo C.1)*.
4. **Deduplicación y Tests de Calidad:** `ROW_NUMBER() OVER (PARTITION BY registro_id ORDER BY fecha_actualizacion DESC)` elimina versiones duplicadas; los tests dbt comprueban unicidad de `registro_id`, rango de latitud/longitud dentro del bounding box de Tenerife y ausencia de nulos en geometría.
"""
