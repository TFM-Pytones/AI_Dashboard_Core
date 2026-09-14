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

El presente TFM responde al **Desafío 3 de TUI Group** (UCM, 2025–2026): diseñar, implementar y productivizar un sistema de inteligencia territorial que diagnostique la capacidad de carga insular, detecte zonas con potencial desaprovechado y modele escenarios de redistribución de la demanda. La plataforma integra más de diez fuentes heterogéneas en un **Data Lakehouse en Microsoft Azure** con arquitectura Medallón (Bronze, Silver y Gold), articulado sobre la **Malla Hexagonal Uber H3 Resolución 8** (2.579 celdas terrestres de ~0,85 km²) para superar el sesgo MAUP de las divisiones administrativas. Las fuentes cubren: parque alojativo oficial y más de 55.000 reseñas de Booking y TripAdvisor; red de transporte público GTFS (TITSA y Tranvía); teledetección Copernicus Sentinel-2 (NDVI y NDBI) y radianza nocturna VIIRS; modelado topoclimático sobre 67 estaciones de Agrocabildo; isócronas de accesibilidad vial hacia 18 destinos estratégicos; y corpus textual multilingüe de YouTube y LosViajeros. La analítica avanzada incluye segmentación no supervisada con HDBSCAN, regresión geográfica ponderada multiescala (MGWR), modelado de tópicos con BERTopic y análisis de sentimiento con XLM-RoBERTa. El sistema culmina en un AI-Dashboard interactivo en Streamlit/PyDeck con simulador gravitatorio de redistribución y motor de informes narrativos vía Groq API.

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

En 2024 Tenerife superó los 7,2 millones de turistas internacionales (+12 % interanual), aportando más del 35 % del PIB regional (ISTAC, 2025). Sin embargo, la actividad turística presenta una asimetría extrema: la franja sur (Adeje, Arona y Santiago del Teide) concentra más del 80 % de las plazas hoteleras regladas, colapsa diariamente la autopista TF-1 con intensidades superiores a 90.000 vehículos/día, sobrecarga las plantas desaladoras y tensiona el mercado del alquiler residencial a través de más de 27.500 viviendas vacacionales registradas (Turismo de Tenerife, 2025). Esta situación encaja con la definición de *overtourism* de Milano et al. (2019): el volumen turístico degrada inaceptablemente tanto la calidad de vida de los residentes como el valor de la experiencia del visitante.

En contraste, los 25 municipios restantes —medianías agrícolas (Arico, Fasnia, Vilaflor, La Guancha, Buenavista del Norte) y la vertiente norte (Garachico, Icod de los Vinos, San Juan de la Rambla)— disponen de condiciones bioclimáticas, paisajísticas y patrimoniales excepcionales, pero sufren despoblación, abandono de tierras y una presencia casi nula en los canales de distribución internacional de TUI.

## 1.2. Objetivos y Preguntas Estratégicas de TUI Group

El **objetivo general** del proyecto es diseñar, desplegar y validar una plataforma de inteligencia territorial que capacite a TUI Group para monitorizar la capacidad de carga insular y planificar la redistribución equilibrada de los flujos turísticos en los 31 municipios de Tenerife. Los siete objetivos específicos se articulan en torno a las cinco preguntas estratégicas del briefing corporativo:

| # | Pregunta Estratégica (Briefing TUI) | Módulo del Proyecto |
| :---: | :--- | :--- |
| **P1** | ¿Dónde se localizan con exactitud las zonas saturadas? | Malla H3 + VIIRS + densidad alojativa |
| **P2** | ¿Qué comarcas rurales tienen condiciones para absorber demanda? | Modelo topoclimático + NDVI + PTNA |
| **P3** | ¿Cómo influye la accesibilidad en el éxito de zonas no costeras? | ORS (18 destinos) + GTFS multiumbral |
| **P4** | ¿De qué se quejan los turistas en el sur y qué buscan en el interior? | XLM-RoBERTa + BERTopic + PyABSA |
| **P5** | ¿Qué impacto tendría redistribuir un 10–20 % de la masa turística? | Simulador gravitatorio de Huff/Reilly |

## 1.3. Propuesta de Valor y Aporte Diferencial

Frente a cuadros de mando estáticos de Business Intelligence, esta plataforma aporta cinco ventajas diferenciales: (1) superación del sesgo MAUP mediante la malla H3; (2) integración multimodal holística de satélite, camas, movilidad, climatología y NLP en una única base de datos espacial; (3) modelado físico topoclimático que reproduce los microclimas reales de Tenerife; (4) Machine Learning con conciencia espacial (HDBSCAN y MGWR); y (5) cierre de la brecha entre el dato y la decisión ejecutiva mediante RAG con Groq API.
"""


def get_chapter_2():
    return """# 2. Infraestructura Cloud y Adquisición de Datos

## 2.1. Arquitectura en Microsoft Azure

La infraestructura se desplegó íntegramente en la región europea de Microsoft Azure con tres componentes principales:

* **Azure Blob Storage (Data Lake Gen2):** Repositorio primario de objetos estructurado en contenedores `bronze-raw`, `silver-processed` y `gold-analytics`. Almacena Parquet particionados, GeoTIFF de teledetección y colecciones JSON brutas.
* **Azure Database for PostgreSQL Flexible Server v16 + PostGIS 3.4:** Motor relacional y geoespacial central (2 vCores, 8 GiB RAM, SSD Premium). Aloja los 48 tablas brutas del esquema `bronze` y los modelos analíticos de `silver` y `gold`. Las tablas de caché de geocodificación (`bronze_registro_geocoding_lookup` y `bronze_booking_geocoding_lookup`) centralizan en la nube todas las coordenadas resueltas, evitando dependencias de archivos locales.
* **VM Azure Linux (Ubuntu 22.04 LTS):** Nodo orquestador de cron jobs, scrapers y ejecuciones de dbt Core 1.8.

El proyecto partió de una instancia Neon.tech para prototipado rápido y migró a Azure al incorporar el backfill histórico de Agrocabildo y los más de dos millones de registros GTFS de TITSA, que superaban las limitaciones de la capa gratuita. La migración se realizó con el protocolo binario `COPY` de PostgreSQL.

## 2.2. Fuentes de Datos Integradas

El sistema consolida doce fuentes heterogéneas en la capa Bronze:

| Origen | Proveedor | Formato | Volumen / Cobertura |
| :--- | :--- | :--- | :--- |
| **AENA** | Ministerio de Transportes | CSV mensual | Pasajeros TFS y TFN, 2019–2026 |
| **Alojamiento Oficial** | Gobierno de Canarias | Open Data / API | 46.820 unidades alojativas regladas |
| **Booking.com** | Plataforma comercial | Scraping ético JSON | 38.412 reseñas geolocalizadas |
| **TripAdvisor** | Plataforma comercial | Scraping ético JSON | 12.840 reseñas de hoteles y actividades |
| **LosViajeros** | Comunidad de viajeros | HTML / foros | 2.650 mensajes de debate |
| **YouTube** | YouTube Data API v3 | JSON API | 1.890 comentarios de vídeos turísticos |
| **Agrocabildo** | Cabildo de Tenerife | API REST horaria | 67 estaciones agrometeorológicas insulares |
| **Copernicus Sentinel-2** | Agencia Espacial Europea | GeoTIFF L2A 10 m | Compuestos trimestrales NDVI / NDBI |
| **NOAA/NASA VIIRS** | Earth Observation Group | GeoTIFF DNB 500 m | Compuestos mensuales de luz nocturna |
| **GTFS TITSA / Tranvía** | Cabildo / Open Data | GTFS ZIP | 3.893 paradas, 142 líneas y calendarios |
| **Cartografía IDECanarias** | GRAFCAN / Gobierno de Canarias | Shapefile / WFS | Límites de 31 municipios, ENP, BIC, MDT05 |
| **Microdatos ISTAC** | Instituto Canario de Estadística | API REST / SDMX | Series mensuales de empleo, turismo y gasto |

## 2.3. Ética, Licencias y Gobernanza de la Extracción

Las fuentes institucionales (ISTAC, IDECanarias, Agrocabildo) se explotan al amparo de la Directiva 2019/1024 y la Ley 37/2007 de reutilización de información del sector público. Los datos de Copernicus siguen la política de acceso abierto de la ESA; el feed GTFS de TITSA se distribuye como datos abiertos de transporte.

Para los datos sociales, los scrapers respetan el fichero `robots.txt`, aplican un throttling probabilístico de 2,5–5,0 segundos por petición e identifican las solicitudes con un User-Agent de afiliación académica UCM. En cumplimiento del RGPD, el pipeline anonimiza de forma irreversible cualquier identificador de usuario, suprimiendo nombres y IPs que no aporten valor estadístico.
"""


def get_chapter_3():
    return """# 3. Data Lakehouse y Topología Geoespacial

## 3.1. Arquitectura Medallón con dbt Core

El almacén analítico sigue el patrón **Medallion Lakehouse** (Armbrust et al., 2021) implementado con dbt Core 1.8:

* **Bronze (Raw):** 48 tablas fuente declaradas en `sources.yml`; preserva el estado original con marca temporal de ingesta.
* **Silver (Limpieza y Conformance):** Modelos SQL que limpian nulos, deduплican registros mediante `ROW_NUMBER() OVER (PARTITION BY id ORDER BY fecha DESC)`, tipifican columnas y proyectan geometrías a EPSG:4326 y EPSG:32628.
* **Gold (Analítica Multidimensional):** Tablas maestras desnormalizadas listas para ML, visualización y RAG:
  * `gold_h3_master` (394 líneas SQL): más de 60 variables biofísicas, topoclimáticas, de accesibilidad y de oferta por celda hexagonal.
  * `gold_sentimiento_h3`: polaridad media y queja modal por celda.
  * `gold_municipio_master` + familia de modelos municipales: datos ISTAC y AENA para los 31 municipios.

dbt gestiona las dependencias entre modelos, los materializa como tablas físicas y aplica tests automáticos de integridad (claves únicas, rangos válidos, no nulos).

## 3.2. La Malla Hexagonal Uber H3 (Resolución 8) y Resolución del MAUP

En Tenerife, municipios como La Orotava abarcan desde la costa (0 m) hasta la cima del Teide (3.715 m), por lo que un promedio municipal mezcla realidades climáticas y económicas radicalmente opuestas. Para resolver el **Problema de la Unidad de Área Modificable (MAUP)** (Openshaw, 1984), el proyecto adopta como teselación primaria la **Malla Hexagonal Uber H3 en Resolución 8**:

* Hexágonos isotrópicos de **~0,85 km²** con distancia uniforme entre centroides vecinos de 990 m.
* El rasterizado bruto de la costa generó 2.746 celdas Bronze; tras el filtrado geoespacial estricto en `silver_h3_grid`, se depuraron **2.579 celdas terrestres limpias** sin valores nulos en topografía ni teledetección.
* Cada celda se indexa por su identificador hexadecimal H3 de 64 bits y su centroide geométrico puro (`ST_Centroid(geometry)`).
* Todas las geometrías se almacenan en **EPSG:4326** (WGS84) para indexación H3 y renderizado web, y se proyectan en tiempo de consulta a **EPSG:32628** (REGCAN95 / UTM Zona 28N) para cálculos métricos reales.
* Los índices GiST en `gold_h3_master` permiten resolver cruces espaciales complejos en 15–45 milisegundos.

## 3.3. Geocodificación Centralizada en Azure PostgreSQL

Para normalizar las direcciones del registro oficial sin coordenadas, se implementó un flujo centralizado de geocodificación:

1. **Normalización Toponímica Canaria:** Corrección de artículos pospuestos (`"Orotava (La)"` → `"La Orotava"`), expansión de abreviaturas y desambiguación insular obligatoria.
2. **Caché en Base de Datos Cloud:** Consulta prioritaria a las tablas de lookup en Azure PostgreSQL. Solo las direcciones inéditas consumen cuota de API y se insertan de forma inmediata en la nube.
3. **Cruce Espacial en dbt:** `silver_alojamientos_oficiales.sql` genera la geometría canónica con `ST_SetSRID(ST_MakePoint(longitud, latitud), 4326)` *(véase Anexo C.1 para el SQL completo)*.
"""
