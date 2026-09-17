# Orquestación de Ingesta hacia Azure PostgreSQL (Capa Bronze)

Módulo responsable de transferir, enriquecer y estructurar todos los conjuntos de datos crudos desde el Data Lake (**Azure Blob Storage**, contenedor `bronce-raw`) hacia el motor relacional **Azure Database for PostgreSQL (PostGIS)** en el esquema `bronze.*`.

---

## 1. Arquitectura del Pipeline de Carga

El proceso está modularizado en 7 etapas secuenciales orquestadas por un ejecutor maestro:

```
                            Azure Blob Storage (bronce-raw)
                                          │
                                          ▼
                         ingestion/postgres/run_all_ingestion.py
                                          │
    ┌─────────────────────────────────────┴─────────────────────────────────────┐
    │                                                                           │
    ▼ FASE 1: Vectores y Malla                                                  ▼ FASE 2: Topografía MDT
 01_ingest_vector_to_postgres.py                                             02_ingest_mdt_to_postgres.py
 - Malla H3 Res 8 (2.746 celdas)                                             - MDT25 (IGN/GRAFCAN)
 - ENP, Zonas Turísticas, Límites                                            - Estadísticas zonales en H3
 - POIs OSM, BICs, Oficinas Turismo                                          - Pendiente, Orientación, Hillshade
 - GTFS Paradas y Rutas (PostGIS)                                            ──► bronze.bronze_mdt_stats
 ──► bronze.bronze_* (EPSG:4326)
    │                                                                           │
    ▼ FASE 3: Teledetección Satelital                                           ▼ FASE 4: Booking.com
 03_ingest_satelite_to_postgres.py                                           04_ingest_booking_to_postgres.py
 - Sentinel-2 (NDVI y NDBI trimestral)                                       - Carga multi-archivo en append
 - VIIRS Luces Nocturnas (Radianza mensual)                                  - Cast de métricas numéricas
 - Flag COVID 2020-2021                                                      ──► bronze.bronze_booking_*
 ──► bronze.bronze_satelite_stats, bronze_viirs_stats
    │                                                                           │
    ▼ FASE 5: Carga Tabular Masiva (COPY Streaming)                             ▼ FASE 6: Geocodificación Booking
 05_ingest_tabular_to_postgres.py                                            06_geocode_booking_pg.py
 - AENA Pasajeros y Operaciones                                              - Limpieza sintáctica de direcciones
 - Alojamientos Oficiales (Hoteles, Extrahoteleros, VV)                      - Nominatim OSM + ArcGIS Fallback
 - GTFS Tabular (Horarios, Viajes, Calendarios)                              - Caché persistente en PostgreSQL:
 - LosViajeros (Temas y 167k Mensajes en chunks)                               `bronze.bronze_booking_geocoding_lookup`
 - YouTube (Vídeos y Comentarios)                                            ──► Geometrías PostGIS Booking
 - ISTAC (Demografía, Empleo, EOH, VV)
 - Clima Agrocabildo (Lecturas particionadas Hive)
 ──► bronze.bronze_*
    │
    ▼ FASE 7: Geocodificación Registros Oficiales
 07_alojamientos_oficiales_geocode.py
 - Corrección de topónimos invertidos ("Orotava (La)" -> "La Orotava")
 - Expansión de siglas viales ("urb.", "cl.", "ctra.")
 - Caché persistente en PostgreSQL: `bronze.bronze_registro_geocoding_lookup`
 - Asignación de coordenadas PostGIS en tablas de registro
 ──► Geometrías PostGIS registros oficiales
```

---

## 2. Detalle de Scripts y Fases de Ejecución

### [`run_all_ingestion.py`](file:///c:/Users/ROBERTO/Proyectos_Python/TFM_TUI_Tenerife/AI_Dashboard_Core/ingestion/postgres/run_all_ingestion.py) — Orquestador Secuencial
* Detecta y ordena alfabéticamente todos los scripts numerados (`01_` a `07_`).
* Ejecuta cada fase en un subproceso aislado con el intérprete Python activo (`sys.executable`).
* Si cualquier script falla o se interrumpe, detiene inmediatamente la canalización (`sys.exit(1)`) para garantizar la integridad referencial de las tablas posteriores.

---

### [`01_ingest_vector_to_postgres.py`](file:///c:/Users/ROBERTO/Proyectos_Python/TFM_TUI_Tenerife/AI_Dashboard_Core/ingestion/postgres/01_ingest_vector_to_postgres.py) — Capas Vectoriales Base
* **Creación de Esquema**: Ejecuta `CREATE SCHEMA IF NOT EXISTS bronze;` y habilita `postgis`.
* **Proyección Estándar**: Comprueba y reproyecta cualquier capa a `EPSG:4326`.
* **Corrección de Encoding**: Repara discrepancias de codificación (Latin-1 vs. UTF-8) en la columna `ETIQUETA` de las zonas turísticas oficiales.
* **Capas cargadas**:
  * `bronze_h3_grid` (2.746 celdas generadas con buffer costero de 0.01°)
  * `bronze_espacios_naturales` (ENP)
  * `bronze_zonas_turisticas`
  * `bronze_limites_municipales` (31 municipios)
  * `bronze_bienes_interes_cultural` (BIC)
  * `bronze_oficinas_turismo`
  * `bronze_osm_pois` (puntos de interés de OpenStreetMap)
  * `bronze_gtfs_paradas` y `bronze_gtfs_rutas`

---

### [`02_ingest_mdt_to_postgres.py`](file:///c:/Users/ROBERTO/Proyectos_Python/TFM_TUI_Tenerife/AI_Dashboard_Core/ingestion/postgres/02_ingest_mdt_to_postgres.py) — Estadísticas Topográficas en H3
* **Fuente**: Modelo Digital del Terreno de 25m (MDT25) del IGN/GRAFCAN.
* **Derivados Geomorfométricos (Método de Horn, 1981)**:
  * **Pendiente (*Slope*)**: Grados de inclinación del terreno [0° - 90°].
  * **Orientación (*Aspect*)**: Grados azimutales [0° - 360°] en sentido horario respecto al Norte geográfico.
  * **Sombreado (*Hillshade*)**: Factor de iluminación de relieve [0 - 255] con sol a azimut 315° (NW) y elevación 45°.
* **Agregación Espacial**: Mediante `rasterstats.zonal_stats`, extrae media, mínimo, máximo y desviación típica de elevación y pendiente para cada una de las celdas de la malla H3, persistiendo en `bronze_mdt_stats`.

---

### [`03_ingest_satelite_to_postgres.py`](file:///c:/Users/ROBERTO/Proyectos_Python/TFM_TUI_Tenerife/AI_Dashboard_Core/ingestion/postgres/03_ingest_satelite_to_postgres.py) — Teledetección Zonal en H3
* **Sentinel-2**: Cruza los composites trimestrales de reflectancia de Google Earth Engine con los polígonos H3, calculando media y desviación típica de NDVI y NDBI por celda y trimestre. Destino: `bronze_satelite_stats`.
* **VIIRS Luces Nocturnas**: Cruza la radianza mensual calibrada de NOAA/NASA (`VNP46A2`), incorporando el flag `periodo_covid` (años 2020-2021) para aislar la caída anómala de actividad económica nocturna en los modelos espaciales. Destino: `bronze_viirs_stats`.

---

### [`04_ingest_booking_to_postgres.py`](file:///c:/Users/ROBERTO/Proyectos_Python/TFM_TUI_Tenerife/AI_Dashboard_Core/ingestion/postgres/04_ingest_booking_to_postgres.py) — Establecimientos y Reseñas de Booking
* Lee todos los archivos Parquet generados incrementalmente por los scrapers en `bronce-raw/booking/`.
* Aplica tipado forzado a variables numéricas (puntuaciones de valoración, recuentos de opiniones, precios) para prevenir discrepancias en las inferencias de esquema de Pandas.
* Ingesta en modo `append` en `bronze_booking_establecimientos` y `bronze_booking_resenas`.

---

### [`05_ingest_tabular_to_postgres.py`](file:///c:/Users/ROBERTO/Proyectos_Python/TFM_TUI_Tenerife/AI_Dashboard_Core/ingestion/postgres/05_ingest_tabular_to_postgres.py) — Ingesta Masiva Streaming (COPY)
Script central de alto rendimiento que utiliza el protocolo binario **`COPY`** de PostgreSQL para transferir tablas de gran volumen sin riesgo de Out-Of-Memory (OOM):
1. **AENA**: `bronze_aena_pasajeros`.
2. **Alojamientos Oficiales**: `bronze_registro_hoteles`, `bronze_registro_extrahoteleros`, `bronze_registro_viviendas_vacacionales`.
3. **GTFS Relacional**: `bronze_gtfs_viajes`, `bronze_gtfs_horarios` (>2M de registros), `bronze_gtfs_calendario`, etc.
4. **LosViajeros**: `bronze_losviajeros_temas` y `bronze_losviajeros_mensajes` (167k filas leídas en bloques controlados).
5. **YouTube**: `bronze_youtube_videos` y `bronze_youtube_comments`.
6. **ISTAC**: Detección dinámica y carga de todos los archivos `istac/*.parquet` en tablas `bronze_istac_*`.
7. **Clima Agrocabildo**: Soporta carga incremental mensual (`INCREMENTAL_LOAD = True`) leyendo las carpetas `año=YYYY/mes=MM/` o carga histórica completa.

---

### [`06_geocode_booking_pg.py`](file:///c:/Users/ROBERTO/Proyectos_Python/TFM_TUI_Tenerife/AI_Dashboard_Core/ingestion/postgres/06_geocode_booking_pg.py) — Geocodificación de Booking
* Normaliza direcciones postales en `bronze_booking_establishments` (extracción de códigos postales, eliminación de paréntesis y prefijos ruidosos).
* Asigna coordenadas lat/lon utilizando el servicio Nominatim (OpenStreetMap) respaldado por la tabla centralizada en Azure PostgreSQL `bronze.bronze_booking_geocoding_lookup`.
* Actualiza la columna geométrica PostGIS `geometry` en la base de datos.

---

### [`07_alojamientos_oficiales_geocode.py`](file:///c:/Users/ROBERTO/Proyectos_Python/TFM_TUI_Tenerife/AI_Dashboard_Core/ingestion/postgres/07_alojamientos_oficiales_geocode.py) — Georreferenciación de Registros Oficiales
* Resuelve discrepancias toponímicas canarias: invierte artículos gramaticales (`"Orotava (La)"` → `"La Orotava"`, `"Torre, La"` → `"La Torre"`).
* Expande abreviaturas comunes en el callejero insular (`"urb."` → `"Urbanización"`, `"cl."` → `"Calle"`, `"ctra."` → `"Carretera"`).
* Georreferencia los registros de turismo de Canarias utilizando la tabla centralizada en Azure PostgreSQL `bronze.bronze_registro_geocoding_lookup` y genera puntos espaciales PostGIS.

---

## 3. Instrucciones de Ejecución

### Requisitos previos en `.env`:
```bash
AZURE_STORAGE_CONNECTION_STRING="DefaultEndpointsProtocol=https;AccountName=...;AccountKey=..."
AZURE_DB_HOST="...postgres.database.azure.com"
AZURE_DB_USER="..."
AZURE_DB_PASSWORD="..."
AZURE_DB_PORT="5432"
AZURE_DB_NAME="..."
```

### Ejecutar la carga completa (secuencial de 01 a 07):
```bash
python ingestion/postgres/run_all_ingestion.py
```

### Ejecutar un paso específico de forma aislada:
```bash
# Solo capas vectoriales y H3
python ingestion/postgres/01_ingest_vector_to_postgres.py

# Solo tablas tabulares masivas
python ingestion/postgres/05_ingest_tabular_to_postgres.py

# Solo geocodificación de registros de turismo
python ingestion/postgres/07_alojamientos_oficiales_geocode.py
```
