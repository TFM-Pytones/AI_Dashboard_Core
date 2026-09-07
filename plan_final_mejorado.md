# 🎯 Plan Final TFM — TUI Tenerife
## Arquitectura Completa y Estado Real del Proyecto

> **Documento de referencia actualizado:** 25 agosto 2026  
> Sustituye al `plan_maestro_tecnico.md` en todos los aspectos de arquitectura de datos.

---

## 🗺️ Arquitectura General: Pipeline Medallón

```
[Fuentes Externas] → Bronze (Azure Blob + Postgres) → Silver (dbt, limpieza) → Gold (dbt, análisis)
```

El flujo de datos completo es:
1. **Ingesta desde el origen** → Script Python descarga/scrapea y sube al **Azure Blob Storage** (container `bronce-raw`).
2. **Bronze → PostgreSQL** → `ingest_bronze_to_postgres.py` lee el Blob y carga tablas crudas en el esquema `bronze` de la base de datos PostgreSQL.
3. **Silver** → dbt lee de `bronze.*` y produce tablas limpias, tipadas y con geometrías PostGIS en el esquema `silver`.
4. **Gold** → dbt lee de `silver.*` y produce los agregados, análisis y features finales en el esquema `gold`.

---

## 🥉 Capa Bronze — Estado Real

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
| `open_meteo_forecast` | Predicciones GFS (⚠️ baja prioridad para el TFM) | `ingest_bronze_to_postgres.py` |
| `istac_municipios` | Indicadores económicos municipales ISTAC | `ingest_bronze_to_postgres.py` |
| `istac_mun_plazas_vv` + otras ISTAC | Estadísticas de VV por municipio | `ingest_bronze_to_postgres.py` |
| `h3_grid` | Malla hexagonal H3 resolución 8 (2.396 celdas) | `ingest_vector_to_postgres.py` |
| `espacios_naturales` | Polígonos ENP (Espacios Naturales Protegidos) | `ingest_vector_to_postgres.py` |
| `limites_municipales` | Polígonos de los 31 municipios de Tenerife | `ingest_vector_to_postgres.py` |
| `zonas_turisticas` | Polígonos de zonas turísticas | `ingest_vector_to_postgres.py` |
| `osm_pois_tenerife` | 15.000+ POIs de OpenStreetMap | `ingest_vector_to_postgres.py` |
| `bienes_culturales` | Polígonos de BIC (Bienes de Interés Cultural) | `ingest_vector_to_postgres.py` |
| `oficinas_turismo` | Puntos de Oficinas de Turismo | `ingest_vector_to_postgres.py` |
| `mdt_stats` | Estadísticas raster MDT (altitud/pendiente) por H3 | Pre-calculado |
| `satelite_stats` | Estadísticas raster NDVI/VIIRS por H3 | Pre-calculado |

---

## 🥈 Capa Silver — Estado Real y Completo

La capa Silver tiene la siguiente estructura final (tras consolidación). 

> [!IMPORTANT]
> En todos los modelos con geometrías, la columna se llama `geometry` y es de tipo `geometry(4326)`. Los índices GIST se definen en el `{{ config() }}` de dbt.

### 📁 alojamiento/
| Modelo | Descripción | Estado |
|---|---|---|
| `silver_registro_hoteles` | Hoteles limpios con `geometry` PostGIS. Coordenadas enriquecidas con geocodificador (COALESCE). Cast seguro `NULLIF`+`REPLACE` en lugar de `TRY_CAST`. | ✅ Completo |
| `silver_registro_viviendas_vacacionales` | Mismo patrón que hoteles | ✅ Completo |
| `silver_registro_extrahoteleros` | Mismo patrón que hoteles | ✅ Completo |
| **`silver_alojamiento_unificado`** | **TABLA PRINCIPAL.** `UNION ALL` de los 3 registros anteriores. Añade columna `tipo_alojamiento`. Índice GIST. Esta es la tabla que usa la capa Gold. | ✅ Completo |

### 📁 booking/
| Modelo | Descripción | Estado |
|---|---|---|
| `silver_booking_establishments` | Establecimientos de Booking. `geometry` PostGIS. Deduplicación y enriquecimiento de coordenadas con geocodificador. | ✅ Completo |
| `silver_booking_reviews` | Reseñas de texto de Booking. **Sin agregar** (1 fila = 1 reseña). Flag `periodo_covid`. Campo `longitud_texto`. Filtra reseñas vacías. | ✅ Completo |

### 📁 espacial/
| Modelo | Descripción | Estado |
|---|---|---|
| `silver_h3_grid` | Malla H3 + cálculo de área y centroides | ✅ Completo |
| `silver_limites_municipales` | Polígonos municipales + área km² + centroides | ✅ Completo |
| `silver_enp` | Espacios Naturales Protegidos. ⚠️ `municipio` es NULL (se asigna en Gold vía `ST_Intersection`) | ✅ Completo |
| `silver_zonas_turisticas` | Polígonos de zonas turísticas | ✅ Completo |
| `silver_osm_pois` | 15.000+ POIs OSM con `geometry`. Sub-dependencia del unificado. | ✅ Completo |
| `silver_bienes_culturales` | BIC (polígonos). Campos: `bic_nombre`, `municipio_nombre`. Sub-dependencia del unificado. | ✅ Completo |
| `silver_oficinas_turismo` | Oficinas de turismo (puntos). Campos: `nombre`, `horario`, `descripcion`, `telefono`, `estado`. Filtro: excluye cerradas temporalmente. Sub-dependencia del unificado. | ✅ Completo |
| **`silver_puntos_interes_unificados`** | **TABLA PRINCIPAL.** `UNION ALL` de OSM + BIC + Oficinas. Columna `fuente` para diferenciar origen. Preserve campos específicos de oficinas. | ✅ Completo |
| `silver_gtfs_paradas` | Paradas TITSA con `geometry` PostGIS | ✅ Completo |
| `silver_gtfs_rutas` | Rutas TITSA | ✅ Completo |
| `silver_indices_satelite` | NDVI, NDBI por H3 (pre-calculados) | ✅ Completo |

### 📁 clima/
| Modelo | Descripción | Estado |
|---|---|---|
| `silver_estaciones_agrocabildo` | Metadatos de estaciones con `geometry` PostGIS | ✅ Completo |
| `silver_clima_horario_agrocabildo` | Lecturas horarias limpias. ⚠️ Problema #7: `id_sensor` sin tabla de metadatos de variable (temperatura, lluvia, etc.) | ⚠️ Funcional, mejorable |
| `silver_era5land` | Histórico climático reanálisis ERA5 | ✅ Completo |
| `silver_gfs_hist` | Predicciones GFS. **⚠️ Baja prioridad**: este dato no es relevante para el modelo MGWR ni el dashboard. Excluir de Gold. | ℹ️ Excluir de Gold |

### 📁 istac/
| Modelo | Descripción | Estado |
|---|---|---|
| `silver_istac_anual` | Indicadores ISTAC a nivel anual por municipio | ✅ Completo |
| `silver_istac_mensual` | Indicadores ISTAC a nivel mensual | ✅ Completo |
| `silver_istac_trimestral` | Indicadores ISTAC a nivel trimestral | ✅ Completo |
| `silver_istac_vivienda_vacacional` | Estadísticas de VV (tasa ocupación, estancia, etc.) | ✅ Completo |
| ~~`silver_istac_estatico`~~ | **ELIMINADO.** Duplicaba `silver_limites_municipales` | 🗑️ Eliminado |
| ~~`silver_istac_municipios_cifras_tenerife`~~ | **ELIMINADO.** Duplicaba anual+mensual | 🗑️ Eliminado |

### 📁 movilidad/
| Modelo | Descripción | Estado |
|---|---|---|
| `silver_aena_pasajeros` | Estadísticas de pasajeros (AENA). Movida de `espacial/` porque es dato tabular, no geográfico. | ✅ Completo |

### 📁 youtube/
| Modelo | Descripción | Estado |
|---|---|---|
| `silver_youtube` | Métricas agregadas por vídeo (engagement, nº comentarios válidos). Para el Dashboard de engagement. | ✅ Completo |
| `silver_losviajeros` | Métricas agregadas por hilo del foro. Para el Dashboard de engagement. | ✅ Completo |
| `silver_youtube_comentarios` | **Sin agregar** (1 fila = 1 comentario). Flag `periodo_covid`. Para el Squad NLP. | ✅ Completo |
| `silver_losviajeros_mensajes` | **Sin agregar** (1 fila = 1 mensaje). Flag `periodo_covid`. Para el Squad NLP. | ✅ Completo |

### 📁 tripadvisor/
| Modelo | Descripción | Estado |
|---|---|---|
| `silver_tripadvisor_ubicaciones` | Establecimientos con `geometry` PostGIS e índice GIST. | ✅ Completo |
| `silver_tripadvisor_resenas` | Reseñas (1 fila = 1 reseña). Flag `periodo_covid`. Filtra reseñas vacías. | ✅ Completo |

---

## 🥇 Capa Gold — Plan de Implementación

> **NOTA:** Los nombres de esquema en Gold son `gold.*`, NO `oro.*` como aparece en el plan maestro antiguo.

### Librerías necesarias (globales)
```
pip install geopandas shapely psycopg2-binary sqlalchemy h3 pandas numpy
pip install rasterstats rasterio                       # Bloque 1 (estadísticas raster)
pip install transformers torch pyabsa langdetect       # Bloque 2 (NLP con coordenadas)
pip install bertopic sentence-transformers umap-learn hdbscan  # Bloque 3 (NLP sin coordenadas)
pip install mgwr libpysal scikit-learn                 # Bloque 5 (MGWR)
pip install openrouteservice                           # Bloque 4 (accesibilidad)
pip install langchain langchain-community langchain-groq groq  # Bloque 7 (Text-to-SQL)
pip install streamlit pydeck plotly wordcloud          # Bloque 8 (Dashboard)
```

---

## 🔵 BLOQUE 1: `gold_h3_master` — La Tabla Maestra H3 que une todo el proyecto
**Squad:** B (Personas 3 y 4) | **Prioridad:** CRÍTICA — todo lo demás depende de esta | **Semana:** 1

### ¿Qué es y para qué sirve?
Esta es la tarea más crítica del TFM. La tabla `gold.h3_master` es la columna vertebral: **una fila por cada hexágono H3** (2.396 hexágonos), con todos los indicadores del proyecto. El `h3_index` (ej: `8928308280fffff`) es la clave primaria que une el trabajo de los 6 miembros del equipo.

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
- **Fuentes Silver:** `silver.h3_grid` + `silver.alojamiento_unificado` (hoteles + VV + extrahoteleros, todos con `geometry`)
- **Técnica:** `ST_Contains(h3.geometry, alojamiento.geometry)` — PostGIS usa los índices GIST automáticamente.
- **SQL exacto:**
```sql
SELECT
    h.h3_index,
    COUNT(a.id)                                                     AS n_establecimientos_registro,
    SUM(a.plazas)                                                   AS n_plazas_registro,
    COUNT(a.id) FILTER (WHERE a.tipo_alojamiento = 'hotel')         AS n_hoteles,
    COUNT(a.id) FILTER (WHERE a.tipo_alojamiento = 'vivienda_vacacional') AS n_vv,
    COUNT(a.id) FILTER (WHERE a.tipo_alojamiento = 'extrahotelero') AS n_extrahoteleros
FROM silver.h3_grid h
LEFT JOIN silver.alojamiento_unificado a ON ST_Contains(h.geometry, a.geometry)
GROUP BY h.h3_index
```
- **Output:** `n_establecimientos_registro`, `n_plazas_registro`, `n_hoteles`, `n_vv`, `n_extrahoteleros`.
- **Interpretabilidad para TUI:** Densidad de oferta oficial reglada. Si `n_plazas_registro` es bajo pero Booking/TripAdvisor tienen muchos establecimientos → posible mercado irregular o VV no declaradas.

---

### Subtarea 1.3 — Agregar valoraciones de Booking y TripAdvisor por hexágono
- **Fuentes Silver:** `silver.booking_establishments` + `silver.booking_reviews` | `silver.tripadvisor_ubicaciones` + `silver.tripadvisor_resenas`
- **Técnica:** JOIN establishments → reviews → ST_Contains con h3_grid. Usar `WHERE NOT periodo_covid`.
- **SQL exacto (patrón Booking — replicar para TripAdvisor):**
```sql
SELECT
    h.h3_index,
    COUNT(DISTINCT e.id)                           AS n_establecimientos_booking,
    ROUND(AVG(r.rating)::numeric, 2)               AS rating_booking_medio,
    COUNT(r.review_id) FILTER (WHERE NOT r.periodo_covid) AS n_reviews_validas_booking
FROM silver.h3_grid h
LEFT JOIN silver.booking_establishments e ON ST_Contains(h.geometry, e.geometry)
LEFT JOIN silver.booking_reviews r ON r.establishment_id = e.id
GROUP BY h.h3_index
```
- **Output:** `n_establecimientos_booking`, `rating_booking_medio`, `n_establecimientos_tripadvisor`, `rating_tripadvisor_medio`.
- **Interpretabilidad:** Un hexágono con 4.8/5 en Booking pero PTNA alto → zona bien valorada pero sin escalar. Oportunidad clara para TUI.

---

### Subtarea 1.4 — Contar POIs por hexágono y categoría
- **Fuente Silver:** `silver.puntos_interes_unificados` (OSM + BIC + Oficinas de Turismo, todos con `geometry`)
- **SQL exacto:**
```sql
SELECT
    h.h3_index,
    COUNT(p.id)                                               AS n_pois_total,
    COUNT(p.id) FILTER (WHERE p.tipo = 'restaurant')         AS n_restaurantes,
    COUNT(p.id) FILTER (WHERE p.tipo IN ('museum','attraction')) AS n_cultura,
    COUNT(p.id) FILTER (WHERE p.categoria = 'natural')       AS n_naturaleza,
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
- **Interpretabilidad:** Accesibilidad sin coche. Hexágonos con muchas paradas y alto NDVI → rutas de senderismo con transporte público.

---

### Subtarea 1.6 — Estadísticas de altitud, pendiente y satélite (JOIN directo por h3_index)
- **Fuente:** `silver.mdt_stats` + `silver.satelite_stats`
- **MDT Completo:** 
  - `elevation_mean`, `elevation_min`, `elevation_max`
  - `slope_mean`, `slope_min`, `slope_max`
  - `aspect_mean`, `aspect_min`, `aspect_max` (Orientación: 0=Norte, 180=Sur)
  - `hillshade_mean`, `hillshade_min`, `hillshade_max`
- **Para VIIRS excluir COVID (calcular media sin 2020-2021):**
```sql
SELECT h3_index, AVG(viirs_anual) AS viirs_medio
FROM bronze.satelite_stats
WHERE anio NOT BETWEEN 2020 AND 2021
GROUP BY h3_index
```
- **Output:** Las 12 métricas del MDT, `ndvi_medio` (0=árido, 1=muy verde), `ndbi_medio`, `viirs_medio` (luminosidad nocturna).
- **Interpretabilidad:** El `aspect` es clave para que el modelo identifique laderas de Barlovento (húmedas) vs Sotavento (secas). NDVI alto + viirs bajo = zona rural verde sin urbanizar. Son variables críticas para el modelo MGWR.

---

### Subtarea 1.7 — Variables climáticas por hexágono (IDW + Gradiente Térmico)
- **Fuente Silver:** `silver.agrocabildo_horario`
- **Técnica Avanzada (Meteorología Espacial):**
  - **IDW (Inverse Distance Weighting):** Buscar las 3 estaciones más cercanas a cada hexágono H3 (`ORDER BY geometry <-> geometry LIMIT 3`). La media pondera más fuertemente a la estación con menor distancia (`1 / distancia^2`).
  - **Corrección por Gradiente Térmico (Lapse Rate):** Restar `0.0065 ºC` por cada metro de altitud que el hexágono H3 esté por encima de la estación meteorológica (`temp_media_anual + ((station_altitud - h3_altitud) * 0.0065)`).
- **Nuevos Indicadores ESG (Dinamismo y Riesgo):**
  - `dias_ola_calor_anual`: Días con temp_max >= 35, humedad_min <= 30 y dir_viento Este/Sur. (Riesgo).
  - `amplitud_termica_media`: (Temp_max - Temp_min). Confort para seniors.
  - `radiacion_mediodia_q3` vs `q1`: Para detectar efecto de "Panza de Burro" en el norte en verano.
- **Output (Estacional Clásico):** `temp_media_anual`, `temp_media_q1`, `temp_media_q2`, `temp_media_q3`, `temp_media_q4`, `lluvia_mm_q1`, `lluvia_mm_q2`, `lluvia_mm_q3`, `lluvia_mm_q4`, `vel_viento_media_anual`, `vel_viento_media_q1`, `vel_viento_media_q2`, `vel_viento_media_q3`, `vel_viento_media_q4`, `humedad_media_anual`, `humedad_media_q1`, `humedad_media_q2`, `humedad_media_q3`, `humedad_media_q4`, `insolacion_media_anual`, `insolacion_media_q1`, `insolacion_media_q2`, `insolacion_media_q3`, `insolacion_media_q4`
- **Interpretabilidad:** El IDW+Altitud asegura que el Teide no tenga temperatura de playa aunque la estación más cercana esté en la costa. Los indicadores de olas de calor son críticos para las inversiones a futuro de TUI ante el cambio climático.


---

### Subtarea 1.8 — Flag de Espacio Natural Protegido
- **Fuente Silver:** `silver.enp` (polígonos ENP)
- **Técnica:** `ST_Intersects` — cualquier solapamiento = ENP.
- **Output:** `es_enp` (BOOLEAN), `pct_area_enp` (NUMERIC, % del hexágono bajo protección).
- **Interpretabilidad:** Restricción legal de desarrollo hotelero convencional. Un hexágono con `es_enp = TRUE` y PTNA alto = **oportunidad de ecoturismo**.

---

### Subtarea 1.9 — Métricas de Dinamismo y Mercado (Crecimiento, Estacionalidad y Origen)
- **Fuente Silver:** 
  - ISTAC: `silver.istac_trimestral` (ocupación por trimestres).
  - Alojamiento: `silver.registro_viviendas_vacacionales` (fechas de alta).
  - NLP: `silver.tripadvisor_resenas` y `silver.booking_reviews` (idioma de la reseña).
- **Técnica:**
  - *Crecimiento Oferta:* Contar cuántas VVs se dieron de alta en los últimos 2 años vs el total (slope de crecimiento).
  - *Mercado Emisor:* `MODE()` (la moda estadística) del idioma de las reseñas en ese hexágono (EN=Británico, DE=Alemán, ES=Nacional).
- **Output:** `crecimiento_oferta_pct`, `ocupacion_q1_vs_q3` (ratio de estacionalidad), `mercado_principal_idioma`.
- **Interpretabilidad:** Un `crecimiento_oferta_pct > 20%` indica una zona en rápida gentrificación turística. El `mercado_principal_idioma` permite a TUI segmentar si es una zona de clientes alemanes vs nórdicos.

---

### Subtarea 1.10 — Flag de Zona Turística Oficial
- **Fuente Silver:** `silver.zonas_turisticas` (polígonos oficiales de zonas turísticas de Tenerife).
- **Técnica:** `ST_Intersects` — cualquier solapamiento del hexágono con un polígono de zona turística.
- **Output:** `es_zona_turistica_oficial` (BOOLEAN).
- **Interpretabilidad:** Fundamental para clasificar las inversiones. Un PTNA alto donde `es_zona_turistica_oficial = TRUE` es un proyecto de **renovación/reposicionamiento** (brownfield). Si es `FALSE`, es un proyecto de **desarrollo nuevo** (greenfield) sujeto a mayores trabas burocráticas pero con potencial de ser pionero.

---

### Subtarea 1.11 — Distancia Euclidiana a la Costa
- **Fuente Silver:** `silver.limites_municipales`
- **Técnica Espacial:** Extraer la línea de costa combinando los municipios con `ST_Boundary(ST_Union(geometry))` y medir la distancia en línea recta desde el hexágono con `ST_Distance()`.
- **Output:** `distancia_costa_metros` (NUMERIC).
- **Interpretabilidad:** Variable de altísimo valor para bienes raíces (Real Estate) hoteleros. Captura la prima de valor ("premium") por estar cerca del mar sin importar las carreteras. Diferente a la accesibilidad vial (Bloque 4).

---

### Output Final del Bloque 1
**Tabla:** `gold.h3_master` | **Filas:** ~2.396 | **Índices:** GIST en `geometry`, B-Tree en `municipio`

| Columna | Tipo | Fuente |
|---|---|---|
| `h3_index` | VARCHAR | PK |
| `cod_municipio`, `municipio` | VARCHAR | Subtarea 1.1 |
| `area_km2`, `centroide_lon`, `centroide_lat` | NUMERIC | Subtarea 1.1 |
| `n_establecimientos_registro`, `n_plazas_registro`, `n_hoteles`, `n_vv`, `n_extrahoteleros` | INT | Subtarea 1.2 |
| `n_establecimientos_booking`, `rating_booking_medio`, `n_reviews_booking` | INT/NUMERIC | Subtarea 1.3 |
| `n_establecimientos_tripadvisor`, `rating_tripadvisor_medio` | INT/NUMERIC | Subtarea 1.3 |
| `n_pois_total`, `n_restaurantes`, `n_cultura`, `n_naturaleza` | INT | Subtarea 1.4 |
| `n_paradas_bus` | INT | Subtarea 1.5 |
| `altitud_media`, `pendiente_media`, `ndvi_medio`, `ndbi_medio`, `viirs_medio` | NUMERIC | Subtarea 1.6 |
| `temp_media_anual`, `temp_media_q1`, `temp_media_q3` | NUMERIC | Subtarea 1.7 |
| `es_enp`, `pct_area_enp` | BOOL/NUMERIC | Subtarea 1.8 |
| `crecimiento_oferta_pct`, `ocupacion_q1_vs_q3` | NUMERIC | Subtarea 1.9 |
| `es_zona_turistica_oficial` | BOOLEAN | Subtarea 1.10 |
| `mercado_principal_idioma` | VARCHAR | Subtarea 1.9 |
| `geometry` | GEOMETRY | `silver.h3_grid` |

---

## 🔴 BLOQUE 2: NLP CON COORDENADAS — Sentimiento y Aspectos Geolocalizados (Booking + TripAdvisor → Malla H3)
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

---

## 🟤 BLOQUE 3: NLP SIN COORDENADAS — Percepción Global de Marca Tenerife (YouTube + LosViajeros)
**Squad:** A (Personas 1 y 2) | **Prioridad:** Media | **Semana:** 1-2 (en paralelo con Bloque 2)

### ¿Qué es y para qué sirve?
Los vídeos de YouTube y posts de foros **no tienen coordenadas de hotel**. Se usan para medir la **percepción global de Tenerife como destino** (análisis de marca), NO para el mapa H3. Su resultado alimenta la pestaña "Visión Global" del Dashboard y el informe narrativo del Bloque 9.

### Librerías necesarias
```
pip install bertopic sentence-transformers umap-learn hdbscan langchain groq
```
---

### Subtarea 3.1 — Modelado de Tópicos (BERTopic)
- **Modelo:** `BERTopic` + embeddings `paraphrase-multilingual-MiniLM-L12-v2` (sentence-transformers).
- **Fuente Silver:** `silver.youtube_comentarios` + `silver.losviajeros_mensajes`. Filtrar `WHERE periodo_covid = FALSE AND longitud_texto > 15`.
- **¿Qué hace?** Agrupa automáticamente miles de comentarios en N temas. Ej: Tema 1="Senderismo Anaga", Tema 2="Ruido sur por la noche".
- **Para que funcione bien:**
  - Necesita mínimo ~500 documentos para que salgan tópicos coherentes.
  - Configurar `min_topic_size=15` para evitar tópicos con 2 palabras sin sentido.
  - La primera ejecución tarda mucho en generar los embeddings (guardar en disco con `model.save("bertopic_model")`).
- **Código esqueleto:**
```python
from bertopic import BERTopic
from sentence_transformers import SentenceTransformer

embedding_model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
topic_model = BERTopic(embedding_model=embedding_model, min_topic_size=15, language="multilingual")
topics, probs = topic_model.fit_transform(lista_textos)
topic_model.save("bertopic_tenerife")  # Guardar para no re-entrenar
```
- **Output:** Tabla `gold.nlp_topicos` con `texto_id`, `plataforma` ('youtube'/'losviajeros'), `topico_id`, `topico_nombre`, `relevancia`.
- **Interpretabilidad para TUI:** Permite responder "¿De qué habla la gente de Tenerife en internet?" sin leer miles de comentarios.

---

### Subtarea 3.2 — Generación de Informe Narrativo Global (LangChain + LLM)
- **Modelo:** `llama-3.1-70b-versatile` vía **Groq**  o `gpt-4o` vía **Azure**.
- **¿Qué hace?** Convierte los resultados de BERTopic en un párrafo ejecutivo para el Dashboard.
- **Prompt exacto a usar:**
```
Eres un analista senior de turismo de TUI. Los tópicos más discutidos sobre Tenerife
en YouTube y foros de viajeros de 2022 en adelante son:
{lista_topicos_con_n_documentos}
Escribe un informe ejecutivo de 3 párrafos resumiendo:
1. La percepción general de Tenerife como destino
2. Los principales problemas mencionados por los visitantes
3. Las oportunidades de mejora para TUI
```
- **Output:** Texto almacenado en `gold.nlp_informe_global`, mostrado en la pestaña "Visión Global" del Dashboard.

---

## 🟡 BLOQUE 4: `gold_h3_accesibilidad` — Accesibilidad Territorial Completa (ORS Matrix + PostGIS)
**Squad:** C (Personas 5 y 6) | **Prioridad:** Alta | **Semana:** 1

### ¿Qué es y para qué sirve?
Este bloque construye la tabla `gold.h3_accesibilidad`, con **una fila por cada hexágono H3** (2.396 en total) y múltiples indicadores de accesibilidad calculados de forma precisa para toda la isla sin dejar ningún hexágono "ciego". Alimenta directamente al modelo MGWR del Bloque 5 como variables X, y al Dashboard como capas visuales interactivas.

La accesibilidad es uno de los predictores con **mayor peso estadístico** en la literatura turística: un establecimiento difícil de llegar desde el aeropuerto tiene hasta un 40% menos de probabilidad de éxito independientemente de su calidad intrínseca.

### Librerías necesarias
```
pip install openrouteservice geopandas pandas psycopg2-binary sqlalchemy shapely
```

---

### Subtarea 4.1 — Routing Matrix ORS: Tiempos Exactos de Conducción para toda la Isla (2.746 hexágonos × 18 destinos)
- **Mejora de Precisión Espacial (Centroide Ponderado por POIs)**: Para evitar el problema de MAUP (que el centro matemático de un hexágono caiga en el mar o en un acantilado inaccesible), la capa Silver (`silver_h3_grid`) calcula las coordenadas de origen basándose en el centro de masa de la actividad humana (POIs de OSM) dentro del hexágono, desplazando el punto de ruteo hacia las zonas habitadas/accesibles.
- **¿Qué es?**: La **API de Matrices de ORS** calcula el tiempo de conducción desde CADA UNO de los 2.746 hexágonos hacia N destinos estratégicos. A diferencia de las isócronas (polígonos visuales), esto produce un **número exacto al minuto** (ej: 42.3 min) para cada hexágono, sin dejar ninguna zona aislada ni "ciega".
- **¿Por qué Matrix y no isócronas para el modelo estadístico?**: Las isócronas clasifican los hexágonos como "dentro o fuera de un anillo de 30 min" (dato binario, pierde resolución). La Matrix da `42.3 min` vs `43.1 min` — información continua mucho más útil para la regresión MGWR.
- **Coste de API**: Plan gratuito ORS: 500 peticiones/día, máx 3.500 pares origen-destino por petición. 2.746 hexágonos < 3.500 → **1 petición por destino**. 18 destinos × 1 petición = **18 peticiones totales** (~3.6% del límite diario).
- **Los 18 Destinos Estratégicos Finales**
| ID | Lugar | Coordenadas [lon, lat] | Justificación |
|---|---|---|---|
| `tfs` | Aeropuerto Sur (TFS) | `[-16.5726, 28.0445]` | Puerta de entrada del 70% del turismo internacional |
| `tfn` | Aeropuerto Norte (TFN) | `[-16.3413, 28.4827]` | Puerta de entrada del turismo nacional e interinsular |
| `capital` | Santa Cruz (Puerto) | `[-16.2519, 28.4700]` | Capital, ferry, conexión industrial y residencial |
| `polo_sur` | Costa Adeje (centro) | `[-16.7356, 28.0805]` | Epicentro de la hostelería premium del sur |
| `polo_norte` | Puerto de la Cruz (centro) | `[-16.5488, 28.4148]` | Epicentro del turismo del norte |
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
  - Hacer una llamada de prueba con solo 5 hexágonos para validar el formato antes de lanzar los 2.396.
  - La respuesta devuelve tiempos en **segundos** — dividir entre 60 para obtener minutos.
  - Si un hexágono queda en zona inaccesible por carretera (mar), ORS devuelve `null` → usar `COALESCE(valor, 999)`.

- **Código esqueleto**
```python
import openrouteservice
import pandas as pd
from sqlalchemy import create_engine

client = openrouteservice.Client(key='TU_ORS_API_KEY')
engine = create_engine("DB_URL")

df = pd.read_sql("SELECT h3_index, centroide_lon, centroide_lat FROM silver.h3_grid", engine)
origenes = df[['centroide_lon', 'centroide_lat']].values.tolist()

destinos = {
    'tfs':        [-16.5726, 28.0445],
    'tfn':        [-16.3413, 28.4827],
    'capital':    [-16.2519, 28.4700],
    'polo_sur':   [-16.7356, 28.0805],
    'polo_norte': [-16.5488, 28.4148],
    'teide':      [-16.6433, 28.2728],
}

resultados = {'h3_index': df['h3_index'].tolist()}

for nombre, coords_destino in destinos.items():
    # 1 petición: 2396 orígenes → 1 destino (2396 pares < límite 3500)
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
| `tiempo_polo_sur_min` | NUMERIC | Minutos en coche a Costa Adeje |
| `tiempo_polo_norte_min` | NUMERIC | Minutos en coche a Puerto de la Cruz |
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
engine = create_engine("DB_URL")

destinos = {
    'tfs': [-16.5726, 28.0445], 'tfn': [-16.3413, 28.4827],
    'capital': [-16.2519, 28.4700], 'polo_sur': [-16.7356, 28.0805],
    'polo_norte': [-16.5488, 28.4148], 'teide': [-16.6433, 28.2728],
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
- **¿Qué es?**: En lugar de depender de APIs externas, se descarga la red real de calles, aceras y senderos de Tenerife desde OpenStreetMap (OSM) y se crea un **servidor de rutas propio dentro de PostgreSQL**. Esto permite calcular distancias reales a pie y la "caminabilidad" (Walkability Index) de cada hexágono, que es brutal para predecir el éxito de alojamientos orientados a turistas sin coche. Demuestra un dominio absoluto de bases de datos espaciales y topologías de red (Grafos). Rompe cualquier límite de peticiones (puedes calcular una matriz de 2396x2396 si quieres) y es 100% gratuito.

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

**Tabla principal:** `gold.h3_accesibilidad` | **Filas:** 2.396 | **Coste total API:** 0 €

| Columna | Tipo | Fuente | Uso en MGWR |
|---|---|---|---|
| `h3_index` | VARCHAR | PK | — |
| `tiempo_tfs_min` | NUMERIC | ORS Matrix (4.1) | ✅ Variable X |
| `tiempo_tfn_min` | NUMERIC | ORS Matrix (4.1) | ✅ Variable X |
| `tiempo_capital_min` | NUMERIC | ORS Matrix (4.1) | Informativo |
| `tiempo_polo_sur_min` | NUMERIC | ORS Matrix (4.1) | Informativo |
| `tiempo_polo_norte_min` | NUMERIC | ORS Matrix (4.1) | Informativo |
| `tiempo_teide_min` | NUMERIC | ORS Matrix (4.1) | ✅ Variable X |
| `tiempo_aeropuerto_min` | NUMERIC | MIN(tfs, tfn) (4.1) | ✅ Variable X principal |
| `aeropuerto_mas_cercano` | VARCHAR | Calculado (4.1) | Dashboard |
| `n_paradas_bus_500m` | INT | GTFS + ST_DWithin (4.3) | ✅ Variable X |
| `n_rutas_distintas` | INT | GTFS (4.3) | Informativo |
| `dist_parada_cercana_m` | NUMERIC | GTFS (4.3) | ✅ Variable X |
| `dist_hospital_km` | NUMERIC | OSM + ST_Distance (4.4) | ✅ Variable X |
| `dist_costa_km` | NUMERIC | limites_municipales (4.5) | ✅ Variable X |
| `walkability_index` | NUMERIC | pgRouting + OSM (4.6) | ✅ Variable X (Pro) |

**Tabla auxiliar:** `gold.isocronas_visuales` (24 filas — polígonos para el Dashboard)



## 🟠 BLOQUE 5: `gold_h3_ptna` — Regresión Espacial MGWR + Índice PTNA (Potencial Turístico No Aprovechado)
**Squad:** B (Personas 3 y 4) | **Prioridad:** Alta | **Semana:** 2

### ¿Qué es y para qué sirve?
MGWR (Multiscale Geographically Weighted Regression) es el **modelo estadístico estrella del TFM**. Permite que un mismo factor (ej: "el verde/NDVI") tenga **distinto peso según la zona** — en el norte el NDVI importa menos que en el sur árido. Con sus resultados construimos el **PTNA**, el indicador más valioso del proyecto para TUI.

### Librerías necesarias
```
pip install mgwr libpysal scikit-learn numpy pandas matplotlib
```
---

### Subtarea 5.1 — Construir el dataset de regresión
- **Input:** `gold.h3_master` (ya completado por Bloques 1, 2, 3 y 4).
- **Filtro obligatorio:** Excluir hexágonos con >50% de NaN y años anteriores a 2022 al calcular medias temporales.
- **Variable Y (a explicar):** `n_plazas_registro / area_h3_km2` → densidad de plazas hoteleras por km².
- **Variables X: (explicativos)**  
  | Variable X | Fuente |
  |---|---|
  | `ndvi_medio` | Satélite Sentinel (Bloque 1) |
  | `ndbi_medio` | Satélite Landsat/Sentinel (Bloque 1) - Densidad de edificación |
  | `viirs_medio` | Satélite VIIRS (Bloque 1) |
  | `altitud_media` | MDT (Bloque 1) |
  | `pendiente_media` | MDT (Bloque 1) |
  | `sentimiento_medio` | NLP Booking y TripAdvisor (Bloque 2) |
  | `tiempo_a_tfs_min` | pgRouting/ORS (Bloque 4) |
  | `n_paradas_15min` | GTFS + pgRouting (Bloque 4) |
  | `n_pois` | OSM (Bloque 1) |

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

df['coef_ndvi']    = modelo.params[:, 0]
df['ptna_score'] = modelo.predy.flatten() - y.flatten()  # Esperado - Observado
```
- *Output:* DataFrame con coeficientes locales (un valor por hexágono por variable).
- Columna `ptna_score` añadida a `oro.h3_master`. Almacenar también en `oro.h3_ptna`.

- **Interpretabilidad para TUI:** `ptna_score > 0` = el hexágono **debería** tener más plazas según sus condiciones → **oportunidad de inversión**. `ptna_score < 0` = zona sobre-explotada → riesgo de overtourism.

---

### Subtarea 5.3 — Índice ESG Territorial (Destinos Sostenibles)
- **¿Qué es?**: Un score de 0 a 100 que evalúa la sostenibilidad medioambiental, social y de gobernanza de cada hexágono, usando **exclusivamente datos públicos** (sin necesidad de datos corporativos confidenciales). Permite a TUI filtrar oportunidades de inversión (PTNA alto) que además cumplan con criterios de turismo sostenible.
- **Cálculo del Score (Ejemplo de Ponderación)**:
  - **[E] Medio Ambiente (40%)**:
    - `ndvi_medio` alto (+ puntos)
    - `viirs_medio` bajo (poca contaminación lumínica = + puntos)
    - `dist_enp_km` (Distancia a Espacios Protegidos): si está pegado es riesgo medioambiental, si está moderadamente cerca es acceso a naturaleza.
  - **[S] Social (40%)**:
    - `densidad_plazas_km2` bajo (menor saturación / overtourism = + puntos)
    - `n_paradas_bus_500m` alto (accesibilidad pública = + puntos)
    - `sentimiento_medio` de quejas de ruido en NLP bajo (+ puntos)
  - **[G] Gobernanza (20%)**:
    - Ratio de `n_hoteles` oficiales vs `n_vv` (Viviendas Vacacionales): mayor ratio de hoteles regulados frente a masificación de VVs = + puntos.
- **SQL / Pandas exacto**:
  Se crea una fórmula lineal simple normalizando todas las variables (MinMaxScaler de 0 a 1) y aplicando los pesos, sumando para obtener un `esg_territorial_score` (0 a 100).
- **Output**: Añadir columna `esg_territorial_score` a `gold.h3_master`.
- **Interpretabilidad para TUI**: Un hexágono con `ptna_score > 0` y `esg_territorial_score > 80` es el **"Santo Grial"** de la inversión para un resort eco-sostenible moderno.

---

## 🟣 BLOQUE 6: `gold_h3_clusters` — Clustering de Zonas Turísticas (HDBSCAN)
**Squad:** A (Personas 1 y 2) | **Prioridad:** Media | **Semana:** 2

### ¿Qué es y para qué sirve?
HDBSCAN agrupa automáticamente los hexágonos en **"tipos de zona"** según sus características. El resultado se visualiza en el mapa con colores.

### Librerías necesarias
```
pip install hdbscan scikit-learn numpy pandas
```
---

### Subtarea 6.1 — Clustering HDBSCAN
- **Variables:** `densidad_plazas_km2`, `viirs_medio`, `sentimiento_medio`, `ndvi_medio`, `ndbi_medio`, `ptna_score`.
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

## ⚡ BLOQUE 7: Agente Text-to-SQL — Consultas en Lenguaje Natural al Mapa (LangChain + LLM)
**Squad:** B (Personas 3 y 4) | **Prioridad:** Media | **Semana:** 2

### ¿Qué es y para qué sirve?
Un directivo de TUI escribe: *"¿Qué zonas tienen alto potencial y buen sentimiento?"*. El agente traduce esa pregunta a SQL, la ejecuta y devuelve los resultados.

### Librerías necesarias
```
pip install langchain langchain-community langchain-openai sqlalchemy psycopg2-binary groq
```

---

### Subtarea 7.1 — Conectar LangChain a PostgreSQL Gold
- **Técnica:** `SQLDatabase` de LangChain detecta automáticamente el esquema de vuestras tablas.
- **Tablas expuestas (SOLO Gold):** `h3_master`, `h3_ptna`, `h3_clusters`.
- **Código esqueleto:**
```python
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import create_sql_agent
from langchain_groq import ChatGroq # si usamos groq finalmente en vez de openai de azure

db = SQLDatabase.from_uri(
    "DB_URL",
    schema="gold", include_tables=["h3_master", "h3_ptna", "h3_clusters"]
)
llm = ChatGroq(model="llama-3.1-70b-versatile", temperature=0)
agent = create_sql_agent(llm=llm, db=db, verbose=True)
```
- *Para que funcione bien:* Limitar las tablas expuestas al agente solo a las de la capa `gold`. No le deis acceso a `silver` entera o confundirá el agente.
---

### Subtarea 7.2 — System Prompt con Contexto del TFM
- *Acción:* Inyectar en el prompt del sistema las definiciones de las columnas clave.
- *Ejemplo de System Prompt:*
  ```
  Eres un analista de datos de turismo. Tienes acceso a una base de datos de Tenerife.
  Las tablas importantes son:
  - oro.h3_master: Una fila por hexágono H3. Columnas: h3_index (id), n_plazas (oferta hotelera),
    ndvi_medio (0=árido, 1=muy verde), ndbi_medio (densidad de edificación), sentimiento_medio (1=neg, 5=pos), ptna_score (>0=oportunidad).
  - oro.h3_clusters: tipo_zona ('Overtourism', 'Rural Sostenible', 'Transicion')
  Cuando el usuario pregunte por "zonas saturadas", filtra WHERE tipo_zona = 'Overtourism'.
  ```
---

### Subtarea 7.3 — Validación con 10 Preguntas de Negocio TUI
- Antes de integrarlo en Streamlit, probad estas preguntas y comprobad que el SQL generado es correcto:
  1. *"¿Qué municipio tiene mayor sentimiento negativo?"*
  2. *"Muéstrame los 5 hexágonos con mayor potencial no aprovechado"*
  3. *"¿Cuántas plazas hoteleras hay en zonas de Overtourism?"*

---

## 🖥️ BLOQUE 8: Dashboard Streamlit — Mapa H3 Interactivo + Chatbot IA
**Squad:** C (Personas 5 y 6) | **Prioridad:** Alta | **Semana:** 2-3

### ¿Qué es y para qué sirve?
El producto entregable final para TUI. Mapa interactivo, capas toggleables, panel global y chatbot IA integrado.

### Librerías necesarias
```
pip install streamlit pydeck sqlalchemy geopandas pandas plotly wordcloud
```
---

### Subtarea 8.1 — Conexión a PostgreSQL
- *Técnica:* Usar `st.cache_resource` para la conexión y `st.cache_data` para cachear las consultas pesadas (cargar la malla H3 solo una vez al arrancar).
- *Código esqueleto:*
  ```python
  import streamlit as st
  from sqlalchemy import create_engine
  import geopandas as gpd

  @st.cache_resource
  def get_engine():
      return create_engine("postgresql://...")

  @st.cache_data
  def load_h3_master():
      return gpd.read_postgis(
          "SELECT h3_index, n_plazas, ndvi_medio, sentimiento_medio, ptna_score, geom FROM oro.h3_master",
          get_engine(), geom_col="geom")
  ```
---

### Subtarea 8.2 — Mapa H3 Interactivo (PyDeck)
- *Librería:* `pydeck` (basado en deck.gl).
- *Para que funcione bien:* PyDeck necesita que la geometría esté en formato GeoJSON (convertir con `geopandas.to_json()`).
- *Capas del mapa (toggle en sidebar):*
  - "Densidad Hotelera" → colorear por `n_plazas_km2` (rojo=mucho, verde=poco).
  - "Potencial PTNA" → colorear por `ptna_score` (amarillo=alto potencial).
  - "Zonas Clustering" → colorear por `tipo_zona` (rojo=Overtourism, verde=Rural).
  - "Isócronas 30min" → polígono de accesibilidad desde aeropuerto.

---

### Subtarea 8.3 — Panel Lateral del Chatbot IA
- Integrar `st.chat_input` con el agente LangChain.
- Al clicar en un hexágono: mostrar barras con aspectos NLP (limpieza, precio), KPI cards (`ndvi_medio`, `ptna_score`) y comparativa con la media de su municipio.
- *Técnica:* `st.chat_input` + `st.chat_message` de Streamlit (nativo desde v1.25).
- *Integración:* Importar el agente de LangChain del Bloque 7 y llamarlo cuando el usuario envíe un mensaje.
- *Funcionalidad extra:* Si el agente devuelve una lista de `h3_index`, que el mapa se actualice automáticamente para resaltar solo esos hexágonos.
---

### Subtarea 8.4 — Gráficos de Detalle al hacer Clic en un Hexágono
- *Librería:* `plotly` para gráficas de barras y `wordcloud` para nubes de palabras.
- *¿Qué mostrar al clicar en un hexágono?*
  - Barras con los aspectos NLP más mencionados (del Bloque 2).
  - Un KPI card con por ejemplo: n_hoteles, NDVI, sentimiento_medio, tipo_zona.

---

### Subtarea 8.5 [Avanzado] — Simulador de Escenarios ("What-If")
- **¿Qué es?**: Un panel interactivo en Streamlit que aparece al hacer clic en un hexágono, permitiendo al usuario modificar variables (ej. "+500 plazas hoteleras", "mejorar accesibilidad") para ver cómo cambiaría el PTNA y el Score ESG en tiempo real.
- **¿Por qué?**: Transforma el Dashboard de una herramienta "pasiva" (lectura de datos) a una herramienta "activa" (planificación estratégica), que es el core business de TUI.
- **Técnica**: Se recogen los valores actuales del hexágono y se multiplican por los **coeficientes locales** guardados en `gold.h3_master` (`coef_ndvi`, etc.) generados por el modelo MGWR en el Bloque 5. El recálculo es matemático instantáneo (no requiere llamadas a la BD ni al modelo de IA).

## 📄 BLOQUE 9: Informe Narrativo Automático + Redacción del TFM
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
- **Integración con el LLM**: Se le pasa esa lista de hexágonos al LLM para que redacte la alerta en tono ejecutivo (ej. "⚠️ Riesgo detectado en Arona Sur: saturación crítica y quejas por ruido").
- **Output**: Sección "Notificaciones / Inbox" en la barra lateral del Dashboard.

---

### Subtarea 9.3 — Redacción del TFM
- **Squad A:** Capítulo NLP — Métodos (BERT, PyABSA, BERTopic), Resultados.
- **Squad B:** Capítulo Análisis Espacial — MGWR (coeficientes locales, PTNA), Agente Text-to-SQL.
- **Squad C:** Capítulo Infraestructura — Pipeline Bronze→Silver→Gold, Accesibilidad, Dashboard.

---

## 🚨 BLOQUE 10: DÍAS FINALES (Días 19-21) — Pruebas y Cierre
**Squad:** Todos | **Semana:** 3 (últimos días)

### Día 19 — Test de Integración End-to-End
- Verificar pipeline completo sin errores: `dbt run → NLP → MGWR → Dashboard`.
- Confirmar 2.396 filas de `gold.h3_master` sin NULLs en columnas críticas.
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

## 🚨 Issues Pendientes en Silver (No bloqueantes para Gold)
| # | Problema | Acción recomendada |
|---|---|---|
| #7 | `silver_clima_horario_agrocabildo` sin variable semántica | Descargar metadatos Agrocabildo y hacer JOIN |
| #9 | `silver_enp` tiene `municipio` NULL | Hacer `ST_Intersection` en Gold |
| #12 | `silver_gfs_hist` no aporta territorialmente | Excluir de Gold |

---

## 📋 Orden de Ejecución Recomendado
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
