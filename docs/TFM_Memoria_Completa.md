# UNIVERSIDAD COMPLUTENSE DE MADRID
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

---

# 1. Introducción y Contexto de Negocio

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

---

# 2. Infraestructura Cloud y Adquisición de Datos

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

---

# 3. Data Lakehouse y Topología Geoespacial

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

---

# 4. Inteligencia Territorial, Modelado Espacio-Temporal y Machine Learning

## 4.1. Caracterización Físico-Territorial y Teledetección Satelital

La capacidad de carga de cada celda hexagonal se caracteriza mediante tres conjuntos de variables biofísicas:

**A. Variables Morfométricas (MDT05 del IGN, 5 m de resolución):** Elevación media (0 m en costa – 3.715 m en el Teide), pendiente media (1,2°–48,5°), orientación o aspecto (discrimina barlovento/sotavento) y sombreado del relieve (hillshade). El operador diferencial de Horn (1981) sobre ventanas 3×3 píxeles calcula la pendiente *(detalle matemático en Anexo C.2)*.

**B. Teledetección Biofísica — Copernicus Sentinel-2 (10 m, L2A):** Mosaicos estacionales filtrados a menos del 20 % de nubosidad con máscara SCL. El **NDVI** mide el vigor fotosintético: oscila de <0,15 en los malpaíses áridos del sur hasta >0,75 en la laurisilva de Anaga; el **NDBI** cartografía el suelo sellado y el asfalto como indicador de huella construida *(fórmulas en Anexo C.2)*.

**C. Radianza Nocturna NOAA/NASA VIIRS (500 m, DNB):** Compuestos mensuales calibrados en nW/(cm²·sr). Los polos turísticos del sur (Adeje, Arona) superan los 65 nW/(cm²·sr), mientras que las celdas de medianías caen por debajo de 4 nW/(cm²·sr) y la cumbre del Teide registra valores cercanos a cero, protegida por la Ley del Cielo (Ley 31/1988).

| Variable | Rango Empírico en Tenerife |
| :--- | :--- |
| Elevación media | 0,0 m (costa) — 3.715,0 m (Teide) |
| Pendiente media | 1,2° (llanuras litorales) — 48,5° (barrancos de Masca/Anaga) |
| NDVI medio | 0,08 (malpaís/lava) — 0,82 (laurisilva en Anaga) |
| NDBI medio | -0,45 (masa forestal densa) — +0,38 (trama urbana compacta) |
| Radianza VIIRS | 0,2 nW/(cm²·sr) (cumbre Teide) — 88,4 nW/(cm²·sr) (Playa de Las Américas) |

## 4.2. Modelo Topoclimático Microinsular

El clima de Tenerife responde a cuatro forzadores atmosféricos simultáneos:

1. **Vientos Alisios del Noreste:** Masas de aire fresco y húmedo del anticiclón de las Azores que inciden de forma permanente sobre la vertiente norte.
2. **Inversión Térmica de Subsidencia (800–1.500 m):** Capa de aire cálido que actúa como tapadera impidiendo el ascenso convectivo y favoreciendo la formación del Mar de Nubes.
3. **Efecto Föhn en Sotavento:** El aire que rebasa la cumbre desciende por la vertiente sur calentándose adiabáticamente, generando un clima árido y despejado en Adeje y Arona.
4. **Calima y Advección Sahariana:** Invasiones de polvo que provocan aumentos térmicos repentinos (>32 °C) y caídas de humedad (<25 %).

La implementación en dbt Core combina **interpolación IDW con k=3 estaciones** de la red de Agrocabildo (67 estaciones activas) y cuatro factores correctores físicos:

* **Gradiente adiabático de temperatura:** -0,0065 °C por metro de desnivel respecto a la estación de referencia.
* **Mar de Nubes (800–1.500 m, barlovento):** Factor +25 % de humedad relativa por condensación persistente de los Alisios.
* **Pisos de cumbre (>1.500 m):** Factor -30 % de humedad por la atmósfera cristalina y seca de alta montaña.
* **Efecto Föhn (sotavento, orientación 90°–300°):** Factor -15 % de humedad; reducción del 60 % de precipitación.
* **Influencia marítima costera (<1,5 km):** Bonificación de +15 % de humedad en toda la franja litoral.
* **Medianías bajas (<800 m, barlovento):** Factor de +5 % de humedad.

La validación frente a 12 estaciones AEMET independientes redujo el RMSE de temperatura de 2,84 °C (IDW estándar) a **0,91 °C**, y el de humedad relativa de 18,6 % a **6,2 %**, confirmando la precisión del modelo físico *(SQL completo en Anexo C.2)*.

## 4.3. Accesibilidad Multimodal y Conectividad

La redistribución de flujos turísticos requiere conocer la accesibilidad real de cada celda hexagonal:

* **Matriz de Conducción Vial (OpenRouteService):** Tiempos de viaje en vehículo privado desde cada uno de los 2.579 hexágonos hacia **18 destinos estratégicos insulares**: aeropuertos TFS y TFN, Santa Cruz, Costa Adeje, Puerto de la Cruz, Teleférico del Teide, La Laguna, Candelaria, Los Gigantes, El Médano, Garachico, Anaga, Masca, Vilaflor, La Orotava, Güímar, Buenavista del Norte y Arico. Adicionalmente se generaron isócronas a 15, 30, 45 y 60 minutos desde ambos aeropuertos.
* **Cobertura en Transporte Público Regular (GTFS TITSA/Tranvía):** Recuento de paradas activas en tres umbrales escalonados: 200 m (proximidad estricta), 500 m (estándar cómodo) y 1.000 m (acceso amplio). Se complementa con la distancia continua a la marquesina más cercana y la distancia al hospital comarcal más próximo.

## 4.4. Segmentación Espacial No Supervisada: HDBSCAN

### Motivación y elección del algoritmo

Los métodos de clustering convencionales presentan limitaciones críticas cuando se aplican a un territorio de morfología tan compleja como Tenerife:

* **K-Means:** Impone un número de clusters fijo de antemano y asume que todos tienen forma esférica y tamaño similar. En Tenerife, donde los polos turísticos del litoral son zonas compactas y muy densas mientras que las medianías agrícolas son extensas y difusas, K-Means los distorsiona sistemáticamente y no es capaz de señalar qué celdas son simplemente ruido geográfico.
* **DBSCAN Clásico:** Aunque detecta outliers, exige un único radio de densidad global (epsilon). Ante la heterogeneidad de densidades del territorio insular —desde las celdas hiperconcentradas de Adeje hasta los hexágonos dispersos de Vilaflor— este radio único falla: o bien fragmenta el litoral en cientos de clusters diminutos, o bien funde en un solo grupo todo el interior rural.
* **HDBSCAN (*Hierarchical Density-Based Spatial Clustering of Applications with Noise*, McInnes et al., 2017):** Construye una jerarquía completa de densidades a múltiples escalas y extrae los clusters estables como aquellos que persisten durante el mayor rango de densidad sin fragmentarse. Esto le permite identificar simultáneamente las zonas turísticas compactas del sur y los amplios corredores rurales del norte, asignando como ruido (cluster -1) las celdas que no encajan en ningún patrón coherente —generalmente celdas de transición entre zonas de alta montaña y el litoral árido—, lo que resulta ecológicamente significativo.

### Implementación y variables de entrada

A partir de las características normalizadas con `RobustScaler` (escalado robusto ante valores extremos) en [`build_features.py`](file:///c:/Users/ROBERTO/Proyectos_Python/TFM_TUI_Tenerife/AI_Dashboard_Core/analytics/clustering/build_features.py), se construyó la matriz de entrada con diez variables por celda:

| Variable | Descripción funcional |
| :--- | :--- |
| `elevation_mean` | Altitud media: forzador del microclima y del tipo de oferta posible |
| `slope_mean` | Pendiente: discrimina terrenos accesibles de zonas inaccesibles |
| `ndvi_mean` | Vigor vegetal: indicador de atractivo ambiental y ecoturístico |
| `ndbi_mean` | Huella construida: proxy de urbanización e infraestructura hotelera |
| `viirs_mean` | Radianza nocturna: indicador de actividad económica y presión turística |
| `n_alojamientos` | Número de establecimientos alojativos oficiales por celda |
| `n_paradas_transporte` | Cobertura de transporte público (radio 500 m) |
| `sentimiento_medio` | Polaridad afectiva media de las reseñas asociadas |
| `hillshade_mean` | Sombreado del relieve: discrimina orientaciones y exposición solar |
| `dist_costa_km` | Distancia a la línea de costa: estructura el gradiente litoral-interior |

Los parámetros del modelo se fijaron en `min_cluster_size = 35` y `min_samples = 10` tras validación por estabilidad del dendrograma de condensación. El **coeficiente de silueta medio** resultante (0,582) ratifica una separabilidad significativamente superior a la de los algoritmos alternativos.

### Cuatro arquetipos territoriales

| Cluster | Denominación | Cobertura | Perfil Distintivo y Comarcas Representativas |
| :---: | :--- | :---: | :--- |
| **C-0** | Polo Turístico Saturado | 14,2 % | Litoral sur (Adeje, Arona) y Puerto de la Cruz. VIIRS >50 nW, >1.850 plazas/km², NDBI alto, sentimiento +0,48 con queja dominante de ruido y masificación. |
| **C-1** | Corona Periurbana y Metropolitana | 22,6 % | Corredor Santa Cruz–La Laguna, Candelaria y Granadilla. Alta dotación de guaguas, NDBI elevado, función residencial de servicios y cercanía a autovías TF-1/TF-5. |
| **C-2** | Interior Rural y Medianías (Ecoturismo) | 31,5 % | Arico, Vilaflor, La Guancha, Fasnia y Buenavista. Altitud media (400–1.100 m), NDVI alto (>0,55), clima templado (18–22 °C), muy baja dotación alojativa actual y sentimiento neto superior (+0,74). **Máximo potencial estratégico para TUI.** |
| **C-3** | Espacios Protegidos y Alta Montaña | 28,4 % | Parque Nacional del Teide, Corona Forestal, Anaga y Teno. Pendientes >25°, altitud >1.500 m, nula dotación hotelera y régimen de protección ecológica estricta. El simulador bloquea reasignaciones hacia este cluster. |

La evaluación comparativa de algoritmos ratifica la elección:

| Algoritmo | Silueta Media | Tratamiento de Ruido | Adecuación al Territorio Canario |
| :--- | :---: | :---: | :--- |
| K-Means (k=4) | 0,384 | No (asignación forzada) | Nula: distorsiona la geografía y fragmenta corredores. |
| DBSCAN Clásico | 0,465 | Sí (parcial) | Deficiente: falla con densidades marcadamente heterogéneas. |
| **HDBSCAN** | **0,582** | **Sí (robusto al ruido)** | **Seleccionado:** jerarquía multiescala adaptada al relieve insular. |

## 4.5. Regresión Geográfica Ponderada (MGWR) e Índice de Potencial de Nicho (PTNA)

### Limitaciones del modelo OLS y justificación de MGWR

Un modelo de regresión por mínimos cuadrados ordinarios (OLS) asume que el efecto de cada variable explicativa sobre la satisfacción del turista es constante en todo el territorio. Esta hipótesis de **estacionariedad global** es indefendible en Tenerife: lo que valora un turista en un resort de playa de Adeje —acceso inmediato al mar, abundancia de servicios hosteleros y animación nocturna— es radicalmente distinto de lo que busca quien elige una casa rural en Vilaflor —sosiego, vistas al Teide, senderismo y gastronomía autóctona—. Imponer el mismo coeficiente para, por ejemplo, la variable "distancia a la costa" en ambas zonas produce estimaciones gravemente sesgadas y residuos espacialmente autocorrelacionados (índice I de Moran: 0,472 con p < 0,001 en OLS).

La **Regresión Geográficamente Ponderada Clásica (GWR)** corrige parcialmente este problema ajustando un modelo local por vecindad, pero utiliza un único radio de ponderación (bandwidth) para todas las variables. Esto introduce una nueva rigidez: la influencia de la vegetación (NDVI) puede operar a una escala muy diferente de la influencia de la conectividad aeroportuaria.

La **Regresión Geográficamente Ponderada Multiescala (MGWR, Fotheringham et al., 2017)** resuelve esta limitación asignando a cada covariable su propio radio de influencia óptimo, estimado empíricamente mediante minimización del criterio AICc corregido. El modelo local adopta la forma:

`y_i = b_0(u_i, v_i) + SUM_k [ b_k(u_i, v_i, bw_k) * x_ik ] + e_i`

donde `(u_i, v_i)` son las coordenadas del centroide de la celda i, `b_k` es el coeficiente local de la variable k y `bw_k` es su ancho de banda espacial óptimo.

### Anchos de banda y escalas de operación empíricas

| Variable Explicativa | Ancho de Banda (hexágonos vecinos) | Escala de Operación |
| :--- | :---: | :--- |
| Distancia a la costa | 85 | Hiperlocal: efecto que se extingue a pocos kilómetros |
| NDVI (vigor vegetal) | 240 | Intermedia: dominio comarcal (~15 km de radio) |
| Temperatura media anual | 310 | Intermedia-regional: gradiente altitudinal amplio |
| Número de paradas GTFS | 420 | Comarcal: red de guaguas cubre municipios enteros |
| Accesibilidad al aeropuerto | 820 | Comarcal-insular: atractor de escala isla entera |

Esta diferenciación de escalas revela que **la valoración turística es un fenómeno multiresolución**: la proximidad al mar determina el atractivo a escala hiperlocal, mientras que la conectividad aeroportuaria opera como variable de contexto insular que solo varía de forma gradual entre el norte y el sur.

### Evaluación comparativa de modelos de regresión

| Modelo | R² Ajustado | AICc | Moran's I Residuos | Dictamen |
| :--- | :---: | :---: | :---: | :--- |
| OLS Global | 0,418 | 4.821,3 | 0,472 (p < 0,001) | Descartado: sesgo espacial severo |
| Spatial Lag (SAR) | 0,594 | 4.310,5 | 0,118 (p < 0,01) | Insuficiente: retardo espacial de escala fija |
| Spatial Error (SEM) | 0,612 | 4.258,2 | 0,094 (p < 0,05) | Parcial: corrige error pero no modela coeficientes locales |
| GWR Clásico | 0,715 | 4.045,8 | 0,062 (p = 0,12) | Mejora sustancial, pero bandwidth único inadecuado |
| **MGWR Multiescalar** | **0,782** | **3.914,6** | **0,041 (p = 0,28)** | **Seleccionado:** residuos no autocorrelacionados |

El salto de R² de 0,418 (OLS) a 0,782 (MGWR) y la reducción del AICc en más de 900 puntos evidencian que los fenómenos de valoración turística en Tenerife no son estacionarios y requieren un enfoque multiescala. La desaparición de la autocorrelación espacial en los residuos (I de Moran: 0,041, p = 0,284) confirma que el modelo MGWR captura correctamente la estructura espacial de los datos.

### El Índice de Potencial Turístico No Aprovechado (PTNA)

A partir de los coeficientes locales de MGWR, se construyó el **Índice PTNA** (*Potential Tourism Niche Attraction*), una puntuación continua en escala [0, 100] que combina cinco dimensiones ponderadas por los pesos empíricos del modelo:

1. **Atractivo Ambiental (35 %):** NDVI elevado (>0,55), horas de sol favorables (según OMM) y ausencia de contaminación lumínica nocturna (VIIRS <10 nW).
2. **Confort Climático (20 %):** Temperatura media anual entre 16 y 24 °C y humedad relativa modelada entre 50 % y 80 %, excluyendo las oscilaciones extremas de calima y sotavento.
3. **Baja Saturación Actual (25 %):** Densidad de plazas alojativas inferior al 10 % de la media insular y radianza nocturna VIIRS en el cuartil inferior.
4. **Reputación Cualitativa Positiva (10 %):** Sentimiento medio de reseñas superior a +0,60, aunque con volumen muestral aún reducido (indicador de potencial no explorado).
5. **Accesibilidad Razonable (10 %):** Tiempo de conducción inferior a 45 minutos hasta al menos uno de los dos aeropuertos y presencia de al menos una parada GTFS en radio de 1.000 m.

Las celdas con PTNA superior a 70 sobre 100 representan los **microdestinos prioritarios para TUI**: zonas con condiciones objetivamente favorables para el ecoturismo, el turismo rural de calidad y el senderismo, pero con una cuota de mercado actual casi nula. Geográficamente, se concentran en las medianías agrícolas de la vertiente norte (Garachico, Icod de los Vinos, La Guancha, Buenavista del Norte) y en los valles del sureste (Arico, Fasnia), coincidiendo con el Cluster 2 de HDBSCAN y validando la coherencia interna entre los dos enfoques analíticos.

---

# 5. Procesamiento del Lenguaje Natural y Percepción de Marca Destino

## 5.1. Corpus Multilingüe de Reseñas y Preprocesamiento

Para capturar la experiencia cualitativa del visitante, el proyecto estructuró un corpus de **más de 55.000 opiniones textuales** procedentes de cuatro fuentes complementarias:

| Fuente | Volumen | Cobertura |
| :--- | :---: | :--- |
| Booking.com | 38.412 reseñas | Desglose positivo/negativo, nota y fecha |
| TripAdvisor | 12.840 opiniones | Hoteles, restaurantes y actividades georreferenciadas |
| LosViajeros (foros) | 2.650 mensajes | Rutas, tráfico y masificación (textos extensos) |
| YouTube Data API v3 | 1.890 comentarios | Vídeos de viajes y experiencias en Tenerife |

El pipeline de preprocesamiento aplicó detección de idioma (`langdetect`), eliminación de HTML y URLs, filtrado de stopwords y normalización de términos locales canarios (`"guagua"`, `"guachinche"`, `"barranco"`).

## 5.2. Inferencia de Sentimiento Multilingüe (XLM-RoBERTa)

Se empleó el transformador **`cardiffnlp/twitter-xlm-roberta-base-sentiment-multilingual`** (Barbieri et al., 2022), preentrenado en 30 idiomas. La inferencia por lotes de 64 documentos (máx. 256 tokens) produce una puntuación continua de polaridad en [-1, +1]:

`Score = (+1 · P_positivo) + (0 · P_neutro) + (-1 · P_negativo)`

Contrastado frente a 1.000 opiniones anotadas manualmente, el modelo alcanzó un **F1-score macro de 0,874** y una **exactitud global del 88,2 %**, superando ampliamente a clasificadores Naive Bayes y VADER (<72 %). El script completo `batch_inference.py` se detalla en el Anexo D.1.

Antes de clasificar el sentimiento, un filtro **zero-shot** basado en `mDeBERTa-v3-base-mnli-xnli` descarta los textos no relacionados con turismo o el impacto del turismo en Canarias (umbral de confianza > 0,25), reduciendo el ruido del corpus.

## 5.3. Modelado de Tópicos No Supervisado (BERTopic y pyabsa)

Para descubrir los temas latentes sin categorías preconcebidas, se articuló un pipeline con **BERTopic** (Grootendorst, 2022): embeddings semánticos de 768 dimensiones con `paraphrase-multilingual-mpnet-base-v2`, reducción UMAP a 5 dimensiones y clustering HDBSCAN con representación c-TF-IDF. Se implementaron dos modelos especializados:

* **Modelo A (Macro Insular):** Entrenado sobre YouTube y LosViajeros (3.245 documentos). Identifica debates generales: atascos en TF-1/TF-5 (polaridad -0,62), masificación en playas del sur (-0,48), senderismo en Teide y Anaga (+0,81) y gastronomía en guachinches (+0,86).
* **Modelo B (Micro Geolocalizado):** Entrenado en Google Colab con GPU sobre más de 50.000 reseñas de Booking y TripAdvisor vinculadas a celdas H3. Mapea qué temáticas emergen en cada zona: ruido nocturno y colas en piscinas en Adeje/Arona vs. sosiego, paisaje y vistas al mar en medianías del norte.

En paralelo, **PyABSA** (Yang y Li, 2023) realiza minería de aspectos (ATE) y clasificación de polaridad por aspecto (APC). Mediante la tabla `gold.aspecto_traducciones`, más de 1.200 variantes lingüísticas se normalizan en seis dimensiones: *Limpieza*, *Servicio*, *Relación Calidad-Precio*, *Ubicación*, *Confort y Ruido*, y *Saturación e Instalaciones*.

## 5.4. Integración del Sentimiento en la Malla H3

El modelo dbt `gold_sentimiento_h3.sql` computa por hexágono el `sentimiento_medio`, el volumen muestral por fuente y la **queja dominante** mediante `MODE() WITHIN GROUP (ORDER BY aspecto_normalizado)`. Los hallazgos estratégicos son:

* **Zona Sur (Adeje/Arona):** Nota global de Booking alta (8,2/10), pero queja principal `"ruido nocturno"` y `"masificación en piscina"`, con sentimiento medio penalizado (+0,48).
* **Medianías y Norte:** Sentimiento neto sensiblemente superior (+0,74); queja residual limitada a `"acceso por curvas"`. El ecoturismo de interior genera mayor fidelización y satisfacción neta en el cliente internacional.

*(La consulta SQL completa de `gold_sentimiento_h3.sql` se incluye en el Anexo C.3.)*

---

# 6. Inteligencia Artificial Generativa y Asistente RAG

## 6.1. Arquitectura RAG y Mitigación de Alucinaciones

Para salvar la brecha entre los datos numéricos de la plataforma y la toma de decisiones ejecutiva, se diseñó una arquitectura de **Generación Aumentada por Recuperación (RAG)**: el modelo de lenguaje no usa su conocimiento preentrenado, sino que recibe como contexto inyectado un resumen estructurado de las métricas de las celdas H3 consultadas.

La mitigación de alucinaciones se basa en tres principios:

1. **Conocimiento factual estrictamente acotado:** El LLM solo puede usar los datos numéricos que se le proporcionan explícitamente en el prompt.
2. **Guardrails de sistema:** El modelo actúa bajo el rol de *Analista Senior de Turismo Sostenible de TUI* con instrucción explícita de no inventar cifras.
3. **Trazabilidad:** Cada informe generado se persiste en `gold.nlp_informe_global`, registrando modelo, fecha, ámbito espacial y parámetros usados.

## 6.2. Motor de Inferencia de Alta Velocidad (Groq API)

Se descartó mantener GPUs dedicadas en Azure (coste > 900 USD/mes para uso esporádico) en favor de la **API de Groq LPU**, que ofrece más de 250 tokens/segundo con tarificación por consumo. El modelo seleccionado es **`openai/gpt-oss-120b`** (con fallback en `llama-3.3-70b-versatile`), operando con temperatura T = 0,4 para maximizar la consistencia lógica *(código del cliente `llm_client.py` en Anexo D.2)*.

## 6.3. Casos de Uso: Informes Macro y Fichas Micro

El sistema ofrece dos modalidades de generación narrativa:

* **Informe Macro Insular:** Sintetiza los tópicos del Modelo A de BERTopic en tres bloques ejecutivos: percepción general de la marca Tenerife, fricciones y puntos críticos (atascos, masificación, dificultad de acceso a Anaga y Masca) y oportunidades de mejora para TUI (reconfiguración de excursiones, promoción de medianías, desestacionalización).
* **Ficha Micro Territorial por Celda H3:** Activada al seleccionar una celda en el mapa, recupera en tiempo real su altitud, microclima ajustado, paradas de transporte, plazas hoteleras, tiempo al aeropuerto, sentimiento medio y queja principal de PyABSA, generando una ficha ejecutiva de viabilidad de absorción de nuevos flujos turísticos en menos de tres segundos.

---

# 7. Productivización: AI-Dashboard Interactivo y Simulador de Decisiones

## 7.1. Arquitectura Frontend (Streamlit + PyDeck)

El cuadro de mando se desarrolló con **Streamlit** y **Deck.gl / PyDeck** como motor de renderizado cartográfico acelerado mediante WebGL. Se eligió esta combinación frente a Power BI o Tableau por tres motivos: renderiza de forma nativa los 2.579 polígonos hexagonales 3D extruidos sin colapsar la interfaz; se integra sin fisuras con el resto del ecosistema Python (clustering, LLM, simulador gravitatorio); y se despliega en contenedores Docker sobre la VM de Azure sin costes de licencia por usuario.

## 7.2. Módulos Operativos del Dashboard

El cuadro de mando se organiza en cuatro módulos:

**Módulo 1 — Explorador Territorial H3:** Permite superponer cuatro capas temáticas sobre las 2.579 celdas insulares: capa biofísica (NDVI, NDBI, VIIRS), capa microclimática (temperatura, humedad modelada con Mar de Nubes, horas de sol), capa de accesibilidad multimodal (isócronas ORS, densidad GTFS en 200/500/1.000 m, distancia a hospitales) y capa de arquetipos HDBSCAN + índice PTNA.

**Módulo 2 — Monitor de Reputación y NLP:** Mapa de calor por *Net Sentiment Score*; selector de quejas por las seis dimensiones de calidad (Limpieza, Servicio, Precio/Calidad, Ubicación, Ruido, Masificación); y botón de generación de informe RAG con Groq sobre el área visible en pantalla.

**Módulo 3 — Simulador Gravitatorio de Redistribución:** Basado en los modelos de interacción espacial de Reilly (1931) y Huff (1963), permite al planificador definir el porcentaje de reasignación desde los municipios saturados del sur (Adeje, Arona) hacia comarcas deficitarias (Arico, Vilaflor, La Guancha, Buenavista). El algoritmo calcula la probabilidad de atracción de cada hexágono receptor en función de su PTNA, accesibilidad vial y distancia funcional, y proyecta al instante: reducción del tráfico diario en la TF-1, incremento de ingresos en medianías y verificación de la capacidad de absorción. El simulador bloquea automáticamente la reasignación hacia celdas del Cluster 3 (ENP) o con pendiente >25°, garantizando la sostenibilidad física de la simulación. Redirigir un 10 % de las pernoctaciones del sur reduce la congestión costera en ~14 % e inyecta más de 42 millones de euros anuales en la economía local de medianías.

**Módulo 4 — Sistema de Alertas Preventivas:** Evalúa reglas de negocio sobre umbrales críticos: *Alerta Roja de Saturación* (plazas/km² > percentil 95 con transporte deficiente); *Alerta Climática de Calima* (temperatura >32 °C y humedad <25 %); y *Alerta de Fricción Reputacional* (sentimiento medio < -0,25 o queja dominante `"ruido nocturno"` / `"masificación"`).

---

# 8. Validación Técnica, ROI y Conclusiones

## 8.1. Validación Empírica de los Resultados

Los resultados se sometieron a triple contraste frente a fuentes oficiales independientes:

1. **Validación Altimétrica:** Cruce de las cotas H3 frente a 67 vértices geodésicos de la Red REGENTE del IGN: **RMSE de 4,12 m**, confirmando la fiabilidad de la topografía base.
2. **Validación del Modelo Topoclimático:** Contraste con 12 estaciones AEMET no usadas en el ajuste. El modelo físico redujo el RMSE de temperatura de 2,84 °C a **0,91 °C** y el de humedad de 18,6 % a **6,2 %**.
3. **Validación del Parque Alojativo:** Las 46.820 unidades identificadas en la capa Silver presentan una desviación inferior al 1,5 % respecto a las memorias anuales del ISTAC y el Registro General Turístico del Gobierno de Canarias.

## 8.2. Respuesta Estratégica a las Preguntas de TUI Group

| Pregunta Briefing TUI | Hallazgo Clave del Proyecto |
| :--- | :--- |
| **P1. ¿Cómo medir la saturación sub-municipal?** | Malla H3 Res 8 (2.579 celdas): densidad de plazas/km², VIIRS nocturna >65 nW en polos y cobertura GTFS en 3 umbrales. |
| **P2. ¿Qué comarcas pueden absorber demanda?** | Cluster 2 HDBSCAN (31,5 % de celdas): medianías con NDVI >0,60, clima templado (18–22 °C) y NSS +0,74. |
| **P3. ¿Cómo influye la accesibilidad?** | El índice PTNA prioriza celdas a <45 min de un aeropuerto y con >2 paradas GTFS en radio de 500 m. |
| **P4. ¿Qué quejas hay en el sur vs. interior?** | Sur: `"ruido nocturno"` y `"masificación"` (NSS +0,48). Interior: queja residual `"acceso por curvas"` (NSS +0,74). |
| **P5. Impacto de redistribuir un 10–20 %** | Redirigir el 10 % alivia ~8.500 trayectos/día en la TF-1 e inyecta >42 M€/año en la economía local de medianías. |

El ROI para TUI se materializa en tres vectores: (1) reducción de 4 semanas a segundos del tiempo de diagnóstico de viabilidad territorial; (2) anticipación de moratorias turísticas y zonas de alta tensión residencial; y (3) identificación de microdestinos premium (enoturismo, astroturismo, senderismo botánico) con márgenes entre un 18 % y un 25 % superiores a los paquetes de sol y playa.

## 8.3. Limitaciones y Líneas de Investigación Futuras

El equipo reconoce tres limitaciones con sus correspondientes vías de mejora:

1. **Frecuencia temporal de la teledetección:** Los compuestos Sentinel-2 son trimestrales por la nubosidad y la calima. La incorporación de Sentinel-1 SAR permitiría monitorizar la humedad del suelo con independencia del estado del cielo.
2. **Flujos de movilidad interna:** La topología ORS y la oferta TITSA aproximan la movilidad; matrices de telefonía móvil aportarían distribución dinámica intra-diaria de turistas en tránsito.
3. **Escalabilidad regional:** La arquitectura Azure + dbt + Docker puede replicarse de forma inmediata en otras islas canarias (Gran Canaria, La Palma, Lanzarote) o en destinos insulares mediterráneos y caribeños gestionados por TUI Group.

---

# Referencias Bibliográficas

1. Anselin, L. (1988). *Spatial Econometrics: Methods and Models*. Kluwer Academic Publishers. https://doi.org/10.1007/978-94-015-7799-1
2. Armbrust, M., Ghodsi, A., Xin, R., y Zaharia, M. (2021). Lakehouse: A new generation of open platforms that unify data warehousing and advanced analytics. *Proceedings of CIDR 2021*, 1–8.
3. Armas-Pérez, F., y Dorta-Antequera, P. (2018). El clima de las Islas Canarias: Dinámica atmosférica y singularidades microclimáticas. *Revista de Climatología*, 18, 45–62.
4. Barbieri, F., Camacho-Collados, J., Espinosa-Anke, L., y Neves, L. (2022). TweetEval: Unified benchmark and comparative evaluation for tweet classification. *Findings of EMNLP 2020*, 1644–1650. https://doi.org/10.18653/v1/2020.findings-emnlp.148
5. Booking.com. (2025). *Plataforma de reservas y reseñas de alojamiento turístico*. Booking Holdings Inc. https://www.booking.com
6. Cabildo de Tenerife. (2024). *Red agrometeorológica insular de Agrocabildo*. Cabildo Insular de Tenerife. https://www.agrocabildo.org
7. Campello, R. J. G. B., Moulavi, D., y Sander, J. (2013). Density-based clustering based on hierarchical density estimates. *PAKDD 2013*, LNCS 7819, 160–172. https://doi.org/10.1007/978-3-642-37456-2_14
8. Copernicus Climate Change Service (C3S). (2024). *Sentinel-2 MSI Level-2A Surface Reflectance Product Guide*. European Space Agency.
9. dbt Labs. (2024). *dbt Core Documentation* (Version 1.8). https://docs.getdbt.com
10. Dorta, P. (2007). Las inversiones térmicas en Canarias y su repercusión en la vegetación y el clima insular. *Investigaciones Geográficas*, 43, 89–108.
11. Elvidge, C. D., Baugh, K., Zhizhin, M., Hsu, F. C., y Ghosh, T. (2017). VIIRS night-time lights. *International Journal of Remote Sensing*, 38(21), 5860–5879. https://doi.org/10.1080/01431161.2017.1342050
12. Fotheringham, A. S., Yang, W., y Kang, W. (2017). Multiscale geographically weighted regression (MGWR). *Annals of the American Association of Geographers*, 107(6), 1247–1265. https://doi.org/10.1080/24694452.2017.1352480
13. General Transit Feed Specification (GTFS). (2024). *GTFS Schedule Reference*. MobilityData IO. https://gtfs.org/schedule/reference/
14. Gobierno de Canarias. (2024). *Anuario estadístico del turismo en Canarias*. Consejería de Turismo y Empleo. https://www.gobiernodecanarias.org/turismo/
15. Google Developers. (2024). *YouTube Data API v3 Reference Guide*. Google LLC. https://developers.google.com/youtube/v3
16. Grootendorst, M. (2022). BERTopic: Neural topic modeling with a class-based TF-IDF procedure. *arXiv preprint arXiv:2203.05794*. https://doi.org/10.48550/arXiv.2203.05794
17. HeiGIT. (2024). *OpenRouteService API* (Version 7.0). Heidelberg Institute for Geoinformation Technology. https://openrouteservice.org
18. Horn, B. K. P. (1981). Hill shading and the reflectance map. *Proceedings of the IEEE*, 69(1), 14–47. https://doi.org/10.1109/PROC.1981.11918
19. Huff, D. L. (1963). A probabilistic analysis of shopping center trade areas. *Land Economics*, 39(1), 81–90. https://doi.org/10.2307/3144521
20. IDECanarias. (2024). *Infraestructura de Datos Espaciales de Canarias: servicios WFS y MDT*. Gobierno de Canarias. https://www.idecanarias.es
21. Instituto Canario de Estadística (ISTAC). (2024). *Municipios en Cifras (C00067A): Indicadores municipales 2018–2024*. Gobierno de Canarias. https://www.gobiernodecanarias.org/istac/
22. Instituto Canario de Estadística (ISTAC). (2025). *Encuesta de Gasto Turístico y FRONTUR-Canarias: Resultados anuales 2024*. Gobierno de Canarias.
23. Instituto Geográfico Nacional (IGN). (2024). *Modelo Digital del Terreno MDT05*. Centro Nacional de Información Geográfica (CNIG).
24. Lewis, P., Perez, E., Piktus, A., et al. (2020). Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks. *NeurIPS 2020*, 33, 9459–9474.
25. LosViajeros.com. (2025). *Foro de viajeros: comunidad online de turismo en español*. https://www.losviajeros.com
26. McInnes, L., Healy, J., y Astels, S. (2017). hdbscan: Hierarchical density based clustering. *Journal of Open Source Software*, 2(11), 205. https://doi.org/10.21105/joss.00205
27. McInnes, L., Healy, J., y Melville, J. (2018). UMAP: Uniform Manifold Approximation and Projection. *arXiv:1802.03426*.
28. Microsoft. (2024). *Azure Database for PostgreSQL – Flexible Server documentation*. Microsoft Corporation. https://learn.microsoft.com/azure/postgresql/flexible-server/
29. Milano, C., Novelli, M., y Cheer, J. M. (2019). Overtourism and degrowth: A social movements perspective. *Journal of Sustainable Tourism*, 27(12), 1857–1875. https://doi.org/10.1080/09669582.2019.1650054
30. Muñoz-Sabater, J., et al. (2021). ERA5-Land: A state-of-the-art global reanalysis dataset for land applications. *Earth System Science Data*, 13(9), 4349–4383. https://doi.org/10.5194/essd-13-4349-2021
31. OpenStreetMap contributors. (2024). *OpenStreetMap: Mapa colaborativo de puntos de interés*. https://www.openstreetmap.org
32. Openshaw, S. (1984). *The Modifiable Areal Unit Problem*. CATMOG 38. Geo Books.
33. PostGIS Project. (2024). *PostGIS: Spatial and Geographic Objects for PostgreSQL* (Version 3.4). https://postgis.net
34. Reimers, N., y Gurevych, I. (2019). Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks. *EMNLP-IJCNLP 2019*, 3982–3992.
35. Reilly, W. J. (1931). *The law of retail gravitation*. W. J. Reilly Inc.
36. Richardson, L. (2024). *Beautiful Soup Documentation* (Version 4.12). https://www.crummy.com/software/BeautifulSoup/
37. Rouse, J. W., et al. (1974). Monitoring the vernal advancement of natural vegetation. *NASA/GSFC Type III Final Report*, Greenbelt, MD.
38. Shepard, D. (1968). A two-dimensional interpolation function for irregularly-spaced data. *ACM National Conference 1968*, 517–524. https://doi.org/10.1145/800186.810616
39. Streamlit Inc. (2024). *Streamlit: An open-source app framework for ML and Data Science*. https://docs.streamlit.io/
40. The PostgreSQL Global Development Group. (2024). *PostgreSQL 16 Documentation*. https://www.postgresql.org/docs/16/
41. Tobler, W. R. (1970). A computer movie simulating urban growth in the Detroit region. *Economic Geography*, 46(sup1), 234–240.
42. Tripadvisor. (2025). *Plataforma de reseñas turísticas*. Tripadvisor LLC. https://www.tripadvisor.com
43. TUI Group. (2024). *TUI Sustainability Agenda 2030: People, Planet, and Progress in Tourism Destinations*. TUI AG.
44. Turismo de Canarias. (2025). *Estrategia de turismo regenerativo RegNext 2025–2030*. Promotur Turismo Canarias. https://www.turismodeislascanarias.com
45. Turismo de Tenerife. (2025). *Informe de coyuntura turística insular: Año 2024*. Cabildo Insular de Tenerife. https://www.webtenerife.com
46. Uber Technologies. (2024). *H3: Hexagonal Hierarchical Spatial Index* (Version 4.1). https://h3geo.org
47. United Nations World Tourism Organization (UNWTO). (2023). *Measuring the Sustainability of Tourism (MST)*. UNWTO Publishing. https://doi.org/10.18111/9789284424368
48. Vaswani, A., et al. (2017). Attention is All You Need. *NeurIPS 2017*, 30, 5998–6008.
49. Yang, H., y Li, K. (2023). PyABSA: A modularized framework for reproducible aspect-based sentiment analysis. *ACL 2023: System Demonstrations*, 400–412.
50. YouTube. (2025). *Plataforma de contenido en vídeo*. Google LLC. https://www.youtube.com
51. Zippenfenig, P. (2023). *Open-Meteo: Free weather API and historical reanalysis data*. https://open-meteo.com

---

# Anexos Técnicos

> **Nota:** Los anexos recogen los detalles técnicos, configuraciones, catálogos, scripts y el manual de despliegue. Según la guía de la UCM, no computan dentro del límite de páginas del cuerpo principal.

---

## Anexo A: Repositorio de Código y Estructura del Proyecto

El código fuente completo está versionado en el repositorio privado de GitHub:
**https://github.com/TFM-Pytones/AI_Dashboard_Core**

Los tutores Carlos Ortega y Santiago Mota tienen acceso de lectura para la evaluación.

```
AI_Dashboard_Core/
├── .env.example                       # Plantilla de credenciales
├── requirements.txt                   # Dependencias Python fijas
├── README.md                          # Guía de configuración y arquitectura
├── run_dbt.py                         # Wrapper de ejecución dbt Core
│
├── ingestion/                         # Pipelines de adquisición de datos
│   ├── aena/                          # Tráfico aéreo (TFS / TFN)
│   ├── alojamientos_oficiales/        # Registro General Turístico
│   ├── booking/                       # Scraping ético de Booking.com
│   ├── clima/                         # Red Agrocabildo (67 estaciones)
│   ├── espacial/                      # Cartografía WFS / IDECanarias
│   ├── gtfs/                          # Red TITSA y Tranvía de Tenerife
│   ├── istac/                         # Microdatos estadísticos ISTAC
│   ├── los_viajeros/                  # Foros de viajeros comunitarios
│   ├── postgres/                      # Utilidades de carga y Azure
│   ├── satelite/                      # Sentinel-2 L2A y VIIRS DNB
│   ├── tripadvisor/                   # Reseñas de TripAdvisor
│   └── youtube/                       # Comentarios YouTube Data API v3
│
├── dbt_project/                       # Proyecto dbt Core 1.8
│   └── models/
│       ├── sources.yml                # Declaración de fuentes Bronze
│       ├── silver/                    # Limpieza, deduplicación y tipado
│       └── gold/                      # Modelos analíticos multidimensionales
│           ├── gold_h3_master.sql
│           ├── gold_sentimiento_h3.sql
│           └── gold_municipio_master.sql
│
├── analytics/                         # Analítica avanzada, ML y NLP
│   ├── accesibilidad/                 # ORS matrix (18 destinos) e isócronas
│   ├── clustering/                    # Features H3 y modelo HDBSCAN
│   ├── llm/                           # Asistente RAG con Groq API
│   ├── sentiment/                     # Inferencia XLM-RoBERTa por lotes
│   └── topics/                        # BERTopic (Modelos A y B)
│
└── docs/                              # Documentación técnica y memoria oficial
```

---

## Anexo B: Variables de Entorno (.env.example)

```bash
# AZURE POSTGRESQL FLEXIBLE SERVER
AZURE_DB_HOST=tfm-tenerife-db.postgres.database.azure.com
AZURE_DB_PORT=5432
AZURE_DB_NAME=postgres
AZURE_DB_USER=psqladmin
AZURE_DB_PASSWORD=********************

# AZURE BLOB STORAGE (DATA LAKE GEN2)
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=tfmtenerifestorage;...
AZURE_CONTAINER_RAW=bronze-raw
AZURE_CONTAINER_PROCESSED=silver-processed
AZURE_CONTAINER_ANALYTICS=gold-analytics

# APIs EXTERNAS
ORS_API_KEY=************************************************
GROQ_API_KEY=************************************************
YOUTUBE_API_KEY=********************************************
```

---

## Anexo C: Modelos SQL y dbt

### C.1. Geocodificación y Centroides en PostGIS

```sql
-- Extracción canónica de centroides H3
SELECT
    h3_index,
    ST_X(ST_Centroid(geometry)) AS centroide_lon,
    ST_Y(ST_Centroid(geometry)) AS centroide_lat,
    geometry
FROM silver.silver_h3_grid;

-- Integración con tabla de lookup centralizada en Azure
SELECT
    a.registro_id, a.nombre, a.modalidad,
    COALESCE(a.latitud, l.latitud_geocoded) AS latitud,
    COALESCE(a.longitud, l.longitud_geocoded) AS longitud,
    ST_SetSRID(ST_MakePoint(
        COALESCE(a.longitud, l.longitud_geocoded),
        COALESCE(a.latitud, l.latitud_geocoded)
    ), 4326) AS geom
FROM bronze.bronze_registro_turistico a
LEFT JOIN bronze.bronze_registro_geocoding_lookup l
    ON l.establecimiento_id = a.registro_id;
```

### C.2. Modelo Topoclimático en gold_h3_master.sql

**Fórmulas base:**
- Temperatura ajustada: `T_ajustada = T_IDW - 0,0065 * (elevacion_H3 - elevacion_estacion)`
- IDW k=3: `Z_estimado = SUM(w_i * Z_i) / SUM(w_i)`, con `w_i = 1 / d_i³`

```sql
WITH idw_base AS (
    SELECT
        h.h3_index, h.elevation_mean, h.slope_mean,
        h.aspect_mean, h.dist_costa_km,
        SUM(c.temperatura / POWER(c.distancia_m, 3)) /
            SUM(1.0 / POWER(c.distancia_m, 3)) AS temp_idw,
        SUM(c.humedad_relativa / POWER(c.distancia_m, 3)) /
            SUM(1.0 / POWER(c.distancia_m, 3)) AS humedad_idw,
        AVG(c.altitud) AS elevacion_estacion_ref
    FROM silver.silver_h3_grid h
    CROSS JOIN LATERAL (
        SELECT e.temperatura, e.humedad_relativa, e.altitud,
               ST_Distance(ST_Transform(h.geom,32628),
                           ST_Transform(e.geom,32628)) AS distancia_m
        FROM silver.silver_clima_estaciones e
        ORDER BY distancia_m ASC LIMIT 3
    ) c
    GROUP BY h.h3_index, h.elevation_mean, h.slope_mean,
             h.aspect_mean, h.dist_costa_km
)
SELECT
    h3_index,
    ROUND((temp_idw - 0.0065*(elevation_mean-elevacion_estacion_ref))::numeric, 2)
        AS temperatura_ajustada,
    CASE
        WHEN (aspect_mean >= 300 OR aspect_mean <= 90) THEN
            CASE
                WHEN elevation_mean BETWEEN 800 AND 1500 THEN
                    LEAST(100.0, humedad_idw*1.25 +
                        CASE WHEN dist_costa_km < 1.5 THEN 15.0 ELSE 0.0 END)
                WHEN elevation_mean > 1500 THEN
                    GREATEST(10.0, humedad_idw*0.70)
                ELSE
                    LEAST(100.0, humedad_idw*1.05 +
                        CASE WHEN dist_costa_km < 1.5 THEN 15.0 ELSE 0.0 END)
            END
        ELSE
            GREATEST(10.0, LEAST(100.0, humedad_idw*0.85 +
                CASE WHEN dist_costa_km < 1.5 THEN 15.0 ELSE 0.0 END))
    END AS humedad_relativa_ajustada
FROM idw_base;
```

### C.3. Agregación de Sentimiento y Queja Principal (gold_sentimiento_h3.sql)

```sql
SELECT
    s.h3_index,
    ROUND(AVG(s.score)::numeric, 2) AS sentimiento_medio,
    COUNT(DISTINCT s.resena_id) AS n_resenas,
    COUNT(DISTINCT s.resena_id) FILTER (WHERE s.fuente = 'booking')
        AS n_resenas_booking,
    COUNT(DISTINCT s.resena_id) FILTER (WHERE s.fuente = 'tripadvisor')
        AS n_resenas_tripadvisor,
    MODE() WITHIN GROUP (ORDER BY COALESCE(t.aspecto_traducido, a.aspecto))
        AS queja_principal
FROM gold.nlp_sentimiento_resenas s
LEFT JOIN gold.nlp_aspectos_resenas a ON a.resena_id = s.resena_id
LEFT JOIN gold.aspecto_traducciones t ON t.aspecto_original = a.aspecto
WHERE s.h3_index IS NOT NULL
GROUP BY s.h3_index;
```

---

## Anexo D: Scripts de Analítica Avanzada, ML y NLP

### D.1. Inferencia de Sentimiento por Lotes con XLM-RoBERTa

```python
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

MODEL_NAME = "cardiffnlp/twitter-xlm-roberta-base-sentiment-multilingual"
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME)

def predict_sentiment_batch(texts: list[str], batch_size: int = 64,
                             device: str = "cuda" if torch.cuda.is_available() else "cpu"):
    model.to(device); model.eval()
    all_scores = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        inputs = tokenizer(batch, padding=True, truncation=True,
                           max_length=256, return_tensors="pt").to(device)
        with torch.no_grad():
            probs = torch.softmax(model(**inputs).logits, dim=-1).cpu().numpy()
        all_scores.extend((probs[:, 2] - probs[:, 0]).tolist())
    return all_scores
```

### D.2. Cliente RAG con Groq API (llm_client.py)

```python
import os
from dotenv import load_dotenv
from groq import Groq

load_dotenv(override=True)

class LLMClient:
    def __init__(self, model: str = "openai/gpt-oss-120b"):
        self.model = model
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))

    def complete(self, prompt: str, temperature: float = 0.4,
                 max_tokens: int = 1200) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature, max_tokens=max_tokens,
        )
        return response.choices[0].message.content
```

### D.3. Preparación de Features para HDBSCAN (build_features.py)

```python
import pandas as pd
from sklearn.preprocessing import RobustScaler

def build_clustering_matrix(df: pd.DataFrame, max_nan_ratio: float = 0.5):
    feature_cols = [
        "elevation_mean", "slope_mean", "aspect_mean", "hillshade_mean",
        "ndvi_mean", "ndbi_mean", "n_alojamientos",
        "n_paradas_transporte", "sentimiento_medio", "viirs_mean"
    ]
    valid_mask = df[feature_cols].isna().mean(axis=1) <= max_nan_ratio
    clean_df = df[valid_mask].copy()
    clean_df[feature_cols] = clean_df[feature_cols].fillna(
        clean_df[feature_cols].median()
    )
    return clean_df, RobustScaler().fit_transform(clean_df[feature_cols])
```

---

## Anexo E: Resultados del Análisis Exploratorio de Datos

* **Asimetría Espacial:** El 82,4 % de las camas hoteleras se ubica a menos de 150 m s.n.m. y a menos de 2 km de la costa, concentradas en Adeje, Arona y Puerto de la Cruz.
* **Densidad Hotelera:** El Cluster 0 de HDBSCAN supera las 1.850 plazas/km²; las medianías agrícolas del norte no alcanzan las 15 plazas/km².
* **Correlación Relieve-Vegetación:** Pearson r = +0,78 entre altitud y NDVI (0–1.200 m, barlovento); r = -0,84 por encima de 1.500 m (cumbre árida y desprovista de vegetación).

---

## Anexo F: Matrices de Evaluación de Modelos

* **Test I de Moran en Residuos:**
  * OLS: I = 0,472, z = 18,4, p < 0,001 (sesgo espacial severo).
  * MGWR: I = 0,041, z = 1,07, p = 0,284 (aleatoriedad confirmada).
* **Métricas XLM-RoBERTa:**
  * Positivo — Precisión: 0,892 | Recall: 0,911 | F1: 0,901
  * Neutro — Precisión: 0,741 | Recall: 0,684 | F1: 0,711
  * Negativo — Precisión: 0,865 | Recall: 0,883 | F1: 0,874
  * **Accuracy global: 88,2 % | Macro F1: 0,874**

---

## Anexo G: Manual de Despliegue

```bash
# 1. Clonar el repositorio y crear entorno virtual
git clone https://github.com/TFM-Pytones/AI_Dashboard_Core.git
cd AI_Dashboard_Core
python -m venv .venv
# Windows: .venv\Scriptsctivate | Linux/Mac: source .venv/bin/activate
pip install --upgrade pip && pip install -r requirements.txt

# 2. Configurar credenciales
cp .env.example .env   # Rellenar PostgreSQL, ORS, Groq y YouTube API keys

# 3. Ejecutar ingesta completa
python ingestion/postgres/run_all_ingestion.py  # Módulos 01 al 07 en orden

# 4. Ejecutar transformaciones dbt
python run_dbt.py --deps
python run_dbt.py --run   # Silver + Gold
python run_dbt.py --test  # Validaciones de integridad

# 5. Inferencia NLP y clustering
python analytics/sentiment/batch_inference.py
python analytics/topics/topic_modeling.py
python analytics/clustering/build_features.py
python analytics/accesibilidad/gold_h3_accesibilidad.py

# 6. Generar informes RAG
python analytics/llm/report_generator.py

# 7. Lanzar el dashboard interactivo
streamlit run app.py --server.port 8501 --server.address 0.0.0.0
```