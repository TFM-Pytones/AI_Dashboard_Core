# Plan Final TFM — TUI Tenerife
## Arquitectura Completa y Estado Real del Proyecto

> **Documento de referencia actualizado:** 25 agosto 2026  
> Sustituye al `plan_maestro_tecnico.md` en todos los aspectos de arquitectura de datos.

---

## Arquitectura General: Pipeline Medallón

```
[Fuentes Externas] → Bronze (Azure Blob + Postgres) → Silver (dbt, limpieza) → Gold (dbt, análisis)
```

El flujo de datos completo es:
1. **Ingesta desde el origen** → Script Python descarga/scrapea y sube al **Azure Blob Storage** (container `bronce-raw`).
2. **Bronze → PostgreSQL** → `ingest_bronze_to_postgres.py` lee el Blob y carga tablas crudas en el esquema `bronze` de la base de datos PostgreSQL.
3. **Silver** → dbt lee de `bronze.*` y produce tablas limpias, tipadas y con geometrías PostGIS en el esquema `silver`.
4. **Gold** → dbt lee de `silver.*` y produce los agregados, análisis y features finales en el esquema `gold`.

---

## Capa Bronze — Estado Real

Las siguientes tablas en PostgreSQL existen en el esquema `bronze`:

| Tabla | Descripción | Ingesta |
|---|---|---|
| `registro_hoteles` | Registro oficial de hoteles de Tenerife | `ingest_bronze_to_postgres.py` |
| `registro_viviendas_vacacionales` | Viviendas vacacionales del registro oficial | `ingest_bronze_to_postgres.py` |
| `registro_extrahoteleros` | Apartamentos, campings, etc. | `ingest_bronze_to_postgres.py` |
| `registro_geocoding_lookup` | Tabla de corrección de coordenadas por geocodificación | `ingest_bronze_to_postgres.py` |
| `booking_establishments` | Establecimientos de Booking scrapeados | `ingest_bronze_to_postgres.py` |
| `booking_reviews` | Reseñas de texto de Booking | `ingest_bronze_to_postgres.py` |
| `booking_geocoding_lookup` | Geocodificación específica de Booking | `ingest_bronze_to_postgres.py` |
| `tripadvisor_ubicaciones` | Establecimientos georreferenciados de TripAdvisor | Carga externa |
| `tripadvisor_resenas` | Reseñas de texto de TripAdvisor | Carga externa |
| `youtube_videos` | Metadatos de vídeos de YouTube | `ingest_bronze_to_postgres.py` |
| `youtube_comments` | Comentarios de YouTube (1 fila = 1 comentario) | `ingest_bronze_to_postgres.py` |
| `losviajeros_temas` | Hilos del foro LosViajeros | `ingest_bronze_to_postgres.py` |
| `losviajeros_mensajes` | Mensajes del foro (1 fila = 1 mensaje) | `ingest_bronze_to_postgres.py` |
| `aena_pasajeros` | Estadísticas de pasajeros aeropuertos Tenerife | `ingest_bronze_to_postgres.py` |
| `gtfs_paradas` | Paradas de autobús TITSA | `ingest_bronze_to_postgres.py` |
| `gtfs_rutas` | Rutas de autobús TITSA | `ingest_bronze_to_postgres.py` |
| `estaciones_agrocabildo` | Metadatos de las 67 estaciones meteorológicas | `ingest_bronze_to_postgres.py` |
| `clima_horario_agrocabildo` | Lecturas horarias de las estaciones | `ingest_bronze_to_postgres.py` |
| `open_meteo_era5land` | Histórico climático ERA5-Land (reanálisis) | `ingest_bronze_to_postgres.py` |
| `open_meteo_forecast` | Predicciones GFS (baja prioridad para el TFM) | `ingest_bronze_to_postgres.py` |
| `istac_municipios` | Indicadores económicos municipales ISTAC | `ingest_bronze_to_postgres.py` |
| `istac_mun_plazas_vv` + otras ISTAC | Estadísticas de VV por municipio | `ingest_bronze_to_postgres.py` |
| `h3_grid` | Malla hexagonal H3 resolución 8 (2.746 celdas Bronze / 2.579 Silver/Gold) | `01_ingest_vector_to_postgres.py` |
| `espacios_naturales` | Polígonos ENP (Espacios Naturales Protegidos) | `ingest_vector_to_postgres.py` |
| `limites_municipales` | Polígonos de los 31 municipios de Tenerife | `ingest_vector_to_postgres.py` |
| `zonas_turisticas` | Polígonos de zonas turísticas | `ingest_vector_to_postgres.py` |
| `osm_pois_tenerife` | 15.000+ POIs de OpenStreetMap | `ingest_vector_to_postgres.py` |
| `bienes_culturales` | Polígonos de BIC (Bienes de Interés Cultural) | `ingest_vector_to_postgres.py` |
| `oficinas_turismo` | Puntos de Oficinas de Turismo | `ingest_vector_to_postgres.py` |
| `mdt_stats` | Estadísticas raster MDT (altitud/pendiente) por H3 | Pre-calculado |
| `satelite_stats` | Estadísticas raster NDVI/VIIRS por H3 | Pre-calculado |

---

## Capa Silver — Estado Real y Completo

La capa Silver tiene la siguiente estructura final (tras consolidación). 

> [!IMPORTANT]
> En todos los modelos con geometrías, la columna se llama `geometry` y es de tipo `geometry(4326)`. Los índices GIST se definen en el `{{ config() }}` de dbt.

### alojamiento/
| Modelo | Descripción | Estado |
|---|---|---|
| `silver_registro_hoteles` | Hoteles limpios con `geometry` PostGIS. Coordenadas enriquecidas con geocodificador (COALESCE). Cast seguro `NULLIF`+`REPLACE` en lugar de `TRY_CAST`. | Completo |
| `silver_registro_viviendas_vacacionales` | Mismo patrón que hoteles | Completo |
| `silver_registro_extrahoteleros` | Mismo patrón que hoteles | Completo |
| **`silver_alojamiento_unificado`** | **TABLA PRINCIPAL.** `UNION ALL` de los 3 registros anteriores. Añade columna `tipo_alojamiento`. Índice GIST. Esta es la tabla que usa la capa Gold. | Completo |

### booking/
| Modelo | Descripción | Estado |
|---|---|---|
| `silver_booking_establishments` | Establecimientos de Booking. `geometry` PostGIS. Deduplicación y enriquecimiento de coordenadas con geocodificador. | Completo |
| `silver_booking_reviews` | Reseñas de texto de Booking. **Sin agregar** (1 fila = 1 reseña). Campo `longitud_texto`. Filtra reseñas vacías. | Completo |

### espacial/
| Modelo | Descripción | Estado |
|---|---|---|
| `silver_h3_grid` | Malla H3 + cálculo de área y centroides | Completo |
| `silver_limites_municipales` | Polígonos municipales + área km² + centroides | Completo |
| `silver_enp` | Espacios Naturales Protegidos. `municipio` es NULL (se asigna en Gold vía `ST_Intersection`) | Completo |
| `silver_zonas_turisticas` | Polígonos de zonas turísticas | Completo |
| `silver_osm_pois` | 15.000+ POIs OSM con `geometry`. Sub-dependencia del unificado. | Completo |
| `silver_bienes_culturales` | BIC (polígonos). Campos: `bic_nombre`, `municipio_nombre`. Sub-dependencia del unificado. | Completo |
| `silver_oficinas_turismo` | Oficinas de turismo (puntos). Campos: `nombre`, `horario`, `descripcion`, `telefono`, `estado`. Filtro: excluye cerradas temporalmente. Sub-dependencia del unificado. | Completo |
| **`silver_puntos_interes_unificados`** | **TABLA PRINCIPAL.** `UNION ALL` de OSM + BIC + Oficinas. Columna `fuente` para diferenciar origen. Preserve campos específicos de oficinas. | Completo |
| `silver_gtfs_paradas` | Paradas TITSA con `geometry` PostGIS | Completo |
| `silver_gtfs_rutas` | Rutas TITSA | Completo |
| `silver_indices_satelite` | NDVI, NDBI por H3 (pre-calculados) | Completo |

### clima/
| Modelo | Descripción | Estado |
|---|---|---|
| `silver_estaciones_agrocabildo` | Metadatos de estaciones con `geometry` PostGIS | Completo |
| `silver_clima_horario_agrocabildo` | Lecturas horarias limpias. Problema #7: `id_sensor` sin tabla de metadatos de variable (temperatura, lluvia, etc.) | Funcional, mejorable |
| `silver_era5land` | Histórico climático reanálisis ERA5 | Completo |
| `silver_gfs_hist` | Predicciones GFS. **Baja prioridad**: este dato no es relevante para el modelo MGWR ni el dashboard. Excluir de Gold. | ℹExcluir de Gold |

### istac/
| Modelo | Granularidad | Indicadores y Variables Contenidas | Estado |
|---|---|---|---|
| **`silver_istac_mensual`** | Mensual (`YYYY-MM`) | **Paro registrado** + **Vivienda Vacacional** (`plazas_vv`, `tasa_ocupacion_vv`, `estancia_media_vv`, `ingresos_vv`, `alojamientos_abiertos_vv`) + **Alojamientos Turísticos EOH** (`pernoctaciones`, `plazas_ofertadas`, `tasa_ocupacion_plazas`, `viajeros_entrados`). | Completo |
| **`silver_istac_trimestral`** | Trimestral (`YYYY-QX`) | **Suite de Empleo y Seguridad Social** (9 indicadores): `empleo_total`, `empleo_asalariados`, `empleo_autonomos`, `empleo_hosteleria`, `empleo_servicios`, `empleo_comercio`, `empleo_construccion`, `empleo_industria`, `empleo_agricultura`. | Completo |
| **`silver_istac_anual`** | Anual (`YYYY`) | **Demografía Oficial** (`poblacion_total`, `poblacion_15_64`, `poblacion_65_mas`, `edad_media`) + **Presión Turística Estructural** (`pob_turistica_equiv`). | Completo |
| ~~`silver_istac_vivienda_vacacional`~~ | — | **CONSOLIDADO.** Sus métricas están integradas en `silver_istac_mensual`. | Consolidado |
| ~~`silver_istac_estatico`~~ | — | **ELIMINADO.** Duplicaba `silver_limites_municipales`. | Eliminado |
| ~~`silver_istac_municipios_cifras_tenerife`~~ | — | **ELIMINADO.** Sustituido por anual/mensual/trimestral. | Eliminado |

### movilidad/
| Modelo | Descripción | Estado |
|---|---|---|
| `silver_aena_pasajeros` | Estadísticas de pasajeros (AENA). Movida de `espacial/` porque es dato tabular, no geográfico. | Completo |

### youtube/
| Modelo | Descripción | Estado |
|---|---|---|
| `silver_youtube` | Métricas agregadas por vídeo (engagement, nº comentarios válidos). Para el Dashboard de engagement. | Completo |
| `silver_losviajeros` | Métricas agregadas por hilo del foro. Para el Dashboard de engagement. | Completo |
| `silver_youtube_comentarios` | **Sin agregar** (1 fila = 1 comentario). Para el Squad NLP. | Completo |
| `silver_losviajeros_mensajes` | **Sin agregar** (1 fila = 1 mensaje). Para el Squad NLP. | Completo |

### tripadvisor/
| Modelo | Descripción | Estado |
|---|---|---|
| `silver_tripadvisor_ubicaciones` | Establecimientos con `geometry` PostGIS e índice GIST. | Completo |
| `silver_tripadvisor_resenas` | Reseñas (1 fila = 1 reseña). Filtra reseñas vacías. | Completo |

---

## Capa Gold — Plan de Implementación y Matriz de Explotación

> **NOTA DE CONVENCIONES:** Todos los modelos analíticos residen bajo el esquema `gold.*` en Azure PostgreSQL (las referencias históricas a `oro.*` quedan unificadas a `gold.*`).

### Catálogo de Tablas Gold y Explotación en los 4 Pilares del TFM
El proyecto estructura su capa analítica Gold en tres niveles territoriales/temporales (Micro H3, Meso Municipal y Macro Insular) más un componente vectorial de texto cualitativo:

| Tabla en `gold.*` | Granularidad / Registros | 1. Variables Numéricas & Modelos | 2. Dashboard Streamlit | 3. LLM (Text-to-SQL) | 4. RAG Semántico |
|---|---|---|---|---|---|
| **`gold_h3_master`** | Microespacial (2.746 hexágonos H3 res 8) | Variables predictoras $X$ para MGWR y clustering HDBSCAN. Atractores físicos, satelitales y oferta. | Capa base hexagonal en PyDeck (color por densidad, NDVI, altitud). Tooltip con oferta y ratings. | Consultas espaciales de micro-zona ("¿dónde hay hexágonos con buen clima y pocas plazas?"). | Clave de unión espacial (`h3_index`) para vincular opiniones cualitativas geolocalizadas. |
| **`gold_h3_sentimiento`** | Microespacial (Hexágonos con reviews) | Puntuaciones continuas de sentimiento y desglose por aspectos (limpieza, precio, ruido) como $X$ de reputación. | Gráfico de radar / barras de aspectos al hacer clic en un hexágono. | Consultas sobre satisfacción y quejas principales por microzona. | Filtro de reviews por aspectos y polaridad para complementar citas de texto. |
| **`gold_h3_accesibilidad`** | Microespacial (2.746 hexágonos H3) | Tiempos continuos de conducción ORS a 18 polos (aeropuertos, Teide, etc.) y distancias a hospitales/guaguas para MGWR. | Capa de isócronas visuales (15, 30, 45 min) y slider de tiempo de viaje. | Preguntas de tiempo de conducción ("¿zonas a < 25 min de TFS?"). | N/A directo (sirve como contexto de fricción espacial). |
| **`gold_h3_ptna`** | Microespacial (2.746 hexágonos H3) | Salida de regresión MGWR: residuo $PTNA = Y_{pred} - Y_{obs}$ y Score ESG Territorial (0-100). | Capa coroplética de calor "Oportunidades de Inversión". Simulador What-If con coeficientes locales. | Consultas de planificación estratégica e inversión turística sostenible. | Búsqueda semántica de opiniones de viajeros en áreas con alto PTNA. |
| **`gold_h3_clusters`** | Microespacial (2.746 hexágonos H3) | Clasificación no supervisada HDBSCAN en tipologías territoriales (Overtourism, Rural, etc.). | Capa de tipologías con leyenda cualitativa y filtrado por arquetipo de destino. | Consultas de perfiles de zona ("muéstrame zonas clasificadas como Rural Sostenible"). | Contextualización semántica de comentarios según la tipología del clúster. |
| **`gold_municipio_master`** | Mesomunicipal (31 municipios con PostGIS) | Indicadores estructurales (población, empleo, ratios de saturación `plazas_por_1000_hab`) y tasas 2022 vs 2025/2026. | Capa coroplética de polígonos municipales en PyDeck (`geometry` SRID 4326), KPI cards y drill-down. | Consultas a nivel municipal ("¿cuáles son los 5 municipios con mayor presión por habitante?"). | Enlace de documentos no estructurados mediante el campo `municipio_mencionado`. |
| **`gold_municipio_anual`** | Mesomunicipal temporal (155 filas: 31 mun × 5 años) | Series anuales y variaciones interanuales (`LAG` YoY) de paro, empleo e ingresos VV. Modelos de elasticidad. | Gráficos evolutivos anuales con Plotly y tablas de variación porcentual. | Consultas de evolución año a año ("¿cómo varió el empleo hostelero en Adeje de 2023 a 2024?"). | N/A directo (contexto temporal). |
| **`gold_municipio_mensual`** | Mesomunicipal temporal fino (1.736 filas: 31 mun × 56 meses) | Descomposición de estacionalidad, series temporales continuas y variación interanual `LAG(..., 12)`. | Explorador multivariante Plotly: comparar curvas mensuales (ingresos vs empleo) de varios municipios. | Consultas de estacionalidad y picos mensuales ("¿mes de mayor facturación de VV en 2025?"). | N/A directo (filtro temporal fino). |
| **`gold_municipio_empleo`** | Mesomunicipal trimestral (31 mun × 18 trimestres = ~558 filas) | Afiliaciones por sector (hostelería, servicios, comercio, industria, construcción, agricultura) y régimen (general vs autónomos). Ratios de dependencia y tasas YoY. | Gráficos de estructura laboral en Streamlit, radar de diversificación vs monocultivo y evolución del trabajo autónomo. | Consultas sobre monocultivo y resiliencia laboral ("¿qué municipios tienen más del 40% de empleo en hostelería?"). | N/A directo (contexto socioeconómico). |
| **`gold_turismo_hotelero_mensual`** | Polos turísticos clave (330 filas: 6 mun × 55 meses) | Flujos hoteleros reales EOH (viajeros, pernoctaciones, plazas, ocupación y estancia media) y variaciones interanuales. | Gráficos de demanda hotelera tradicional, comparativa Polo Sur vs Norte vs Metropolitano. | Consultas de hotelería oficial ("¿cuál es la tasa de ocupación hotelera en Adeje y Arona en verano?"). | N/A directo (contexto hotelero). |
| **`gold_turismo_hotelero_anual`** | Polos turísticos clave (24 filas: 6 mun × 4 años) | Población Turística Equivalente (**PTE**) del ISTAC, ratio de sobrecarga demográfica flotante y pernoctaciones anuales acumuladas. | KPIs de presión de carga ESG: ratio de turistas flotantes permanentes sobre residentes censados. | Consultas sobre capacidad de carga e impacto demográfico ("¿qué municipio tiene mayor población turística equivalente?"). | N/A directo. |
| **`gold_aena_pasajeros`** | Macroinsular movilidad (110 filas: mensual TFS/TFN) | Indicador macroeconómico de demanda turística; ratios pasajeros/operación y correlación con ocupación insular. | KPI Cards en cabecera del Dashboard (turistas último mes) y gráfico de tráfico TFS vs TFN. | Consultas sobre capacidad aérea y estacionalidad de vuelos internacionales vs nacionales. | N/A directo. |
| **`rag_documentos_viajeros`** | Cualitativo textual (Fragmentos de reseñas y foros) | Embeddings vectoriales densos (`vector(384)` / `vector(1536)` en `pgvector`) y entidades toponímicas extraídas. | Evidencias textuales y citas reales en el panel del Chatbot para justificar recomendaciones. | Invocado por el orquestador cuando la consulta requiere respuestas descriptivas/cualitativas. | **Pilar Central RAG:** Búsqueda por similitud de coseno (`<->`) para responder "¿por qué?" y "¿qué opinan?". |

### Librerías necesarias (globales)
```
pip install geopandas shapely psycopg2-binary sqlalchemy h3 pandas numpy pgvector
pip install rasterstats rasterio                       # Bloque 1 (estadísticas raster)
pip install transformers torch pyabsa langdetect       # Bloque 2 (NLP con coordenadas)
pip install bertopic sentence-transformers umap-learn hdbscan  # Bloque 3 (NLP sin coordenadas)
pip install mgwr libpysal scikit-learn                 # Bloque 5 (MGWR)
pip install openrouteservice                           # Bloque 4 (accesibilidad)
pip install langchain langchain-community langchain-groq groq  # Bloque 7 (Text-to-SQL y RAG)
pip install streamlit pydeck plotly wordcloud          # Bloque 8 (Dashboard)
```

---

## BLOQUE 1: `gold_h3_master` — La Tabla Maestra H3 que une todo el proyecto
**Squad:** B (Personas 3 y 4) | **Prioridad:** CRÍTICA — todo lo demás depende de esta | **Semana:** 1

### ¿Qué es y para qué sirve?
Esta es la tarea más crítica del TFM. La tabla `gold_h3_master` es la columna vertebral del proyecto: **una fila por cada hexágono H3** (2.579 hexágonos insulares consolidados desde `silver_h3_grid`), con todos los indicadores integrados. El `h3_index` (ej: `8928308280fffff`) es la clave primaria que une el trabajo de los 6 miembros del equipo.

> **ARQUITECTURA Y ORDEN DEL PIPELINE (Fase 1 vs Fase Final):**
> 1. **Fase 1 (Base Territorial Bloque 1):** Se construye el cimiento geoespacial, administrativo, satelital (Copernicus), climático (Agrocabildo), topográfico (MDT) y de oferta oficial y OTAs.
> 2. **Fase Final (Consolidación Post-Bloques 2, 3 y 4):** Una vez ejecutados los **Bloques 2 y 3** (NLP/PyABSA `gold_h3_sentimiento`) y el **Bloque 4** (Accesibilidad vial ORS `gold_h3_accesibilidad`), sus variables se integran a `gold_h3_master` por `h3_index`. Con esta tabla consolidada definitiva se alimentan los modelos **MGWR** (Bloque 5), **Clustering HDBSCAN** (Bloque 6), el **Agente Text-to-SQL / RAG** (Bloque 7) y el **Dashboard Streamlit** (Bloque 8).

### Librerías necesarias
```
pip install geopandas shapely psycopg2-binary sqlalchemy rasterstats rasterio h3 pandas numpy
```
---

### Subtarea 1.1 — Asignar municipio a cada hexágono (Cruce Espacial Polígono-Polígono)
- **Fuentes Silver:** `silver.h3_grid` (polígonos H3) + `silver.limites_municipales` (polígonos 31 municipios)
- **Técnica:** `ST_Intersects` + `ST_Area` del solapamiento para asignar el municipio con mayor cobertura cuando un hexágono cruza dos términos municipales.
- **SQL exacto:**
```sql
SELECT
    h.h3_index,
    m.cod_municipio,
    m.nombre_municipio AS municipio,
    h.area_km2,
    h.centroide_lon,
    h.centroide_lat,
    h.geometry
FROM silver.h3_grid h
LEFT JOIN silver.limites_municipales m
    ON ST_Intersects(h.geometry, m.geometry)
    AND ST_Area(ST_Intersection(h.geometry, m.geometry)) =
        (SELECT MAX(ST_Area(ST_Intersection(h2.geometry, m2.geometry)))
         FROM silver.limites_municipales m2
         WHERE ST_Intersects(h2.geometry, m2.geometry) AND h2.h3_index = h.h3_index)
```
- **Output:** Columnas `h3_index`, `cod_municipio`, `municipio`, `area_km2`, `centroide_lon`, `centroide_lat`, `geometry`.
- **Interpretabilidad:** Permite agrupar hexágonos por municipio en el dashboard.

---

### Subtarea 1.2 — Contar alojamientos y plazas por hexágono
- **Fuentes Silver:** `silver.h3_grid` + `silver.alojamientos_oficiales` (hoteles + VV + extrahoteleros, todos con `geometry`)
- **Técnica:** `ST_Contains(h3.geometry, alojamiento.geometry)` — PostGIS usa los índices GIST automáticamente.
- **SQL exacto:**
```sql
SELECT
    h.h3_index,
    COUNT(a.id)                                                     AS n_establecimientos_registro,
    COALESCE(SUM(a.plazas), 0)                                      AS n_plazas_registro,
    COUNT(a.id) FILTER (WHERE a.tipo_alojamiento = 'hotel')         AS n_hoteles,
    COUNT(a.id) FILTER (WHERE a.tipo_alojamiento = 'vivienda_vacacional') AS n_vv,
    COUNT(a.id) FILTER (WHERE a.tipo_alojamiento = 'extrahotelero') AS n_extrahoteleros
FROM silver.h3_grid h
LEFT JOIN silver.alojamientos_oficiales a ON ST_Contains(h.geometry, a.geometry)
GROUP BY h.h3_index
```
- **Output:** `n_establecimientos_registro`, `n_plazas_registro`, `n_hoteles`, `n_vv`, `n_extrahoteleros`.
- **Interpretabilidad para TUI:** Densidad de oferta oficial reglada. Permite calcular el ratio de equilibrio hotelero vs vacacional y la presión turística por km².

---

### Subtarea 1.3 — Agregar valoraciones de Booking y TripAdvisor (Separadas y Métricas Unificadas)
- **Fuentes Silver:** `silver.booking_establishments` + `silver.booking_reviews` | `silver.tripadvisor_ubicaciones` + `silver.tripadvisor_resenas`
- **Técnica:** JOIN establishments → reviews → ST_Contains con `h3_grid`. Filtro temporal `>= 2022`.
- **Métricas Separadas y Consolidadas:**
  - **Booking:** `n_establecimientos_booking`, `rating_booking_medio` (escala 1-10), `n_reviews_booking`.
  - **TripAdvisor:** `n_establecimientos_tripadvisor`, `rating_tripadvisor_medio` (escala 1-5), `n_reviews_tripadvisor`.
  - **Consolidadas (KPI Global):** 
    - `n_reviews_total` = masa crítica total de opiniones.
    - `rating_global_100` = valoración ponderada normalizada (Booking $\times 10$ y TripAdvisor $\times 20$) sobre 100, ponderada por el volumen de reseñas de cada plataforma.
- **SQL exacto:**
```sql
booking AS (
    SELECT
        h.h3_index,
        COUNT(DISTINCT e.establishment_id) AS n_establecimientos_booking,
        ROUND(AVG(r.rating)::numeric, 2) AS rating_booking_medio,
        COUNT(r.review_id) AS n_reviews_booking
    FROM h3 h
    LEFT JOIN silver.booking_establishments e ON ST_Contains(h.geometry, e.geometry)
    LEFT JOIN silver.booking_reviews r ON r.establishment_id = e.establishment_id
    GROUP BY h.h3_index
),
tripadvisor AS (
    SELECT
        h.h3_index,
        COUNT(DISTINCT e.location_id) AS n_establecimientos_tripadvisor,
        ROUND(AVG(r.rating)::numeric, 2) AS rating_tripadvisor_medio,
        COUNT(r.review_id) AS n_reviews_tripadvisor
    FROM h3 h
    LEFT JOIN silver.tripadvisor_ubicaciones e ON ST_Contains(h.geometry, e.geometry)
    LEFT JOIN silver.tripadvisor_resenas r ON r.location_id = e.location_id
    GROUP BY h.h3_index
)
```
- **Interpretabilidad:** Permite al LLM y Dashboard comparar cómo califican los clientes de Booking vs TripAdvisor, y a los modelos espaciales usar un único score continuo homogéneo.

---

### Subtarea 1.4 — Contar POIs por hexágono y categoría
- **Fuente Silver:** `silver.puntos_interes_unificados` (OSM + BIC + Oficinas de Turismo, todos con `geometry`)
- **SQL exacto:**
```sql
SELECT
    h.h3_index,
    COUNT(p.id)                                               AS n_pois_total,
    COUNT(p.id) FILTER (WHERE p.tipo IN ('restaurant', 'bar', 'cafe', 'fast_food', 'pub')) AS n_restaurantes,
    COUNT(p.id) FILTER (WHERE p.categoria IN ('Atracciones_Turisticas', 'Cultura')) AS n_cultura,
    COUNT(p.id) FILTER (WHERE p.categoria IN ('Naturaleza_Deporte')) AS n_naturaleza,
    COUNT(p.id) FILTER (WHERE p.fuente = 'IDE_Canarias')     AS n_pois_institucionales
FROM silver.h3_grid h
LEFT JOIN silver.puntos_interes_unificados p ON ST_Contains(h.geometry, p.geometry)
GROUP BY h.h3_index
```
- **Output:** `n_pois_total`, `n_restaurantes`, `n_cultura`, `n_naturaleza`, `n_pois_institucionales`.
- **Interpretabilidad:** Zonas con muchos POIs de naturaleza pero pocas plazas → potencial ecoturismo.

---

### Subtarea 1.5 — Paradas de transporte público por hexágono
- **Fuente Silver:** `silver.gtfs_paradas` (con `geometry`)
- **Técnica:** `ST_Contains`.
- **Output:** `n_paradas_bus`.
- **Interpretabilidad:** Accesibilidad directa en transporte público sin vehículo privado.

---

### Subtarea 1.6 — Estadísticas de relieve (MDT) y Satélite (Copernicus)
- **Fuente:** `bronze.mdt_stats` + `silver.satelite_stats`
- **MDT Optimizado (Eliminación de redundancias):**
  - `altitud_media_m` (elevación media del terreno).
  - `desnivel_m` (`elevation_max - elevation_min`): Mide la rugosidad orográfica interna del hexágono sin la colinealidad de tener `min` y `max` en crudo.
  - `slope_mean` (pendiente media en grados).
  - `aspect_mean` (orientación de la ladera 0-360º: Barlovento vs Sotavento).
  - `hillshade_mean` (mantenido para renderizado visual estético y relieve sombreado en el Dashboard).
- **Satélite (Copernicus Sentinel-2 & VIIRS):**
  - **Medias estructurales:** `ndvi_medio`, `viirs_medio`, `ndbi_medio`.
  - **Desglose interanual 2022-2026 (para LLM Text-to-SQL y series temporales del Dashboard):**
    - `ndvi_2022` a `ndvi_2026`
    - `viirs_2022` a `viirs_2026`
    - `ndbi_2022` a `ndbi_2026`
  - **Desglose estacional por trimestres (Q1 a Q4):**
    - `ndvi_q1`, `ndvi_q2`, `ndvi_q3`, `ndvi_q4`
    - `viirs_q1`, `viirs_q2`, `viirs_q3`, `viirs_q4`
  - **Tasa de Dinamismo Temporal Sintético:**
    - `cambio_luz_nocturna_pct`: `((viirs_2026 - viirs_2022) / NULLIF(viirs_2022, 0)) * 100` (proxy directo de crecimiento de actividad económica).
- **Interpretabilidad:** La combinación de años y trimestres permite al LLM responder consultas históricas (*"¿cómo creció la actividad nocturna entre 2022 y 2025?"*) y de estacionalidad (*"¿actividad en invierno Q1 vs verano Q3?"*), mientras los modelos ML consumen directamente las medias estructurales y la tasa de cambio evitando colinealidad.

---

### Subtarea 1.7 — Clima por hexágono (IDW + Gradiente Térmico + Horas de Sol Reales)
- **Fuente Silver:** `silver.clima_agrocabildo`
- **Técnica de Interpolación Espacial:**
  - **IDW (Inverse Distance Weighting, K=3):** Ponderación cuadrática inversa a las 3 estaciones más próximas.
  - **Corrección Térmica (Lapse Rate):** $-0.0065$ ºC por metro de diferencia de altitud entre el hexágono y las estaciones.
  - **Efectos Orográficos:** Factores de mar de nubes (humedad), sombra de lluvia (vertientes barlovento/sotavento) y amortiguación térmica costera.
- **Indicadores ESG y Extremos:**
  - `dias_ola_calor_anual`: Días con temp_max $\ge 35$ ºC, humedad $\le 30\%$ y viento de componente Este/Sur.
  - `amplitud_termica_media`: Diferencia diaria entre temperatura máxima y mínima.
- **Horas de Sol Diarias Reales (Estándar OMM $\ge 120\text{ W/m}^2$):**
  - Se sustituye la radiación cruda en W/m² por **horas de sol diarias efectivas**:
    - `horas_sol_diarias_media`: Media anual de horas de sol al día.
    - `horas_sol_q1`, `horas_sol_q2`, `horas_sol_q3`, `horas_sol_q4`: Horas de sol diarias por trimestre.
- **Desglose Estacional Trimestral (para LLM y Dashboard):**
  - **Temperatura:** `temp_media_anual`, `temp_media_q1`, `temp_media_q2`, `temp_media_q3`, `temp_media_q4`.
  - **Precipitación:** `lluvia_mm_anual`, `lluvia_mm_q1`, `lluvia_mm_q2`, `lluvia_mm_q3`, `lluvia_mm_q4`.
  - **Viento:** `vel_viento_media_anual`, `vel_viento_media_q1`, `vel_viento_media_q2`, `vel_viento_media_q3`, `vel_viento_media_q4` (identifica trimestres idóneos para deportes náuticos).
  - **Humedad:** `humedad_media_anual`, `humedad_media_q1`, `humedad_media_q2`, `humedad_media_q3`, `humedad_media_q4` (identifica zonas con efecto panza de burro).

---

### Subtarea 1.8 — Espacio Natural Protegido (ENP) con Denominación
- **Fuente Silver:** `silver.enp` (polígonos ENP de Canarias)
- **Técnica:** Solapamiento espacial con `ST_Intersection` y cálculo de porcentaje sobre el área del hexágono.
- **Output:**
  - `pct_area_enp`: Porcentaje del hexágono cubierto por figuras de protección (0 a 1). Se descarta el flag booleano simple `es_enp` al ser redundante con `pct_area_enp > 0`.
  - `nombre_enp`: Nombre de los espacios naturales protegidos que intersectan (`STRING_AGG(DISTINCT nombre_enp, ', ')`), ej: *"Parque Nacional del Teide"*, *"Parque Rural de Anaga"*.
- **Interpretabilidad:** Vital para el RAG y Text-to-SQL (*"¿qué hexágonos están en Anaga o en el Teide?"*) y para definir restricciones legales en el MGWR.

---

### Subtarea 1.9 — Zona Turística Oficial con Denominación y Cobertura
- **Fuente Silver:** `silver.zonas_turisticas`
- **Técnica:** Solapamiento espacial y agregación textual.
- **Output:**
  - `pct_area_zona_turistica`: Porcentaje de cobertura en zona turística oficial (0 a 1).
  - `nombre_zona_turistica`: Denominación oficial (`STRING_AGG(DISTINCT nombre_zona, ', ')`), ej: *"Playa de las Américas"*, *"Costa Adeje"*, *"Puerto de la Cruz"*.
- **Interpretabilidad:** Permite al LLM y al Dashboard segmentar entre zonas maduras oficiales y zonas residenciales o rurales.

---

### Subtarea 1.10 — Distancia Euclidiana a la Costa (en Kilómetros)
- **Fuente Silver:** `silver.limites_municipales`
- **Técnica Espacial:** Perímetro insular `ST_Boundary(ST_Union(geometry))` y medición con `ST_Distance(centroid, costa) / 1000.0`.
- **Output:** `dist_costa_km` (NUMERIC en km, unificado con `gold_h3_accesibilidad`).
- **Interpretabilidad:** Predictor clave de prima de localización costera frente al interior.

---

### Output de la Tabla: `gold.gold_h3_master` (Fase 1 Base)
**Tabla:** `gold.gold_h3_master` | **Filas:** 2.579 | **Índices:** GIST en `geometry`, B-Tree en `cod_municipio` y `h3_index`

| Bloque Temático | Columnas en la Tabla | Tipo | Utilidad Clave |
|---|---|---|---|
| **Identificación** | `h3_index`, `cod_municipio`, `municipio`, `area_km2`, `centroide_lon`, `centroide_lat`, `geometry` | VARCHAR / NUMERIC / GEOMETRY | Clave primaria territorial y polígonos PyDeck |
| **Alojamiento Oficial** | `n_establecimientos_registro`, `n_plazas_registro`, `n_hoteles`, `n_vv`, `n_extrahoteleros` | INT | Oferta reglada y cálculo de densidad |
| **OTAs (Booking)** | `n_establecimientos_booking`, `rating_booking_medio`, `n_reviews_booking` | INT / NUMERIC | Demanda y satisfacción en Booking |
| **OTAs (TripAdvisor)**| `n_establecimientos_tripadvisor`, `rating_tripadvisor_medio`, `n_reviews_tripadvisor` | INT / NUMERIC | Demanda y satisfacción en TripAdvisor |
| **Reputación Unificada**| `n_reviews_total`, `rating_global_100` | INT / NUMERIC | Masa crítica de opiniones y valoración 0-100 |
| **POIs y Transporte** | `n_pois_total`, `n_restaurantes`, `n_cultura`, `n_naturaleza`, `n_pois_institucionales`, `n_paradas_bus` | INT | Atractores turísticos y transporte público |
| **Relieve y Terreno** | `altitud_media_m`, `desnivel_m`, `slope_mean`, `aspect_mean`, `hillshade_mean` | NUMERIC | Orográfico, barreras físicas y relieve sombreado |
| **Satélite Estructural**| `ndvi_medio`, `viirs_medio`, `ndbi_medio`, `cambio_luz_nocturna_pct` | NUMERIC | Base biofísica y dinamismo económico (VIIRS) |
| **Satélite Anual (LLM)**| `ndvi_2022..2026`, `viirs_2022..2026`, `ndbi_2022..2026` | NUMERIC | Consultas interanuales Text-to-SQL y series |
| **Satélite Trimestral**| `ndvi_q1..q4`, `viirs_q1..q4` | NUMERIC | Estacionalidad turística invierno vs verano |
| **Clima ESG y Extremos**| `dias_ola_calor_anual`, `amplitud_termica_media` | NUMERIC | Vulnerabilidad climática y confort térmico |
| **Horas de Sol Reales**| `horas_sol_diarias_media`, `horas_sol_q1..q4` | NUMERIC | Insolación efectiva según estándar OMM |
| **Clima Estacional** | `temp_media_anual`, `temp_media_q1..q4`, `lluvia_mm_anual`, `lluvia_mm_q1..q4`, `vel_viento_media_anual`, `vel_viento_media_q1..q4`, `humedad_media_anual`, `humedad_media_q1..q4` | NUMERIC | Series climáticas trimestrales para LLM y confort |
| **Territorio y Normativa**| `pct_area_enp`, `nombre_enp`, `pct_area_zona_turistica`, `nombre_zona_turistica`, `dist_costa_km` | NUMERIC / VARCHAR | Restricciones ambientales, zonas turísticas y litoralidad |

> **Nota de Consolidación:** Las columnas del Bloque 4 (`tiempo_aeropuerto_min`, `tiempo_teide_min`, `dist_hospital_km`, etc.) y de los Bloques 2/3 (`sentimiento_medio`, quejas por aspectos) se incorporan en la vista final consolidada de explotación tras la ejecución de dichos módulos.

---

## BLOQUE 1.B: Tablas Maestras Municipales y Macrotendencias de Movilidad
Tablas de la capa Gold que consolidan la información a nivel municipal (con geometría PostGIS para mapas coropléticos) y series temporales (ISTAC y AENA) para el Dashboard, el análisis numérico y el agente LLM Text-to-SQL.

### Subtarea 1.B.1 — `gold_municipio_master` (La Tabla Maestra Municipal con PostGIS)
- **Granularidad:** 1 fila por municipio (31 filas en total, 0% NULLs ni falsos ceros).
- **Propósito:** Mapa coroplético en Streamlit (PyDeck/Folium), drill-down municipal al hacer clic en un hexágono, ratios de presión turística, índices satelitales multitemporales y tendencias de evolución (2022 vs 2025/2026).
- **Estructura (0% NULLs garantizados):**
  - `cod_municipio`, `municipio`, `area_km2`, `centroide_lon`, `centroide_lat`, `geometry` (MultiPolygon SRID 4326 con índice GIST).
  - Demografía, Paro y Afiliación General: `poblacion_actual`, `paro_actual`, `empleo_total_actual`, `empleo_asalariados_actual`, `empleo_autonomos_actual`.
  - Radiografía Sectorial CNAE 2026: `empleo_hosteleria_actual`, `empleo_servicios_actual`, `empleo_comercio_actual`, `empleo_construccion_actual`, `empleo_industria_actual`, `empleo_agricultura_actual`.
  - Ratios de Especialización Económica: `pct_dependencia_hosteleria`, `pct_terciarizacion`, `pct_autonomos`, `pct_asalariados`, `pct_comercio`, `pct_construccion`, `pct_industria`, `pct_agricultura`.
  - Vivienda Vacacional actual (100% municipios): `plazas_vv_actual`, `tasa_ocupacion_vv_actual`, `estancia_media_vv_actual`, `ingresos_vv_actual`.
  - Oferta reglada y agregados H3 (Censo oficial Cabildo): `n_hexagonos`, `n_establecimientos_registro`, `n_plazas_registro`, `n_hoteles`, `n_vv`, `n_extrahoteleros`, ratings Booking/TripAdvisor, POIs, clima, altitud.
  - Ratios de presión: `densidad_plazas_km2`, `plazas_por_1000_hab`.
  - Ratios de evolución continua (2022 vs 2025/2026): `crec_poblacion_pct`, `var_paro_pct`, `crec_empleo_total_pct`, `crec_empleo_autonomos_pct`, `crec_plazas_vv_pct`, `crec_ingresos_vv_pct`, `cambio_luz_nocturna_pct` (VIIRS 2022 vs 2026).
  - Índices Satelitales (Sentinel-2 y VIIRS): `ndvi_medio`, `ndvi_2022`, `ndvi_2026`, `ndbi_medio`, `ndbi_2022`, `ndbi_2026`, `cambio_ndbi_absoluto`, `viirs_medio`, `viirs_2022`, `viirs_2026`.
  *(Nota metodológica: Se eliminaron las columnas de encuestas hoteleras muestrales EOH y PTE que ISTAC solo publica para 6 municipios, evitando el 80.6% de ceros encubiertos y garantizando métricas 100% universales).*

### Subtarea 1.B.2 — `gold_municipio_anual` (Serie Histórica Anual con Variaciones YoY)
- **Granularidad:** 31 municipios × 5 años (2022 a 2026) = 155 filas (0% NULLs ni falsos ceros).
- **Propósito:** Análisis de coyuntura año a año. Años 2022-2025 cerrados completos; 2026 parcial YTD con referencia censal de 2025 y medias mensuales comparables.
- **Estructura (0% NULLs garantizados):**
  - Identificación y Demografía: `cod_municipio`, `municipio`, `anio`, `n_meses`, `es_anio_completo`, `poblacion`.
  - Mercado Laboral Continuo: `paro_medio`, `var_paro_yoy_pct`, `empleo_total_medio`, `crec_empleo_total_yoy_pct`, `empleo_autonomos_medio`, `crec_empleo_autonomos_yoy_pct`.
  - Vivienda Vacacional (ISTAC universal): `plazas_vv_media`, `crec_plazas_vv_yoy_pct`, `ingresos_vv_media_mensual`, `crec_ingresos_mensual_yoy_pct`, `ingresos_vv_acumulados`, `tasa_ocupacion_vv_media`, `estancia_media_vv`.

### Subtarea 1.B.3 — `gold_municipio_mensual` (Serie Temporal Mes a Mes 2022-2026)
- **Granularidad:** 31 municipios × 55 meses (2022-01 a 2026-07) = 1.705 filas (0% NULLs ni falsos ceros).
- **Propósito:** Gráficos de líneas con Plotly en el Dashboard, curvas de estacionalidad turística por estación climática y comparaciones interanuales mismo mes año anterior (`LAG 12`).
- **Estructura (0% NULLs garantizados):**
  - Identificación y Temporalidad: `cod_municipio`, `municipio`, `periodo` ('2022-01' a '2026-07'), `anio`, `mes`, `trimestre`, `estacion` ('Invierno', 'Primavera', 'Verano', 'Otoño').
  - Mercado Laboral: `paro_registrado`, `paro_yoy_pct`.
  - Vivienda Vacacional: `plazas_vv`, `plazas_vv_yoy_pct`, `tasa_ocupacion_vv`, `estancia_media_vv`, `ingresos_vv`, `ingresos_vv_yoy_pct`, `alojamientos_abiertos_vv`.

### Subtarea 1.B.4 — `gold_aena_pasajeros` (Movilidad Aérea y Estacionalidad de la Isla)
- **Granularidad:** 110 filas (mensual 2022-2026 para TFS y TFN).
- **Propósito:** Permite al LLM responder consultas de demanda aeroportuaria y alimentar el KPI Macro de la portada del Dashboard sin consultar Silver.
- **Estructura:** `periodo`, `anio`, `mes`, `trimestre`, `temporada`, `aeropuerto_codigo` ('TFS', 'TFN'), `aeropuerto_nombre`, `tipo_trafico_principal` ('Internacional predominante', 'Nacional e Interinsular'), `pasajeros`, `operaciones`, `pasajeros_por_operacion`.

### Subtarea 1.B.5 — `gold_municipio_empleo` (Evolución Laboral Trimestral 100% Continua)
- **Granularidad:** 31 municipios × 18 trimestres (2022-Q1 a 2026-Q2) = 558 filas exactas (0% NULLs).
- **Propósito:** Analizar la evolución temporal continua del mercado laboral municipal, el peso del autoempleo y el crecimiento del empleo registrado.
- **Diseño Libre de NULLs (Optimizado para LLM y Text-to-SQL):**
  - Para evitar vacíos y respuestas erróneas en agentes LLM, esta tabla se concentra en los regímenes con serie continua completa (Total, Asalariados, Autónomos).
  - La radiografía estructural de especialización sectorial CNAE (hostelería, servicios, comercio, etc. de 2026) se concentra en `gold_municipio_master`, donde conforma una foto fija 100% poblada.
- **Estructura y Columnas:**
  - Identificación: `cod_municipio`, `municipio`, `periodo` ('2022-Q1' a '2026-Q2'), `periodo_texto`, `anio`, `trimestre`.
  - Cifras Absolutas de Afiliación: `empleo_total`, `empleo_asalariados`, `empleo_autonomos`.
  - Ratios Estructurales (% sobre empleo total):
    - `pct_autonomos`: Tasa de trabajo por cuenta propia / microemprendimiento local.
    - `pct_asalariados`: Tasa de trabajo asalariado por cuenta ajena.
  - Variaciones Interanuales (`LAG 4` con línea base 2021): `crec_empleo_total_yoy_pct`, `crec_empleo_autonomos_yoy_pct` (100% pobladas para todos los trimestres).

### Subtarea 1.B.6 — `gold_turismo_hotelero_mensual` y `gold_turismo_hotelero_anual` (Hotelería Tradicional EOH y Presión Demográfica PTE)
- **Granularidad:** 
  - Mensual: 6 municipios turísticos oficiales (Adeje, Arona, Puerto de la Cruz, Santiago del Teide, Santa Cruz de Tenerife, Granadilla de Abona) × 55 meses (2022-01 a 2026-07) = 330 filas exactas (0% NULLs).
  - Anual: 6 municipios turísticos × 4 años (2022-2025) = 24 filas exactas (0% NULLs).
- **Propósito:** Poner a disposición del Dashboard y del agente LLM en la capa **Gold** toda la riqueza analítica de la hotelería regulada tradicional (EOH del ISTAC/INE) y la Población Turística Equivalente (PTE), concentrándola donde realmente existe medición estadística (sin dispersar falsos ceros en los restantes 25 municipios).
- **Estructura `gold_turismo_hotelero_mensual`:**
  - Identificación y Territorio: `cod_municipio`, `municipio`, `polo_turistico` ('Polo Sur', 'Polo Norte', 'Polo Metropolitano'), `periodo`, `anio`, `mes`, `trimestre`, `estacion` ('Invierno', 'Primavera', 'Verano', 'Otoño').
  - Flujo y Capacidad: `viajeros_entrados`, `pernoctaciones`, `plazas_ofertadas_hotel`, `tasa_ocupacion_plazas`, `estancia_media_hotel_dias`.
  - Variaciones Interanuales (`LAG 12`): `crec_viajeros_yoy_pct`, `crec_pernoctaciones_yoy_pct`.
- **Estructura `gold_turismo_hotelero_anual`:**
  - `cod_municipio`, `municipio`, `polo_turistico`, `anio`, `n_meses`, `poblacion`, `pob_turistica_equiv`, `pct_pob_turistica_equiv_sobre_pob` (KPI central de capacidad de carga demográfica ESG).
  - Totales y Medias: `viajeros_entrados_total`, `crec_viajeros_yoy_pct`, `pernoctaciones_total`, `crec_pernoctaciones_yoy_pct`, `plazas_ofertadas_hotel_media`, `ocupacion_media_plazas`, `estancia_media_hotel_dias`.

---

## BLOQUE 2: NLP CON COORDENADAS — Sentimiento y Aspectos Geolocalizados (Booking + TripAdvisor → Malla H3)
**Squad:** A (Personas 1 y 2) | **Prioridad:** Alta | **Semana:** 1-2

### ¿Qué es y para qué sirve?
Booking y TripAdvisor tienen reseñas asociadas a un establecimiento concreto. Como ese establecimiento tiene coordenadas, podemos "ponerlo" en su hexágono H3 y saber exactamente **QUÉ se critica en cada zona del mapa**. Es el NLP que alimenta directamente al modelo MGWR del Bloque 5 y al mapa interactivo del Dashboard.

### Librerías necesarias
```
pip install transformers torch pyabsa langdetect psycopg2-binary pandas sqlalchemy
```
---

### Subtarea 2.1 — Sentimiento general por reseña (BERT Multilingüe)
- **Fuente Silver:** `silver.booking_reviews` + `silver.tripadvisor_resenas`. Filtrar `WHERE anio > 2021`.
- **Modelo:** `nlptown/bert-base-multilingual-uncased-sentiment` — clasifica de 1 (muy negativo) a 5 (muy positivo).
- **Para que funcione bien:**
  - Reseñas de máx 512 tokens (truncar si son más largas).
  - Ejecutar en batches de 32 para no petar la RAM.
  - Si no hay GPU, añadir `device='cpu'` y esperar ~3-4 horas por batch.
- **Código esqueleto:**
```python
from transformers import pipeline
sentiment_pipe = pipeline("text-classification", model="nlptown/bert-base-multilingual-uncased-sentiment", device=-1) # -1 = CPU, 0 = GPU
resultados = sentiment_pipe(lista_textos, batch_size=32, truncation=True, max_length=512)
scores = [int(r['label'].split()[0]) for r in resultados]
```
- **Cruce espacial:** `ST_Contains(h3.geometry, establecimiento.geometry)`.
- **Output:** Tabla `gold.nlp_sentimiento_resenas` con `resena_id`, `hotel_id`, `score`.
- **Interpretabilidad para TUI:** Score bajo (1-2) = señal de alerta operativa. Score alto (4-5) en zona con PTNA elevado = oportunidad de escalar una marca ya bien percibida.

---

### Subtarea 2.2 — Aspectos específicos por reseña (PyABSA)
- **Modelo** `pyabsa` con checkpoint `multilingual`.
- **¿Qué hace?** Extrae pares `(aspecto, sentimiento)` de cada frase. Ej: `("limpieza", "negativo")`, `("ubicacion", "positivo")`.
- **Aspectos a detectar:** `["precio", "limpieza", "ubicacion", "transporte", "naturaleza", "servicio", "ruido"]`.
- **Para que funcione bien:**
  - PyABSA necesita `torch >= 1.13`. Verificar versión antes.
  - Los aspectos son detectados automáticamente por el modelo, no hace falta definirlos a mano.
- **Código esqueleto:**
```python
from pyabsa import AspectTermExtraction as ATEPC
extractor = ATEPC.AspectExtractor('multilingual', auto_device=True)
resultados = extractor.predict(lista_textos, pred_sentiment=True)
```
- **Output:** Tabla `gold.nlp_aspectos_resenas` con `resena_id`, `aspecto`, `sentimiento`.
- **Interpretabilidad para TUI:** "Las quejas en Adeje se concentran en 'ruido' y 'precio', no en 'servicio'" → acción concreta para TUI.

---

### Subtarea 2.3 — Cruce NLP → Hexágono H3 (El Paso Crítico)
- **Técnica:** JOIN multi-step: `reseña → establecimiento (con geometry) → ST_Contains → hexágono H3`.
- **SQL exacto:**
```sql
SELECT
    h.h3_index,
    ROUND(AVG(s.score)::numeric, 2)                AS sentimiento_medio,
    COUNT(s.review_id)                             AS n_resenas,
    COUNT(s.review_id) FILTER (WHERE s.plataforma = 'booking')     AS n_resenas_booking,
    COUNT(s.review_id) FILTER (WHERE s.plataforma = 'tripadvisor') AS n_resenas_tripadvisor,
    MODE() WITHIN GROUP (ORDER BY a.aspecto)       AS queja_principal
FROM silver.h3_grid h
LEFT JOIN silver.booking_establishments e_b ON ST_Contains(h.geometry, e_b.geometry)
LEFT JOIN silver.tripadvisor_ubicaciones e_t ON ST_Contains(h.geometry, e_t.geometry)
LEFT JOIN gold.nlp_sentimiento_resenas s
    ON (s.plataforma = 'booking' AND s.review_id IN (SELECT review_id FROM silver.booking_reviews WHERE establishment_id = e_b.id))
    OR (s.plataforma = 'tripadvisor' AND s.review_id IN (SELECT review_id FROM silver.tripadvisor_resenas WHERE location_id = e_t.location_id))
LEFT JOIN gold.nlp_aspectos_resenas a ON a.review_id = s.review_id
GROUP BY h.h3_index
```
- **Output Final:** Columnas `sentimiento_medio`, `n_resenas`, `queja_principal` incorporadas a `gold.h3_master`.

> **Nota de ejecución (post-implementación, 16-sep-2026):** `gold.gold_h3_sentimiento` se construyó como tabla real independiente, no incorporada a `gold.h3_master` como dice el "Output Final" de arriba. El plan es inconsistente consigo mismo sobre dónde debía vivir este resultado: esta subtarea (Bloque 2) asume que las columnas terminan fusionadas en `gold.h3_master`, mientras que el Bloque 5 (Subtarea 5.1) asume una tabla separada, unida vía `LEFT JOIN`. Se siguió el criterio del Bloque 5. Además, el SQL exacto de arriba no se pudo ejecutar tal cual: las tablas realmente pobladas (`gold.nlp_sentimiento_resenas`, `gold.nlp_aspectos_resenas`) no coinciden en esquema con lo que asumía — la clave real es `resena_id` (no `review_id`) y `h3_index` ya viene precalculado en `gold.nlp_sentimiento_resenas` (no hace falta el `ST_Contains` contra `silver.h3_grid` ni el join intermedio por establecimiento). Ver `analytics/mgwr/scripts/00_create_sentimiento_table.py` para el SQL real usado.

---

## BLOQUE 3: NLP CUALITATIVO Y SIN COORDENADAS — Percepción Global, Tópicos y Base de Conocimiento RAG (YouTube + LosViajeros)
**Squad:** A (Personas 1 y 2) | **Prioridad:** Media | **Semana:** 1-2 (en paralelo con Bloque 2)

### ¿Qué es y para qué sirve?
Los vídeos de YouTube (transcripciones y comentarios) y posts de foros (LosViajeros) **no disponen de coordenadas GPS directas de hotel**. Sin embargo, son la fuente más rica de vivencias cualitativas, dudas de planificación e imagen de marca. 
Este bloque cumple un triple propósito estructurado en `analytics/`:
1. **Modelado de Tópicos (BERTopic):** Extraer los grandes temas de conversación sobre Tenerife.
2. **Georreferenciación Indirecta (`analytics/geo/extract_toponyms.py`):** Recuperar contexto espacial asociando menciones de playas, miradores y pueblos a municipios y hexágonos H3.
3. **Base de Conocimiento Vectorial (`gold.rag_documentos_viajeros`):** Almacenar fragmentos de texto vectorizados en `pgvector` para permitir al Chatbot del Dashboard responder preguntas cualitativas citando opiniones reales de turistas.

### Librerías necesarias
```
pip install bertopic sentence-transformers umap-learn hdbscan pgvector sqlalchemy langchain groq
```
---

### Subtarea 3.1 — Modelado de Tópicos en Dos Vías (`analytics/topics/`)
El pipeline en `analytics/topics/` divide el corpus en dos modelos complementarios adaptados al formato de datos:
- **Modelo A — Corpus General y Percepción de Marca (`export_general_corpus.py` & `topic_modeling_A_general_colab.ipynb`):**
  - **Fuente:** Transcripciones y comentarios de YouTube (`silver.youtube_comentarios`).
  - **Objetivo:** Capturar la narrativa mediática y la percepción internacional de Tenerife (clima, vida nocturna, masificación vs paraíso natural, coste de vida).
- **Modelo B — Corpus Geográfico y Consejos de Viajeros (`export_geo_corpus.py` & `topic_modeling_geo_colab.ipynb`):**
  - **Fuente:** Foros especializados (`silver.losviajeros_mensajes`).
  - **Objetivo:** Extraer consejos de logística, estado de carreteras, rutas de senderismo (Anaga, Masca, Teide) y recomendaciones gastronómicas (guachinches).
- **Parámetros recomendados:** `min_topic_size=20`, `n_neighbors=15`, representación basada en `c-TF-IDF` + LLM representation.
- **Output:** Almacenamiento en `gold.nlp_topicos` con `texto_id`, `plataforma`, `topico_id`, `nombre_topico`, `palabras_clave`, `relevancia`.

---

### Subtarea 3.2 — Extracción Toponímica y Rescate Espacial (`analytics/geo/extract_toponyms.py`)
- **¿Qué resuelve?** Muchos comentarios dicen: *"La puesta de sol en Benijo fue mágica pero la carretera tiene curvas peligrosas"*. No hay latitud/longitud en la fila, pero hay un topónimo claro (*Benijo*).
- **Algoritmo del Gazetteer Insular:**
  1. Diccionario de entidades geográficas de Tenerife (playas, barrancos, núcleos, miradores, municipios).
  2. Detección por expresiones regulares normalizadas (eliminando stopwords y tildes).
  3. Desambiguación orográfica mediante hash de altitud MDT para nombres repetidos.
  4. Asignación del `cod_municipio` y el `h3_index` del centroide de la entidad geográfica detectada.
- **Resultado:** Puente crucial que permite filtrar opiniones cualitativas por municipio en el Dashboard y en la base RAG.

---

### Subtarea 3.3 — Base Vectorial Cualitativa (`gold.rag_documentos_viajeros`)
- **Esquema de la tabla Gold para RAG:**
  - `id`: BIGSERIAL PRIMARY KEY.
  - `fuente`: VARCHAR ('youtube_comentario', 'youtube_transcripcion', 'losviajeros', 'booking_review', 'tripadvisor_review').
  - `documento_id`: Identificador original del registro en Silver.
  - `municipio_mencionado`: VARCHAR (asignado por gazetteer toponímico o cruce espacial, nullable).
  - `h3_index`: VARCHAR (hexágono representativo, nullable).
  - `aspecto_relacionado`: VARCHAR ('limpieza', 'transporte', 'playas', 'gastronomia', 'ruido', 'precios', etc.).
  - `texto`: TEXT (chunk de texto limpio sin spam y > 20 caracteres).
  - `fecha`: DATE.
  - `embedding`: `vector(384)` (generado con `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`).
- **Índice Vectorial en PostgreSQL:**
  ```sql
  CREATE INDEX idx_rag_viajeros_embedding ON gold.rag_documentos_viajeros 
  USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);
  ```

---

### Subtarea 3.4 — Generación de Informes Narrativos Ejecutivos (`analytics/llm/`)
- Implementado en `analytics/llm/report_generator.py` y `report_generator_alojamiento.py` mediante clientes de Groq (`llama-3.3-70b-versatile` / `mixtral-8x7b-32768`).
- Genera resúmenes ejecutivos automáticos de percepción de marca y recomendaciones estratégicas por municipio o polo turístico.
- Alimenta la sección "Visión Estratégica" del Dashboard Streamlit.

---

## BLOQUE 4: `gold_h3_accesibilidad` — Accesibilidad Territorial Completa (ORS Matrix + PostGIS)
**Squad:** C (Personas 5 y 6) | **Prioridad:** Alta | **Semana:** 1

### ¿Qué es y para qué sirve?
Este bloque construye la tabla `gold.gold_h3_accesibilidad`, con **una fila por cada hexágono H3** (2.579 en total consolidados desde `silver_h3_grid`) y múltiples indicadores de accesibilidad calculados de forma precisa para toda la isla sin dejar ningún hexágono "ciego". Alimenta directamente al modelo MGWR del Bloque 5 como variables X, y al Dashboard como capas visuales interactivas.

La accesibilidad es uno de los predictores con **mayor peso estadístico** en la literatura turística: un establecimiento difícil de llegar desde el aeropuerto tiene hasta un 40% menos de probabilidad de éxito independientemente de su calidad intrínseca.

### Librerías necesarias
```
pip install openrouteservice geopandas pandas psycopg2-binary sqlalchemy shapely
```

---

### Subtarea 4.1 — Routing Matrix ORS: Tiempos Exactos de Conducción para toda la Isla (2.579 hexágonos × 18 destinos)
- **Precisión Espacial (Centroide Canónico H3)**: Se utilizan los centroides geométricos exactos de cada hexágono H3 en EPSG:4326.
- **¿Qué es?**: La **API de Matrices de ORS** calcula el tiempo de conducción desde CADA UNO de los 2.579 hexágonos hacia N destinos estratégicos. A diferencia de las isócronas (polígonos visuales), esto produce un **número exacto al minuto** (ej: 42.3 min) para cada hexágono, sin dejar ninguna zona aislada ni "ciega".
- **¿Por qué Matrix y no isócronas para el modelo estadístico?**: Las isócronas clasifican los hexágonos como "dentro o fuera de un anillo de 30 min" (dato binario, pierde resolución). La Matrix da `42.3 min` vs `43.1 min` — información continua mucho más útil para la regresión MGWR.
- **Coste de API**: Plan gratuito ORS: 500 peticiones/día, máx 3.500 pares origen-destino por petición. 2.579 hexágonos < 3.500 → **1 petición por destino**. 18 destinos × 1 petición = **18 peticiones totales** (~3.6% del límite diario).
- **Los 18 Destinos Estratégicos Finales**
| ID | Lugar | Coordenadas [lon, lat] | Justificación |
|---|---|---|---|
| `tfs` | Aeropuerto Sur (TFS) | `[-16.5726, 28.0445]` | Puerta de entrada del 70% del turismo internacional |
| `tfn` | Aeropuerto Norte (TFN) | `[-16.3413, 28.4827]` | Puerta de entrada del turismo nacional e interinsular |
| `capital` | Santa Cruz (Puerto) | `[-16.2519, 28.4700]` | Capital, ferry, conexión industrial y residencial |
| `extremo_sur` | Costa Adeje (centro) | `[-16.7356, 28.0805]` | Epicentro de la hostelería premium del sur |
| `extremo_norte` | Puerto de la Cruz (centro) | `[-16.5488, 28.4148]` | Epicentro del turismo del norte |
| `teide` | Teleférico del Teide (Base) | `[-16.6214, 28.2547]` | Principal punto de interés geográfico central |
| `la_laguna` | La Laguna (Histórico) | `[-16.3155, 28.4871]` | Patrimonio UNESCO y turismo cultural |
| `candelaria` | Basílica Candelaria | `[-16.3683, 28.3516]` | Turismo religioso y ruta costera sureste |
| `los_gigantes` | Acantilados Oeste | `[-16.8415, 28.2435]` | Polo turístico occidental y paisaje |
| `el_medano` | El Médano (Surf) | `[-16.5366, 28.0461]` | Polo turístico y deportivo del sur |
| `garachico` | Garachico (Pueblo) | `[-16.7645, 28.3734]` | Turismo natural/histórico del noroeste |
| `anaga` | Parque Rural de Anaga | `[-16.1573, 28.5660]` | Extremo noreste. Aislamiento geográfico y ecoturismo |
| `masca` | Masca (Teno) | `[-16.8344, 28.3197]` | Interior noroeste (Teno). Alta montaña y aislamiento |
| `vilaflor` | Vilaflor | `[-16.6377, 28.1582]` | Interior centro-sur. Pueblo a mayor altitud |
| `la_orotava` | La Orotava | `[-16.5227, 28.3903]` | Eje del Valle norte y paso obligado al Teide |
| `guimar` | Pirámides de Güímar | `[-16.4088, 28.3078]` | Interior del sureste. Ancla del valle de Güímar |
| `buenavista` | Buenavista del Norte | `[-16.8897, 28.3722]` | Extremo noroeste. Resorts de golf y ferry |
| `arico` | Poris de Abona / Arico | `[-16.4648, 28.1655]` | Costa sureste. Ancla para detectar alto PTNA costero |
- **Para que funcione bien**
  - Los centroides deben estar en formato `[lon, lat]` (ORS usa longitud primero, al contrario que PostGIS).
  - Hacer una llamada de prueba con solo 5 hexágonos para validar el formato antes de lanzar los 2.579.
  - La respuesta devuelve tiempos en **segundos** — dividir entre 60 para obtener minutos.
  - Si un hexágono queda en zona inaccesible por carretera (mar), ORS devuelve `null` → usar `COALESCE(valor, 999)`.

- **Código esqueleto**
```python
import openrouteservice
import pandas as pd
from sqlalchemy import create_engine

client = openrouteservice.Client(key='TU_ORS_API_KEY')
engine = create_engine("AZURE_DB_URL")

df = pd.read_sql("SELECT h3_index, centroide_lon, centroide_lat FROM silver.h3_grid", engine)
origenes = df[['centroide_lon', 'centroide_lat']].values.tolist()

destinos = {
    'tfs':           [-16.5726, 28.0445],
    'tfn':           [-16.3413, 28.4827],
    'capital':       [-16.2519, 28.4700],
    'extremo_sur':   [-16.7356, 28.0805],
    'extremo_norte': [-16.5488, 28.4148],
    'teide':         [-16.6433, 28.2728],
}

resultados = {'h3_index': df['h3_index'].tolist()}

for nombre, coords_destino in destinos.items():
    # 1 petición: 2579 orígenes → 1 destino (2579 pares < límite 3500)
    response = client.distance_matrix(
        locations=origenes + [coords_destino],
        sources=list(range(len(origenes))),
        destinations=[len(origenes)],
        profile='driving-car',
        metrics=['duration'],
    )
    # La API devuelve segundos -> convertir a minutos
    duraciones_min = [
        round(row[0] / 60, 1) if row[0] is not None else 999
        for row in response['durations']
    ]
    resultados[f'tiempo_{nombre}_min'] = duraciones_min

df_acc = pd.DataFrame(resultados)
# Columna derivada: aeropuerto más cercano y su tiempo
df_acc['tiempo_aeropuerto_min'] = df_acc[['tiempo_tfs_min', 'tiempo_tfn_min']].min(axis=1)
df_acc['aeropuerto_mas_cercano'] = df_acc.apply(
    lambda r: 'TFS' if r['tiempo_tfs_min'] <= r['tiempo_tfn_min'] else 'TFN', axis=1
)
df_acc.to_sql('h3_accesibilidad', engine, schema='gold', if_exists='replace', index=False)
print(f"Escritos {len(df_acc)} hexágonos en gold.h3_accesibilidad")
```
- **Output**
| Columna | Tipo | Descripción |
|---|---|---|
| `tiempo_tfs_min` | NUMERIC | Minutos en coche al Aeropuerto Sur |
| `tiempo_tfn_min` | NUMERIC | Minutos en coche al Aeropuerto Norte |
| `tiempo_capital_min` | NUMERIC | Minutos en coche a Santa Cruz |
| `tiempo_extremo_sur_min` | NUMERIC | Minutos en coche a Costa Adeje |
| `tiempo_extremo_norte_min` | NUMERIC | Minutos en coche a Puerto de la Cruz |
| `tiempo_teide_min` | NUMERIC | Minutos en coche al Teide |
| `tiempo_aeropuerto_min` | NUMERIC | MIN(tfs, tfn) — tiempo al aeropuerto más cercano |
| `aeropuerto_mas_cercano` | VARCHAR | 'TFS' o 'TFN' |

- **Interpretabilidad para TUI y el modelo MGWR**
  - `tiempo_aeropuerto_min` es la variable con **mayor peso estadístico esperado** en el modelo MGWR.
  - `tiempo_teide_min` captura la barrera orográfica: zonas con >45 min al Teide son extremas (Anaga, Teno), lo que explica su aislamiento del desarrollo turístico masivo.
  - Hexágono con `tiempo_aeropuerto_min > 60` y `ptna_score > 0` = zona remota con potencial real → segmento ecoturismo de aventura.

---

### Subtarea 4.2 — Isócronas Visuales Pre-calculadas (Capas Interactivas del Dashboard)
- **¿Qué es?**: Polígonos GeoJSON que delimitan las zonas alcanzables en 15, 30, 45 y 60 minutos en coche desde cada destino estratégico. Se calculan **una sola vez**, se guardan en BD como geometrías PostGIS, y el Dashboard los renderiza como capas toggleables en el mapa.
- **¿Por qué hace falta además de la Matrix?**: La Matrix da números por hexágono (invisible en el mapa). Las isócronas dan anillos de color visibles — el directivo de TUI activa "Aeropuerto Sur" y ve exactamente hasta dónde llega en 30 minutos de conducción. Son complementarias y ambas son necesarias.
- **Para que funcione bien**
  - Generar en orden decreciente (60, 45, 30, 15 min) para que los anillos interiores tapen los exteriores al pintar.
  - Guardar como `geometry` PostGIS con SRID 4326.
- **Código esqueleto**
```python
import openrouteservice, geopandas as gpd, json
from shapely.geometry import shape
from sqlalchemy import create_engine

client = openrouteservice.Client(key='TU_ORS_API_KEY')
engine = create_engine("AZURE_DB_URL")

destinos = {
    'tfs': [-16.5726, 28.0445], 'tfn': [-16.3413, 28.4827],
    'capital': [-16.2519, 28.4700], 'extremo_sur': [-16.7356, 28.0805],
    'extremo_norte': [-16.5488, 28.4148], 'teide': [-16.6433, 28.2728],
}
rangos_min = [60, 45, 30, 15]  # Decreciente para renderizado correcto en mapa

filas = []
for nombre, coords in destinos.items():
    response = client.isochrones(
        locations=[coords], profile='driving-car',
        range=[m * 60 for m in rangos_min], range_type='time'
    )
    for feature in response['features']:
        filas.append({
            'destino': nombre,
            'rango_min': feature['properties']['value'] // 60,
            'geometry': shape(feature['geometry'])
        })

gdf = gpd.GeoDataFrame(filas, geometry='geometry', crs=4326)
gdf.to_postgis('isocronas_visuales', engine, schema='gold', if_exists='replace')
print(f"Escritas {len(gdf)} isócronas en gold.isocronas_visuales")
```
- **Output**
Tabla `gold.isocronas_visuales` (24 filas — 6 destinos × 4 rangos):
| Columna | Tipo | Descripción |
|---|---|---|
| `destino` | VARCHAR | Nombre del punto de origen ('tfs', 'teide', etc.) |
| `rango_min` | INT | Rango temporal (15, 30, 45, 60 min) |
| `geometry` | GEOMETRY(POLYGON, 4326) | Polígono de la isócrona para pintar en el mapa |

- **Interpretabilidad para el Dashboard**
  El usuario activa/desactiva capas ("Aeropuerto Sur 30 min", "Teide 45 min"). Al superponer con la capa de PTNA, ve zonas de alto potencial bien conectadas → información de inversión inmediata.

---

### Subtarea 4.3 — Accesibilidad a Paradas de Bus a Pie (GTFS con 3 Umbrales)
- **¿Qué es?**: Contar cuántas paradas de autobús TITSA hay a distintas distancias del hexágono (200m, 500m, 1000m) y la distancia real a la más cercana. Mide la accesibilidad sin coche privado — crítica para el perfil de turista joven europeo o el residente sin vehículo.
- **Fuente Silver**: `silver.silver_gtfs_paradas` (columna `geometry` tipo POINT, SRID 4326).
- **Para que funcione bien**
  - El radio de 1000m supera intencionalmente el tamaño del hexágono (efecto vecindad), permitiendo medir accesibilidad peatonal a paradas que matemáticamente caen en hexágonos vecinos.
  - Usar `LEFT JOIN` (no `INNER JOIN`) para que zonas sin paradas registren conteos en 0.
  - La `dist_parada_cercana_m` devuelve `NULL` para hexágonos verdaderamente remotos donde no se detecte ninguna parada en el municipio o isla.

- **Output**
| Columna | Tipo | Descripción |
|---|---|---|
| `n_paradas_bus_200m` | INT | Paradas TITSA a ≤200m del centroide (ultra-urbano) |
| `n_paradas_bus_500m` | INT | Paradas TITSA a ≤500m del centroide (~7 min a pie) |
| `n_paradas_bus_1000m` | INT | Paradas TITSA a ≤1000m del centroide (~12 min a pie) |
| `dist_parada_cercana_m` | NUMERIC | Metros reales a la parada más cercana (NULL si no existe) |

- **Interpretabilidad y Uso Estratégico**
  - **Para el Modelo MGWR (Regresión)**: Usar **solo** `dist_parada_cercana_m` (variable continua). Evita la altísima multicolinealidad entre los 3 conteos (VIF altísimo) que desestabilizaría los coeficientes.
  - **Para el Modelo DBSCAN (Clustering)**: Usar `dist_parada_cercana_m` normalizada (StandardScaler) o aplicar un PCA a los 3 conteos para colapsarlos a 1 componente principal y no sesgar los clústers espaciales.
  - **Para el Dashboard (TUI)**: Usar las tres columnas binarias (`> 0`) como **filtros booleanos en el mapa**. Permite a un planificador turístico filtrar rápidamente zonas con "Bus en la puerta" vs "Bus accesible caminando".

---

### Subtarea 4.4 — Distancia al Hospital más Cercano (OSM + ST_Distance)
- **¿Qué es?**: Distancia en km al centro hospitalario/urgencias más cercano de cada hexágono. Factor relevante para turismo senior y familiar, que valora la seguridad sanitaria al elegir destino.
- **Fuente Silver**: `silver.osm_pois` donde `tipo = 'hospital'`. Los principales son HUNSC (Candelaria), HUC (La Laguna), Hospital Sur (Adeje) y Hospital Norte (Pto. de la Cruz).
- **Para que funcione bien**
  - Usamos distancia euclidiana (en línea recta con `::geography`) — suficiente para el modelo y sin coste de API.
  - `CROSS JOIN LATERAL` en lugar de `CROSS JOIN` simple para optimizar el plan de ejecución de PostgreSQL.

- **SQL exacto**
```sql
WITH hospitales AS (
    SELECT geometry, nombre
    FROM silver.osm_pois
    WHERE tipo = 'hospital' AND nombre IS NOT NULL
)
SELECT
    h.h3_index,
    ROUND(MIN(ST_Distance(
        ST_SetSRID(ST_MakePoint(h.centroide_lon, h.centroide_lat), 4326)::geography,
        hosp.geometry::geography
    ))::numeric / 1000, 2)  AS dist_hospital_km
FROM silver.h3_grid h
CROSS JOIN hospitales hosp
GROUP BY h.h3_index
```

- **Output**
| Columna | Tipo | Descripción |
|---|---|---|
| `dist_hospital_km` | NUMERIC | Kilómetros al hospital/urgencias más cercano |

- **Interpretabilidad para TUI y el modelo MGWR**
- `dist_hospital_km > 20` con PTNA alto → zona con potencial pero con riesgo percibido de aislamiento sanitario → establecimientos adecuados: ecoturismo de aventura o rural, NO resort familiar de lujo.
- Dato clave para la segmentación del tipo de turista objetivo en los informes narrativos automáticos del Bloque 9.

---

### Subtarea 4.5 — Distancia a la Costa (Litoralidad como Atractivo Turístico)
- **¿Qué es?**: Distancia en km de cada hexágono a la línea de costa de Tenerife. Es el predictor más fuerte del precio por noche en la literatura turística española (coeficiente β ≈ -0.42 en estudios de precios hedónicos): a más distancia de la costa, menos precio y menos turismo convencional.
- **Fuente Silver**: El límite exterior de `silver.limites_municipales` — la unión de todos los polígonos municipales da el contorno de la isla, que equivale a la línea de costa.
- **Para que funcione bien**
  - `ST_Boundary(ST_Union(...))` extrae solo el perímetro exterior del polígono unificado de la isla.
  - Calcular una sola vez y reusar en todos los hexágonos con `CROSS JOIN`.
  - Sin coste de API.

- **SQL exacto**
```sql
WITH linea_costa AS (
    SELECT ST_Boundary(ST_Union(geometry)) AS geom
    FROM silver.limites_municipales
)
SELECT
    h.h3_index,
    ROUND(ST_Distance(
        ST_SetSRID(ST_MakePoint(h.centroide_lon, h.centroide_lat), 4326)::geography,
        lc.geom::geography
    )::numeric / 1000, 2)  AS dist_costa_km
FROM silver.h3_grid h
CROSS JOIN linea_costa lc
```

- **Output**
| Columna | Tipo | Descripción |
|---|---|---|
| `dist_costa_km` | NUMERIC | Kilómetros a la línea de costa más cercana |

- **Interpretabilidad para TUI y el modelo MGWR**
- `dist_costa_km < 1` + NDVI bajo + VIIRS alto = zona costera urbanizada (Las Américas, Los Cristianos).
- `dist_costa_km < 2` + NDVI alto + PTNA alto = **franja costera verde sin desarrollar** → oportunidad premium para TUI (resort de alto standing con acceso a naturaleza y playa).
- Es la variable que mejor separará los clústeres `"Saturado"` (pegados a la costa) vs `"Rural Infrautilizado"` (interior de la isla).

---


### Subtarea 4.6 [Avanzado] — Walkability Index y pgRouting Local (OSM)
- **¿Qué es?**: En lugar de depender de APIs externas, se descarga la red real de calles, aceras y senderos de Tenerife desde OpenStreetMap (OSM) y se crea un **servidor de rutas propio dentro de PostgreSQL**. Esto permite calcular distancias reales a pie y la "caminabilidad" (Walkability Index) de cada hexágono, que es brutal para predecir el éxito de alojamientos orientados a turistas sin coche. Demuestra un dominio absoluto de bases de datos espaciales y topologías de red (Grafos). Rompe cualquier límite de peticiones (puedes calcular una matriz de 2579x2579 si quieres) y es 100% gratuito.

- **Librerías y Herramientas necesarias**
  - Herramienta de línea de comandos: `osm2pgrouting` (para convertir el `.osm.pbf` a tablas SQL de nodos y aristas).
  - Extensión PostgreSQL: `CREATE EXTENSION pgrouting;`

- **Para que funcione bien**
  1. Descargar el mapa de Canarias desde Geofabrik (`canarias-latest.osm.pbf`) y recortar Tenerife con `osmium`.
  2. Usar `osm2pgrouting` para crear las tablas `ways` y `ways_vertices_pgr`.
  3. Calcular el **Walkability Index**: la densidad de intersecciones (cruces de calles) por hexágono. A mayor densidad, más "caminable" es la zona (las zonas peatonales tienen muchos cruces cortos; las autopistas pocos y largos).

- **SQL exacto (Cálculo del Walkability Index)**
```sql
-- Contar cuántos nodos (cruces/intersecciones) de la red peatonal caen en cada hexágono
SELECT 
    h.h3_index,
    COUNT(v.id) AS n_intersecciones_osm,
    ROUND((COUNT(v.id) / h.area_km2)::numeric, 2) AS walkability_index
FROM silver.h3_grid h
LEFT JOIN ways_vertices_pgr v 
    ON ST_Contains(h.geometry, v.the_geom)
GROUP BY h.h3_index, h.area_km2
```

- **Output**
| Columna | Tipo | Descripción |
|---|---|---|
| `walkability_index` | NUMERIC | Densidad de cruces/calles por km² (Walkability) |

- **Interpretabilidad para TUI y el modelo MGWR**
- `walkability_index > 150` = Zona urbana altamente caminable (ej: Centro de La Laguna o Puerto de la Cruz). Ideal para hoteles *boutique* urbanos donde el turista valora salir andando a cenar.
- Un índice alto correlaciona positivamente con el rating de TripAdvisor en "Ubicación".

---

### Output Final del Bloque 4

**Tabla principal:** `gold.gold_h3_accesibilidad` | **Filas:** 2.583 | **Coste total API:** 0 €

Desglose exhaustivo de las **27 columnas** calculadas por [`analytics/accesibilidad/gold_h3_accesibilidad.py`](file:///c:/Users/ROBERTO/Proyectos_Python/TFM_TUI_Tenerife/AI_Dashboard_Core/analytics/accesibilidad/gold_h3_accesibilidad.py):

| Nº | Columna | Tipo | Subtarea / Origen | Descripción y Uso en MGWR / Dashboard |
|:---:|---|---|---|---|
| 1 | `h3_index` | VARCHAR(15) | PK | Clave primaria de unión (Malla H3 Resolución 8). |
| 2 | `tiempo_aeropuerto_min` | NUMERIC | Derivada (4.1) | `MIN(tiempo_tfs_min, tiempo_tfn_min)`. **Variable X principal en MGWR** (fricción de llegada exterior). |
| 3 | `aeropuerto_mas_cercano` | VARCHAR(3) | Derivada (4.1) | Código del aeropuerto con menor tiempo de acceso: `'TFS'` (Sur) o `'TFN'` (Norte). Filtro de Dashboard. |
| 4 | `tiempo_tfs_min` | NUMERIC | ORS Matrix (4.1) | Tiempo en coche por carretera (minutos) al Aeropuerto Tenerife Sur (Reina Sofía). |
| 5 | `tiempo_tfn_min` | NUMERIC | ORS Matrix (4.1) | Tiempo en coche por carretera (minutos) al Aeropuerto Tenerife Norte (Ciudad de La Laguna). |
| 6 | `tiempo_capital_min` | NUMERIC | ORS Matrix (4.1) | Tiempo en coche por carretera a Santa Cruz de Tenerife. |
| 7 | `tiempo_extremo_sur_min` | NUMERIC | ORS Matrix (4.1) | Tiempo en coche a Costa Adeje / Playa de las Américas. Base para `tiempo_polo_turistico_min`. |
| 8 | `tiempo_extremo_norte_min` | NUMERIC | ORS Matrix (4.1) | Tiempo en coche a Puerto de la Cruz. Base para `tiempo_polo_turistico_min`. |
| 9 | `tiempo_teide_min` | NUMERIC | ORS Matrix (4.1) | Tiempo en coche al Teleférico del Teide (Base). **Variable X en MGWR** (atractor central de montaña). |
| 10 | `tiempo_la_laguna_min` | NUMERIC | ORS Matrix (4.1) | Tiempo en coche a San Cristóbal de La Laguna (Ciudad Patrimonio UNESCO). |
| 11 | `tiempo_candelaria_min` | NUMERIC | ORS Matrix (4.1) | Tiempo en coche a Candelaria (Centro religioso / costa este). |
| 12 | `tiempo_los_gigantes_min` | NUMERIC | ORS Matrix (4.1) | Tiempo en coche a Acantilados de Los Gigantes (Polo turístico oeste). |
| 13 | `tiempo_el_medano_min` | NUMERIC | ORS Matrix (4.1) | Tiempo en coche a El Médano (Polo de deportes náuticos y viento). |
| 14 | `tiempo_garachico_min` | NUMERIC | ORS Matrix (4.1) | Tiempo en coche a Garachico (Polo histórico y piscinas naturales del noroeste). |
| 15 | `tiempo_anaga_min` | NUMERIC | ORS Matrix (4.1) | Tiempo en coche al Macizo de Anaga (Reserva de la Biosfera / senderismo). |
| 16 | `tiempo_masca_min` | NUMERIC | ORS Matrix (4.1) | Tiempo en coche al Caserío y Barranco de Masca. |
| 17 | `tiempo_vilaflor_min` | NUMERIC | ORS Matrix (4.1) | Tiempo en coche a Vilaflor (Pueblo más alto de la isla / acceso Teide Sur). |
| 18 | `tiempo_la_orotava_min` | NUMERIC | ORS Matrix (4.1) | Tiempo en coche a La Orotava (Patrimonio histórico / Valle de La Orotava). |
| 19 | `tiempo_guimar_min` | NUMERIC | ORS Matrix (4.1) | Tiempo en coche a Güímar (Pirámides y comarca sureste). |
| 20 | `tiempo_buenavista_min` | NUMERIC | ORS Matrix (4.1) | Tiempo en coche a Buenavista del Norte (Extremo noroeste / Teno). |
| 21 | `tiempo_arico_min` | NUMERIC | ORS Matrix (4.1) | Tiempo en coche a Porís de Abona / Arico (Escalada y costa intermedia). |
| 22 | `n_paradas_bus_200m` | INTEGER | GTFS PostGIS (4.3) | Paradas de bus TITSA a ≤ 200 m del centroide (~3 min a pie, estándar ultra-urbano). |
| 23 | `n_paradas_bus_500m` | INTEGER | GTFS PostGIS (4.3) | Paradas de bus TITSA a ≤ 500 m del centroide (~7 min a pie, cuenca caminable estándar). |
| 24 | `n_paradas_bus_1000m` | INTEGER | GTFS PostGIS (4.3) | Paradas de bus TITSA a ≤ 1.000 m del centroide (~12-14 min a pie, periurbano). |
| 25 | `dist_parada_cercana_m` | NUMERIC | GTFS PostGIS (4.3) | Distancia geodésica exacta en metros a la parada TITSA más próxima. **Variable X en MGWR**. |
| 26 | `dist_hospital_km` | NUMERIC | OSM PostGIS (4.4) | Distancia euclidiana mínima en km al hospital/clínica más cercano. **Variable X en MGWR**. |
| 27 | `dist_costa_km` | NUMERIC | Límites Mun (4.5) | Distancia euclidiana mínima en km a la línea de costa. **Variable X en MGWR** (litoralidad). |

**Tabla auxiliar:** `gold.isocronas_visuales` (24 filas — polígonos de 15, 30 y 45 min para el Dashboard en PyDeck)



## BLOQUE 5: `gold_h3_ptna` — Regresión Espacial MGWR + Índice PTNA (Potencial Turístico No Aprovechado)
**Squad:** B (Personas 3 y 4) | **Prioridad:** Alta | **Semana:** 2

### ¿Qué es y para qué sirve?
MGWR (Multiscale Geographically Weighted Regression) es el **modelo estadístico estrella del TFM**. Permite que un mismo factor (ej: "el verde/NDVI") tenga **distinto peso según la zona** — en el norte el NDVI importa menos que en el sur árido. Con sus resultados construimos el **PTNA**, el indicador más valioso del proyecto para TUI.

### Librerías necesarias
```
pip install mgwr libpysal scikit-learn numpy pandas matplotlib
```
---

### Subtarea 5.1 — Construir el dataset de regresión
- **Input:** `gold.gold_h3_master` LEFT JOIN `gold.gold_h3_accesibilidad` LEFT JOIN `gold.gold_h3_sentimiento`.
- **Filtro obligatorio:** Excluir hexágonos marítimos o con >50% de NaN.
- **Variable Y (a explicar):** `densidad_plazas_km2` (`n_plazas_registro / area_km2` del Registro Oficial de Turismo).
- **Variables X para MGWR (Seleccionadas bajo criterio de VIF < 10 y sin multicolinealidad):**
  | Variable X Real | Tabla Origen | Decisión / Razón de Negocio TUI |
  |---|---|---|
  | `altitud_media_m` | `gold_h3_master` | **Incluir** (Gradiente orográfico costa-cumbre, barrera a sol y playa) |
  | `slope_mean` | `gold_h3_master` | **Incluir** (Pendiente media: barrera constructiva y vial) |
  | `ndvi_medio` | `gold_h3_master` | **Incluir** (Sentinel-2: cobertura vegetal y atractivo paisajístico) |
  | `temp_media_anual` | `gold_h3_master` | **Incluir** (Confort térmico corregido por altitud con gradiente) |
  | `lluvia_mm_anual` | `gold_h3_master` | **Incluir** (Diferencial pluviométrico estructural norte/sur) |
  | `tiempo_aeropuerto_min` | `gold_h3_accesibilidad` | **Incluir** (`MIN(tiempo_tfs, tiempo_tfn)`: variable reina de conectividad exterior) |
  | `tiempo_polo_turistico_min` | `gold_h3_accesibilidad` | **Sustitución recomendada:** `MIN(tiempo_extremo_sur_min, tiempo_extremo_norte_min)` para capturar proximidad al polo turístico maduro más cercano evitando la colinealidad negativa de meter sur y norte separados. |
  | `tiempo_teide_min` | `gold_h3_accesibilidad` | **Incluir** (Fricción temporal al Parque Nacional / centro insular) |
  | `dist_parada_cercana_m` | `gold_h3_accesibilidad` | **Sustitución recomendada:** Usar la distancia continua en metros en lugar del conteo `n_paradas_bus_500m`, para evitar el exceso de ceros en zonas rurales y medir aislamiento continuo. |
  | `dist_hospital_km` | `gold_h3_accesibilidad` | **Incluir** (Seguridad sanitaria, factor crítico para turismo familiar y senior de TUI) |
  | `dist_costa_km` | `gold_h3_master` / `acc` | **Incluir** (Litoralidad y distancia al modelo sol y playa) |
  | `pct_area_enp` | `gold_h3_master` | **Incluir** (Restricción legal estricta al desarrollo hotelero) |
  | `n_restaurantes`, `n_naturaleza`, `n_cultura` | `gold_h3_master` | **Incluir** (Densidad de POIs y servicios de ocio caminables) |
  | `sentimiento_medio` | `gold_h3_sentimiento` | **Incluir** (Calidad percibida en Booking + TripAdvisor) |
  | `ndbi_medio` | `gold_h3_master` | **Excluir** (Proxy directo de urbanización, colineal con plazas) |
  | `viirs_medio` (todos) | `gold_h3_master` | **EXCLUIR** (Proxy directo de Y por luz nocturna, inflaría el R2 de forma tramposa) |
  | Columnas trimestrales (clima/NDVI/VIIRS) | `gold_h3_master` | **EXCLUIR** (Colinealidad casi perfecta con las medias anuales, VIF > 20) |
  | 15 Destinos secundarios ORS | `gold_h3_accesibilidad` | **EXCLUIR** (Los tiempos a Garachico, Buenavista, Güímar, etc. saturan el modelo de colinealidad. Solo se usan los 3 polos estratégicos). |
  | `walkability_index` | Teórico (pgRouting) | **EXCLUIR** (Sustituido con éxito por `dist_parada_cercana_m` + `n_restaurantes`). |

> **Nota de ejecución (post-implementación, 16-sep-2026):** De las 3 variables de tiempo listadas arriba (`tiempo_aeropuerto_min`, `tiempo_polo_turistico_min`, `tiempo_teide_min`), 2 (`tiempo_teide_min` y `tiempo_polo_turistico_min`) tuvieron que excluirse del modelo final por multicolinealidad severa: VIF 185.9–345.8 entre las 3 (muy por encima del umbral 10) y correlación >0.98 en los tres pares (r=0.9877 a r=0.9970) — en una isla de este tamaño, las 3 miden esencialmente lo mismo ("qué tan lejos del interior/costa está el hexágono"). Solo `tiempo_aeropuerto_min` quedó en el modelo MGWR final (v3). Detalle completo con la evidencia (matriz de correlación, VIF por variable) en `analytics/mgwr/docs/contexto_maestro_proyecto_ptna.md`, Hallazgo 10.

---

### Subtarea 5.2 — Ejecutar el modelo MGWR e Índice PTNA
- **`MGWR`**: Regresión Ponderada Geográficamente Multiescala
- **`PTNA`** Potencial Turístico No Aprovechado, se calcula como:
  ```
  PTNA = Valor_esperado_por_MGWR - Valor_observado_real
  ```
  - Normalizar todas las variables X con `StandardScaler` de sklearn antes de pasarlas al modelo.
  - Las coordenadas de entrada son los **centroides** de cada hexágono H3 en EPSG:4326.
- **Código esqueleto:**
```python
from mgwr.gwr import MGWR
from mgwr.sel_bw import Sel_BW
from sklearn.preprocessing import StandardScaler
import numpy as np

# Coordenadas de los centroides
coords = list(zip(df['centroide_lon'], df['centroide_lat']))
# Variables normalizadas
X = StandardScaler().fit_transform(df[variables_x].fillna(df[variables_x].median()))
y = df[['densidad_plazas_km2']].values

# Selección automática del ancho de banda
bw = Sel_BW(coords, y, X).search()
modelo = MGWR(coords, y, X, bw).fit()

df['coef_ndvi']  = modelo.params[:, 0]
df['ptna_score'] = modelo.predy.flatten() - y.flatten()  # Esperado - Observado
```
- *Output:* DataFrame con coeficientes locales por hexágono.
- Columna `ptna_score` añadida a `gold.gold_h3_ptna` y `gold.gold_h3_master`.
- **Interpretabilidad para TUI:** `ptna_score > 0` = el hexágono **debería** tener más plazas según sus condiciones territoriales/climáticas → **oportunidad de inversión**. `ptna_score < 0` = zona sobre-explotada → riesgo de saturación / overtourism.

---

### Subtarea 5.3 — Marco Multidimensional ESG (Environmental, Social, Governance) Territorial y Municipal
- **¿Qué es?**: Un sistema integral de evaluación de la sostenibilidad (0 a 100) que opera a dos escalas territoriales complementarias: **Microespacial H3** (para evaluar hexágonos y filtrar oportunidades con PTNA) y **Mesomunicipal** (para diagnóstico de políticas públicas, capacidad de carga y resiliencia territorial). Emplea **exclusivamente datos públicos abiertos** (Sentinel-2, VIIRS, Agrocabildo, OpenStreetMap, Registro Oficial de Turismo, ISTAC y opiniones de viajeros NLP).

- **1. Dimensión Medioambiental [E] (Environmental - 40%)**:
  - *Microespacial H3 (`gold_h3_master` / `gold_h3_ptna`)*:
    - `ndvi_medio` y su evolución interanual (`ndvi_2026 - ndvi_2022`): Salud vegetal, vigor ecológico y masa arbórea frente a degradación.
    - `viirs_medio` y `cambio_luz_nocturna_pct`: Polución lumínica y alteración de los ciclos biológicos de la avifauna insular (ej: pardela cenicienta).
    - `ndbi_medio`: Grado de sellado e impermeabilización del suelo frente a infiltración natural.
    - `pct_area_enp` y cercanía a la costa `dist_costa_km`: Fragilidad ecológica de hábitats protegidos y ecosistemas litorales.
    - `dias_ola_calor_anual` y `amplitud_termica_media`: Resiliencia climática y confort térmico microclimático.
  - *Mesomunicipal (`gold_municipio_master` / `gold_h3_master` agregado por municipio)*:
    - **Sobrecarga de Recursos e Hídrica:** Ratio de Población Turística Equivalente sobre Población Residente (`pob_turistica_equiv / poblacion_total` del ISTAC). Mide la presión per cápita directa sobre plantas desaladoras, redes de saneamiento, depuración de aguas residuales y recogida de residuos sólidos. **Cobertura real 6/31 municipios (19.4%) — se mantiene como columna informativa en `gold.gold_bloque5_municipio_anual_extra`, fuera del cálculo del score (ver nota de ejecución).**
    - **Salud vegetal y sellado de suelo:** `ndvi_medio`, agregado por `AVG` desde los hexágonos H3 del municipio (`gold_h3_master`).
    - **Contaminación lumínica:** `viirs_medio`, `AVG` por municipio.
    - **Fragilidad ecológica de hábitats protegidos:** `pct_area_enp`, ponderado por el área real de cada hexágono (`SUM(pct_area_enp · area_km2) / SUM(area_km2)`).
    - **Resiliencia climática:** `dias_ola_calor_anual` (`AVG` por municipio, capeado en el percentil 95 antes de normalizar) y `amplitud_termica_media` (`AVG` por municipio).

- **2. Dimensión Social [S] (Social - 40%)**:
  - *Microespacial H3 (`gold_h3_master` / `gold_h3_sentimiento`)*:
    - `densidad_plazas_km2` y ratio de presión habitacional: Riesgo de sobreturismo, gentrificación y expulsión de residentes por saturación de alojamiento turístico.
    - Cobertura de servicios esenciales y movilidad: `dist_hospital_km` (seguridad sanitaria) y equidad de acceso al transporte público (`dist_parada_cercana_m`, `n_paradas_bus_500m`).
    - Convivencia y bienestar vecinal (NLP): Proporción de quejas en reseñas de viajeros sobre masificación, suciedad o ruidos molestos (aspectos `ruido`, `precio`).
  - *Mesomunicipal (`gold_municipio_master` & `silver.silver_istac_anual`)*:
    - **Monocultivo y Vulnerabilidad Laboral:** `% dependencia hostelería` (`pct_dependencia_hosteleria`). Los municipios con hiperconcentración hostelera presentan una extrema vulnerabilidad social ante crisis exógenas (quiebras de turoperadores, pandemias).
    - **Tensión Social y Empleo:** Evolución del desempleo (`paro_actual`, `var_paro_pct`) y presión turística por habitante (`plazas_por_1000_hab`).
    - **Estructura Etaria y Dependencia Demográfica:** `edad_media` municipal (ISTAC 2025) y `ratio_dependencia` = `(poblacion_total − poblacion_15_64) / poblacion_15_64` (población fuera del tramo activo sobre población en edad activa). Sustituyen a `renta_bruta_irpf` y `% poblacion_extranjera` (ver nota de ejecución).

- **3. Dimensión de Gobernanza y Regulación [G] (Governance - 20%)**:
  - *Microespacial H3 (`gold_h3_master`)*:
    - **Regulación Formal vs Vivienda Vacacional:** Ratio `n_hoteles / (n_hoteles + n_vv)`. La oferta hotelera reglada se rige por convenios colectivos, inspección laboral estricta, control fiscal y licencias de actividad, mitigando la proliferación desregulada de viviendas vacacionales.
    - **Protección Patrimonial y Equipamiento:** Presencia de Bienes de Interés Cultural (`silver_bienes_culturales`), POIs institucionales y oficinas de información turística oficiales.
  - *Mesomunicipal (`gold_municipio_empleo` & `gold_h3_master` agregado por municipio)*:
    - **Formalización del Tejido Productivo:** `% autónomos` (`pct_autonomos`), reasignada desde el pilar Social — se interpreta aquí como proxy de formalización productiva/actividad económica independiente formal, no como tejido emprendedor. Sustituye a `empresas_ss` (ver nota de ejecución).
    - **Regulación Formal de Alojamiento (agregado municipal):** mismo ratio `n_hoteles / (n_hoteles + n_vv)` del pilar G microespacial, pero **sumado antes de dividir** por municipio (`SUM(n_hoteles) / SUM(n_hoteles + n_vv)`, nunca promedio del ratio por hexágono — la diferencia es sustancial, ver metodología). Sustituye a `parque_vehiculos_1000hab` (ver nota de ejecución).

- **Fórmula y Output**:
  - Normalización min-max de variables $X_{norm} = \frac{X - X_{min}}{X_{max} - X_{min}}$ (invirtiendo polaridad en factores negativos como polución lumínica, paro o ruido).
  - Ponderación compuesta: $Score_{ESG} = 0.40 \cdot E + 0.40 \cdot S + 0.20 \cdot G \in [0, 100]$.
  - Columna `esg_h3_score` en `gold.gold_h3_esg_v1` (nombre real verificado contra Postgres — el plan la nombraba `esg_territorial_score`, columna que no existe con ese nombre; ver nota de ejecución 3).
  - Dimensión mesomunicipal: tabla propia `gold.gold_bloque5_municipio_esg_v1` (31 filas, una por municipio), con columna `esg_municipal_score` — no se modificó `gold_municipio_master` para no tocar sin coordinar modelos dbt de otros bloques (ver nota de ejecución).
- **Interpretabilidad para TUI:** Permite implementar el filtro de inversión sostenible de TUI: seleccionar hexágonos con alto potencial no aprovechado ($PTNA > 0$) y excelente desempeño ESG ($esg\_h3\_score > 60$ — umbral ajustado a la escala real de la variable, ver nota de ejecución 3; el valor original del plan, $> 75$, es matemáticamente inalcanzable), garantizando un retorno financiero compatible con la sostenibilidad social y ecológica de Tenerife. Implementado como tabla propia `gold.gold_bloque5_h3_oportunidad_v1` (columna booleana `es_oportunidad_ideal`, 2579 filas, 247 en `true`).

> **Nota de ejecución (post-implementación, 16-sep-2026):** De las 6 variables mesomunicipales requeridas arriba, 2 (`pob_turistica_equiv` y las 4 columnas EOH de ocupación mensual) se resolvieron con tablas satélite propias del Bloque 5 (`gold.gold_bloque5_municipio_anual_extra`, `gold.gold_bloque5_municipio_mensual_extra`) en lugar de modificar `gold_municipio_master`/`gold_municipio_mensual` directamente, para no tocar sin coordinar los modelos dbt de otros bloques. Las otras 4 variables (`renta_bruta_irpf`, `poblacion_extranjera`, `empresas_ss`, `parque_vehiculos_1000hab`) siguen sin ingesta real — gap confirmado por grep en todo el repo, no hay ninguna tabla silver/gold que las contenga.

> **Nota de ejecución 2 — ESG mesomunicipal completo (post-implementación, 16-sep-2026):** Confirmado con el responsable de ISTAC del equipo que las 4 variables de la nota anterior no van a tener ingesta real. Decisión propia del equipo (libertad total sobre este bloque): reemplazarlas por variables que sí existen, verificadas contra Postgres con cobertura real sobre los 31 municipios, VIF (umbral 10) contra las variables ya en uso, y capeo p95 donde correspondía. Además, el pilar [E] mesomunicipal (que en el plan original dependía en solitario de `pob_turistica_equiv`, con cobertura real de solo 6/31 municipios) se completó con 5 variables adicionales agregadas desde `gold_h3_master` a nivel municipio, alcanzando cobertura 31/31 sin necesidad de excluir el pilar ni reponderar ignorándolo. Detalle completo de la verificación (semáforos, VIF, correlaciones, ejemplos numéricos) y la justificación conceptual de cada reemplazo en `analytics/mgwr/docs/metodologia_bloque5_ptna.md`, sección "Índice ESG Territorial — dimensión mesomunicipal". Tabla final: `gold.gold_bloque5_municipio_esg_v1` (31 filas), script `analytics/mgwr/scripts/08_gold_municipio_esg.py`. No se corrió de nuevo el modelo MGWR/PTNA — el ESG mesomunicipal es independiente de ese pipeline, igual que el ESG H3.

> **Nota de ejecución 3 — Filtro combinado PTNA×ESG para TUI (post-implementación, 16-sep-2026):** Este cruce, descrito como objetivo final de interpretabilidad de la Subtarea 5.3, nunca se había construido ni validado. Al hacerlo se encontraron 2 problemas reales, no solo de redacción: (1) la columna que el plan llama `esg_territorial_score` no existe — el nombre real en `gold.gold_h3_esg_v1` es `esg_h3_score`; (2) el umbral `esg_score > 75` de esta misma sección (y el `> 80` de la Subtarea 9.2, Bloque 9, que usa el mismo criterio con otro umbral — inconsistencia entre ambas secciones del plan detectada en este trabajo) son **matemáticamente inalcanzables**: el máximo real de `esg_h3_score` sobre los 2579 hexágonos es 68.55 (P50=55.08, P95=62.75). Decisión propia del equipo: mantener un umbral absoluto pero ajustado a la escala real, `esg_h3_score > 60` (en vez de un percentil dinámico), combinado sin cambios con `ptna_score > 0`. Resultado verificado contra Postgres: join 1:1 exacto entre `gold_h3_ptna_v3` y `gold_h3_esg_v1` (2579/2579, sin huérfanos), **247/2579 hexágonos cumplen el criterio**, de los cuales 22 tienen `confianza_ptna='baja'` (1 preexistente + 21 sumados después por el Hallazgo 12, ver `metodologia_bloque5_ptna.md` sección 3 — incluidos, no excluidos: se deja como columna informativa para que cada consumo decida si filtrarlo). Tabla final: `gold.gold_bloque5_h3_oportunidad_v1` (2579 filas totales, columna booleana `es_oportunidad_ideal`), script `analytics/mgwr/scripts/09_gold_h3_oportunidad.py`. **La Subtarea 9.2 (Bloque 9) no se tocó** — queda fuera del alcance de este bloque, pero hereda la misma inconsistencia de nombre de columna (`esg_territorial_score`) y de umbral (`> 80`) sin resolver; quien retome ese bloque debería revisar esta nota antes de implementarlo tal cual está escrito.

---

### Subtarea 5.4 — Análisis Numérico Multiescala y Elasticidades Temporales (ISTAC + AENA + MGWR)
- **Aprovechamiento de Variables Numéricas en Conjunto:**
  1. **Estratificación y Validación de Residuos Espaciales:** Cruzar el residuo **PTNA** de cada hexágono H3 con los indicadores estructurales de `gold.gold_municipio_master` (como `plazas_por_1000_hab` o `crec_plazas_vv_pct`). Permite identificar si los hexágonos con alto PTNA teórico están limitados en la práctica por saturación habitacional municipal o moratorias.
  2. **Modelado de Elasticidad y Series Temporales:** Con `gold.gold_municipio_mensual` y `gold.gold_municipio_anual`, analizar la elasticidad de oferta-empleo:
     - Relación econométrica entre el crecimiento de viviendas vacacionales (`crec_plazas_vv_yoy_pct`) y las variaciones del paro (`var_paro_yoy_pct`) y empleo en hostelería.
     - Detección cuantitativa del desacoplamiento 2025: la oferta de plazas VV se frena en municipios maduros (+0.1% en Arona, -0.2% en Adeje), mientras los ingresos siguen subiendo (+17.3% en Arona, +11.8% en Adeje) debido al incremento de tarifas medias diarias (ADR).
  3. **Correlación Cruzada de Demanda Aérea:** Cruzar `gold.gold_aena_pasajeros` con la serie mensual de ingresos y ocupación municipal para cuantificar la estacionalidad de demanda y los retardos temporales de transmisión del flujo de pasajeros entre aeropuertos (TFS / TFN) y zonas turísticas.

---

## BLOQUE 6: `gold_h3_clusters` — Clustering de Zonas Turísticas (HDBSCAN)
**Squad:** A (Personas 1 y 2) | **Prioridad:** Media | **Semana:** 2

### ¿Qué es y para qué sirve?
HDBSCAN agrupa automáticamente los hexágonos en **"tipos de zona"** según sus características biofísicas, de oferta, accesibilidad y reputación.

### Librerías necesarias
```
pip install hdbscan scikit-learn numpy pandas
```
---

### Subtarea 6.1 — Pipeline de Feature Engineering y Clustering (`analytics/clustering/build_features.py`)
- **Pipeline implementado en `analytics/clustering/build_features.py`:**
  - Carga los datos de `gold.gold_h3_master`, `gold.gold_h3_accesibilidad` y `gold.gold_h3_sentimiento`.
  - Imputación inteligente de nulos territoriales y normalización con `StandardScaler` / `MinMaxScaler`.
  - Reducción de dimensionalidad con PCA para evitar la maldición de la dimensionalidad en HDBSCAN.
- **Variables integradas:**
  - **Identidad Base**: `densidad_plazas_km2`, `n_plazas_hoteles`, `n_plazas_viviendas_vacacionales`.
  - **Satelital y Terreno**: `elevacion_media`, `ndvi_medio_anual`, `ndbi_medio_anual`, `viirs_medio_anual`.
  - **Accesibilidad**: `dist_parada_cercana_m`, PCA de tiempos ORS (`tiempo_aeropuerto_min`, `tiempo_teide_min`).
  - **Territorio**: `dist_costa_km`, `pct_area_enp`, `pct_area_zona_turistica`.
  - **Reputación y POIs**: `sentimiento_medio`, `n_resenas_total`, suma de POIs.
  - **Target de Inversión**: `ptna_score`.
- **Clústeres esperados:**
  - `"Saturado / Overtourism"` → Alta densidad de plazas, alta luz nocturna, bajo sentimiento (Sur: Las Américas, Los Cristianos).
  - `"Urbano Sin Turismo"` → Alta densidad urbana, alta luz nocturna, bajo NDVI, sin PTNA (Santa Cruz, La Laguna).
  - `"Rural Sostenible"` → Alto NDVI, alto PTNA, baja oferta regulada, buen ESG (Norte / Anaga, Teno).
  - `"Transición Costera"` → Oferta intermedia en transformación (Puerto de la Cruz, franja norte).
- **Output:** Tabla `gold.gold_h3_clusters` con `h3_index`, `cluster_id`, `tipo_zona`, `probabilidad_cluster`.

### Subtarea 6.2 — Validación Cartográfica de Clústeres
- Visualizar los clústeres en mapa interactivo de PyDeck/GeoPandas para contrastar con la realidad territorial insular y fijar las etiquetas de negocio definitivas para TUI._costa_km`, `pct_area_enp`, `pct_area_zona_turistica`
  - **Reputación y POIs**: `sentimiento_medio`, `n_resenas_total`, suma de `n_pois_naturaleza/playa/cultura`.
  - **Target**: `ptna_score`
- **Clústeres esperados:**
  - `"Saturado/Overtourism"` → Alta densidad, alta luz nocturna, bajo sentimiento (Sur: Las Américas).
  - `"Urbano Sin Turismo"` → Alta densidad, alta luz nocturna, bajo NDVI, sin PTNA (Santa Cruz, La Laguna).
  - `"Rural Infrautilizada"` → Alto NDVI, alto PTNA, poca oferta (Norte/Anaga, Teno).
  - `"Transición"` → (Puerto de la Cruz, franja costera norte).
- **Output:** Tabla `gold.h3_clusters` con `h3_index`, `tipo_zona`.

### Subtarea 6.2 — Etiquetar Manualmente los Clústeres
- *Acción:* Visualizar los clústeres en un mapa de Tenerife con `geopandas` + `matplotlib`. Estudiar qué zonas geográficas caen en cada clúster y ponerles un nombre.
- *Output:* Tabla `oro.h3_clusters` con columnas `h3_index`, `tipo_zona` (ej: `"Overtourism"`, `"Rural Infrautilizaada"`, `"Transicion"`).
---

## BLOQUE 7: Agente Text-to-SQL — Consultas en Lenguaje Natural al Mapa (LangChain + LLM)
**Squad:** B (Personas 3 y 4) | **Prioridad:** Media | **Semana:** 2

### ¿Qué es y para qué sirve?
Un directivo de TUI escribe: *"¿Qué zonas tienen alto potencial y buen sentimiento?"*. El agente traduce esa pregunta a SQL, la ejecuta y devuelve los resultados.

### Librerías necesarias
```
pip install langchain langchain-community langchain-openai sqlalchemy psycopg2-binary groq
```

---

### Subtarea 7.1 — Conectar LangChain a PostgreSQL Gold
- **Técnica:** `SQLDatabase` de LangChain conectado exclusivamente al esquema `gold`.
- **Tablas expuestas (SOLO Gold):**
  - `gold_h3_master`: Datos microterritoriales (hexágonos H3, oferta, POIs, clima, satélite).
  - `gold_municipio_master`: Datos municipales con polígono PostGIS, oferta agregada, demografía y ratios de evolución.
  - `gold_municipio_anual`: Serie anual 2022-2026 con variaciones YoY de paro, empleo e ingresos.
  - `gold_municipio_mensual`: Serie temporal mes a mes 2022-2026 con estacionalidad y comparativas interanuales `LAG 12`.
  - `gold_aena_pasajeros`: Tráfico mensual de pasajeros y operaciones en TFS y TFN por temporada.
  - `gold_h3_ptna`: Potencial Turístico No Aprovechado (MGWR).
  - `gold_h3_clusters`: Tipología de zonas (HDBSCAN: Overtourism, Rural, etc.).
- **Código esqueleto:**
```python
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import create_sql_agent
from langchain_groq import ChatGroq

tablas_gold = [
    "gold_h3_master", "gold_municipio_master", 
    "gold_municipio_anual", "gold_municipio_mensual", 
    "gold_aena_pasajeros", "gold_h3_ptna", "gold_h3_clusters"
]

db = SQLDatabase.from_uri(
    "AZURE_DB_URL",
    schema="gold", 
    include_tables=tablas_gold
)
llm = ChatGroq(model="openai/gpt-oss-120b", temperature=0)
agent = create_sql_agent(llm=llm, db=db, verbose=True)
```
- *Para que funcione bien:* Limitar las tablas expuestas al agente solo a las de la capa `gold`. No darle acceso a `silver` o `bronze` para evitar alucinaciones con esquemas en desarrollo.

---

### Subtarea 7.2 — System Prompt con Contexto del TFM
- *Acción:* Inyectar en el prompt del sistema las definiciones exactas de las tablas y columnas para consultas analíticas directas.
- *Ejemplo de System Prompt:*
  ```
  Eres un analista senior de inteligencia turística para TUI en Tenerife.
  Tienes acceso a la base de datos analítica (esquema gold, 100% libre de nulos y de ceros ficticios):
  - gold.gold_h3_master: Micro-nivel (hexágonos H3 de ~0.7 km²). Columnas: h3_index, municipio, n_plazas_registro, n_hoteles, n_vv, rating_booking_medio, rating_tripadvisor_medio, sentimiento_medio, queja_principal, temp_media_anual, lluvia_mm_anual, altitud_media_m, distancia_costa_metros, ndvi_medio, ndbi_medio, viirs_medio, es_enp.
  - gold.gold_municipio_master: Meso-nivel municipal (31 municipios). Foto fija actual, radiografía sectorial CNAE 2026, oferta reglada oficial (Cabildo) y satélite multitemporal. Columnas: cod_municipio, municipio, poblacion_actual, n_plazas_registro, n_hoteles, n_vv, densidad_plazas_km2, plazas_por_1000_hab, paro_actual, empleo_total_actual, empleo_asalariados_actual, empleo_autonomos_actual, empleo_hosteleria_actual, empleo_servicios_actual, empleo_comercio_actual, pct_dependencia_hosteleria, pct_terciarizacion, pct_autonomos, plazas_vv_actual, tasa_ocupacion_vv_actual, estancia_media_vv_actual, ingresos_vv_actual, crec_plazas_vv_pct, crec_ingresos_vv_pct, var_paro_pct, crec_empleo_total_pct, crec_empleo_autonomos_pct, ndvi_medio, ndbi_medio, cambio_ndbi_absoluto, viirs_medio, cambio_luz_nocturna_pct, geometry.
  - gold.gold_municipio_empleo: Evolución trimestral continua de afiliación (2022-Q1 a 2026-Q2). Columnas: cod_municipio, municipio, periodo, anio, trimestre, empleo_total, empleo_asalariados, empleo_autonomos, pct_autonomos, pct_asalariados, crec_empleo_total_yoy_pct, crec_empleo_autonomos_yoy_pct.
  - gold.gold_municipio_anual: Evolución anual continua (2022-2026). Columnas: cod_municipio, municipio, anio, n_meses, es_anio_completo, poblacion, paro_medio, var_paro_yoy_pct, empleo_total_medio, crec_empleo_total_yoy_pct, empleo_autonomos_medio, crec_empleo_autonomos_yoy_pct, plazas_vv_media, crec_plazas_vv_yoy_pct, ingresos_vv_media_mensual, crec_ingresos_mensual_yoy_pct, ingresos_vv_acumulados, tasa_ocupacion_vv_media, estancia_media_vv.
  - gold.gold_municipio_mensual: Serie mes a mes continua (2022-01 a 2026-07). Columnas: cod_municipio, municipio, periodo, anio, mes, trimestre, estacion ('Invierno', 'Primavera', 'Verano', 'Otoño'), paro_registrado, paro_yoy_pct, plazas_vv, plazas_vv_yoy_pct, tasa_ocupacion_vv, estancia_media_vv, ingresos_vv, ingresos_vv_yoy_pct, alojamientos_abiertos_vv.
  - gold.gold_turismo_hotelero_mensual: Hotelería tradicional EOH en los 6 municipios turísticos oficiales (Adeje, Arona, Puerto de la Cruz, Santiago del Teide, Santa Cruz, Granadilla). Columnas: cod_municipio, municipio, polo_turistico, periodo, anio, mes, trimestre, estacion, viajeros_entrados, pernoctaciones, plazas_ofertadas_hotel, tasa_ocupacion_plazas, estancia_media_hotel_dias, crec_viajeros_yoy_pct, crec_pernoctaciones_yoy_pct.
  - gold.gold_turismo_hotelero_anual: Hotelería acumulada y Población Turística Equivalente (PTE) en los 6 municipios turísticos. Columnas: cod_municipio, municipio, polo_turistico, anio, poblacion, pob_turistica_equiv, pct_pob_turistica_equiv_sobre_pob, viajeros_entrados_total, pernoctaciones_total, plazas_ofertadas_hotel_media, ocupacion_media_plazas, estancia_media_hotel_dias.
  - gold.gold_aena_pasajeros: Aeropuertos (TFS y TFN, mensual). Columnas: periodo, anio, mes, aeropuerto_codigo, aeropuerto_nombre, temporada, pasajeros, operaciones, pasajeros_por_operacion.
  - gold.gold_h3_ptna: Oportunidades de inversión (ptna_score > 0 indica potencial no aprovechado).
  - gold.gold_h3_clusters: Clústeres espaciales (tipo_zona: 'Overtourism', 'Rural Sostenible', 'Transicion').
  Reglas:
  - Para preguntas espaciales de hexágonos, consulta gold_h3_master.
  - Para preguntas de impacto social, empleo general, oferta de hoteles/VVs o ranking municipal insular actual, consulta gold_municipio_master.
  - Para análisis de series temporales de empleo y autoempleo, consulta gold_municipio_empleo.
  - Para comparativas históricas año a año de todos los municipios, consulta gold_municipio_anual.
  - Para preguntas sobre estacionalidad climática mensual de vivienda vacacional y paro, consulta gold_municipio_mensual.
  - Para preguntas sobre el sector hotelero tradicional (EOH: pernoctaciones, viajeros, ocupación de camas de hotel), consulta gold_turismo_hotelero_mensual.
  - Para preguntas sobre Población Turística Equivalente (PTE), presión demográfica flotante o totales hoteleros anuales, consulta gold_turismo_hotelero_anual.
  - Para preguntas sobre conectividad aérea, vuelos y tráfico de pasajeros, consulta gold_aena_pasajeros.
  ```

---

### Subtarea 7.3 — Validación con Preguntas de Negocio TUI
Probar el agente con consultas reales de diferentes granularidades:
1. *Micro / Espacial:* "¿Qué hexágonos de Adeje tienen más de 500 plazas y una queja principal de ruido?"
2. *Meso / Municipal:* "¿Cuáles son los 5 municipios con mayor presión turística (plazas por habitante)?"
3. *Tendencia Anual:* "¿En qué municipio crecieron más los ingresos por vivienda vacacional entre 2022 y 2025?"
4. *Macro / Aeropuertos:* "¿Cuál es el mes de mayor tráfico de pasajeros internacionales en Tenerife Sur?"
5. *Estratégica / Inversión:* "Muéstrame zonas con ptna_score alto que no estén en Espacio Natural Protegido."

---

### Subtarea 7.4 — Arquitectura RAG para Consultas Cualitativas (Embeddings)
- **¿Por qué RAG además de Text-to-SQL?**
  - **Text-to-SQL (Tablas Gold):** Responde preguntas cuantitativas, agregadas y espaciales (*¿Cuántos?, ¿Dónde?, ¿Qué porcentaje?*).
  - **RAG Semántico (pgvector en Gold):** Responde preguntas cualitativas no estructuradas (*¿Qué opinan los turistas sobre las carreteras de Anaga?*, *¿Por qué se quejan del transporte público en Los Cristianos?*).
- **Estructura de la tabla RAG (`gold.rag_documentos_viajeros`):**
  - `id`: Identificador único.
  - `fuente`: 'youtube', 'losviajeros', 'tripadvisor', 'booking'.
  - `municipio_mencionado`: Topónimo asignado vía gazetteer (o NULL).
  - `texto`: Texto limpio de la reseña / comentario / mensaje.
  - `fecha`: Fecha de publicación.
  - `embedding`: Columna tipo `vector(384)` generada con `sentence-transformers/all-MiniLM-L6-v2` o `paraphrase-multilingual-mpnet-base-v2`.
- **Flujo del Chatbot Dual en Streamlit:**
  1. El router evalúa la consulta del usuario.
  2. Si la consulta es cuantitativa/estructurada → llama al **SQL Agent (Text-to-SQL)** contra `gold.*`.
  3. Si la consulta es de opinión/experiencia → realiza una búsqueda por similitud de coseno (`<->`) en `gold.rag_documentos_viajeros` y sintetiza la respuesta con el LLM citando las opiniones reales recuperadas.

---

## BLOQUE 8: Dashboard Streamlit — Mapa H3 Interactivo + Chatbot IA
**Squad:** C (Personas 5 y 6) | **Prioridad:** Alta | **Semana:** 2-3

### ¿Qué es y para qué sirve?
El producto entregable final para TUI. Mapa interactivo, capas toggleables, panel global y chatbot IA integrado.

### Librerías necesarias
```
pip install streamlit pydeck sqlalchemy geopandas pandas plotly wordcloud
```
---

### Subtarea 8.1 — Conexión y Carga Optimizada de Modelos Gold
- *Técnica:* Usar `st.cache_resource` para el motor SQLAlchemy y `st.cache_data` con TTL para cachear las tablas de la capa Gold al arrancar la aplicación:
- *Código esqueleto:*
  ```python
  import streamlit as st
  from sqlalchemy import create_engine
  import geopandas as gpd
  import pandas as pd

  @st.cache_resource
  def get_engine():
      return create_engine("AZURE_DB_URL")

  @st.cache_data
  def load_gold_data():
      engine = get_engine()
      # Microterritorial: hexágonos H3 con geometría
      gdf_h3 = gpd.read_postgis(
          "SELECT h3_index, municipio, n_plazas_registro, n_hoteles, n_vv, "
          "rating_booking_medio, ndvi_medio, temp_media_anual, ptna_score, esg_territorial_score, "
          "tipo_zona, geom FROM gold.gold_h3_master "
          "LEFT JOIN gold.gold_h3_ptna USING (h3_index) "
          "LEFT JOIN gold.gold_h3_clusters USING (h3_index)",
          engine, geom_col="geom"
      )
      # Mesoterritorial: 31 municipios con polígono PostGIS (SRID 4326)
      gdf_mun = gpd.read_postgis(
          "SELECT cod_municipio, municipio, poblacion_actual, n_plazas_registro, "
          "densidad_plazas_km2, plazas_por_1000_hab, paro_actual, empleo_hosteleria_actual, "
          "crec_plazas_vv_pct, crec_ingresos_vv_pct, var_paro_pct, geometry "
          "FROM gold.gold_municipio_master",
          engine, geom_col="geometry"
      )
      # Series temporales mensuales (ISTAC y AENA)
      df_mun_mes = pd.read_sql("SELECT * FROM gold.gold_municipio_mensual ORDER BY periodo", engine)
      df_aena = pd.read_sql("SELECT * FROM gold.gold_aena_pasajeros ORDER BY periodo", engine)
      return gdf_h3, gdf_mun, df_mun_mes, df_aena
  ```

---

### Subtarea 8.2 — Mapa Multiescalar Interactivo (PyDeck)
- *Librería:* `pydeck` (motor deck.gl de alto rendimiento).
- *Capas del Mapa (Selector por Escala y Temática):*
  1. **Capa Municipal Coroplética (`GeoJsonLayer` / `PolygonLayer`):**
     - Polígonos de los 31 municipios desde `gold.gold_municipio_master.geometry`.
     - Coloreado temático según métricas de presión:
       - *Presión Residencial:* `plazas_por_1000_hab` (gradiente verde a rojo intenso).
       - *Densidad Turística:* `densidad_plazas_km2`.
       - *Evolución de Oferta:* `crec_plazas_vv_pct` (2022 vs 2025/2026).
     - Al hacer clic en un municipio: centrado automático de cámara y filtrado de los hexágonos H3 pertenecientes a dicho término municipal.
  2. **Capa Microespacial Hexagonal H3 (`PolygonLayer`):**
     - Malla de 2.746 celdas desde `gold.gold_h3_master`.
     - Modos de visualización:
       - *Oportunidades de Inversión:* `ptna_score` (amarillo-dorado = alto potencial no aprovechado).
       - *Sostenibilidad Territorial:* `esg_territorial_score` (verde esmeralda = eco-sostenible).
       - *Tipologías HDBSCAN:* Colores discretos por `tipo_zona` (Rojo = Overtourism, Verde = Rural Sostenible, Azul = Urbano, Naranja = Transición).
  3. **Capa de Isócronas y Conectividad (`gold.isocronas_visuales`):**
     - Polígonos translúcidos de tiempos de viaje (15, 30, 45 min) a TFS, TFN y Parque Nacional del Teide.

---

### Subtarea 8.3 — Explorador de Macrotendencias y Series Temporales (Plotly)
- **Pestaña "Coyuntura y Series Temporales":**
  - **Selector Multivariante de Municipios:** Permite al usuario comparar hasta 4 municipios simultáneamente (ej: Adeje vs Arona vs Puerto de la Cruz vs Santa Cruz).
  - **Gráficos Dinámicos con Plotly:**
    - *Curva de Vivienda Vacacional vs Ingresos:* Serie 2022-2026 de `plazas_vv` e `ingresos_vv` mensuales para identificar el desacoplamiento de precios y oferta.
    - *Impacto Laboral:* Serie comparativa de `empleo_hosteleria` frente a `paro_registrado`.
    - *Tasas Interanuales (YoY):* Evolución de variaciones porcentuales mismo mes año anterior (`LAG 12`) que revelan el punto de inflexión de 2025.
  - **Panel Macro AENA en Cabecera:**
    - Tarjetas KPI con pasajeros último mes, variación respecto al año anterior y ratio pasajeros/vuelo.
    - Gráfico comparativo de estacionalidad: TFS (predominio internacional, pico en invierno) vs TFN (tráfico nacional e interinsular, pico en verano).

---

### Subtarea 8.4 — Panel Lateral del Chatbot IA Híbrido (Text-to-SQL + RAG)
- **Integración Nativa con `st.chat_input` y `st.chat_message`:**
- **Orquestador Dual Inteligente:**
  1. Si la consulta del usuario es cuantitativa, de agregación o espacial (*"¿cuántas plazas hoteleras hay en Adeje?", "¿qué municipio tiene mayor paro?"*):
     - El router despacha la petición al **SQL Agent (LangChain Text-to-SQL)** contra las tablas `gold.*`.
     - Genera la consulta SQL, la ejecuta y presenta la cifra o tabla resumen.
  2. Si la consulta es de percepción, quejas o experiencia del viajero (*"¿por qué se quejan los turistas del transporte en el sur?", "¿qué opinan sobre las carreteras de Anaga?"*):
     - El router despacha la petición al **Motor RAG Semántico**.
     - Ejecuta búsqueda por similitud de coseno (`<->`) en `gold.rag_documentos_viajeros`.
     - El LLM sintetiza los fragmentos recuperados citando las fuentes reales (YouTube / LosViajeros).
- **Contextualización Cartográfica Interactiva:** Al hacer clic en un municipio o hexágono en el mapa, sus datos clave se inyectan en el prompt del chat como contexto de sesión, permitiendo al usuario repreguntar: *"¿Qué podemos hacer en este municipio según sus datos?"*.

---

### Subtarea 8.5 — Gráficos de Detalle y Simulador de Escenarios ("What-If")
- **Panel Drawer al Seleccionar un Hexágono:**
  - Radar chart con valoraciones de aspectos NLP (limpieza, servicio, ubicación, ruido, precio) procedentes de `gold.gold_h3_sentimiento`.
  - Comparativa del hexágono frente a la media de su municipio (en NDVI, altitud, ratio de plazas).
- **Simulador What-If Interactivo:**
  - Sliders para modificar variables locales (ej. "+300 plazas hoteleras", "-10 min al aeropuerto por mejora vial").
  - Multiplicación matricial instantánea por los coeficientes locales guardados de MGWR (`coef_tiempo_aeropuerto`, `coef_ndvi`) para proyectar el nuevo $PTNA$ estimado sin demoras de base de datos.

## BLOQUE 9: Informe Narrativo Automático + Redacción del TFM
**Squad:** Todos | **Semana:** 3

### ¿Qué es y para qué sirve?
Convertir los resultados numéricos del modelo en lenguaje ejecutivo comprensible para TUI, y documentar el trabajo completo en el PDF del TFM.

---

### Subtarea 9.1 — Informe Ejecutivo Automático por Zona (LLM)
- Para los **5 hexágonos con mayor PTNA**, llamar al LLM (Groq) con el contexto del hexágono y generar recomendación: *"Este hexágono en el norte de la isla presenta una cobertura vegetal del 78%, accesibilidad de 25 min desde TFN, pero solo 12 plazas hoteleras. Recomendación: evaluar apertura de hotel rural."*
- *Output:* Sección "Informe Automático" en el Dashboard.

---

### Subtarea 9.2 [Avanzado] — Motor de Alertas Inteligentes (Push Triggers)
- **¿Qué es?**: Un sistema proactivo ("Inbox" en el Dashboard) donde el LLM evalúa anomalías o combinaciones clave en los datos y emite alertas para el usuario sin que este tenga que preguntar.
- **Técnica**: Programar un script que se ejecute post-dbt (o al iniciar el dashboard) que busque:
  1. *Alertas de Overtourism*: `esg_territorial_score < 40` + `sentimiento_medio < 2`.
  2. *Alertas de Oportunidad*: `ptna_score > 80` + `esg_territorial_score > 80`.
- **Integración con el LLM**: Se le pasa esa lista de hexágonos al LLM para que redacte la alerta en tono ejecutivo (ej. "Riesgo detectado en Arona Sur: saturación crítica y quejas por ruido").
- **Output**: Sección "Notificaciones / Inbox" en la barra lateral del Dashboard.

---

### Subtarea 9.3 — Redacción del TFM
- **Squad A:** Capítulo NLP — Métodos (BERT, PyABSA, BERTopic), Resultados.
- **Squad B:** Capítulo Análisis Espacial — MGWR (coeficientes locales, PTNA), Agente Text-to-SQL.
- **Squad C:** Capítulo Infraestructura — Pipeline Bronze→Silver→Gold, Accesibilidad, Dashboard.

---

## BLOQUE 10: DÍAS FINALES (Días 19-21) — Pruebas y Cierre
**Squad:** Todos | **Semana:** 3 (últimos días)

### Día 19 — Test de Integración End-to-End
- Verificar pipeline completo sin errores: `dbt run → NLP → MGWR → Dashboard`.
- Confirmar 2.579 filas de `gold.gold_h3_master` sin NULLs en columnas críticas.
- **Test de carga:** 3 personas navegando simultáneamente.

### Día 20 — Simulacro con Preguntas TUI
- Ejecutar las 10 preguntas Text-to-SQL y validar resultados visuales en mapa.
- Mostrar los 5 informes narrativos al tutor.

### Día 21 — Congelación y Entrega
- **Congelación del código:** Tag `v1.0.0` en GitHub. No se aceptan más commits.
- **Checklist final:**
  - [ ] Dashboard desplegado y accesible (URL pública o demo en local)
  - [ ] PDF del TFM revisado cruzado y entregado

---

## Issues Pendientes en Silver (No bloqueantes para Gold)
| # | Problema | Acción recomendada |
|---|---|---|
| #7 | `silver_clima_horario_agrocabildo` sin variable semántica | Descargar metadatos Agrocabildo y hacer JOIN |
| #9 | `silver_enp` tiene `municipio` NULL | Hacer `ST_Intersection` en Gold |
| #12 | `silver_gfs_hist` no aporta territorialmente | Excluir de Gold |

---

## Orden de Ejecución Recomendado
```
SEMANA 1:
  Día 1-2: dbt run --select silver
  Día 3-5: BLOQUE 1 (gold_h3_master) | BLOQUE 4 (accesibilidad) | BLOQUE 2 (NLP coordenadas)

SEMANA 2:
  Día 6-7: BLOQUE 2 (aspectos PyABSA) | BLOQUE 3 (NLP global YouTube/LosViajeros)
  Día 8-9: BLOQUE 5 (MGWR + PTNA) | BLOQUE 6 (Clustering zonas)
  Día 10:  BLOQUE 7 (Text-to-SQL Agente LangChain)

SEMANA 3:
  Día 11-14: BLOQUE 8 (Dashboard Streamlit) | BLOQUE 9 (Informes LLM + Redacción PDF)
  Día 15-21: BLOQUE 10 (Pruebas End-to-End, Simulacro TUI, Entrega)
```