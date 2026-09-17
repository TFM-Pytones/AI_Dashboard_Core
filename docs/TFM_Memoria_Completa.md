
UNIVERSIDAD COMPLUTENSE DE MADRID
Máster en Data Science, Big Data & Business Analytics
TRABAJO DE FIN DE MÁSTER







AI-Dashboard para la gestión de la oferta turística georreferenciada e integración con datos abiertos externos de la isla de Tenerife
Desafío 3 — Caso TUI Group








Autores:
Juan Andrés Cabrera Taramasco · Jaime de Vera Martín · Roberto Hernando Ascaso
Guillermo Martínez Ortigosa · Jorge Tamirat Montes Nocete · Mario Rosete Lázaro

Curso Académico 2025–2026

Índice General




# Resumen Ejecutivo

Tenerife recibe anualmente más de 7,2 millones de turistas internacionales bajo una distribución polarizada: la franja costera meridional concentra más del 80 % del parque alojativo y de la presión sobre infraestructuras y vivienda, mientras las comarcas del norte y medianías —de excepcional valor agroambiental y cultural— permanecen desaprovechadas. Esta hiperconcentración genera colapso vial en la TF-1 y TF-5, tensión hídrica y creciente rechazo social.
El presente TFM responde al Desafío 3 de TUI Group desarrollando un sistema integral de inteligencia territorial y toma de decisiones. La solución articula un Data Lakehouse en Microsoft Azure con arquitectura Medallón (Bronze, Silver, Gold) sobre la malla hexagonal Uber H3 Resolución 8 (2.579 celdas insulares de ~0,85 km²), resolviendo el sesgo MAUP de las divisiones municipales. El pipeline integra microdatos oficiales (AENA, Registro Turístico, ISTAC), movilidad GTFS (TITSA y tranvía), teledetección Sentinel-2 (NDVI) y VIIRS (radiancia nocturna), modelado topoclimático corregido por gradiente adiabático (67 estaciones de Agrocabildo) y minería multilingüe NLP sobre >55.000 reseñas de Booking, TripAdvisor, YouTube y LosViajeros.
La analítica avanzada despliega regresión espacial MGWR (R²=0,8272) para formular el Índice de Potencial Turístico No Aprovechado (PTNA), segmentación no supervisada HDBSCAN (6 arquetipos insulares), tópicos BERTopic, clasificación afectiva XLM-RoBERTa (F1=0,874), asistente conversacional RAG híbrido y un simulador interactivo de políticas en Streamlit/PyDeck. Los resultados demuestran que derivar un 10 % de la demanda alivia un 14 % la congestión costera e inyecta más de 45 M€ anuales en comarcas de oportunidad.
Palabras clave: Inteligencia Territorial, Uber H3, PostGIS, Arquitectura Medallón, Topoclimatología, Teledetección, HDBSCAN, MGWR, BERTopic, RAG, TUI Group, Tenerife.


# 1. Introducción y contexto de negocio


## 1.1. El problema de negocio en Tenerife: saturación costera y vacío rural

En 2024, Tenerife superó los 7,2 millones de turistas internacionales, un 12 % más que el año anterior (ISTAC, 2025). El turismo aporta cerca del 35 % del PIB canario y el 39,7 % del empleo de la región (Gobierno de Canarias, 2024). Sin embargo, el problema de fondo no radica en el volumen global de visitantes, sino en su extrema asimétrica territorial. la actividad turística se concentra de forma desproporcionada en un reducido número de municipios. Como evidencian nuestros datos de afiliación a la Seguridad Social (ISTAC), existe una extrema polarización laboral en la que, mientras la hostelería directa absorbe el 16,6 % del empleo insular (72.088 afiliados), en municipios costeros como Adeje o Santiago del Teide representa el 57,0 % y el 49,2 % de la ocupación municipal total.
Esta hiperconcentración se traslada por igual al mercado residencial a través de las 30.589 viviendas vacacionales registradas en el Registro General Turístico (128.419 plazas alojativas en total) de las cuales más del 58 % (17.837 viviendas) se aglutinan en solo cinco municipios del sur (Arona, Adeje, Granadilla de Abona, Santiago del Teide y San Miguel de Abona). Esta concentración en la costa ha traído consigo un caso claro de overtourism (Milano et al., 2019): atascos habituales en las autopistas TF-1 y TF-5, fuerte presión hídrica y la depuración, erosión de espacios naturales frágiles y un mercado del alquiler tensionado. En contraste, las medianías, el norte y el noroeste de la isla —municipios como Buenavista del Norte, Icod de los Vinos, San Juan de la Rambla o Vilaflor de Chasna— tienen un patrimonio histórico, paisajístico y gastronómico enorme, pero sufren despoblación y poca actividad económica. Repartir mejor el flujo turístico es, sencillamente, la única forma sostenible de que el destino aguante a largo plazo (Turismo de Canarias, 2025).

## 1.2. Objetivos generales y preguntas estratégicas

El objetivo general del proyecto es diseñar, construir y validar un sistema de inteligencia territorial y apoyo a la decisión con el dashboard diseñado que junta la oferta turística georreferenciada de Tenerife con datos abiertos externos, para identificar zonas saturadas, detectar focos de potencial desaprovechado y simular escenarios de redistribución de la demanda basados en datos reales.

| Nº | Pregunta Estratégica de TUI | Cómo la resolvemos |
| :--- | :--- | :--- |
| P1 | ¿Dónde se localizan con exactitud las zonas saturadas? | Malla H3 micro-espacial + VIIRS |
| P2 | ¿Qué zonas tienen alto potencial pero baja visibilidad? | Clustering HDBSCAN + Índice de Potencial (PTNA) |
| P3 | ¿Qué comarcas rurales tienen condiciones para absorber demanda? | Modelo topoclimático + NDVI + PTNA |
| P4 | ¿Cómo influye la accesibilidad en el éxito de zonas no costeras? | ORS (18 destinos) + GTFS multiumbral |
| P5 | ¿Qué áreas muestran señales de congestión? | Índice de saturación: densidad + quejas modales de NLP + VIIRS |
| P6 | ¿De qué se quejan los turistas en el sur y qué buscan en el interior? | XLM-RoBERTa + BERTopic + PyABSA |
| P7 | ¿Qué impacto tendría redistribuir un 10–20 % de la masa turística? | Simulador territorial interactivo What-If (app/simulador.py) |


Tabla 1. Preguntas estratégicas del briefing de TUI y cómo las resolvemos

## 1.3. Justificación del aporte diferencial de la solución

Mientras que la literatura académica como en la práctica profesional, de análisis de sentimiento en redes sociales, cuadros de mando de Business Intelligence o las evaluaciones territoriales como disciplinas estancas, la presente solución articula una plataforma une todo en una única arquitectura, alimentada por datos reales y a gran escala, aportando cinco ventajas diferenciales:
Superación del sesgo MAUP (Modifiable Areal Unit Problem): Sustitución de las delimitaciones municipales administrativas por una teselación hexagonal regular (Uber H3, resolución 8, celdas de 0,737 km² y 461 m de apotema), eliminando las distorsiones de escala espacial.
Integración multimodal unificada: Consolidación en un único modelo espacial de doce fuentes heterogéneas: teledetección (Sentinel-2 y VIIRS), oferta reglada y vacacional geocodificada, red de transporte público (GTFS e isócronas ORS), climatología horaria y minería de texto multilingüe.
Modelado físico topoclimático de precisión: Simulación de los microclimas insulares mediante gradientes adiabáticos, inversión térmica del mar de nubes (800–1.500 m) y corrección orográfica Foehn por orientación de laderas (aspect).
Modelización analítica con conciencia espacial (Spatial Machine Learning): Aplicación de algoritmos diseñados específicamente para estructuras espaciales no homogéneas: agrupamiento por densidad jerárquica con identificación de ruido mediante HDBSCAN, y regresión multiescala ponderada geográficamente (MGWR) para modelar la no-estacionariedad de la presión turística.
Prescripción ejecutiva mediante RAG (Retrieval-Augmented Generation): Interrogación en lenguaje natural sobre las tablas maestras *Gold* mediante inferencia ultrarrápida LPU (Groq y Llama-3), traduciendo el dato multidimensional en recomendaciones estratégicas inmediatas.

# 2. Infraestructura y adquisición de datos


## 2.1. Arquitectura en Microsoft Azure

La infraestructura se desplegó íntegramente en la región europea de Microsoft Azure con tres componentes principales:
* Azure Blob Storage (Data Lake Gen2): Repositorio primario de objetos `bronze-raw`. Almacena Parquets, TIFF de teledetección y colecciones JSON brutas.
* Azure Database for PostgreSQL Flexible Server v16 + PostGIS 3.4: Motor relacional y geoespacial central (2 vCores, 8 GiB RAM, SSD Premium). Aloja 48 tablas brutas del esquema `bronze` y los modelos analíticos de `silver` y `gold`.
* VM Azure Linux (Ubuntu 24.04 LTS, Standard B2ats v2): Nodo orquestador de cron jobs, scrapers y ejecuciones de dbt Core 1.8.
* El proyecto partió de una instancia Neon.tech para prototipado rápido y migró a Azure al incorporar el backfill histórico de Agrocabildo y los más de dos millones de registros GTFS de TITSA, que superaban las limitaciones de la capa gratuita.

## 2.2. Extracción de microdatos oficiales tabulares y espaciales

* Instituto Canario de Estadística (ISTAC): Mediante integración directa con dos recursos REST de su API oficial (Municipios en Cifras C00067A y el recurso estadístico de Vivienda Vacacional C00065A_000061), se ingirieron veinticuatro indicadores socioeconómicos y de demanda alojativa para los 31 municipios de Tenerife (códigos INE 38001 a 38052). Este corpus abarca la demografía censal, el desempleo registrado mensual, la matriz de pernoctaciones y ocupación hotelera (EOH), la suite trimestral de afiliaciones a la Seguridad Social (desglosada por regímenes general/autónomo y seis sectores de actividad económica), la Población Turística Equivalente (PTE) y las series completas de vivienda vacacional (plazas, ocupación, estancia media e ingresos brutos),  garantizando la caracterización socioeconómica continua tanto de los polos tradicionales como de los municipios de interior.
* Cartografía Vectorial Oficial: Desde el portal insular de datos abiertos (datos.tenerife.es) y GRAFCAN/IDECanarias, se integraron los límites municipales (31), Bienes de Interés Cultural (125 BIC), oficinas de turismo (31), Zonas Turísticas (17) y Espacios Naturales Protegidos (43 ENP), estandarizados en GeoParquet y PostGIS (EPSG:4326 y EPSG:32628).
* Modelo Digital del Terreno (MDT25): Con celda de 25 m y mediante el operador de gradiente de Horn (1981), se extrajeron altitud, pendiente, orientación y sombreado (hillshade a 315° NW y 45° de elevación), integrando sus estadísticas zonales en la malla insular.

## 2.3. Integración de la red de transporte público insular (GTFS)

La movilidad colectiva se modeló a partir de los datos GTFS de TITSA (guaguas) y Metropolitano de Tenerife (tranvía). Se estructuró en siete tablas maestras: 3.934 paradas físicas georreferenciadas, 873 trazados de rutas (183 líneas comerciales), 48.655 viajes planificados y un histórico operativo de 1,36 millones de registros de paso horarios (derivados de los 2,08 millones del volcado bruto). Esta topología permite calcular isócronas de accesibilidad turística y evaluar la conectividad de las zonas de interior frente a los núcleos costeros.

## 2.4. Ingesta meteorológica de alta resolución y teledetección satelital

Para caracterizar los marcados microclimas insulares derivados del relieve y los vientos alisios, se integró la red del Agrocabildo (Cabildo de Tenerife):
* Series Meteorológicas: Recoge el inventario de 68 estaciones automáticas (378 sensores físicos) y 136,4 millones de lecturas brutas (2019–2026). En la capa Silver se depuraron 12,95 millones de registros correspondientes a las 57 estaciones maduras (instaladas antes de 2022) y a las horas punta dando granularidad horaria, garantizando series históricas continuas y sin sesgos de muestreo.
* Teledetección Satelital: Se procesaron compuestos trimestrales de reflectancia sin nubosidad de Copernicus Sentinel-2 (20 m) (Agencia Espacial Europea, 2024) para computar los índices de vegetación (NDVI) y edificación (NDBI) sobre la malla insular (46.422 registros en Silver), junto con la serie mensual de luz nocturna del sensor NOAA/NASA VIIRS (Elvidge et al., 2017) con 241.648 observaciones como proxy de actividad antropogénica.

## 2.5. Extracción de datos cualitativos sociales y reputacionales

Para capturar la percepción de la demanda y el sentimiento del visitante, se combinaron tres canales complementarios:
* Comunidades de Viajeros (LosViajeros.com): Mediante web scraping ético con BeautifulSoup (Richardson, 2024) se recopiló el debate cualitativo completo sobre Tenerife entre 2004 y 2026, abarcando 248 hilos temáticos y 167.274 mensajes brutos (168.035 procesados en Silver tras limpieza de entidades y etiquetas).
* Contenido Audiovisual (YouTube Data API v3) (Google Developers, 2024): Se monitorizaron 41 vídeos de alta difusión turística, extrayendo 3.100 comentarios brutos depurados a 2.819 opiniones contemporáneas (2022–2026).
* Plataformas de Alojamiento (Booking.com y TripAdvisor) (Booking.com, 2025), (Tripadvisor, 2025): Constituyen el núcleo geolocalizado del análisis reputacional, acumulando más de 105.000 reseñas brutas y consolidando en Silver 74.695 reseñas limpias y georreferenciadas (73.888 de Booking y 807 de TripAdvisor) asociadas a 3.740 establecimientos hoteleros y 748 actividades turísticas, lo que posibilita su indexación directa en los hexágonos H3.

## 2.6. Derechos de uso, licencias y marco ético de los datos

El tratamiento de datos se rigió por principios estrictos de diligencia debida legal y ética, diferenciando dos regímenes normativos:
• Datos abiertos institucionales y teledetección: Las fuentes gubernamentales (ISTAC, IDECanarias, Cabildo de Tenerife, Agrocabildo y la red GTFS de TITSA) se explotan bajo la Directiva (UE) 2019/1024 y la Ley 37/2007 de reutilización del sector público (licencias CC-BY 4.0). Las imágenes satelitales Sentinel-2 (ESA) y VIIRS (NASA/NOAA) se rigen por sus respectivas políticas científicas de acceso libre y abierto.
• Extracción cualitativa, RGPD y transición comercial: Para Booking.com y TripAdvisor, la ingesta se restringió estrictamente al marco de investigación académica de la UCM, implementando rate limiting conservador (2,5–5,0 s por petición), caché relacional en PostGIS y cabeceras identificadas sin sobrecarga de servidores. En cumplimiento estricto del RGPD, se aplicó anonimización irreversible (cero almacenamiento de nombres, perfiles o IPs; disociación mediante hash SHA-256 y agregación espacial H3). Para la explotación comercial en TUI Group, el desacoplamiento de la arquitectura medallón permite sustituir directamente los extractores experimentales por las APIs oficiales correspondientes (Booking Connectivity Partner, TripAdvisor Content y YouTube Enterprise).

# 3. Data Lakehouse y Topología Geoespacial


## 3.1. Arquitectura medallón en PostgreSQL con dbt Core

El almacén analítico implementa el patrón arquitectónico Medallion Lakehouse (Armbrust et al., 2021) sobre Azure Database for PostgreSQL Flexible Server v16 con la extensión espacial PostGIS 3.4, gestionado mediante dbt Core 1.8. La orquestación del ciclo de vida del dato se delega en Apache Airflow 2.x, desplegado de forma contenerizada (Docker Compose) sobre el nodo orquestador Ubuntu en Azure. El sistema articula tres flujos de trabajo (DAGs):
Carga histórica integral (historical_full_pipeline): Ejecución única estructurada en cinco fases secuenciales paralelizadas: (1) ingesta masiva desacoplada a Azure Blob Storage; (2) vuelco estructurado a tablas crudas en PostgreSQL; (3) estandarización y tipado en capa Silver; (4) inferencia analítica y NLP intensivo condicionado por GPU; y (5) consolidación multidimensional en capa Gold (la topología completa de tareas e interdependencias de Airflow se detalla en el Anexo G).
Refresco incremental periódico: (incremental_monthly_pipeline): Se procesa mensualmente de manera periódica (día 5 de cada mes) para regenerar exclusivamente las fuentes dinámicas (satélite, series ISTAC, climatología, censo de alojamientos y tráfico aéreo de AENA).
Actualización reputacional (social_refresh): Ingesta bajo demanda para reevaluar el sentimiento y los tópicos textuales cuando se incorporan nuevas reseñas de Booking, TripAdvisor, YouTube o foros.
Las tres capas del Lakehouse en Postgre que gestiona dbt son:
* Bronze (Raw): 48 tablas fuente declaradas en sources.yml. Preserva fielmente el estado original del dato con marcas temporales de auditoría, garantizando trazabilidad e inmutabilidad.
* Silver (Limpieza y asentamiento): 9 dominios temáticos (alojamiento, booking, clima, espacial, istac, losviajeros, movilidad, tripadvisor y youtube) que resuelven nulos, tipifican tipos de datos y proyectan geometrías a los estándares EPSG:4326 y EPSG:32628.
* Gold (Analítica multidimensional): Tablas maestras desnormalizadas, optimizadas para alimentar los modelos de Machine Learning, el simulador de decisiones y el panel interactivo (catálogo ampliado en la el Anexo A3).
dbt gestiona de forma determinista el grafo acíclico dirigido (DAG) de dependencias entre modelos, materializándolos como tablas indexadas mediante índices espaciales GiST y BRIN. La solidez del almacén se apoya en una suite de 216 pruebas de calidad automáticas declaradas en archivos schema.yml, auditando unicidad de identificadores, completitud de geometrías, rangos admisibles de sensores y relaciones de clave foránea entre capas (la matriz exhaustiva de gobernanza y pruebas de calidad se recoge en el Anexo C.4).

## 3.2. Malla hexagonal Uber H3 (resolución 8) y solución del MAUP

En Tenerife, municipios como La Orotava abarcan desde la costa (0 m) hasta la cima del Teide (3.715 m), por lo que un promedio municipal mezcla realidades climáticas y económicas opuestas. Para resolver el Problema de la Unidad de Área Modificable (MAUP) (Openshaw, 1984), el proyecto adopta como teselación primaria la Malla Hexagonal Uber H3 en Resolución 8:
* Geometría isotrópica y regular: Hexágonos isotrópicos de ~0,85 km² con distancia uniforme entre centroides vecinos de 990 m.
* Depuración territorial insular: El rasterizado bruto de la costa generó 2.746 celdas Bronze; tras el filtrado geoespacial en la tabla silver_h3_grid de los hexágonos que por caer en el mar no tenían valores provenientes del MDT o los índices satelitales, se depuraron 2.579 celdas terrestres limpias sin valores nulos en topografía ni teledetección.
* Soporte pivote maestro: la tabla silver_h3_grid actúa como tabla pivote maestra del sistema: toda entidad puntual (alojamientos, paradas, reseñas) o cobertura poligonal (municipios, espacios protegidos) se indexa a su celda mediante relaciones espaciales de contención o intersección en PostGIS.
* Estándar de Sistemas de Coordenadas: Las geometrías se persisten en EPSG:4326 (WGS84) para compatibilidad con la indexación H3 y motores de visualización web (PyDeck), proyectándose en tiempo de consulta a EPSG:32628 (UTM Zona 28N) cuando se requieren mediciones métricas exactas de distancias y superficies.
* Rendimiento espacial: La combinación de índices espaciales GiST e índices únicos B-Tree sobre el identificador hexadecimal H3 permite resolver cruces geográficos masivos en decenas de milisegundos.

## 3.3. Geocodificación centralizada y control de calidad del dato

El Registro General Turístico de Canarias incluye numerosas entradas sin coordenadas geográfica. Para normalizar estas direcciones sin coordenadas se implementó un flujo centralizado de geocodificación que opera íntegramente en la nube:
* Normalización Toponímica Canaria: Tratamiento heurístico de sintaxis insular (corrección de artículos pospuestos como "Orotava (La)" a "La Orotava"), expansión de abreviaturas viales y desambiguación territorial forzada (sufijo ", Tenerife, España" en cada consulta).
* Caché Relacional en la Nube: Antes de consumir peticiones sobre APIs externas (OpenStreetMap / ArcGIS), el pipeline consulta las tablas de lookup centralizadas (bronze_registro_geocoding_lookup y bronze_booking_geocoding_lookup). Solo las direcciones inéditas consumen cuota externa, persistiendo de inmediato las coordenadas resueltas para su reutilización compartida por todo el equipo.
* Cruce Espacial Robusto: El modelo de dbt silver_alojamientos_oficiales.sql construye la geometría canónica priorizando las coordenadas originales válidas del registro y recurriendo a las geocodificadas únicamente ante valores nulos (el script SQL de asignación y fallback se detalla en el Anexo C.1).
* Deduplicación y Tests de Calidad: Mediante funciones analíticas de particionado por identificador oficial y marca temporal más reciente, se depuran versiones duplicadas, mientras que los tests declarativos de dbt verifican la unicidad de registro, la ausencia de geometrías nulas y la contención estricta dentro de la caja delimitadora (bounding box) de Tenerife.

# 4. Inteligencia Territorial, Modelado Microclimático y Machine Learning Espacial


## 4.1. Doble escala analítica: malla H3 maestra y agregación municipal

Para articular una toma de decisiones informada en TUI Group, el sistema combina simultáneamente dos niveles complementarios de agregación espacial:
* Escala micro territorial (Malla H3 Resolución 8): Articulada sobre gold_h3_master, unifica en las 2.579 celdas terrestres limpias (~0,85 km² y 461 m de apotema) más de sesenta covariables biofísicas, microclimáticas, de conectividad vial, oferta reglada y reputación online. Esta resolución micro permite evaluar la viabilidad de producto en un barranco o núcleo rural específico sin arrastrar los sesgos del promedio comarcal.
* Escala macro estratégica (Ámbito municipal): La capa liderada por gold_municipio_master agrega los indicadores socioeconómicos del ISTAC y el tráfico aéreo de AENA para los 31 términos municipales. Esta perspectiva macro facilita el seguimiento de KPIs corporativos, la correlación de diversas variables y el diálogo con las administraciones públicas.

## 4.2. Caracterización biofísica y teledetección satelital

La capacidad de carga y el atractivo ambiental del territorio se parametrizaron mediante teledetección multiespectral y radiancia nocturna procesadas en Google Earth Engine (GEE):
* Composites trimestrales Copernicus Sentinel-2 (20 m): Para superar el bloqueo visual de la «panza de burro» y los episodios de polvo sahariano, se generaron 30 compuestos trimestrales mediante un triple filtro a nivel de píxel (clasificación de escena SCL, aerosol AOT < 0,3 y banda azul B02). De ellos se derivaron el NDVI (vigor vegetal, de 0,08 en lavas áridas a 0,82 en Anaga) y el NDBI (huella de suelo construido), consolidando 46.422 registros limpios en Silver.
* Radiancia nocturna NOAA/NASA VIIRS DNB (500 m): A partir de 90 compuestos mensuales calibrados, se obtuvo un proxy objetivo de presión antrópica y actividad económica nocturna: los polos turísticos saturados del sur superan los 65 nW/(cm²·sr), mientras que las medianías rurales caen por debajo de 4 nW/(cm²·sr).

## 4.3. Climatología analítica y modelado topoclimático microinsular

El clima de Tenerife está modelado principalmente por cuatro factores físicos: vientos alisios del noreste, inversión térmica de subsidencia (800–1.500 m), efecto Föhn en sotavento y advecciones de calima sahariana. Para modelar con fidelidad estos microclimas, se articuló en dbt una cadena de inferencia topoclimática sobre las 57 estaciones que empleamos de la red de Agrocabildo:
* Interpolación espacial y gradiente térmico: Se aplicó ponderación por distancia inversa cuadrática (IDW k=3) corregida por gradiente adiabático vertical (-0,0065 °C/m según la cota de la celda respecto a la estación) y amortiguación litoral (Anexo C.2).
* Modelado físico de humedad y precipitación: Se incorporó un factor de condensación orográfica que eleva la humedad relativa en un 25 % en la franja del Mar de Nubes (800–1.500 m en barlovento) y la reduce en un 30 % en la cumbre seca subsidente (>1.500 m). En sotavento sur se modeló el efecto paraguas orográfico (-15 % humedad, -60 % lluvia).

## 4.4. Fricción de red y accesibilidad multimodal

La viabilidad de descongestionar el sur depende de la conectividad real por carretera. En una isla de relieve escarpado, las distancias euclídeas son engañosas. Por ello, el sistema realizó matrices de viaje vial mediante OpenRouteService (ORS) desde cada celda H3 hacia 18 destinos estratégicos (aeropuertos TFS/TFN, Teide, núcleos costeros y cabeceras comarcales). Esto se complementó con la cobertura de transporte público regular GTFS (conteo escalonado de paradas TITSA a 200 m, 500 m y 1.000 m) y la distancia al hospital comarcal más cercano, generando isócronas continuas de 15, 30, 45 y 60 minutos en gold_h3_accesibilidad.

## 4.5. Regresión geográfica ponderada multiescala (MGWR), Índice PTNA y Marco ESG

Los modelos lineales globales (OLS) asumen erróneamente homogeneidad espacial insular. La Regresión Geográfica Ponderada Multiescala (MGWR) resuelve esta no-estacionariedad estimando anchos de banda locales independientes para cada variable explicativa. El modelo checkpoint v3 reveló escalas locales para el vigor vegetal (NDVI, bw=198) y la cota altimétrica (bw=138), mientras que 9 variables (distancias costeras y tiempos al aeropuerto) saturaron a escala insular (bw≈2.573). El MGWR eleva el R² global de 0,5444 (OLS) a 0,8272 y reduce sustancialmente la autocorrelación espacial residual (I de Moran de 0,3065 a 0,0355, p=0,0110).
* Índice de Potencial Turístico No Aprovechado (PTNA) y Salvaguarda ESG: El PTNA cuantifica la brecha entre la densidad alojativa estimada por el modelo y la observada (ptna_score = predy_MGWR − Y_observado), identificando celdas con condiciones objetivas superiores a su explotación actual. Para garantizar una descompresión sostenible, se integró un Índice ESG Territorial (0–100) en tres pilares: Medioambiental (E, 40 %: NDVI, polución lumínica VIIRS, sellado NDBI y ENP protegidos), Social (S, 40 %: densidad residencial, transporte TITSA y ausencia de quejas) y Gobernanza (G, 20 %: formalización hotelera y patrimonio BIC). El filtro combinado (PTNA > 0 y ESG > 60) aísla exactamente 247 hexágonos de oportunidad ideal (9,6 % de la isla), liderados por Santa Cruz (34), La Laguna (29), La Orotava (22), Buenavista del Norte (20), El Tanque (19) y Los Realejos (18).

## 4.6. Segmentación territorial no supervisada: Arquetipos con HDBSCAN

Conociendo los forzadores territoriales y el potencial PTNA, se aplicó HDBSCAN (Hierarchical Density-Based Spatial Clustering of Applications with Noise) La justificación es la marcada orografía insular y la polarización turística invalidan algoritmos basados en particiones esféricas homogéneas (K-Means) o sin control legal de protección. El modelo definitivo opera sobre 8 covariables canónicas: plazas alojativas y radiancia nocturna VIIRS (estabilizadas con transformación logarítmica log1p para atenuar colas pesadas), NDVI (vigor vegetal), NDBI (huella construida), altitud media, pendiente, distancia a la costa y el porcentaje de superficie en Espacio Natural Protegido. Tras estandarización con StandardScaler, un análisis PCA condensa el 81,5 % de la varianza en tres dimensiones no redundantes. La calibración óptima de HDBSCAN (min_cluster_size = 30, min_samples = 10, selección EOM) identificó de forma no supervisada 4 macro-clústeres de densidad (57,3 % del territorio). El 42,7 % restante de celdas de transición y ruido se reasignó mediante reglas territoriales:
* Celdas con ≥ 500 plazas pasaron al cluster Saturado / Overtourism.
* Celdas con VIIRS ≥ 20 nW/(cm²·sr) y ENP < 20 % se clasificaron como Urbano Residencial.
* El ruido remanente se absorbió proyectándolo al centroide euclídeo más próximo en el espacio PCA. El resultado consolida seis tipologías territoriales exhaustivas con el 100 % de cobertura insular.

| Clúster territorial | Cobertura y peso (n / %) | Perfil físico, biofísico y turístico | Comarcas y municipios representativos | Directriz estratégica para TUI Group |
| :--- | :--- | :--- | :--- | :--- |
| Espacio Natural / Teide y Cumbre | 716 celdas (27,8 %) | Altitud media ~1.768 m, máxima protección (93 % ENP), radiancia VIIRS nula (~0 nW), sustrato volcánico de alta cota. | Parque Nacional del Teide, cumbre central y Corona Forestal alta. | Preservación absoluta y exclusión hotelera; comercialización exclusiva de astroturismo y senderismo diurno de bajo impacto con guías certificados. |
| Espacios Rurales Protegidos (Anaga/Teno) | 456 celdas (17,7 %) | Altitud media ~714 m, relieve muy abrupto (pendiente media ~30°), 87 % ENP, elevado vigor vegetal (NDVI alto), nula planta hotelera masiva. | Macizo de Anaga (Santa Cruz, La Laguna), Parque Rural de Teno (Buenavista, Santiago del Teide). | Ecoturismo botánico y senderismo regulado de residuo cero; valorización del patrimonio etnográfico sin nuevas edificaciones. |
| Transición Costera y Medianías | 895 celdas (34,7 %) | Altitud media ~328 m, baja protección (8 % ENP), radiancia VIIRS moderada (4,9 nW), posición bisagra entre el litoral y la cumbre. | Corredores periurbanos y medianías bajas de Granadilla, San Miguel, Güímar, Fasnia y Candelaria. | Vector de descompresión territorial; desarrollo de productos híbridos de media montaña, enoturismo y desvío de flujos excursionistas. |
| Rural Agrícola / Medianías Norte | 412 celdas (16,0 %) | Altitud media ~490 m, alto verdor y humedad (elevado NDVI), baja edificación (NDBI bajo), VIIRS bajo (4,8 nW), clima templado con influencia atlántica. | Medianías de Icod de los Vinos, La Orotava, Los Realejos, Garachico, Buenavista del Norte, Tacoronte. | Foco prioritario de inversión y diversificación de TUI: micro hoteles boutique rurales, agroturismo, rutas gastronómicas de guachinches y estancias de desconexión. |
| Saturado / Overtourism (Regla ≥500 pl.) | 61 celdas (2,4 %) | Cota litoral (~71 m), hiperdensidad de camas (>500 pl/celda, >1.850 pl/km²), alta radiancia VIIRS (~28 nW), queja dominante de masificación y ruido en NLP. | Playa de las Américas, Los Cristianos, Costa Adeje (Adeje, Arona) y frente litoral maduro de Puerto de la Cruz. | Moratoria y contención estricta de camas; reconversión de planta existente hacia estándares sostenibles, elevación de ADR y redistribución de clientes. |
| Urbano Residencial (Regla VIIRS≥20) | 39 celdas (1,5 %) | Máxima radiancia económica (>41 nW promedio), 0 % ENP, elevada huella de suelo construido (NDBI), funciones residenciales y de servicios metropolitanos. | Casco urbano consolidado de Santa Cruz de Tenerife y San Cristóbal de La Laguna. | Turismo cultural urbano, patrimonio UNESCO, rutas gastronómicas metropolitanas y eventos corporativos MICE, protegiendo el parque residencial. |


Tabla 2. Arquetipos territoriales identificados con HDBSCAN y directrices para TUI Group
Para transformar este diagnóstico territorial discreto en insights accionables de negocio para TUI Group, los 2.579 hexágonos se proyectan en una matriz continua bidimensional: el Eje 1 (Saturación Turística [0–1], calibrado según plazas, VIIRS, proximidad litoral y densidad hotelera) frente al Eje 2 (Potencial Rural y Sostenible [0–1], que integra el índice PTNA derivado de MGWR, NDVI vegetal, ausencia de suelo sellado y gobernanza climática ESG). Este cruce analítico permite prescribir a cada micro zona insular uno de los 5 Arquetipos de Producto Turístico de TUI: Sol y Playa, Ecoturismo Rural y Medianías, Cultural y Patrimonial, Aventura y Turismo Activo, y Bienestar. Estos clústeres se visualizan interactivamente en las vistas de Mapa y Oportunidades TUI del AI-Dashboard.

# 5. Procesamiento del Lenguaje Natural (NLP) y Percepción de Marca Destino


## 5.1. Inferencia multilingüe de polaridad afectiva por lotes

* El análisis cualitativo procesó un corpus de más de 55.000 opiniones de cuatro fuentes (Booking, TripAdvisor, YouTube y LosViajeros) en cinco idiomas (ES, EN, DE, FR, IT), desacoplando el pipeline según la estructura del dato:
* Filtro de relevancia zero-shot para redes sociales: Aplicado sobre los comentarios de YouTube mediante el transformador MoritzLaurer/mDeBERTa-v3-base-mnli-xnli.  frente a cuatro hipótesis (turismo vs. canal, charla y spam). Se descartan textos que no superen al ruido por un margen de confianza >0,25. Las reseñas regladas de Booking y TripAdvisor, al constituir estancias verificadas, pasan directamente a inferencia.
* Inferencia de polaridad y calificación continua: Los comentarios depurados de YouTube son clasificados mediante cardiffnlp/twitter-xlm-roberta-base-sentiment en 3 clases discretas: positivo, neutro y negativo, por lotes de 32 documentos, alcanzando en validación manual frente a 1.000 reseñas un Macro F1 de 0,874 y una exactitud global del 88,2 % (Anexo F). Paralelamente, las reseñas de alojamiento de Booking y TripAdvisor se procesan con nlptown/bert-base-multilingual-uncased-sentiment, infiriendo una calificación continua en escala de 1 a 5 estrellas que se persiste en gold.nlp_sentimiento_resenas y permite la posterior agregación espacial en la capa Gold.

## 5.2. Descubrimiento no supervisado de tópicos insulares (BERTopic)

Para identificar las temáticas sin imponer diccionarios predeterminados, se implementó el marco de BERTopic mediante embeddings semánticos multilingües de 768 dimensiones (paraphrase-multilingual-mpnet-base-v2). Para neutralizar el sesgo de idioma y evitar que el algoritmo agrupe por lengua en lugar de por semántica, se aplicó un centrado vectorial por idioma que redujo la dependencia mutua (NMI de 0,218 a 0,031). En producción, para evitar que HDBSCAN descartase como ruido el 76,8 % de los documentos breves, el agrupamiento se optimizó mediante PCA a 50 dimensiones y K-Means, generando palabras clave con c-TF-IDF multilingüe y asignando nombres en español asistidos por LLM (openai/gpt-oss-120b a través de API Groq):
* Modelo A (Visión macro insular): Entrenado sobre YouTube y mensajes no geolocalizados de LosViajeros (k=20, coherencia 0,71), captura debates estratégicos generales: congestión vehicular en las autopistas TF-1 y TF-5 (polaridad media -0,62), saturación de playas del sur (-0,48) y valoraciones excelentes de la gastronomía y guachinches (+0,86).
* Modelo B (Micro geolocalizado): Entrenado sobre 51.252 reseñas geocodificadas de Booking, TripAdvisor y mensajes con toponimia validada en gold.geo_mentions (k=50). Asigna temáticas a hexágonos H3 específicos, contraponiendo quejas de masificación, ruidos nocturnos y fatiga de instalaciones en el litoral sur frente a sosiego, naturaleza y confort en las medianías del norte.

## 5.3. Minería de aspectos específicos y extracción de quejas principales (PyABSA)

Mediante el modelo multilingüe PyABSA-ATEPC (Aspect-Term Extraction and Polarity Classification), el sistema extrae simultáneamente los términos de experiencia y su polaridad afectiva en una única pasada de inferencia por lotes de 32 textos. Dado la variedad de idiomas de los turistas, aplicamos una traducción híbrida e incremental (Google Translate con respaldo en MyMemory y detección langdetect), persistiendo el mapeo en gold.aspecto_traducciones. Más de 1.200 términos normalizados se estructuran en seis dimensiones canónicas: Limpieza, Servicio, Relación Calidad-Precio, Ubicación, Confort/Ruido y Saturación/Instalaciones.

## 5.4. Integración espacial del sentimiento en la malla H3

El modelo analítico gold_sentimiento_h3 consolida los indicadores cualitativos a escala hexagonal. La queja principal de cada celda se obtiene computando la moda del aspecto más frecuente condicionada estrictamente a menciones con sentimiento negativo. Esta restricción matemática es crítica para evitar que el indicador quede falseado por aspectos mayoritariamente positivos como ubicación o desayuno. El modelo consolida resultados sobre 410 de los 2.579 hexágonos (15,9 % del territorio), coincidiendo de forma exacta con las celdas insulares que albergan oferta alojativa con reseñas geolocalizadas.

## 5.5. Evaluación técnica comparativa de modelos frente a alternativas

En cumplimiento de los estándares de evaluación, la selección metodológica de técnicas analíticas y de aprendizaje automático se fundamenta en su contraste explícito frente a alternativas descartadas:

| Técnica Seleccionada | Tarea / Dominio | Métricas Clave Obtenidas | Ventaja Diferencial de Negocio | Riesgo Técnico / Mitigación | Alternativa Descartada y Justificación |
| :--- | :--- | :--- | :--- | :--- | :--- |
| XLM-RoBERTa + mDeBERTa Zero-Shot | Filtro de relevancia y polaridad de opiniones | Macro F1 = 0,874; Exactitud = 88,2 % | Inferencia multilingüe real (ES/EN/DE/FR/IT) sensible al contexto y libre de sesgo léxico estático. | Coste computacional mitigado con filtro previo en YouTube y lotes de 32 textos. | VADER / TextBlob: descartados por depender de diccionarios estáticos sin contexto ni soporte multilingüe. |
| BERTopic (mpnet-base-v2 + c-TF-IDF) | Descubrimiento no supervisado de tópicos | Coherencia semántica = 0,71 (14 temas macro, 50 micro) | Extracción no supervisada de temáticas emergentes sin imponer taxonomías previas. | Ruido de HDBSCAN mitigado mediante PCA(50) + K-Means y etiquetado asistido por LLM (Llama-3). | LDA clásico: descartado por pobre rendimiento ante textos coloquiales cortos y pérdida de contexto semántico. |
| MGWR Multiescala | Determinantes espaciales y cálculo del PTNA | R² = 0,782; AICc = 3.914,6; Moran I = 0,041 | Asigna anchos de banda locales independientes por variable, capturando microclimas y economías locales. | Riesgo de colinealidad local controlado mediante filtrado estricto de VIF < 5. | OLS Global (R² = 0,418, Moran I = 0,472): descartado por sesgo espacial severo e hipótesis homogénea falsa. |
| HDBSCAN (con PCA) | Tipificación territorial de 2.579 celdas H3 | Varianza PCA = 81,5 %; 6 tipologías (cobertura 100 %) | Detecta morfologías arbitrarias y aísla ruido geográfico reasignado con reglas territoriales. | Calibración de min_cluster_size optimizada mediante análisis de estabilidad de dendrograma. | K-Means: descartado por forzar clústeres esféricos de igual tamaño, distorsionando la geografía insular. |


Tabla 3. Evaluación comparativa de técnicas de modelización frente a alternativas descartadas

# 6. Inteligencia Artificial Generativa, RAG Híbrido y Asistente Conversacional Inteligente


## 6.1. Arquitectura RAG Híbrida y Motor de Inferencia LPU (Groq API)

Para salvar la brecha operativa entre los modelos multidimensionales y la toma de decisiones ejecutiva en TUI sin incurrir en alucinaciones factuales, se implementó una arquitectura desacoplada gobernada por guardarraíles estrictos. Se descartó el aprovisionamiento de GPUs dedicadas en Azure Cloud (>900 USD/mes) en favor de la API Cloud de Groq, cuyos procesadores LPU (Language Processing Unit) ofrecen inferencia superior a 250 tokens/segundo.
El motor seleccionado es openai/gpt-oss-120b (con *fallback* en llama-3.3-70b-versatile). Debido a que este modelo consume presupuesto interno en tokens de razonamiento antes de emitir texto, se calibraron techos específicos por tarea: max_tokens=150 para el router, max_tokens=1000 para Text-to-SQL y max_tokens=1200 para informes ejecutivos, operando con T=0,0 en tareas deterministas y T=0,4 en síntesis narrativa. A través del script report_generator.py, el sistema genera periódicamente memorias ejecutivas de tres párrafos (percepción global, fricciones críticas y oportunidades TUI) almacenadas en gold.nlp_informe_global bajo dos alcances: Ámbito General (Modelo A de BERTopic post-2022) y Ámbito Alojamiento (Modelo B usando más de 38.000 opiniones de nuestras fuentes).

## 6.2. Indexación Vectorial, Extracción Determinista y Fusión RRF

El motor RAG opera sobre un corpus de 87.981 fragmentos almacenados en gold.nlp_chunks. El 95,5 % de las reseñas tiene ≤ 1.000 caracteres y se ingiere de forma atómica para preservar la coherencia contextual. El 4,5 % restante se procesa mediante segmentación recursiva por oraciones en bloques de 800 caracteres con 100 de solapamiento para mantener el contexto entre fragmentos. Cada fragmento se enriquece con metadatos de autor, fecha, valoración, tópico y su adscripción geoespacial mediante un cruce PostGIS con celdas H3 de gold_h3_master para Booking/TripAdvisor y mención toponímica para foros.
* Indexación Vectorial Densa: Se empleó sentence-transformers/paraphrase-multilingual-mpnet-base-v2 (768 dimensiones) indexado en PostgreSQL con pgvector HNSW (m = 16, ef_construction = 64, distancia coseno (<=>)). Para evitar la degradación de recall ante filtros SQL selectivos, se activó el escaneo iterativo (SET LOCAL hnsw.iterative_scan = 'relaxed_order' con ef_search = 100) sobre un CTE MATERIALIZED, reduciendo la latencia de 15 segundos a <40 milisegundos.
* Filtros Deterministas: El módulo filtros.py extrae entidades toponímicas, zonas protegidas y gentilicios plurales mediante regex y diccionarios, eliminando la latencia y alucinaciones de un extractor LLM. Si la intersección estricta resulta vacía, relaja adaptativamente fechas conservando los filtros geográficos obligatorios.
* Búsqueda Híbrida y Fusión RRF: Combina la similitud semántica con búsqueda léxica BM25 (ts_rank_cd logarítmico sobre índice GIN) mediante Reciprocal Rank Fusion:
* Figura 1. Algoritmo de fusión de rangos recíprocos (Reciprocal Rank Fusion, RRF) para la integración de resultados léxicos (BM25) y densos (embeddings). Fuente: Elaboración propia basada en Cormack, Clarke y Büttcher (2009)
* Balanceo de Corpus y Deduplicación: Ante el monopolio de Booking (84 % del volumen bruto), se limita sus fragmentos a un máximo de 2 en preguntas de destino general, dando visibilidad a YouTube y foros. Se aplica deduplicación por hash de los primeros 200 caracteres normalizados para purgar réplicas anidadas en foros.

## 6.3. Guardrails anti-alucinación y asistente dual (Router + Text-to-SQL)

Para garantizar respuestas fiables ante comités directivos de TUI, rag_answer.py incorpora cuatro salvaguardas anti-alucinación estrictas: (1) Descomposición contextual de opiniones en título, aspectos positivos y aspectos negativos; (2) Citación obligatoria entre corchetes [1][2] vinculada a fragmentos reales del Lakehouse; (3) Fórmula determinista de abstención si la similitud semántica no supera los umbrales mínimos; y (4) Prohibición explícita de extrapolar porcentajes globales a partir de muestras cualitativas locales.
* El asistente conversacional articula un doble motor de respuesta: un Router de Intención (router.py con LLM a T=0,0) que bifurca las consultas entre analítica cuantitativa (enrutadas al Agente Text-to-SQL con validación sintáctica AST sobre 7 tablas maestras Gold) y síntesis reputacional cualitativa (enrutadas al pipeline RAG híbrido).

## 6.4. Validación empírica del sistema RAG

El sistema ofrece dos modalidades de generación narrativa:
* Informe Macro Insular: Sintetiza los tópicos del Modelo A de BERTopic en tres bloques ejecutivos: percepción general de la marca Tenerife, fricciones y puntos críticos (atascos, masificación, dificultad de acceso a Anaga y Masca) y oportunidades de mejora para TUI (reconfiguración de excursiones, promoción de medianías, desestacionalización).
Ficha Micro Territorial por Celda H3: Activada al seleccionar una celda en el mapa, recupera en tiempo real su altitud, microclima ajustado, paradas de transporte, plazas hoteleras, tiempo al aeropuerto, sentimiento medio y queja principal de PyABSA, generando una ficha ejecutiva de viabilidad de absorción de nuevos flujos turísticos en menos de tres segundos.

# 7. Productivización: AI-Dashboard Interactivo y Simulador de Decisiones

7.1. Arquitectura Frontend y renderizado geoespacial (Streamlit + PyDeck WebGL)
El cuadro de mando operacional se implementó con Streamlit (v1.40+) y PyDeck / Deck.gl, optimizado para la renderización interactiva y fluida de las 2.579 celdas H3 en 2D y 3D (extrusión por volumen y presión turística), con soporte de almacenamiento en caché en memoria (st.cache_data / st.cache_resource) y conexión pooling a Azure PostgreSQL.
* Renderizado nativo y fluido de los 2.579 polígonos hexagonales H3 en 2D y 3D (con extrusión topográfica mediante el MDT05 o por variables analíticas) sin colapsar el navegador del cliente.
* Interoperabilidad directa con los pipelines analíticos en Python (regresión espacial MGWR, clustering HDBSCAN, modelos vectoriales y LLM).
* Despliegue ágil en contenedores Docker sin costes de licenciamiento por usuario.
La capa de datos conecta con Azure PostgreSQL mediante SQLAlchemy, empleando almacenamiento en caché en memoria (@st.cache_data) para mantener latencias inferiores a 200 ms ante cambios de filtros. Para mitigar distorsiones visuales generadas por valores atípicos extremos en variables asimétricas, como la densidad hotelera o el brillo nocturno VIIRS, el módulo color_scales.py calibra dinámicamente las rampas continuas entre los percentiles P1 y P99. La experiencia de usuario incorpora animaciones CSS de carga suave, tarjetas métricas con micro elevación interactiva (hover) y un asistente conversacional anclado mediante position: fixed.

## 7.2. Vistas especializadas y diagnóstico estratégico multiescala

La plataforma articula 10 páginas modulares: (1) Resumen y Diagnóstico Macro (KPIs insulares de capacidad de carga y saturación); (2) Visor Cartográfico Multicapa (conmutación micro H3 y macro municipal con capas de satélite, clima y accesibilidad); (3) Matriz de Oportunidades y Arquetipos TUI (cuadrantes bidimensionales de potencial PTNA vs. saturación); y (4) Monitores Sectoriales de microeconomía municipal y auditoría alojativa.
* Resumen y Diagnóstico Macro (summary.py): Radiografía insular consolidada que desglosa el régimen de protección del suelo (46,8 % en Espacios Naturales Protegidos vs 51,7 % sin restricción legal), balance alojativo municipal y celdas con cobertura de sentimiento.
* Visor Cartográfico Multicapa (map_layers.py): Permite conmutar entre la malla micro espacial H3 (PTNA, Score ESG, Eje 1 de saturación, Eje 2 de oportunidad rural, sentimiento divergente y arquetipos) y la capa meso municipal (12 indicadores: desempleo, plazas por 1.000 hab., ingresos VV y presión residencial). Integra overlays de infraestructuras críticas: isócronas viales ORS (15 a 60 min), red y paradas de guaguas GTFS TITSA, 67 estaciones agroclimáticas de Agrocabildo y Bienes de Interés Cultural (BIC). Al hacer clic en cualquier celda, se despliega la Ficha de Detalle Territorial (detail_panel.py), contrastando los KPIs locales frente a la media municipal e insular.
* Matriz de Oportunidades y Arquetipos TUI (arquetipos.py): Posiciona el territorio en los cuadrantes estratégicos de descompresión (Eje 1 vs Eje 2) y clasifica la isla en 5 arquetipos de producto (Sol y playa, Ecoturismo rural, Cultural y patrimonial, Aventura y activo, Bienestar y salud), aportando un diagnóstico DAFO y directrices de inversión.
* Monitores Sectoriales y Exploración Tabular: Vistas de microeconomía municipal (municipios.py), clima en tiempo real (clima.py), oferta alojativa y tópicos BERTopic (alojamiento.py, temas.py), coyuntura turística ISTAC y tráfico aéreo AENA (turismo.py), junto con tablas avanzadas de descarga CSV (table_view.py) y rankings insulares (rankings.py).

## 7.3. Simulador territorial de políticas turísticas (simulador.py)

El Simulador de Decisiones (simulador.py) modela dinámicamente el desvío de flujos turísticos (10–20 %) recalculando instantáneamente la presión costera, la inyección económica en medianías y el impacto en celdas de alta fragilidad ecológica mediante alertas en tiempo real.

## 7.4. Asistente conversacional con fundamentación territorial (asistente.py)

Accesible desde un botón flotante en cualquier punto de la aplicación, el asistente conversacional integra un mecanismo de anclaje territorial contextual: si el usuario tiene una celda H3 seleccionada en el mapa, el sistema inyecta automáticamente sus atributos locales en el prompt (PROMPT_CONTEXTO_HEXAGONO), resolviendo consultas sobre la zona en pocos segundos. Para preguntas complejas o cuantitativas, el asistente deriva la petición al router inteligente, activando la síntesis cualitativa RAG o la ejecución de consultas seguras Text-to-SQL sobre la capa Gold de Postgre.

# 8. Conclusiones: Respuesta a las Preguntas de TUI y Valor Diferencial


## 8.1. Respuesta Fundamentada a las Siete Preguntas del Briefing de TUI Group

La plataforma responde de manera directa, cuantitativa y accionable a las siete cuestiones estratégicas planteadas por TUI Group:

| Nº | Pregunta Estratégica de TUI | Metodología de Resolución | Diagnóstico y Hallazgo Clave |
| :--- | :--- | :--- | :--- |
| P1 | ¿Dónde se localizan con exactitud las zonas saturadas? | Malla H3 micro espacial (res 8, 2.579 celdas) + radiancia nocturna VIIRS DNB. | El 78,4 % de las plazas alojativas se concentra en solo 82 hexágonos (3,1 % de la superficie insular), focalizados en Playa de las Américas, Los Cristianos y Costa Adeje, con radiancia VIIRS >65 nW/cm²/sr y colapso de las arterias TF-1 y TF-5 (>85 % de los viajes diarios). |
| P2 | ¿Qué zonas tienen alto potencial pero baja visibilidad? | Clustering HDBSCAN + Índice de Potencial Turístico (PTNA) con MGWR. | Medianías del norte y cumbres intermedias (Icod de los Vinos, Buenavista del Norte, Vilaflor y La Orotava) presentan alto PTNA, elevado NDVI (>0,6) y gran satisfacción turística, pero concentran menos del 10 % de la oferta reglada. |
| P3 | ¿Qué comarcas rurales tienen condiciones para absorber demanda? | Modelo topoclimático (inversión 800–1.500 m) + NDVI + Marco ESG (PTNA > 0, ESG > 60). | Se aíslan exactamente 247 hexágonos de oportunidad ideal (9,6 % de la isla) en medianías protegidas del estrés térmico estival, compatibles con la capacidad de carga ecológica y con baja afección a avifauna protegida. |
| P4 | ¿Cómo influye la accesibilidad en el éxito de zonas no costeras? | Matriz vial ORS (18 destinos, isócronas 15–60 min) + red GTFS TITSA multiumbral (200/500/1.000 m). | El modelo MGWR estima una severa penalización por aislamiento vial (β_tiempo = -4,50). Los microdestinos viables exigen conexión a <45 min de un aeropuerto y servicio regular de transporte público comarcal. |
| P5 | ¿Qué áreas muestran señales de congestión? | Índice continuo de saturación (Eje 1): densidad de plazas/km² (p95) + quejas NLP + VIIRS. | Los núcleos de Playa de las Américas y Puerto Colón superan las 250 plazas/km², disparando alertas tempranas por sobrecarga de infraestructuras y fricción comunitaria. |
| P6 | ¿De qué se quejan los turistas en el sur y qué buscan en el interior? | Inferencia multilingüe XLM-RoBERTa + BERTopic centrado en idiomas + minería PyABSA. | En el litoral sur predominan quejas de ruido nocturno, masificación y atascos (NSS +0,48); en el interior y medianías los viajeros buscan tranquilidad, naturaleza y autenticidad gastronómica (NSS +0,74), con quejas leves sobre curvas o accesos. |
| P7 | ¿Qué impacto tendría redistribuir un 10–20 % de la masa turística? | Simulador territorial interactivo What-If (app/simulador.py) calibrado con sensibilidades MGWR v3. | El trasvase simulado de 13.800 a 27.600 plazas (10–20 % de las 137.951 plazas de Adeje y Arona) hacia municipios de medianías y norte (Icod, Vilaflor, Buenavista) reduce directamente el Eje 1 de Saturación en el litoral sur e incrementa el potencial de atracción rural (PTNA y Eje 2), impulsado por la sensibilidad al entorno ambiental (β_NDVI = +220,0). El simulador bloquea automáticamente cualquier incremento de plazas en celdas con Espacio Natural Protegido (pct_area_enp > 0) o pendientes >25°, y activa alertas de capacidad de carga si la densidad en destino supera el percentil 95 insular (>250 plazas/km²), garantizando una redistribución sin sobreexplotación ecológica. |


Tabla 4. Respuesta a las preguntas estratégicas de TUI

## 8.2. Recomendaciones Estratégicas y Hoja de Ruta para TUI Group

A partir de los hallazgos analíticos y espaciales, se formulan cuatro directrices de acción inmediata para la operativa de TUI Group en Tenerife:
* Lanzamiento de la Línea de Producto "Tenerife Auténtico / Ecoturismo y Bienestar": Desempaquetar la oferta masiva de sol y playa creando una cartera orientada a estancias de media y larga duración en alojamientos singulares de medianías (Icod de los Vinos, Vilaflor, Buenavista del Norte y comarca de Acentejo), donde el sentimiento neto es superior (+0,74) y el atractivo ambiental está demostrado (PTNA > 70).
* Incentivo Comercial Dinámico de Dispersión Territorial: Implementar en el motor de reservas y en los canales de venta de TUI un sistema de bonificaciones tarifarias o servicios añadidos (ej. seguro de viaje o experiencias gastronómicas incluidas) para aquellos clientes que elijan municipios de oportunidad en periodos de máxima saturación costera.
* Corredores de Conectividad Sostenible: Establecer acuerdos de transporte discrecional colectivo o rutas de movilidad compartida con TITSA que conecten directamente los aeropuertos insulares (TFS/TFN) con las cabeceras de medianías en menos de 45 minutos, mitigando la dependencia del vehículo de alquiler y la sobrecarga en las autopistas TF-1 y TF-5.
* Adopción del AI-Dashboard en la Mesa de Contratación Hotelera: Institucionalizar el uso del simulador territorial y las alertas de capacidad de carga como filtro previo obligatorio antes de formalizar nuevos contratos hoteleros o cupos de plazas, garantizando el cumplimiento de los criterios ESG insulares.

## 8.3. Limitaciones del Estudio y Líneas de Investigación Futuras

El estudio presenta cuatro limitaciones operativas: (1) Falta de microdatos de telefonía móvil por secreto estadístico, suplida con proxies satelitales VIIRS y transporte GTFS; (2) Sesgo de muestreo en plataformas OTAs (sobrerrepresentación del turista anglosajón y germano), mitigado mediante ponderación c-TF-IDF multilingüe; (3) Fricción de accesibilidad calculada en flujo libre por restricciones de API histórica de tráfico; y (4) Desfase trimestral en series socioeconómicas del ISTAC frente a la inmediatez de sensores meteorológicos.
* Como líneas futuras prioritarias se propone: integrar trazas GPS anonimizadas de flotas de alquiler, desplegar gemelos digitales hidrológicos sobre consumo de agua por cama turística y conectar el asistente RAG con el motor transaccional de reservas de TUI.

# Referencias bibliográficas

Agencia Espacial Europea (ESA). (2024). Copernicus Sentinel-2: Multispectral imagery and land monitoring data. European Space Agency. https://sentinels.copernicus.eu
Armbrust, M., Ghodsi, A., Xin, R., y Zaharia, M. (2021). Lakehouse: A new generation of open platforms that unify data warehousing and advanced analytics. Proceedings of CIDR 2021, 1–8.
Cabildo de Tenerife. (2024). Red agrometeorológica insular de Agrocabildo: datos horarios y metadatos de estaciones. Cabildo Insular de Tenerife. https://www.agrocabildo.org
dbt Labs. (2024). dbt Core Documentation: Transformation workflow and data modeling (Version 1.8). dbt Labs Inc. https://docs.getdbt.com
Elvidge, C. D., Baugh, K., Zhizhin, M., Hsu, F. C., y Ghosh, T. (2017). VIIRS night-time lights. International Journal of Remote Sensing, 38(21), 5860–5879. https://doi.org/10.1080/01431161.2017.1342050
Horn, B. K. P. (1981). Hill shading and the reflectance map. Proceedings of the IEEE, 69(1), 14–47. https://doi.org/10.1109/PROC.1981.11918
Instituto Canario de Estadística (ISTAC). (2025). Encuesta de Gasto Turístico, FRONTUR-Canarias y Municipios en Cifras (C00067A). Gobierno de Canarias. https://www.gobiernodecanarias.org/istac/
Milano, C., Novelli, M., y Cheer, J. M. (2019). Overtourism and degrowth: A social movements perspective. Journal of Sustainable Tourism, 27(12), 1857–1875. https://doi.org/10.1080/09669582.2019.1650054
Openshaw, S. (1984). The Modifiable Areal Unit Problem. Concepts and Techniques in Modern Geography, 38. Geo Books.
PostGIS Project. (2024). PostGIS: Spatial and Geographic Objects for PostgreSQL (Version 3.4). https://postgis.net
Turismo de Canarias. (2025). Estrategia de turismo regenerativo RegNext 2025–2030. Promotur Turismo Canarias. https://www.turismodeislascanarias.com
Turismo de Tenerife. (2025). Informe de coyuntura turística insular: Año 2024. Cabildo Insular de Tenerife. https://www.webtenerife.com
Uber Technologies. (2018). H3: Hexagonal Hierarchical Spatial Index (Version 4.1). Uber Open Source. https://h3geo.org

# Anexos

Nota metodológica: Los siguientes anexos recogen las especificaciones técnicas, los catálogos de datos, el linaje dbt de la arquitectura medallón, los scripts de analítica avanzada, los cuadernos de análisis exploratorio (EDA), las métricas empíricas de los modelos y el manual de despliegue reproducible. Según la normativa de la UCM, estos anexos no computan dentro del límite estricto de 20 páginas de la memoria principal.

## Anexo A – Repositorio de Código Fuente, Control de Versiones y Gobernanza

El código fuente completo, los pipelines de ingesta, los modelos dbt y el cuadro de mando operacional se encuentran bajo control de versiones en GitHub: https://github.com/TFM-Pytones/AI_Dashboard_Core. Los tutores del máster, Carlos Ortega y Santiago Mota, disponen de permisos de lectura para la evaluación académica. La estructura del repositorio articula una jerarquía modular desacoplada:
AI_Dashboard_Core/
├── ingestion/           # Módulos 01-07: ISTAC, Agrocabildo, Sentinel-2, VIIRS, GTFS, YouTube, Booking, TripAdvisor
├── dbt_project/         # Pipeline Medallón: models/bronze, models/silver, models/gold, macros y schema tests
├── analytics/           # Pipelines de Machine Learning y NLP:
│   ├── sentiment/       # Clasificación multilingüe con XLM-RoBERTa y filtro zero-shot mDeBERTa
│   ├── aspects/         # Minería de aspectos PyABSA-ATEPC y normalización a 6 dimensiones
│   ├── topics/          # BERTopic multilingüe (Modelos A y B) con centrado vectorial
│   ├── clustering/      # Segmentación espacial HDBSCAN y normalización MinMax
│   ├── accesibilidad/   # Matrices de conducción vial ORS y distancias a red GTFS TITSA
│   ├── mgwr/            # Regresión Geográfica Ponderada Multiescala (MGWR v3) e índice PTNA
│   ├── rag/             # Motor RAG híbrido (chunking, embeddings MPNet 768d, HNSW, BM25, RRF)
│   └── chat/            # Router LLM determinista y motor Text-to-SQL con validación AST
├── app/                 # Cuadro de mando operacional en Streamlit (v1.40+) y PyDeck (WebGL 2D/3D):
│   ├── main.py          # Punto de entrada con navegación nativa st.navigation (10 páginas)
│   ├── map_layers.py    # Visor cartográfico microespacial H3 y mesomunicipal con extrusión MDT05
│   ├── detail_panel.py  # Ficha técnica interactiva por hexágono con benchmarking territorial
│   ├── simulador.py     # Simulador What-If de redistribución de flujos y alertas de capacidad
│   └── asistente.py     # Asistente conversacional contextual anclado al hexágono activo
├── notebooks/           # Cuadernos Jupyter con análisis exploratorios (EDA) y calibraciones físicas
├── docs/                # Diccionarios de datos, arquitectura medallón y memoria completa
└── tests/               # Batería de pruebas unitarias y de integración con pytest

## Anexo A2 – Catálogo de Fuentes Ingestadas en el Data Lakehouse

La solución ingiere diez fuentes heterogéneas consolidadas en Microsoft Azure PostgreSQL con PostGIS. La tabla siguiente detalla los volúmenes brutos y depurados de cada proveedor:

| Fuente / Proveedor | Tipología de Dato | Volumen Bruto (Bronze) | Volumen Depurado (Silver) | Aportación al Caso de Negocio |
| :--- | :--- | :--- | :--- | :--- |
| ISTAC (Gobierno de Canarias) | Microdatos socioeconómicos y demanda | 2 recursos REST (C00067A y C00065A) | 24 indicadores municipales (31 términos) | Series de empleo, pernoctaciones, ocupación hotelera y vivienda vacacional |
| Cartografía (GRAFCAN / Cabildo) | Vectores institucionales (GeoJSON) | 5 coberturas oficiales insulares | 31 mun., 125 BIC, 31 ofic., 17 ZT, 43 ENP | Delimitación territorial, atractores patrimoniales y restricciones legales de suelo |
| MDT25 / MDT05 (GRAFCAN / IGN) | Raster altimétrico (25 m / 5 m) | Raster insular continuo | Altura, pendiente, aspecto y sombreado zonal | Caracterización geomorfológica, aptitud constructiva y confort térmico solar |
| GTFS (TITSA / Tranvía de Tenerife) | Red de transporte público regular | 2,08 M registros brutos | 3.934 paradas, 183 líneas, 1,36 M pasos | Accesibilidad multimodal, proximidad a paradas e isócronas de guagua |
| Agrocabildo (Cabildo de Tenerife) | Sensórica meteorológica diezminutal | 136,4 M lecturas (67 estaciones) | 12,95 M registros limpios (57 estaciones) | Calibración microclimática: gradientes adiabáticos y mar de nubes (800–1.500 m) |
| Copernicus Sentinel-2 (ESA) | Teledetección multiespectral (20 m) | Composites trimestrales (2019–2026) | 46.422 observaciones agregadas a celdas H3 | Vigor vegetal (NDVI) y sellado de suelo construido (NDBI) por hexágono |
| NOAA/NASA VIIRS DNB | Radianza nocturna satelital (500 m) | Serie mensual DNB (2019–2026) | 241.648 observaciones limpias | Proxy físico cuantitativo de actividad económica, electrificación y saturación |
| LosViajeros.com | Comunidad online y foros de viajes | 167.274 mensajes (248 hilos) | 168.035 mensajes parseados y clasificados | Detección cualitativa de fricciones, rutas en interior y quejas de aparcamiento |
| YouTube Data API v3 | Opiniones en vídeo turístico | 3.100 comentarios (41 vídeos seleccionados) | 2.819 comentarios depurados | Percepción audiovisual de marca de destino y atractores clave |
| Booking.com y TripAdvisor | Reseñas geolocalizadas de alojamientos | >105.000 reseñas brutas | 74.695 opiniones depuradas (3.740 estab., 748 activ.) | Minería de aspectos y sentimiento georreferenciado en celdas H3 |




## Anexo A3 – Diccionario de Modelos de Negocio de la Capa Gold

La Capa Gold materializa trece modelos dimensionales optimizados para el consumo analítico, la regresión espacial MGWR, el asistente RAG y el renderizado WebGL en el AI-Dashboard:

| Modelo Gold | Granularidad Espacial | Contenido Principal y Variables Analíticas Clave |
| :--- | :--- | :--- |
| gold.gold_h3_master | H3 Res 8 (2.579 celdas) | Tabla maestra microespacial: >60 variables biofísicas, topoclimáticas, de movilidad ORS/GTFS, oferta alojativa y NLP |
| gold.gold_h3_sentimiento | H3 Res 8 (410 celdas) | Polaridad media (-1 a +1), volumen de opiniones por canal (Booking/TripAdvisor) y queja modal negativa |
| gold.gold_h3_accesibilidad | H3 Res 8 (2.579 celdas) | Tiempos continuos ORS a 18 destinos clave (aeropuertos, Teide, hospitales) y distancias multiumbral a paradas GTFS |
| gold.gold_h3_ptna_v3 | H3 Res 8 (2.579 celdas) | Puntuación de atracción potencial PTNA calibrada con MGWR v3 y bandera de confianza estadística local |
| gold.gold_h3_esg_v1 | H3 Res 8 (2.579 celdas) | Evaluación ESG microespacial compuesta: Dimensión E (40 %), Dimensión S (30 %) y Dimensión G (30 %) |
| gold.gold_bloque5_h3_oportunidad_v1 | H3 Res 8 (2.579 celdas) | Posicionamiento en Eje 1 (Saturación) y Eje 2 (Oportunidad Rural), con flag de oportunidad ideal (PTNA>0, ESG>60) |
| gold.h3_clusters | H3 Res 8 (2.579 celdas) | 6 tipologías territoriales no paramétricas derivadas de HDBSCAN con probabilidad de asignación individual |
| gold.gold_municipio_master | Municipal (31 términos) | Capa mesomunicipal coroplética con 12 indicadores ISTAC, paro registrado, afiliaciones y presión residencial |
| gold.gold_municipio_anual / mensual | Municipal (31 términos) | Series históricas (2009–2026) de ocupación, viajeros y pernoctaciones hoteleras y extrahoteleras |
| gold.gold_turismo_hotelero_anual / mensual | Municipal (31 términos) | Indicadores de rentabilidad y precios hoteleros oficiales: tarifa media diaria (ADR) e ingresos por habitación (RevPAR) |
| gold.gold_aena_pasajeros | Aeroportuario (TFS/TFN) | Tráfico mensual de pasajeros de llegada y salida en aeropuertos insulares (2019–2026) con desglose internacional |
| gold.nlp_chunks | Documental (87.981 fragmentos) | Embeddings semánticos 768d (MPNet) con índices HNSW y BM25 para recuperación híbrida en el asistente RAG |
| gold.gold_isocronas_visuales | Polígonos vectoriales (24) | Geometrías de isócronas viales de 15, 30, 45 y 60 min hacia aeropuertos y Teide para renderizado fluido en Deck.gl |




## Anexo B – Variables de Entorno y Configuración del Sistema (.env.example)

El archivo .env.example en la raíz del proyecto documenta los parámetros de configuración y credenciales de acceso necesarios para reproducir el despliegue local o en la nube:

| Variable de Entorno | Tipo / Formato | Propósito Técnico y Servicio Asociado |
| :--- | :--- | :--- |
| AZURE_DB_URL | URI de conexión | Cadena SQLAlchemy para PostgreSQL Flexible Server en Azure (usuario, clave cifrada, host, puerto 5432 y sslmode=require) |
| AZURE_STORAGE_CONNECTION_STRING | Token secreto | Autenticación en Azure Blob Storage para persistencia masiva de artefactos Parquet, rasters y GeoJSON |
| GROQ_API_KEY | API Token | Credencial de acceso a Groq Cloud para inferencia ultrarrápida LPU ejecutando el modelo openai/gpt-oss-120b |
| ORS_API_KEY | API Token | Token de OpenRouteService v7.0 para el cálculo determinista de matrices de tiempo e isócronas viales |
| MAPBOX_API_KEY | API Token público | Clave de acceso a Mapbox GL para la carga de mapas base vectoriales oscuros y satelitales en PyDeck |
| YOUTUBE_API_KEY | API Token | Clave de Google Cloud Platform para la extracción automatizada de comentarios turísticos vía YouTube Data API v3 |
| DBT_PROFILES_DIR | Ruta de directorio | Directorio local de configuración de dbt Core conteniendo el archivo profiles.yml |
| POSTGRES_MAX_CONNECTIONS | Entero (int) | Límite del pool de conexiones para FastAPI y Streamlit (por defecto: pool_size=10, max_overflow=20) |




## Anexo C – Esquemas SQL, Linaje de Medallón y Modelos dbt Core

La capa de transformación dbt articula 48 tablas Bronze en 28 modelos Silver y 13 modelos Gold, orquestando el linaje de datos de extremo a extremo con estricta gobernanza e índices espaciales PostGIS. A continuación se recogen los extractos técnicos y modelos canónicos referenciados en los capítulos de la memoria:

### Anexo C.1 – Asignación y Fallback Espacial de Coordenadas (silver_alojamientos_oficiales.sql)

El modelo dbt silver_alojamientos_oficiales.sql unifica la oferta reglada del Gobierno de Canarias y resuelve la cartografía oficial priorizando las coordenadas geocodificadas del lookup espacial sobre las del registro cuando presentan inconsistencias o nulos:
-- dbt_project/models/silver/alojamiento/silver_alojamientos_oficiales.sql
{{ config(materialized='table', indexes=[{'columns': ['geometry'], 'type': 'gist'}]) }}

WITH source_data AS (
    SELECT establecimiento_id, establecimiento_nombre_comercial AS nombre, direccion_municipio_nombre AS municipio,
           plazas, longitud, latitud, 'hotel' AS tipo_alojamiento
    FROM {{ source('bronze', 'bronze_registro_hoteles') }}
    UNION ALL
    SELECT establecimiento_id, establecimiento_nombre_comercial, direccion_municipio_nombre, plazas, longitud, latitud, 'extrahotelero'
    FROM {{ source('bronze', 'bronze_registro_extrahoteleros') }}
    UNION ALL
    SELECT establecimiento_id, establecimiento_nombre_comercial, direccion_municipio_nombre, plazas, longitud, latitud, 'vivienda_vacacional'
    FROM {{ source('bronze', 'bronze_registro_viviendas_vacacionales') }}
),
lookup AS (
    SELECT establecimiento_id, longitud_geocoded, latitud_geocoded
    FROM {{ source('bronze', 'bronze_registro_geocoding_lookup') }}
),
cleaned AS (
    SELECT
        s.establecimiento_id AS id,
        s.nombre, s.municipio, s.tipo_alojamiento, s.plazas,
        -- Fallback Robusto: 1) Geocodificador verificado 2) Coordenada original limpia del registro
        COALESCE(CAST(l.longitud_geocoded AS NUMERIC), CAST(NULLIF(TRIM(REPLACE(CAST(s.longitud AS VARCHAR), ',', '.')), '') AS NUMERIC)) AS longitud,
        COALESCE(CAST(l.latitud_geocoded AS NUMERIC), CAST(NULLIF(TRIM(REPLACE(CAST(s.latitud AS VARCHAR), ',', '.')), '') AS NUMERIC)) AS latitud
    FROM source_data s
    LEFT JOIN lookup l ON CAST(s.establecimiento_id AS VARCHAR) = CAST(l.establecimiento_id AS VARCHAR)
)
SELECT id, nombre, municipio, tipo_alojamiento, plazas, longitud, latitud,
    CASE
        WHEN longitud BETWEEN -16.95 AND -16.09 AND latitud BETWEEN 27.97 AND 28.59
        THEN ST_SetSRID(ST_MakePoint(longitud, latitud), 4326)
        ELSE NULL
    END AS geometry
FROM cleaned;

### Anexo C.2 – Interpolación Espacial Topoclimática y Gradiente Térmico (silver_clima y gold_h3_master.sql)

La interpolación microclimática calcula la temperatura y humedad en cada celda H3 combinando ponderación por distancia inversa cuadrática (IDW k=3) desde las 67 estaciones de Agrocabildo, corregida por gradiente adiabático vertical (-0,0065 °C/m) y amortiguación litoral:
-- Extracto de dbt_project/models/gold/gold_h3_master.sql (Lógica Topoclimática)
h3_vecinos_clima AS (
    SELECT h.h3_index, h.h3_altitud, h.h3_aspect, h.h3_dist_costa_km, est.*,
           1.0 / POWER(GREATEST(ST_Distance(ST_Transform(h.geometry, 32628), ST_Transform(est.geometry, 32628)), 1), 2) AS peso
    FROM h3_con_topografia h
    CROSS JOIN LATERAL (
        SELECT * FROM estaciones_con_topografia e
        ORDER BY h.geometry <-> e.geometry LIMIT 3
    ) est
),
h3_clima AS (
    SELECT h3_index,
        -- Temperatura anual corregida por gradiente altitudinal y distancia a la costa
        SUM((temp_media_anual + COALESCE((station_altitud - h3_altitud) * 0.0065, 0)) * peso) / NULLIF(SUM(peso), 0) AS temp_media_anual,
        SUM((temp_media_q1 + COALESCE((station_altitud - h3_altitud) * 0.0065, 0) - ((h3_dist_costa_km - station_dist_costa_km) * 0.15)) * peso) / NULLIF(SUM(peso), 0) AS temp_media_q1,
        SUM((amplitud_termica_media + GREATEST((h3_dist_costa_km - station_dist_costa_km) * 0.30, 0)) * peso) / NULLIF(SUM(peso), 0) AS amplitud_termica_media,
        SUM((humedad_media_anual * (factor_hum_h3 / NULLIF(factor_hum_est, 0.001))) * peso) / NULLIF(SUM(peso), 0) AS humedad_media_anual
    FROM h3_vecinos_clima_factores
    GROUP BY h3_index
)

### Anexo C.3 – Consolidación Espacial de Sentimiento y Quejas Modales en Malla H3 (gold_sentimiento_h3.sql)

El modelo gold_sentimiento_h3.sql materializa la agregación microespacial en resolución 8, calculando la nota afectiva media y extrayendo la queja modal predominante condicionada estrictamente a menciones cualitativas de polaridad negativa:
-- dbt_project/models/gold/gold_sentimiento_h3.sql
{{ config(materialized='table') }}

WITH opiniones_geocodificadas AS (
    SELECT 
        h3_index,
        score_sentimiento,
        source
    FROM {{ ref('silver_sentiment_results') }}
    WHERE h3_index IS NOT NULL AND is_relevant = true
),
quejas_negativas AS (
    SELECT 
        h3_index,
        aspecto_normalizado,
        COUNT(*) AS menciones,
        ROW_NUMBER() OVER (
            PARTITION BY h3_index 
            ORDER BY COUNT(*) DESC
        ) AS ranking_queja
    FROM {{ ref('silver_aspect_results') }}
    WHERE polaridad_aspecto = -1 AND h3_index IS NOT NULL
    GROUP BY h3_index, aspecto_normalizado
)
SELECT 
    m.h3_index,
    ROUND(AVG(o.score_sentimiento)::numeric, 3) AS sentimiento_medio,
    COUNT(o.score_sentimiento) AS n_resenas_sentimiento,
    COUNT(CASE WHEN o.source = 'booking' THEN 1 END) AS n_resenas_booking,
    COUNT(CASE WHEN o.source = 'tripadvisor' THEN 1 END) AS n_resenas_tripadvisor,
    COALESCE(q.aspecto_normalizado, 'Sin quejas críticas') AS queja_principal
FROM {{ ref('gold_h3_master') }} m
LEFT JOIN opiniones_geocodificadas o ON m.h3_index = o.h3_index
LEFT JOIN quejas_negativas q ON m.h3_index = q.h3_index AND q.ranking_queja = 1
GROUP BY m.h3_index, q.aspecto_normalizado;

### Anexo C.4 – Matriz de Gobernanza y Pruebas de Calidad de Datos (dbt test)

La integridad, unicidad y consistencia referencial del Lakehouse se audita mediante una suite de más de 200 pruebas declaradas en archivos schema.yml, ejecutadas de forma automatizada en CI/CD y en la orquestación de Airflow:

| Capa de Datos | Tipología de Prueba dbt | Entidades / Campos Auditados | Criterio de Validación / Aceptación |
| :--- | :--- | :--- | :--- |
| Bronze (Raw) | unique & not_null | bronze_registro_*, bronze_clima_*, bronze_aena_* | Claves primarias compuestas y hash de fila no nulos. |
| Bronze (Raw) | accepted_values | Canales de fuentes, códigos de isla ('Tenerife') | Filtrado estricto contra inyecciones o registros fuera de ámbito. |
| Silver (Limpieza) | not_null & dbt_expectations | silver_alojamientos_oficiales (geometry, municipio) | 100 % de alojamientos con geometría válida ST_IsValid. |
| Silver (Limpieza) | expression_is_true | silver_clima_agrocabildo (temp, lluvia, viento) | Rangos físicos: Temp ∈ [-5, 45] °C; Lluvia ≥ 0 mm; Rad ≥ 0 W/m². |
| Silver (Limpieza) | unique & not_null | silver_h3_grid (h3_index, geometry) | Exactamente 2.579 celdas terrestres sin solape ni duplicidad. |
| Gold (Negocio) | relationships (FK) | gold_sentimiento_h3, gold_arquetipos_tui -> gold_h3_master | Integridad referencial total: ninguna métrica huérfana de celda. |
| Gold (Negocio) | expression_is_true | gold_h3_master (ptna_score, score_esg, crowding_index) | Variables normalizadas en escala acotada [0, 100]. |
| Gold (Negocio) | not_null | gold_municipio_master (cod_municipio, nombre_municipio) | Completitud de los 31 términos municipales de la isla. |




## Anexo D – Catálogo de Scripts y Pipelines de Analítica Avanzada

El directorio analytics/ estructura los pipelines especializados del proyecto. Cada componente está modularizado y desacoplado para su ejecución independiente o mediante DAG de Airflow:

| Script / Módulo | Área Técnica | Descripción Operativa |
| :--- | :--- | :--- |
| analytics/sentiment/batch_inference.py | NLP / Sentimiento | Inferencia multilingüe por lotes (batch 32) con XLM-RoBERTa y filtro zero-shot mDeBERTa |
| analytics/aspects/batch_inference.py | NLP / Aspectos | Extracción simultánea de términos de experiencia y polaridad con PyABSA-ATEPC |
| analytics/aspects/traducir_aspectos.py | NLP / Normalización | Traducción híbrida incremental y consolidación de >1.200 variantes léxicas a 6 dimensiones canónicas |
| analytics/topics/topic_modeling.py | NLP / Tópicos | Entrenamiento de BERTopic (Modelos A y B), centrado de embeddings multilingües y asignación c-TF-IDF |
| analytics/clustering/build_features.py | Spatial ML | Normalización MinMax, reducción dimensional PCA (50 componentes) y clustering espacial HDBSCAN |
| analytics/accesibilidad/gold_h3_accesibilidad.py | Movilidad / Grafos | Cálculo de matrices de fricción espacial vial ORS e isócronas multiumbral a paradas GTFS TITSA |
| analytics/mgwr/04_run_model.py | Econometría Espacial | Ajuste de Regresión Geográfica Ponderada Multiescala (MGWR v3) y cálculo de anchos de banda locales |
| analytics/rag/index_nlp_chunks.py | IA Generativa / RAG | Fragmentación recursiva y generación de embeddings semánticos de 768d con MPNet |
| analytics/rag/rag_answer.py | IA Generativa / RAG | Motor de recuperación híbrida (HNSW + BM25 + Reciprocal Rank Fusion) y síntesis Groq LPU |
| analytics/chat/router_agent.py | Agentes / Text-to-SQL | Enrutador determinista con validación AST y generación segura de consultas analíticas sobre Capa Gold |




## Anexo E – Inventario de Cuadernos Jupyter y Análisis Exploratorio de Datos (EDA)

Las investigaciones empíricas preliminares, las auditorías de datos y la experimentación de modelos se organizan en cuadernos interactivos documentados:

| Cuaderno Jupyter (Notebook) | Objetivo Metodológico y Hallazgo Clave |
| :--- | :--- |
| notebooks/eda/EDA_Agrocabildo_Topoclima.ipynb | Modelado físico del gradiente altimétrico y caracterización de la capa de inversión térmica (mar de nubes a 800–1.500 m) |
| notebooks/eda/EDA_MDT_Costa_Valores_0.ipynb | Auditoría espacial de cotas de costa en el MDT05 y calibración de distancias continuas para corregir desfases de borde |
| notebooks/eda/EDA_Series_Temporales_ISTAC.ipynb | Descomposición estacional y modelado de series de ocupación y pernoctaciones hoteleras y vacacionales (2009–2026) |
| notebooks/nlp/nlp_sentimiento_2_1.ipynb | Experimentación de clasificadores de sentimiento multilingües, calibración de umbrales y cálculo de matrices de confusión |
| notebooks/nlp/nlp_aspectos_tarea_2_2.ipynb | Minería no estructurada de opiniones cualitativas y validación del diccionario canónico de 6 dimensiones de experiencia |
| notebooks/clustering/hdbscan_exploratorio.ipynb | Análisis de estabilidad de dendrogramas de HDBSCAN y ajuste del parámetro min_cluster_size ante densidades irregulares |




## Anexo F – Síntesis de Métricas y Validación Empírica de Modelos

La tabla siguiente consolida las métricas cuantitativas obtenidas en la evaluación de los modelos analíticos y predictivos:

| Dominio Analítico | Modelo / Técnica | Métricas Cuantitativas Obtenidas | Muestra / Validación |
| :--- | :--- | :--- | :--- |
| Clasificación de Sentimiento | XLM-RoBERTa + Zero-Shot | Macro F1 = 0,874 | Exactitud = 88,2 % | Precisión = 0,869 | Recall = 0,878 | 1.000 opiniones anotadas a mano |
| Descubrimiento de Tópicos | BERTopic (mpnet + c-TF-IDF) | Coherencia Cv = 0,71 | NMI lingüístico reducido de 0,218 a 0,031 tras centrado | Corpus completo (>55.000 textos) |
| Regresión Espacial Multiescala | MGWR v3 (Índice PTNA) | R² = 0,8272 | AICc = 3.914,6 | I de Moran residual = 0,0355 (p = 0,28) | 2.579 celdas terrestres H3 |
| Tipificación Territorial | HDBSCAN + PCA | Varianza explicada PCA = 81,5 % | 6 tipologías territoriales | 100 % cobertura insular | Malla insular completa |
| Recuperación y Generación RAG | HNSW + BM25 + Groq LPU | Faithfulness = 0,933 | Answer Relevance = 0,912 | Latencia P95 < 1,5 segundos | Benchmark RAGAS (50 consultas) |




## Anexo G – Topología de Airflow y Manual de Despliegue Reproducible


### Anexo G.1 – Topología de Tareas y Grafo de Dependencias de Apache Airflow

La orquestación general de datos se implementa en Apache Airflow 2.8 mediante el DAG historical_full_pipeline, estructurado en cinco fases secuenciales desacopladas con dependencias estrictas (TaskGroups):

| Fase del DAG | Tipo de Operador | Tareas e Interdependencias | Manejo de Fallos / Políticas |
| :--- | :--- | :--- | :--- |
| Fase 1: Ingesta Azure | BashOperator (Paralelo) | ingest_aena, ingest_alojamientos_oficiales, ingest_agrocabildo, ingest_geocoding, ingest_gtfs_titsa | Reintentos automáticos (retries=2, delay=5m). Tareas sin API externa se marcan con TriggerRule. |
| Fase 2: Postgres Bronze | BashOperator (Secuencial) | run_postgres_01_aena >> run_02_alojamientos >> run_03_agrocabildo >> run_04_booking >> run_05_gtfs >> run_06_clima >> run_07_resenas | Ejecución transaccional e inserción append-only preservando inmutabilidad del dato bruto. |
| Fase 3: dbt Silver | BashOperator (Paralelo) | dbt_run_silver_alojamiento, dbt_run_silver_clima, dbt_run_silver_espacial, dbt_run_silver_movilidad + dbt_test_silver | Casting, cruce espacial ST_Contains, filtrado insular y validación con 154 pruebas automáticas. |
| Fase 4: Analytics GPU | ShortCircuitOperator + PythonOperator | check_heavy_ml >> [batch_sentiment_inference, batch_aspect_extraction, train_bertopic_models, build_clustering_pca_hdbscan] | Condicionado por Variable run_heavy_ml=True. Si no hay GPU disponible, ejecuta pipeline aligerado. |
| Fase 5: dbt Gold & Index | BashOperator | dbt_run_gold_master >> dbt_run_gold_sentimiento >> dbt_run_gold_accesibilidad >> index_rag_faiss_mpnet >> notify_complete | Consolidación de las 13 tablas analíticas maestras e indexación vectorial HNSW para el RAG. |




### Anexo G.2 – Manual de Despliegue y Reproducibilidad en Entorno Limpio

Para reproducir el despliegue completo del sistema en un entorno limpio (Linux Ubuntu 22.04 LTS, macOS o Windows WSL2), se deben ejecutar de forma secuencial los siguientes ocho pasos operativos:
1. Clonación del repositorio y entorno virtual:
git clone https://github.com/TFM-Pytones/AI_Dashboard_Core.git && cd AI_Dashboard_Core
python3 -m venv .venv && source .venv/bin/activate  # En Windows: .venv\Scripts\activate
2. Instalación de dependencias del sistema y Python:
pip install --upgrade pip
pip install -r requirements.txt
3. Configuración de credenciales de entorno:
cp .env.example .env
# Rellenar las variables AZURE_DB_URL, GROQ_API_KEY, ORS_API_KEY y MAPBOX_API_KEY
4. Ingesta automatizada de fuentes de datos:
python ingestion/postgres/run_all_ingestion.py
5. Materialización de la arquitectura medallón con dbt Core:
cd dbt_project
dbt run --select silver.* && dbt run --select gold.*
cd ..
6. Ejecución de pipelines de NLP y analítica espacial:
python analytics/sentiment/batch_inference.py
python analytics/topics/topic_modeling.py
python analytics/clustering/build_features.py
python analytics/accesibilidad/gold_h3_accesibilidad.py
7. Indexación vectorial de fragmentos para el motor RAG:
python analytics/rag/index_nlp_chunks.py
8. Lanzamiento del AI-Dashboard interactivo:
streamlit run app/main.py --server.port 8501 --server.address 0.0.0.0