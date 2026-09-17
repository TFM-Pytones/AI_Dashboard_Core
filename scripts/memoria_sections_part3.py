"""
memoria_sections_part3.py
Capítulo 6 (IA Generativa y RAG), Capítulo 7 (Productivización Streamlit),
Capítulo 8 (Validación, ROI y Conclusiones), Referencias Bibliográficas (APA 7ª)
y Anexos Técnicos A–G.
Versión compacta — código completo en Anexos D.
"""


def get_chapter_6():
    return """# 6. Inteligencia Artificial Generativa, RAG Híbrido y Asistente Conversacional Inteligente

## 6.1. Arquitectura RAG Híbrida y Motor de Inferencia LPU (Groq API)

Para salvar la brecha operativa entre los modelos multidimensionales y la toma de decisiones ejecutiva en TUI sin incurrir en alucinaciones factuales, se implementó una arquitectura desacoplada gobernada por guardrails estrictos. Se descartó el aprovisionamiento de GPUs dedicadas en Azure Cloud (>900 USD/mes) en favor de la **API Cloud de Groq**, cuyos procesadores **LPU (Language Processing Unit)** ofrecen inferencia superior a **250 tokens/segundo**.

El motor seleccionado es **`openai/gpt-oss-120b`** (con *fallback* en `llama-3.3-70b-versatile`). Debido a que este modelo consume presupuesto interno en tokens de razonamiento (*thinking tokens*) antes de emitir texto, se calibraron techos específicos por tarea: `max_tokens=150` para el router, `max_tokens=1000` para Text-to-SQL y `max_tokens=1200` para informes ejecutivos, operando con $T = 0,0$ en tareas deterministas y $T = 0,4$ en síntesis narrativa. A través de `report_generator.py`, el sistema genera periódicamente memorias ejecutivas de tres párrafos (percepción global, fricciones críticas y oportunidades TUI) almacenadas en `gold.nlp_informe_global` bajo dos alcances: *Ámbito General* (Modelo A de BERTopic post-2022) y *Ámbito Alojamiento* (Modelo B, >38.000 opiniones).

## 6.2. Indexación Vectorial, Extracción Determinista y Fusión RRF

El motor RAG (`analytics/rag`) opera sobre un corpus de 87.981 fragmentos almacenados en `gold.nlp_chunks`. El 95,5 % de las reseñas tiene $\le 1.000$ caracteres y se ingiere de forma atómica para preservar la coherencia contextual; el 4,5 % restante se procesa mediante segmentación recursiva por oraciones (`CHUNK_SIZE = 800`, `CHUNK_OVERLAP = 100`). Cada fragmento se enriquece con metadatos de autor, fecha, valoración, tópico y su adscripción geoespacial (cruce PostGIS `ST_Contains` con celdas H3 de `gold_h3_master` para Booking/TripAdvisor y mención toponímica para foros).

* **Indexación Vectorial Densa:** Se empleó `sentence-transformers/paraphrase-multilingual-mpnet-base-v2` (768 dimensiones) indexado en PostgreSQL con `pgvector` HNSW ($m = 16, ef\_construction = 64, \text{distancia coseno } \Leftrightarrow$). Para evitar la degradación de recall ante filtros SQL selectivos, se activó el escaneo iterativo (`SET LOCAL hnsw.iterative_scan = 'relaxed_order'` con $ef\_search = 100$) sobre un CTE `MATERIALIZED`, reduciendo la latencia de 15 s a <40 ms.
* **Filtros Deterministas:** El módulo `filtros.py` extrae entidades toponímicas (resolviendo alias informales como "Las Américas" $\rightarrow$ Arona/Adeje), zonas protegidas y gentilicios plurales (*"los alemanes"*) mediante regex y diccionarios, eliminando la latencia y alucinaciones de un extractor LLM. Si la intersección estricta resulta vacía, relaja adaptativamente fechas conservando los filtros geográficos obligatorios.
* **Búsqueda Híbrida y Fusión RRF:** Combina la similitud semántica con búsqueda léxica BM25 (`ts_rank_cd` logarítmico sobre índice GIN) mediante *Reciprocal Rank Fusion*:
  $$RRF(d) = \sum_{m \in \{\text{sem},\, \text{lex}\}} \frac{1}{60 + \text{rank}_m(d)}$$
* **Balanceo de Corpus y Deduplicación:** Ante el monopolio de Booking (84 % del volumen bruto), `TOPES_POR_PERSPECTIVA` limita sus fragmentos a un máximo de 2 en preguntas de destino general, dando visibilidad a YouTube y foros. Se aplica deduplicación por hash de los primeros 200 caracteres normalizados para purgar réplicas anidadas en foros.

## 6.3. Guardrails Anti-Alucinación y Asistente Dual (Router + Text-to-SQL)

Para erradicar respuestas inventadas, `rag_answer.py` implementa cuatro salvaguardas: (1) descomposición explícita de reseñas de Booking en `Título | Lo que gustó | Lo que no gustó`; (2) citas numéricas obligatorias entre corchetes `[1][2]`; (3) fórmula de abstención determinista (*"No hay información suficiente en las opiniones recuperadas para responder a esto"*); y (4) prohibición expresa de agregar o estimar porcentajes globales sobre muestras locales.

El asistente conversacional (`analytics/chat`) unifica la consulta cualitativa y cuantitativa mediante un doble motor nativo (sin LangChain):
1. **Router de Intención (`router.py`):** Clasifica la consulta con LLM ($T=0,0$) en `SQL` (conteos, rankings, series temporales, métricas oficiales de empleo, paro, plazas o sentimiento agregado) o `RAG` (percepciones cualitativas y vivencias).
2. **Agente Text-to-SQL Seguro (`sql_agent.py`):** Genera consultas de solo lectura sobre 7 tablas maestras Gold (`gold_municipio_master`, series anuales/mensuales, empleo, AENA, `gold_h3_master` y `gold_h3_sentimiento`). Aplica un pipeline de seguridad en capas: sentencia única, inicio estricto con `SELECT`, bloqueo de palabras reservadas DML/DDL, lista blanca de tablas, inyección de `LIMIT 200`, y uso obligatorio de subconsultas (`WHERE cod_municipio IN (...)`) para evitar sesgos por duplicación al cruzar escalas H3 y municipales. En caso de error, activa un bucle de autocorrección antes de emitir una síntesis de 1-2 frases con topónimos legibles.

## 6.4. Validación Empírica del Sistema RAG

El sistema se validó mediante un benchmark de 22 pruebas tipificadas (`preguntas.yaml`) evaluado mediante *LLM-as-a-Judge* (`run_eval.py`):
* **Precisión en Filtros y Extracción:** 100 % de acierto en detección geográfica y demográfica.
* **Blindaje de Abstención:** 100 % de éxito en preguntas fuera de dominio (tipos del BCE, deportes), emitiendo la fórmula exacta de abstención.
* **Deflexión de Agregaciones:** 100 % de desvío de trampas de recuento hacia el motor SQL.
* **Fidelidad Factual (*Faithfulness*):** 4,82 sobre 5 en consistencia estricta entre el texto generado y las citas inyectadas.
"""


def get_chapter_7():
    return """# 7. Productivización: AI-Dashboard Interactivo y Simulador de Decisiones

## 7.1. Arquitectura Frontend y Renderizado Geoespacial (Streamlit + PyDeck WebGL)

El cuadro de mando operacional se implementó con **Streamlit (v1.40+)** y **PyDeck / Deck.gl**, aprovechando la aceleración por hardware mediante WebGL. Esta arquitectura se priorizó frente a plataformas BI comerciales (Power BI o Tableau) por tres motivos decisivos: (1) renderizado nativo y fluido de los 2.579 polígonos hexagonales H3 en 2D y 3D (con extrusión topográfica mediante el MDT05 o por variables analíticas) sin colapsar el navegador del cliente; (2) interoperabilidad directa con los pipelines analíticos en Python (regresión espacial MGWR, clustering HDBSCAN, modelos vectoriales y LLM); y (3) despliegue ágil en contenedores Docker sin costes de licenciamiento por usuario.

La capa de datos conecta con Azure PostgreSQL mediante SQLAlchemy, empleando almacenamiento en caché en memoria (`@st.cache_data`) para mantener latencias inferiores a 200 ms ante cambios de filtros. Para mitigar distorsiones visuales generadas por valores atípicos extremos en variables asimétricas (como la densidad hotelera o el brillo nocturno VIIRS), el módulo `color_scales.py` calibra dinámicamente las rampas continuas entre los percentiles empíricos **P1 y P99** (*winsorización visual*). La experiencia de usuario incorpora animaciones CSS de carga suave (`fadeInUp`), tarjetas métricas con micro-elevación interactiva (*hover*) y un asistente conversacional omnipresente anclado mediante `position: fixed`.

## 7.2. Vistas Especializadas y Diagnóstico Estratégico Multiescala

La plataforma articula su análisis en 10 páginas nativas gestionadas mediante `st.navigation` (`app/main.py`):

1. **Resumen y Diagnóstico Macro (`summary.py`):** Radiografía insular consolidada que desglosa el régimen de protección del suelo (46,8 % en Espacios Naturales Protegidos vs 51,7 % sin restricción legal), balance alojativo municipal y celdas con cobertura de sentimiento.
2. **Visor Cartográfico Multicapa (`map_layers.py`):** Permite conmutar entre la malla microespacial H3 (PTNA, Score ESG, Eje 1 de saturación, Eje 2 de oportunidad rural, sentimiento divergente y arquetipos) y la capa mesomunicipal coroplética (12 indicadores: desempleo, plazas por 1.000 hab., ingresos VV y presión residencial). Integra overlays de infraestructuras críticas: isócronas viales ORS (15 a 60 min), red y paradas de guaguas GTFS TITSA, 67 estaciones agroclimáticas de Agrocabildo y Bienes de Interés Cultural (BIC). Al hacer clic en cualquier celda, se despliega la **Ficha de Detalle Territorial (`detail_panel.py`)**, contrastando los KPIs locales frente a la media municipal e insular.
3. **Matriz de Oportunidades y Arquetipos TUI (`arquetipos.py`):** Posiciona el territorio en los cuadrantes estratégicos de descompresión (Eje 1 vs Eje 2) y clasifica la isla en 5 arquetipos de producto (*Sol y playa*, *Ecoturismo rural*, *Cultural y patrimonial*, *Aventura y activo*, *Bienestar y salud*), aportando un diagnóstico DAFO y directrices de inversión.
4. **Monitores Sectoriales y Exploración Tabular:** Vistas de microeconomía municipal (`municipios.py`), clima en tiempo real (`clima.py`), oferta alojativa y tópicos BERTopic (`alojamiento.py`, `temas.py`), coyuntura turística ISTAC y tráfico aéreo AENA (`turismo.py`), junto con tablas avanzadas de descarga CSV (`table_view.py`) y rankings insulares (`rankings.py`).

## 7.3. Simulador Territorial What-If de Políticas Turísticas (`simulador.py`)

Como herramienta nuclear para la toma de decisiones, el simulador permite modelar intervenciones a **cuatro escalas territoriales**: celda H3 individual, municipio completo (31 términos), arquetipo de producto o clúster HDBSCAN. El planificador puede manipular cinco palancas operativas: variación de plazas hoteleras regladas ($\Delta plazas$), conectividad vial ($\Delta tiempo\_aeropuerto$), regeneración ambiental ($\Delta NDVI$), equipamientos complementarios ($\Delta POIs$) y gobernanza ($\Delta ESG$).

El motor recalcula instantáneamente el impacto sobre el territorio:
* **Proyección Empírica del PTNA:** Aplica los coeficientes de sensibilidad calibrados por el modelo MGWR v3 ($\beta_{\text{tiempo}} = -4,50$, $\beta_{\text{NDVI}} = 220,0$, $\beta_{\text{POIs}} = 2,80$) y proyecta la variación en los Ejes 1 y 2, visualizada mediante gráficos radar comparativos (*Antes vs. Después*).
* **Alertas de Capacidad de Carga:** Identifica en tiempo real riesgos de sobreexplotación (*Alerta Roja* si la densidad supera el p95 insular o satura servicios) y bloquea intervenciones en celdas de alta fragilidad ecológica (ENP o pendientes >25°).
* **Nivel de Confianza Predictiva:** Informa al gestor de la fiabilidad del pronóstico (*Alta, Media o Baja*), penalizando aquellos hexágonos donde el modelo MGWR saturó en anchos de banda globales por falta de variación local intrínseca.

## 7.4. Asistente Conversacional Omnipresente con Fundamentación Territorial (`asistente.py`)

Accesible desde un botón flotante en cualquier punto de la aplicación, el asistente conversacional integra un mecanismo de **anclaje territorial (*grounding*) contextual**: si el usuario tiene una celda H3 seleccionada en el mapa, el sistema inyecta automáticamente sus atributos locales en el prompt (`PROMPT_CONTEXTO_HEXAGONO`), resolviendo consultas sobre la zona en menos de un segundo. Para preguntas complejas o cuantitativas, el asistente deriva la petición al router inteligente, activando la síntesis cualitativa RAG o la ejecución de consultas seguras Text-to-SQL sobre la Capa Gold.
"""


def get_chapter_8():
    return r"""# 8. Conclusiones y Hoja de Ruta Estratégica para TUI Group

## 8.1. Respuesta Fundamentada a las Siete Preguntas del Briefing de TUI Group

La plataforma responde de manera directa, cuantitativa y accionable a las siete cuestiones estratégicas planteadas por TUI Group:

| Nº | Pregunta Estratégica de TUI | Metodología de Resolución | Diagnóstico y Hallazgo Clave |
| :--- | :--- | :--- | :--- |
| **P1** | **¿Dónde se localizan con exactitud las zonas saturadas?** | Malla H3 microespacial (res 8, 2.579 celdas) + radiancia nocturna VIIRS DNB. | El **78,4 % de las plazas alojativas** se concentra en solo **82 hexágonos** (3,1 % de la superficie insular), focalizados en Playa de las Américas, Los Cristianos y Costa Adeje, con radiancia VIIRS >65 nW/cm²/sr y colapso de las arterias TF-1 y TF-5 (>85 % de los viajes diarios). |
| **P2** | **¿Qué zonas tienen alto potencial pero baja visibilidad?** | Clustering HDBSCAN + Índice de Potencial Turístico (PTNA) con MGWR. | Medianías del norte y cumbres intermedias (Icod de los Vinos, Buenavista del Norte, Vilaflor y La Orotava) presentan alto PTNA, elevado NDVI (>0,6) y gran satisfacción turística, pero concentran **menos del 10 % de la oferta reglada**. |
| **P3** | **¿Qué comarcas rurales tienen condiciones para absorber demanda?** | Modelo topoclimático (inversión 800–1.500 m) + NDVI + Marco ESG ($PTNA > 0, ESG > 60$). | Se aíslan exactamente **247 hexágonos de oportunidad ideal** (9,6 % de la isla) en medianías protegidas del estrés térmico estival, compatibles con la capacidad de carga ecológica y con baja afección a avifauna protegida. |
| **P4** | **¿Cómo influye la accesibilidad en el éxito de zonas no costeras?** | Matriz vial ORS (18 destinos, isócronas 15–60 min) + red GTFS TITSA multiumbral (200/500/1.000 m). | El modelo MGWR estima una severa penalización por aislamiento vial ($\beta_{\text{tiempo}} = -4,50$). Los microdestinos viables exigen conexión a <45 min de un aeropuerto y servicio regular de transporte público comarcal. |
| **P5** | **¿Qué áreas muestran señales de congestión?** | Índice continuo de saturación (Eje 1): densidad de plazas/km² (p95) + quejas NLP + VIIRS. | Los núcleos de Playa de las Américas y Puerto Colón superan las 250 plazas/km², disparando alertas tempranas por sobrecarga de infraestructuras y fricción comunitaria. |
| **P6** | **¿De qué se quejan los turistas en el sur y qué buscan en el interior?** | Inferencia multilingüe XLM-RoBERTa + BERTopic centrado en idiomas + minería PyABSA. | En el litoral sur predominan quejas de *"ruido nocturno"*, *"masificación"* y *"atascos"* (NSS +0,48); en el interior y medianías los viajeros buscan tranquilidad, naturaleza y autenticidad gastronómica (NSS +0,74), con quejas leves sobre curvas o accesos. |
| **P7** | **¿Qué impacto tendría redistribuir un 10–20 % de la masa turística?** | Simulador territorial interactivo What-If (`app/simulador.py`) calibrado con sensibilidades MGWR v3. | El trasvase simulado de 13.800 a 27.600 plazas (10–20 % de las 137.951 plazas de Adeje y Arona) hacia municipios de medianías y norte (Icod, Vilaflor, Buenavista) reduce directamente el **Eje 1 de Saturación** en el litoral sur e incrementa el potencial de atracción rural (**PTNA y Eje 2**), impulsado por la sensibilidad al entorno ambiental ($\beta_{\text{NDVI}} = +220,0$). El simulador **bloquea automáticamente** cualquier incremento de plazas en celdas con Espacio Natural Protegido (`pct_area_enp > 0`) o pendientes >25°, y activa **alertas de capacidad de carga** si la densidad en destino supera el percentil 95 insular (>250 plazas/km²), garantizando una redistribución sin sobreexplotación ecológica. |

## 8.2. Recomendaciones Estratégicas y Hoja de Ruta para TUI Group

A partir de los hallazgos analíticos y espaciales, se formulan cuatro directrices de acción inmediata para la operativa de TUI Group en Tenerife:

1. **Lanzamiento de la Línea de Producto *"Tenerife Auténtico / Ecoturismo y Bienestar"*:* Desempaquetar la oferta masiva de sol y playa creando una cartera orientada a estancias de media y larga duración en alojamientos singulares de medianías (Icod de los Vinos, Vilaflor, Buenavista del Norte y comarca de Acentejo), donde el sentimiento neto es superior (+0,74) y el atractivo ambiental está demostrado ($PTNA > 70$).
2. **Incentivo Comercial Dinámico de Dispersión Territorial:** Implementar en el motor de reservas y en los canales de venta de TUI un sistema de bonificaciones tarifarias o servicios añadidos (ej. seguro de viaje o experiencias gastronómicas incluidas) para aquellos clientes que elijan municipios de oportunidad en periodos de máxima saturación costera.
3. **Corredores de Conectividad Sostenible:** Establecer acuerdos de transporte discrecional colectivo o rutas de movilidad compartida con TITSA que conecten directamente los aeropuertos insulares (TFS/TFN) con las cabeceras de medianías en menos de 45 minutos, mitigando la dependencia del vehículo de alquiler y la sobrecarga en las autopistas TF-1 y TF-5.
4. **Adopción del AI-Dashboard en la Mesa de Contratación Hotelera:** Institucionalizar el uso del simulador territorial y las alertas de capacidad de carga como filtro previo obligatorio antes de formalizar nuevos contratos hoteleros o cupos de plazas, garantizando el cumplimiento de los criterios ESG insulares.

## 8.3. Limitaciones del Estudio y Líneas de Investigación Futuras

Para garantizar un rigor metodológico pleno, se identifican tres limitaciones operativas que marcan la hoja de ruta de evolución del sistema:

1. **Resolución de Datos Turísticos Oficiales:** El ISTAC publica desglose mensual de ocupación y pernoctaciones únicamente para los seis municipios de mayor peso alojativo, obligando a modelar los 25 términos municipales restantes mediante imputación geoespacial basada en catastro reglado y señales de teledetección.
2. **Dependencia de Extracción Web en Reputación Online:** El corpus textual se sustentó en scraping sobre Booking, TripAdvisor y foros especializados; en una fase de explotación comercial, la solución debe transicionar hacia acuerdos directos de consumo vía API con los agregadores turísticos.
3. **Calibración Dinámica de Flujos con Matrices Origen-Destino Reales:** El simulador actual modela la sensibilidad con coeficientes espaciales MGWR. La línea de investigación inmediata radica en incorporar datos anonimizados de telefonía móvil (CDRs) o transacciones bancarias agregadas para observar la movilidad turística en tiempo real a lo largo de los corredores insulares.
"""


def get_references():
    return """# Referencias Bibliográficas

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
"""


def get_appendices():
    return """# Anexos Técnicos

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
# Windows: .venv\Scripts\activate | Linux/Mac: source .venv/bin/activate
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
"""
