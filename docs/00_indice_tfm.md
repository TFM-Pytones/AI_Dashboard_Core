# Índice General del Proyecto — Trabajo de Fin de Máster (TFM)

**Título:** AI-Dashboard para la Gestión y Sostenibilidad de la Oferta Turística Georreferenciada e Integración con Datos Abiertos de la Isla de Tenerife  
**Caso de Aplicación de Negocio:** Consultoría Estratégica de Redistribución de Flujos Turísticos y Nuevas Oportunidades (Caso TUI)

---

## 1. Introducción y Contexto de Negocio
- 1.1. Resumen Ejecutivo y Alcance del Proyecto
- 1.2. El Paradigma Turístico en Tenerife: Tensión entre saturación de la franja costera sur e interior rural infrautilizado
- 1.3. Objetivos Generales y Específicos de la Plataforma
- 1.4. Preguntas Estratégicas de Negocio (Aplicación al caso TUI: redistribución, capacidad de carga y diversificación de producto)
- 1.5. Propuesta de Valor y Aporte Diferencial frente a Cuadros de Mando Tradicionales y Herramientas AutoML

---

## 2. Configuración de Infraestructura Cloud y Adquisición de Datos (Capa Bronze / Raw)
- 2.1. Aprovisionamiento de Infraestructura Cloud en Microsoft Azure:
  - Almacén de objetos desacoplado: Azure Blob Storage (contenedor `bronce-raw`)
  - Servidor de base de datos relacional y espacial: Azure Database for PostgreSQL (Flexible Server con extensión PostGIS)
  - Cómputo orquestador en máquina virtual Linux Ubuntu (`mv-orquestador-tfm`)
- 2.2. Ingesta de Registros Oficiales y Microdatos Estadísticos:
  - Censo oficial de alojamientos turísticos reglados del Gobierno de Canarias (Hoteles, Extrahoteleros y Vivienda Vacacional bajo el Decreto 113/2015)
  - Microdatos demográficos, mercado laboral por sectores CNAE y Encuesta de Ocupación Hotelera (API REST del ISTAC, sistemas C00067A y C00065A_000061)
  - Tráfico aeroportuario mensual de pasajeros comerciales, vuelos y carga (Estadísticas oficiales de AENA para TFS y TFN)
- 2.3. Topología de Red de Movilidad y Capas Espaciales Base:
  - Ficheros GTFS del transporte público regular insular (Guaguas de TITSA y Tranvía de Metropolitano de Tenerife)
  - Capas geográficas institucionales (Límites de los 31 municipios, Espacios Naturales Protegidos [ENP], Zonas Turísticas Oficiales, Bienes de Interés Cultural [BIC] y Oficinas de Turismo)
  - Puntos de interés (POIs) turísticos y servicios complementarios de OpenStreetMap (Overpass API)
- 2.4. Teledetección Satelital y Red Meteorológica Oficial:
  - Consumo de la red de 67 estaciones automáticas de Agrocabildo (API REST v2.0.0 con control de flujo a 10 req/min y particionamiento Hive `año=YYYY/mes=MM/`)
  - Extracción y procesamiento en Google Earth Engine (GEE) de composites trimestrales Sentinel-2 L2A (NDVI y NDBI con triple filtrado SCL, calima AOT < 0.3 y banda azul B02)
  - Calibración de radianza económica mensual mediante luces nocturnas NOAA/NASA VIIRS (VNP46A2) con tratamiento específico del período pandémico COVID-19 (2020-2021)
- 2.5. Captura Ética de Datos Cualitativos y Reputación de Destino:
  - Web scraping ético y distribuido sobre Booking.com (descubrimiento por sitemaps XML, exclusión estricta de PII y persistencia por lotes)
  - Extracción vía API de TripAdvisor (Terra API con validación geoespacial perimetral PostGIS para evitar homónimos)
  - Minería de foros de viajeros (LosViajeros.com: 248 hilos temáticos y 167.000 mensajes) y contenidos audiovisuales de YouTube Data API v3

---

## 3. Ingeniería de Datos, Data Lakehouse y Topología Geoespacial (Capa Silver)
- 3.1. Arquitectura Medallón en Azure Database for PostgreSQL (PostGIS)
- 3.2. La Malla Hexagonal Uber H3 (Resolución 8) como Soporte Territorial Canónico:
  - Adopción de teselado hexagonal regular frente a divisiones administrativas tradicionales para mitigar el Problema de la Unidad de Área Modificable (MAUP)
  - Buffer perimetral de amortiguación costera de 0.01° (~1,1 km) y transición metodológica de 2.746 celdas Bronze a 2.579 celdas terrestres limpias en Silver/Gold
  - Centroides canónicos puramente geométricos (`ST_Centroid`) para evitar sesgos de atracción por densidad de POIs
  - Estándar de Sistemas de Coordenadas: Almacenamiento e indexación en `EPSG:4326` y proyección métrica al vuelo en `EPSG:32628` (UTM 28N)
- 3.3. Transformaciones Analíticas y Control de Calidad con dbt:
  - Desnormalización y consolidación de la red GTFS (reducción de 7 tablas operativas a modelos espaciales analíticos de paradas y trazados viarios)
  - Estandarización de series temporales del ISTAC, tratamiento de secreto estadístico y tipado numérico
  - Deduplicación idempotente de establecimientos y opiniones
- 3.4. Geocodificación y Limpieza Centralizada en Base de Datos:
  - Normalización toponímica canaria (inversión de artículos gramaticales y expansión de abreviaturas del callejero)
  - Persistencia de coordenadas en tablas relacionales de consulta (`bronze_registro_geocoding_lookup` y `bronze_booking_geocoding_lookup`)

---

## 4. Inteligencia Territorial, Modelado Microclimático y Machine Learning (Capa Gold)
- 4.1. Análisis Topográfico y Geomorfométrico de Alta Resolución:
  - Procesamiento del Modelo Digital del Terreno (MDT25 de GRAFCAN)
  - Derivación matemática de Pendiente (Método de Horn, 1981), Orientación (*Aspect*) y Sombreado (*Hillshade*) con estadísticas zonales por celda H3
- 4.2. Monitorización Ambiental, Vigor Vegetal y Huella Antrópica:
  - Dinámica trimestral de cobertura vegetal (NDVI), presión de suelo sellado/construido (NDBI) y actividad nocturna (VIIRS)
- 4.3. Climatología Analítica y Modelado Topoclimático Microinsular:
  - Interpolación espacial ponderada por distancia inversa (IDW K=3) sobre las 67 estaciones automáticas
  - Calibración altimétrica de temperatura mediante gradiente térmico vertical (-0,0065 °C/m) y termorregulación marina litoral (`delta_dist_costa`)
  - Modelado topoclimático de humedad y precipitación bajo el régimen de Alisios:
    - Estrato de condensación e inversión térmica ("Mar de Nubes" / "Panza de burro" entre 800 m y 1.500 m: +25% de humedad)
    - Cumbre árida subsidente por encima de la inversión térmica (> 1.500 m: -30% de humedad)
    - Efecto Föhn y sombra de lluvia en la vertiente sur de sotavento (-15% humedad, -60% lluvia)
    - Amortiguación por brisa marina litoral (franja costera < 1,5 km: +15% humedad)
  - Viento orográfico e indicadores climáticos ESG: horas de sol diarias reales bajo estándar OMM ($\ge 120\text{ W/m}^2$), amplitud térmica diaria y detección de eventos extremos de ola de calor y calima sahariana
- 4.4. Modelado de Accesibilidad Multimodal y Fricción Espacial (`gold_h3_accesibilidad`):
  - Matrices viales de tiempo de conducción continuo con OpenRouteService hacia 18 polos turísticos estratégicos (aeropuertos, Teide, núcleos costeros)
  - Generación de isócronas visuales de alcance temporal (15, 30, 45 y 60 minutos)
  - Accesibilidad peatonal a la red de transporte público GTFS bajo 3 umbrales escalonados (paradas a $\le 200\text{ m}$, $\le 500\text{ m}$ y $\le 1000\text{ m}$) y distancia continua (`dist_parada_cercana_m`)
  - Proximidad a infraestructuras críticas de seguridad sanitaria (`dist_hospital_km`)
- 4.5. Detección de Aglomeraciones y Oportunidades Territoriales:
  - Segmentación no supervisada de tipologías territoriales mediante Clustering Espacial Basado en Densidad con Ruido (HDBSCAN)
  - Evaluación de factores explicativos de localización turística mediante Regresión Geográficamente Ponderada Multiescalar (MGWR)

---

## 5. Procesamiento del Lenguaje Natural (NLP) y Percepción de Marca Destino
- 5.1. Inferencia de Sentimiento Multilingüe por Lotes:
  - Implementación del modelo transformador `cardiffnlp/twitter-xlm-roberta-base-sentiment` sobre opiniones de Booking, TripAdvisor, YouTube y LosViajeros
  - Puntuación continua de polaridad y métricas de confianza estadística
- 5.2. Modelado de Tópicos No Supervisado con BERTopic:
  - Modelo A (Percepción Macro Insular): Detección de macro-temáticas en comentarios de redes y foros (masificación, precios, transporte, paisaje)
  - Modelo B (Tópicos Micro Geolocalizados): Extracción de tópicos asociados a establecimientos y núcleos urbanos específicos
- 5.3. Minería de Aspectos Específicos (PyABSA):
  - Desglose de polaridad por dimensiones de experiencia: relación calidad/precio, limpieza, atención del personal, confort térmico y ubicación

---

## 6. Inteligencia Artificial Generativa y Asistente RAG
- 6.1. Arquitectura de Generación Aumentada por Recuperación (RAG) sobre opiniones y datos territoriales
- 6.2. Motor de Inferencia de Alta Velocidad (Groq API con modelos fundacionales Llama-3 / GPT-OSS)
- 6.3. Generación Automatizada de Informes Ejecutivos:
  - Informe macro insular para dirección estratégica de producto (rol analista senior de TUI)
  - Diagnóstico micro territorial de oferta, clima y reputación al seleccionar celdas H3 en el mapa interactivo

---

## 7. Productivización: AI Dashboard Interactivo y Simulación de Decisiones
- 7.1. Arquitectura Frontend de la Plataforma (Streamlit con renderizado acelerado Deck.gl / PyDeck)
- 7.2. Módulos Interactivos de Explotación:
  - Explorador territorial H3 con capas conmutables: Biofísica (NDVI/NDBI/VIIRS), Microclima, Accesibilidad y Saturación Turística
  - Monitor interactivo de Sentimiento y Tópicos NLP
  - Simulador de redistribución de flujos y capacidad de carga territorial hacia el interior insular
  - Sistema de alertas automatizadas basadas en umbrales de saturación y eventos climáticos adversos

---

## 8. Pruebas, Validación y Conclusiones
- 8.1. Validación Empírica de los Resultados en Tenerife y Contraste con Datos Reales
- 8.2. Impacto Estratégico y Retorno de Inversión (ROI) para la Toma de Decisiones en TUI
- 8.3. Limitaciones Técnicas del Proyecto, Consideraciones Éticas y Vías Futuras de Investigación
