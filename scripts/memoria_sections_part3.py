"""
memoria_sections_part3.py
Capítulo 6 (IA Generativa y RAG), Capítulo 7 (Productivización Streamlit),
Capítulo 8 (Validación, ROI y Conclusiones), Referencias Bibliográficas (APA 7ª)
y Anexos Técnicos A–G.
Versión compacta — código completo en Anexos D.
"""


def get_chapter_6():
    return """# 6. Inteligencia Artificial Generativa y Asistente RAG

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
"""


def get_chapter_7():
    return """# 7. Productivización: AI-Dashboard Interactivo y Simulador de Decisiones

## 7.1. Arquitectura Frontend (Streamlit + PyDeck)

El cuadro de mando se desarrolló con **Streamlit** y **Deck.gl / PyDeck** como motor de renderizado cartográfico acelerado mediante WebGL. Se eligió esta combinación frente a Power BI o Tableau por tres motivos: renderiza de forma nativa los 2.579 polígonos hexagonales 3D extruidos sin colapsar la interfaz; se integra sin fisuras con el resto del ecosistema Python (clustering, LLM, simulador gravitatorio); y se despliega en contenedores Docker sobre la VM de Azure sin costes de licencia por usuario.

## 7.2. Módulos Operativos del Dashboard

El cuadro de mando se organiza en cuatro módulos:

**Módulo 1 — Explorador Territorial H3:** Permite superponer cuatro capas temáticas sobre las 2.579 celdas insulares: capa biofísica (NDVI, NDBI, VIIRS), capa microclimática (temperatura, humedad modelada con Mar de Nubes, horas de sol), capa de accesibilidad multimodal (isócronas ORS, densidad GTFS en 200/500/1.000 m, distancia a hospitales) y capa de arquetipos HDBSCAN + índice PTNA.

**Módulo 2 — Monitor de Reputación y NLP:** Mapa de calor por *Net Sentiment Score*; selector de quejas por las seis dimensiones de calidad (Limpieza, Servicio, Precio/Calidad, Ubicación, Ruido, Masificación); y botón de generación de informe RAG con Groq sobre el área visible en pantalla.

**Módulo 3 — Simulador Gravitatorio de Redistribución:** Basado en los modelos de interacción espacial de Reilly (1931) y Huff (1963), permite al planificador definir el porcentaje de reasignación desde los municipios saturados del sur (Adeje, Arona) hacia comarcas deficitarias (Arico, Vilaflor, La Guancha, Buenavista). El algoritmo calcula la probabilidad de atracción de cada hexágono receptor en función de su PTNA, accesibilidad vial y distancia funcional, y proyecta al instante: reducción del tráfico diario en la TF-1, incremento de ingresos en medianías y verificación de la capacidad de absorción. El simulador bloquea automáticamente la reasignación hacia celdas del Cluster 3 (ENP) o con pendiente >25°, garantizando la sostenibilidad física de la simulación. Redirigir un 10 % de las pernoctaciones del sur reduce la congestión costera en ~14 % e inyecta más de 42 millones de euros anuales en la economía local de medianías.

**Módulo 4 — Sistema de Alertas Preventivas:** Evalúa reglas de negocio sobre umbrales críticos: *Alerta Roja de Saturación* (plazas/km² > percentil 95 con transporte deficiente); *Alerta Climática de Calima* (temperatura >32 °C y humedad <25 %); y *Alerta de Fricción Reputacional* (sentimiento medio < -0,25 o queja dominante `"ruido nocturno"` / `"masificación"`).
"""


def get_chapter_8():
    return """# 8. Validación Técnica, ROI y Conclusiones

## 8.1. Validación Empírica de los Resultados

Los resultados se sometieron a triple contraste frente a fuentes oficiales independientes:

1. **Validación Altimétrica:** Cruce de las cotas H3 frente a 67 vértices geodésicos de la Red REGENTE del IGN: **RMSE de 4,12 m**, confirmando la fiabilidad de la topografía base.
2. **Validación del Parque Alojativo:** Las 46.820 unidades identificadas en la capa Silver presentan una desviación inferior al 1,5 % respecto a las memorias anuales del ISTAC y el Registro General Turístico del Gobierno de Canarias.
3. **Consistencia Topoclimática:** Evaluación cualitativa de los gradientes térmicos y orográficos frente a los pisos bioclimáticos de la isla, reproduciendo la inversión del Mar de Nubes y la aridez del sur sin artefactos espaciales.

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
