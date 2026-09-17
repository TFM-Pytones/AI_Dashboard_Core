"""
memoria_sections_part2.py
Capítulo 4 (Inteligencia Territorial y Machine Learning)
y Capítulo 5 (NLP y Percepción de Marca Destino).
Versión compacta — fórmulas y código movidos a Anexos.
"""


def get_chapter_4():
    return """# 4. Inteligencia Territorial, Modelado Espacio-Temporal y Machine Learning

## 4.1. Caracterización Físico-Territorial y Teledetección Satelital

La capacidad de carga de cada celda hexagonal se caracteriza mediante tres conjuntos de variables biofísicas:

**A. Variables Morfométricas (MDT25 del GRAFCAN, 25 m de resolución):** Elevación media (0 m en costa – 3.715 m en el Teide), pendiente media (1,2°–48,5°), orientación topográfica (*aspect*, discrimina barlovento/sotavento) y sombreado del relieve (*hillshade*). El operador diferencial de Horn (1981) sobre ventanas 3×3 píxeles calcula la pendiente *(SQL en Anexo C.2)*.

**B. Teledetección Biofísica — Copernicus Sentinel-2 (20 m, L2A):** Tenerife impide el enfoque estándar de una escena por mes: la *"panza de burro"* —banco de estratocúmulos que bloquea la vertiente norte entre 600 y 1.500 m durante 6–8 meses al año— dejaría el norte sin datos con un filtro simple de nubosidad <20 %. Adicionalmente, la calima sahariana no es detectada por el algoritmo SCL de Sentinel-2 y sesga el NDVI a la baja. La solución adoptada es el **composite de mediana trimestral** procesado en Google Earth Engine sobre la colección `COPERNICUS/S2_SR_HARMONIZED`, con un triple filtro de calidad en cascada a nivel de píxel: (1) máscara SCL que excluye nubes, cirrus y sombras (clases 1, 3, 8, 9 y 10); (2) umbral AOT < 0,3 DN para descartar aerosol sahariano; y (3) banda azul B02 < 0,18 como refuerzo anti-calima. El resultado son **30 composites trimestrales** (2019 Q1 – 2026 Q2) particionados en Azure Blob Storage con cobertura completa de los 2.579 hexágonos. Las variables derivadas calculadas directamente en GEE antes de la exportación son:

- **NDVI** (vigor fotosintético): de <0,15 en malpaíses áridos hasta >0,75 en la laurisilva de Anaga.
- **NDBI** (huella construida): de −0,45 en masa forestal densa hasta +0,38 en trama urbana compacta.

En `gold_h3_master` se consolidan los estadísticos anuales (2022–2026) y trimestrales (Q1–Q4) de NDVI, NDBI y el cambio porcentual de luz nocturna VIIRS respecto a 2022.

**C. Radianza Nocturna NOAA/NASA VIIRS (500 m, DNB):** Composites mensuales calibrados en nW/(cm²·sr) procedentes de GEE (`NOAA/VIIRS/DNB/MONTHLY_V1/VCMSLCFG`). Los polos turísticos del sur (Adeje, Arona) superan los 65 nW/(cm²·sr); las celdas de medianías caen por debajo de 4 nW/(cm²·sr). La serie Bronze cubre 90 meses (2019–2026); la capa Silver filtra desde 2022 para trabajar en la ventana post-pandemia homogénea.

| Variable | Rango Empírico en Tenerife |
| :--- | :--- |
| Elevación media | 0,0 m (costa) — 3.715,0 m (Teide) |
| Pendiente media | 1,2° (llanuras litorales) — 48,5° (barrancos de Masca/Anaga) |
| NDVI medio | 0,08 (malpaís/lava) — 0,82 (laurisilva en Anaga) |
| NDBI medio | -0,45 (masa forestal densa) — +0,38 (trama urbana compacta) |
| Radianza VIIRS | 0,2 nW/(cm²·sr) (cumbre Teide) — 88,4 nW/(cm²·sr) (Playa de Las Américas) |

## 4.2. Modelo Topoclimático Microinsular

El clima de Tenerife responde a cuatro forzadores atmosféricos simultáneos: los **vientos Alisios del Noreste** (masas de aire fresco y húmedo); la **inversión térmica de subsidencia** (800–1.500 m) que genera el Mar de Nubes; el **efecto Föhn en sotavento** (aire descendente que se calienta adiabáticamente, generando el clima árido del sur); y la **calima y advección sahariana** (invasiones de polvo que elevan la temperatura por encima de 32 °C y reducen la humedad por debajo del 25 %).

El modelo topoclimático, implementado en `gold_h3_master.sql` como una cadena de CTEs (`clima_diario`, `estaciones_clima`, `estaciones_con_topografia`, `h3_vecinos_clima`, `h3_vecinos_clima_factores`, `h3_clima`), combina **interpolación IDW con k=3 estaciones** de la red de Agrocabildo (67 estaciones activas) ponderadas por distancia euclídea inversa cuadrática (`peso = 1 / d²`) y cuatro sistemas de corrección físicos aplicados simultáneamente al H3 de destino y a la estación de origen:

1. **Gradiente adiabático de temperatura:** La temperatura ajustada se calcula como `T_ajust = T_IDW + (elevación_estación − elevación_H3) × 0,0065 °C/m`. Las variaciones estacionales incorporan además un delta por diferencia de distancia a la costa (±0,05 a ±0,15 °C/km según trimestre).

2. **Factor de humedad por orientación de ladera y altitud:** El factor multiplicativo se construye distinguiendo barlovento (aspect 300°–90°, factor +1,05 a +1,25 según altitud), sotavento (aspect 90°–300°, factor 0,85) y cumbre seca (>1.500 m, factor 0,70). La franja costera (<1,5 km) añade +0,15 puntos de factor en cualquier orientación.

3. **Factor de precipitación por sombra de lluvia:** En barlovento <1.500 m el factor es 1,30 (orografía favorece la convección); en sotavento es 0,40 (efecto paraguas orográfico).

4. **Factor de viento por exposición:** La cara norte-noreste (aspect 0°–90°) recibe un multiplicador 1,20; el sotavento (180°–270°), 0,60; las cumbres (>2.000 m), 1,40.

5. **Indicadores ESG de extremos climáticos:** La capa `estaciones_clima` computa, por estación, los **días de ola de calor** (`temp_max ≥ 35 °C` + `humedad_min ≤ 30 %` + `dirección del viento 60°–200°` simultáneos), la **amplitud térmica media diaria** y las **horas de sol reales** según el estándar OMM (radiación medida ≥ 120 W/m²), desagregadas por trimestre. Estas variables se interpolan IDW al hexágono y alimentarán el **Índice ESG Territorial** *(pendiente de implementación, definición completa en el plan del proyecto, sección 5.3)*.

Este modelado físico determinista permite corregir las limitaciones de la interpolación euclídea simple en una orografía abrupta como la de Tenerife, capturando el gradiente térmico vertical y el marcado contraste barlovento-sotavento sin requerir una densificación artificial de sensores *(lógica SQL implementada en `gold_h3_master.sql`, extracto en Anexo C.2)*.

## 4.3. Accesibilidad Multimodal y Conectividad

La redistribución de flujos turísticos requiere conocer la accesibilidad real de cada celda hexagonal:

* **Matriz de Conducción Vial (OpenRouteService):** Tiempos de viaje en vehículo privado desde cada uno de los 2.579 hexágonos hacia **18 destinos estratégicos insulares**: aeropuertos TFS y TFN, Santa Cruz, Costa Adeje, Puerto de la Cruz, Teleférico del Teide, La Laguna, Candelaria, Los Gigantes, El Médano, Garachico, Anaga, Masca, Vilaflor, La Orotava, Güímar, Buenavista del Norte y Arico. Adicionalmente se generaron **isócronas de conducción** a 15, 30, 45 y 60 minutos desde ambos aeropuertos (`gold_isocronas_visuales.py`), materializadas en `gold.gold_h3_accesibilidad` y listas para visualización directa en el dashboard.

* **Cobertura en Transporte Público Regular (GTFS TITSA/Tranvía):** Recuento de paradas activas en tres umbrales escalonados: 200 m (proximidad estricta), 500 m (estándar cómodo) y 1.000 m (acceso amplio), más la distancia continua a la marquesina más cercana. La distancia al hospital comarcal más próximo actúa como indicador de acceso a servicios esenciales y alimenta la dimensión Social del Índice ESG.

## 4.4. Tablas Gold: Catálogo y Estructura

El conjunto de modelos Gold materializa en PostgreSQL el resultado de toda la cadena de transformaciones. Los **11 modelos Gold** del proyecto son:

| Modelo Gold | Contenido | Escala |
| :--- | :--- | :---: |
| `gold_h3_master` | >60 variables biofísicas, topoclimáticas, alojativas, NLP y de accesibilidad | H3 (2.579 celdas) |
| `gold_sentimiento_h3` | Sentimiento medio, volumen por fuente, queja modal | H3 |
| `gold_municipio_master` | Indicadores ISTAC, AENA, empleo y alojamiento | Municipal (31) |
| `gold_municipio_anual` | Series anuales de pernoctaciones, plazas y ocupación | Municipal |
| `gold_municipio_mensual` | Desestacionalización y estacionalidad mensual | Municipal |
| `gold_municipio_empleo` | Afiliaciones SS por sector (hostelería, autónomos, monocultivo) | Municipal |
| `gold_turismo_hotelero_anual` | KPIs hoteleros anuales (RevPAR, ADR, GOP) | Municipal |
| `gold_turismo_hotelero_mensual` | KPIs hoteleros mensuales con ARIMA de referencia | Municipal |
| `gold_aena_pasajeros` | Serie de pasajeros TFS/TFN (2019–2026) | Aeropuerto |
| `gold_h3_ptna` | Índice PTNA, coeficientes MGWR locales, `esg_territorial_score` *(pendiente)* | H3 |
| `gold_h3_clusters` | Arquetipos HDBSCAN, probabilidad de pertenencia, etiqueta de negocio | H3 |

`gold_h3_master` actúa como **tabla maestra** de la que derivan el simulador gravitatorio, el asistente RAG y todos los módulos del dashboard. Sus índices GiST en la geometría y su índice único en `h3_index` permiten resolver cruces espaciales complejos en 15–45 milisegundos.

## 4.5. Segmentación Espacial No Supervisada: HDBSCAN

### Motivación y elección del algoritmo

Los métodos de clustering convencionales presentan limitaciones críticas cuando se aplican a un territorio de morfología tan compleja como Tenerife:

* **K-Means:** Impone un número de clusters fijo de antemano y asume que todos tienen forma esférica y tamaño similar. En Tenerife, donde los polos turísticos del litoral son zonas compactas y muy densas mientras que las medianías agrícolas son extensas y difusas, K-Means los distorsiona sistemáticamente y no es capaz de señalar qué celdas son simplemente ruido geográfico.
* **DBSCAN Clásico:** Aunque detecta outliers, exige un único radio de densidad global (epsilon). Ante la heterogeneidad de densidades del territorio insular —desde las celdas hiperconcentradas de Adeje hasta los hexágonos dispersos de Vilaflor— este radio único falla: o bien fragmenta el litoral en cientos de clusters diminutos, o bien funde en un solo grupo todo el interior rural.
* **HDBSCAN (*Hierarchical Density-Based Spatial Clustering of Applications with Noise*, McInnes et al., 2017):** Construye una jerarquía completa de densidades a múltiples escalas y extrae los clusters estables como aquellos que persisten durante el mayor rango de densidad sin fragmentarse. Esto le permite identificar simultáneamente las zonas turísticas compactas del sur y los amplios corredores rurales del norte, asignando como ruido (cluster -1) las celdas que no encajan en ningún patrón coherente —generalmente celdas de transición entre zonas de alta montaña y el litoral árido—, lo que resulta ecológicamente significativo.

### Implementación y variables de entrada

A partir de las características normalizadas con `RobustScaler` en [`build_features.py`](file:///c:/Users/ROBERTO/Proyectos_Python/TFM_TUI_Tenerife/AI_Dashboard_Core/analytics/clustering/build_features.py), se construyó la matriz de entrada con diez variables por celda:

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

## 4.6. Regresión Geográfica Ponderada (MGWR) e Índice de Potencial de Nicho (PTNA)

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

A partir de los coeficientes locales de MGWR, se construyó el **Índice PTNA** (*Potential Tourism Niche Attraction*), una puntuación continua en escala [0, 100] que combina cinco dimensiones ponderadas por los pesos empíricos del modelo. El valor `ptna_score` se calcula como la diferencia entre la densidad de plazas esperada por el modelo y la observada: `ptna_score > 0` indica un hexágono con condiciones objetivamente superiores a su ocupación turística actual (oportunidad de inversión); `ptna_score < 0` señala zonas sobre-explotadas respecto a su vocación territorial (riesgo de overtourism).

1. **Atractivo Ambiental (35 %):** NDVI elevado (>0,55), horas de sol favorables (según OMM) y ausencia de contaminación lumínica nocturna (VIIRS <10 nW).
2. **Confort Climático (20 %):** Temperatura media anual entre 16 y 24 °C y humedad relativa modelada entre 50 % y 80 %, excluyendo las oscilaciones extremas de calima y sotavento.
3. **Baja Saturación Actual (25 %):** Densidad de plazas alojativas inferior al 10 % de la media insular y radianza nocturna VIIRS en el cuartil inferior.
4. **Reputación Cualitativa Positiva (10 %):** Sentimiento medio de reseñas superior a +0,60, aunque con volumen muestral aún reducido (indicador de potencial no explorado).
5. **Accesibilidad Razonable (10 %):** Tiempo de conducción inferior a 45 minutos hasta al menos uno de los dos aeropuertos y presencia de al menos una parada GTFS en radio de 1.000 m.

Las celdas con PTNA superior a 70 sobre 100 representan los **microdestinos prioritarios para TUI**: zonas con condiciones objetivamente favorables para el ecoturismo, el turismo rural de calidad y el senderismo, pero con una cuota de mercado actual casi nula. Geográficamente, se concentran en las medianías agrícolas de la vertiente norte (Garachico, Icod de los Vinos, La Guancha, Buenavista del Norte) y en los valles del sureste (Arico, Fasnia), coincidiendo con el Cluster 2 de HDBSCAN y validando la coherencia interna entre los dos enfoques analíticos.

### Línea de trabajo futura: Marco ESG Territorial

Como extensión directa del Índice PTNA, el proyecto tiene planificada la implementación del **Marco Multidimensional ESG Territorial** (`gold_h3_ptna.esg_territorial_score`, campo definido en esquema pero pendiente de materialización): una puntuación compuesta [0, 100] que evalúa cada hexágono en tres dimensiones —Medioambiental [E] (40 %): evolución temporal del NDVI, polución VIIRS, sellado NDBI y `dias_ola_calor_anual`; Social [S] (40 %): densidad alojativa, cobertura GTFS, distancia a hospital y quejas NLP de masificación; y Gobernanza [G] (20 %): ratio hotel/VV y presencia de BICs—. Esta métrica permitirá filtrar las oportunidades de inversión de TUI al cruce de alto PTNA y alto ESG, garantizando un retorno financiero compatible con la sostenibilidad ecológica y social de la isla.
"""


def get_chapter_5():
    return """# 5. Procesamiento del Lenguaje Natural y Percepción de Marca Destino

## 5.1. Corpus Multilingüe de Reseñas y Preprocesamiento

Para capturar la experiencia cualitativa del visitante, el proyecto estructuró un corpus de **más de 55.000 opiniones textuales** procedentes de cuatro fuentes complementarias:

| Fuente | Volumen | Cobertura |
| :--- | :---: | :--- |
| Booking.com | 38.412 reseñas | Desglose positivo/negativo, nota y fecha |
| TripAdvisor | 12.840 opiniones | Hoteles, restaurantes y actividades georreferenciadas |
| LosViajeros (foros) | 2.650 mensajes | Rutas, tráfico y masificación (textos extensos) |
| YouTube Data API v3 | 1.890 comentarios | Vídeos de viajes y experiencias en Tenerife |

El pipeline de preprocesamiento (`batch_inference.py`) aplica limpieza de URLs, normalización de espacios y filtrado por longitud mínima de texto (mínimo 3 caracteres).

## 5.2. Inferencia de Sentimiento Multilingüe (XLM-RoBERTa)

El pipeline de sentimiento opera en dos etapas secuenciales integradas en el DAG de Airflow (Fase 4, tasks `sentiment_batch_inference` y `sentiment_backfill_relevance`):

**Etapa 1 — Filtro de Relevancia Zero-Shot:** Antes de clasificar el sentimiento, un clasificador zero-shot `MoritzLaurer/mDeBERTa-v3-base-mnli-xnli` evalúa cada texto contra cuatro hipótesis: *"comentario sobre turismo en Canarias"*, *"comentario sobre el canal de YouTube"*, *"conversación personal no relacionada"* y *"spam o publicidad"*. Un texto se descarta si la hipótesis off-topic gana por un margen de confianza superior a 0,25, reduciendo el ruido del corpus sin descartar críticas válidas aunque sean negativas. El lote de clasificación zero-shot se procesa en grupos de 8 textos (la evaluación de 4 hipótesis simultáneas es intensiva en GPU).

**Etapa 2 — Clasificación de Sentimiento:** Se empleó el transformador **`cardiffnlp/twitter-xlm-roberta-base-sentiment`** (Barbieri et al., 2022). La inferencia por lotes de 32 documentos (máx. 256 tokens) produce tres probabilidades (positivo, neutro, negativo), de las que se deriva la puntuación continua:

`Score = (+1 · P_positivo) + (0 · P_neutro) + (-1 · P_negativo)`

Los resultados se persisten en `bronze.ml_sentiment_results` con la columna `is_relevant` (filtro zero-shot), `label`, `score`, `model_name` y `processed_at`. El diseño es **incremental**: en cada ejecución solo se procesan los textos cuyo `source_id` no existe aún en la tabla, sin reprocesar lo ya clasificado. La tabla es genérica (`source TEXT`) para absorber cualquier fuente futura sin cambiar el esquema.

Contrastado frente a 1.000 opiniones anotadas manualmente, el modelo alcanzó un **F1-score macro de 0,874** y una **exactitud global del 88,2 %**, superando ampliamente a clasificadores Naive Bayes y VADER (<72 %) *(métricas completas en Anexo F)*.

## 5.3. Minería de Aspectos (PyABSA-ATEPC)

La tarea de análisis de aspectos (*Aspect-Based Sentiment Analysis*, ABSA) se realiza con **PyABSA** (Yang y Li, 2023) en su modalidad ATEPC (*Aspect-Term Extraction and Polarity Classification* en un solo paso), orchestrada en la Fase 4 del DAG de Airflow (task `aspects_batch_inference`, `analytics/aspects/batch_inference.py`). El checkpoint empleado es `pyabsa-multilingual-ATEPC`, que detecta simultáneamente los términos de aspecto presentes en el texto y su polaridad.

Los resultados se persisten en `silver.aspect_results`. Mediante la tabla de traducción `gold.aspecto_traducciones`, más de 1.200 variantes lingüísticas detectadas en cinco idiomas se normalizan a **seis dimensiones canónicas**: *Limpieza*, *Servicio*, *Relación Calidad-Precio*, *Ubicación*, *Confort y Ruido*, y *Saturación e Instalaciones*.

El análisis exploratorio en el notebook `analytics/tarea2/nlp_aspectos_tarea_2_2.ipynb` y la normalización de términos en `traducir_aspectos.ipynb` precedieron a la implementación del pipeline de producción, garantizando la solidez del vocabulario canónico antes del procesamiento masivo.

## 5.4. Modelado de Tópicos No Supervisado (BERTopic)

Para descubrir los temas latentes sin categorías preconcebidas se articuló un pipeline con **BERTopic** (Grootendorst, 2022): embeddings semánticos de 768 dimensiones con `paraphrase-multilingual-mpnet-base-v2`, reducción UMAP a 5 dimensiones y clustering HDBSCAN con representación c-TF-IDF. Se implementaron **dos modelos especializados** con partición del corpus por disponibilidad de geolocalización:

* **Modelo A — Macro Insular** (`analytics/topics/topic_modeling.py`, ejecutable en CPU): Entrenado sobre YouTube (reseñas ya filtradas por relevancia en `silver.sentiment_results`) y mensajes de LosViajeros **sin ubicación detectada** (el 54 % del corpus de 1.590 mensajes sin coordenadas en `gold.geo_mentions`). Los tópicos identificados incluyen: atascos en TF-1/TF-5 (polaridad -0,62), masificación en playas del sur (-0,48), senderismo en Teide y Anaga (+0,81) y gastronomía en guachinches (+0,86). El modelo se persiste en `analytics/topics/bertopic_model/` para ejecuciones incrementales: en ejecuciones sucesivas solo se clasifican los documentos nuevos (`topic_model.transform`), sin reentrenar desde cero. Parámetros: `min_topic_size = 15`, `min_corpus_size_check = 500`.

* **Modelo B — Micro Geolocalizado** (`topic_modeling_geo_colab.ipynb`, requiere GPU): Entrenado en Google Colab sobre el corpus geolocalizados de Booking (38.412 reseñas) + TripAdvisor (12.840) + LosViajeros con coordenada detectada (46 % del corpus, ~730 mensajes). El corpus se exporta mediante `analytics/topics/export_geo_corpus.py`, se procesa en Colab y los resultados se reimportan a PostgreSQL con `import_geo_results.py`. Vincula cada tópico a su hexágono H3, permitiendo mapear: ruido nocturno y colas en piscinas en Adeje/Arona frente a sosiego, paisaje y vistas al mar en medianías del norte.

## 5.5. Integración del Sentimiento en la Malla H3

El modelo dbt `gold_sentimiento_h3.sql` computa por hexágono el `sentimiento_medio`, el volumen muestral por fuente y la **queja dominante** mediante `MODE() WITHIN GROUP (ORDER BY aspecto_normalizado)`. Los hallazgos estratégicos son:

* **Zona Sur (Adeje/Arona):** Nota global de Booking alta (8,2/10), pero queja principal `"ruido nocturno"` y `"masificación en piscina"`, con sentimiento medio penalizado (+0,48).
* **Medianías y Norte:** Sentimiento neto sensiblemente superior (+0,74); queja residual limitada a `"acceso por curvas"`. El ecoturismo de interior genera mayor fidelización y satisfacción neta en el cliente internacional.

*(La consulta SQL completa de `gold_sentimiento_h3.sql` se incluye en el Anexo C.3.)*
"""

