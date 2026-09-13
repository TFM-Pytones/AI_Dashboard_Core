# ingestion/ — Módulo de Adquisición e Ingesta de Datos (Capa Bronze / Raw)

Módulo encargado de la captura automatizada de datos desde fuentes externas heterogéneas, su almacenamiento estructurado en el Data Lake (**Azure Blob Storage**) y su posterior carga en el esquema `bronze.*` de **Azure Database for PostgreSQL (PostGIS)**.

---

## 🏗️ Arquitectura de Ingesta en Dos Fases

El pipeline de ingesta sigue un patrón desacoplado en dos niveles para garantizar escalabilidad, tolerancia a fallos e idempotencia:

```
                                  ARQUITECTURA DE INGESTA
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ FASE 1: Extracción hacia Azure Blob Storage (Raw Landing Zone: contenedor bronce-raw)   │
│                                                                                        │
│  APIs / Web Scraping / WFS / Satélite                                                  │
│  ├── aena/                  ──> aena_pasajeros_upload_blob.py     ──> aena/*.parquet   │
│  ├── alojamientos_oficiales/──> alojamientos_oficiales_download.py──> registro/*.json │
│  ├── booking/               ──> booking_scraper.py (Selenium)     ──> booking/*.parquet│
│  ├── clima/                 ──> clima_*_upload_blob.py (RateLimit)──> clima/*.parquet  │
│  ├── espacial/              ──> *_upload_blob.py (H3, ENP, POIs)  ──> spatial/*.geojson│
│  ├── gtfs/                  ──> gtfs_upload_blob.py (TITSA/TITF)  ──> gtfs/*.parquet   │
│  ├── istac/                 ──> istac_*_upload_blob.py            ──> istac/*.parquet  │
│  ├── satelite/              ──> sentinel2/viirs_upload_blob.py    ──> satelite/*.tif   │
│  ├── tripadvisor/           ──> tripadvisor_upload_blob.py        ──> tripadvisor/*.pq │
│  └── youtube/               ──> youtube_upload_blob.py (API v3)   ──> youtube/*.parquet│
└─────────────────────────────────────────┬──────────────────────────────────────────────┘
                                          │
                                          ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ FASE 2: Carga Orquestada a Azure PostgreSQL (Esquema bronze.* con PostGIS)             │
│                                                                                        │
│  ingestion/postgres/run_all_ingestion.py                                               │
│  ├── 01_ingest_vector_to_postgres.py       ──> Capas vectoriales PostGIS (EPSG:4326)   │
│  ├── 02_ingest_mdt_to_postgres.py          ──> Estadísticas topográficas MDT en H3     │
│  ├── 03_ingest_satelite_to_postgres.py     ──> Estadísticas Sentinel-2 y VIIRS en H3   │
│  ├── 04_ingest_booking_to_postgres.py      ──> Establecimientos y reseñas de Booking   │
│  ├── 05_ingest_tabular_to_postgres.py      ──> Carga masiva COPY (GTFS, ISTAC, Clima) │
│  ├── 06_geocode_booking_pg.py              ──> Geocodificación y validación Booking   │
│  └── 07_alojamientos_oficiales_geocode.py  ──> Georreferenciación registros oficiales  │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 🗂️ Módulos y Fuentes de Datos Disponibles

### 1. `aena/` — Tráfico Aéreo y Pasajeros
Descarga y estructura las estadísticas oficiales de AENA para los dos aeropuertos de la isla:
* **Script:** `aena_pasajeros_upload_blob.py`
* **Output:** `bronce-raw/aena/aena_pasajeros_tenerife_mensual.parquet`
* **Variables:** Año, mes, aeropuerto (TFS Reina Sofía y TFN Ciudad de La Laguna), pasajeros, operaciones y tipo de tráfico (internacional vs. interinsular/nacional).

### 2. `alojamientos_oficiales/` — Registro de Turismo del Gobierno de Canarias
Descarga del censo oficial de alojamientos turísticos reglados del Cabildo y Gobierno de Canarias:
* **Script:** `alojamientos_oficiales_download.py`
* **Archivos auxiliares:** `geocode_cache.json` (caché de coordenadas para evitar re-peticiones).
* **Tipologías:** Hoteles, apartamentos/extrahoteleros y viviendas vacacionales inscritas en el Registro General Turístico.

### 3. `booking/` — Scraping de Establecimientos y Reseñas
Scraper automatizado con Selenium headless para recopilar oferta y opinión en Booking.com:
* **Descubrimiento:** Vía sitemaps XML oficiales (`sitembk-hotel-es.*.xml.gz`) cruzados con topónimos de OpenStreetMap (Overpass API) para aislar Tenerife.
* **Scripts principales:**
  * `booking_scraper.py`: Scraper modular con control de banners, reintentos y esperas inteligentes.
  * `booking_scraper_deep.py`: Extracción profunda de opiniones por establecimiento.
  * `run_continuous.py`: Ejecución continua por lotes con persistencia de estado (`scraping_progress.json`).
  * `validate_booking_data.py`: Comprobación de integridad post-scraping.
  * `build_priority_keywords.py` y `build_tenerife_keywords.py`: Generadores de palabras clave de filtrado espacial.
* **Ética y cumplimiento:** Sin almacenamiento de datos personales (PII), rotación de User-Agent, respeto al rate limiting y almacenamiento directo en `bronce-raw/booking/`.

### 4. `clima/` — Red de Estaciones Agrocabildo y Reanálisis
Conexión a la red meteorológica oficial del Cabildo de Tenerife (67 estaciones automáticas):
* **Scripts:**
  * `clima_client.py`: Cliente con control de flujo (**Rate Limit:** 10 peticiones/min, pausa de 6,5 s para evitar `HTTP 429`).
  * `clima_realtime_upload_blob.py`: Ingesta incremental de las últimas 24 horas.
  * `clima_historical_upload_blob.py`: Backfill histórico continuo (desde 2019) con checkpointing en `backfill_progress.json`.
  * `clima_metadatos_upload_blob.py`: Coordenadas, altitud y sensores de las 67 estaciones.
  * `repartition_clima_azure.py`: Mantenimiento y optimización de particiones en Blob Storage.
* **Almacenamiento:** Particionado por estación (`clima_horario_agrocabildo/estacion_{id}.parquet`) para evitar saturación de memoria RAM.

### 5. `espacial/` — Capas Vectoriales Base y Malla H3
Generación del tablero territorial e ingesta de geometrías de referencia:
* **Scripts:**
  * `h3_grid_upload_blob.py`: Genera la malla hexagonal de Uber H3 en **Resolución 8** (~0,85 km² por celda, **2.746 celdas** en Bronze) aplicando un buffer costero de 0.01° (~1,1 km) para garantizar la cobertura total de acantilados, playas y hoteles de primera línea. En la capa Silver (`silver_h3_grid`), se filtran mediante `ST_Intersects` con los 31 municipios y se descartan las celdas sin elevación o teledetección válida, consolidando **2.579 celdas terrestres** definitivas y libres de nulos.
  * `enp_zonas_upload_blob.py`: Descarga WFS de Espacios Naturales Protegidos (ENP) y Zonas Turísticas Oficiales de IDECanarias.
  * `cabildo_opendata_upload_blob.py`: Descarga de Bienes de Interés Cultural (BICs) y oficinas de turismo.
  * `osm_tourism_upload_blob.py`: POIs de OpenStreetMap (restaurantes, bares, museos, miradores).

### 6. `gtfs/` — Transporte Público Insular
Parseo y estructuración de los datos en formato GTFS de TITSA (guaguas) y Metropolitano de Tenerife (tranvía):
* **Script:** `gtfs_upload_blob.py`
* **Outputs:** `paradas.parquet` (3.893 paradas geolocalizadas), `rutas.parquet`, `viajes.parquet`, `horarios.parquet` (>2M de registros), `calendario.parquet`.

### 7. `istac/` — Estadísticas Oficiales de Canarias
Ingesta de microdatos tabulares del Instituto Canario de Estadística (ISTAC):
* **Scripts:**
  * `istac_municipios_cifras_upload_blob.py`: Indicadores municipales (población, empleo por sectores CNAE, paro registrado, demografía).
  * `istac_vivienda_vacacional_upload_blob.py`: Series históricas mensuales y anuales de oferta y plazas de vivienda vacacional.

### 8. `satelite/` — Teledetección (Sentinel-2 y VIIRS)
Extracción y procesamiento de imágenes satelitales mediante Google Earth Engine (GEE):
* **Scripts:**
  * `sentinel2_upload_blob.py`: Composites trimestrales medianos (2019-2026) libres de nubes y calima (filtrado SCL y AOT sahariana < 0.3) con bandas NDVI y NDBI a 20 metros.
  * `viirs_upload_blob.py`: Composites mensuales de luces nocturnas (NOAA VIIRS DNB / VNP46A2) para medir radianza económica y polución lumínica.
* **Documentación técnica:** Ver `ingestion/satelite/DECISIONES_TECNICAS.md`.

### 9. `tripadvisor/` — Opiniones y Alojamientos
Transformación y carga de datos recopilados de TripAdvisor:
* **Scripts:**
  * `tripadvisor_json_to_parquet.py`: Convierte los ficheros JSON brutos de ubicaciones y opiniones a formato Parquet columnar optimizado.
  * `tripadvisor_upload_blob.py`: Sube las tablas consolidadas al contenedor `bronce-raw`.

### 10. `youtube/` — Redes Sociales y Percepción del Destino
Extracción de contenido audiovisual sobre Tenerife vía API oficial:
* **Script:** `youtube_upload_blob.py` (usa YouTube Data API v3).
* **Outputs:** 41 vídeos representativos y ~3.100 comentarios con métricas de engagement (likes, replies, fechas) subidos a Azure Blob.

### 11. `postgres/` — Orquestación de Carga hacia Azure PostgreSQL
Carpeta responsable de transferir todos los datos crudos desde Azure Blob Storage hacia el esquema `bronze.*` de la base de datos relacional:
* **Script maestro:** `run_all_ingestion.py` — Ejecuta de forma secuencial y ordenada las 7 fases:
  1. `01_ingest_vector_to_postgres.py`: Carga y repara encoding (Latin-1/UTF-8) de capas espaciales (municipios, ENP, H3, POIs).
  2. `02_ingest_mdt_to_postgres.py`: Carga estadísticas del Modelo Digital del Terreno en la malla H3.
  3. `03_ingest_satelite_to_postgres.py`: Carga estadísticas zonales de satélite (NDVI, NDBI, VIIRS) en H3.
  4. `04_ingest_booking_to_postgres.py`: Carga establecimientos y reseñas de Booking.
  5. `05_ingest_tabular_to_postgres.py`: Carga masiva de tablas tabulares (GTFS, ISTAC, TripAdvisor, YouTube, clima) mediante streaming transaccional con el comando **`COPY`** de PostgreSQL, optimizando el uso de memoria RAM en tablas millonarias.
  6. `06_geocode_booking_pg.py`: Normaliza y asigna coordenadas a establecimientos de Booking.
  7. `07_alojamientos_oficiales_geocode.py`: Georreferencia y asigna geometrías PostGIS a los registros oficiales de turismo.

---

## 🚀 Guía de Ejecución

### Requisitos previos
Configura las variables de entorno en el archivo `.env` de la raíz:
```bash
AZURE_STORAGE_CONNECTION_STRING="DefaultEndpointsProtocol=https;AccountName=...;AccountKey=..."
AZURE_DB_HOST="...postgres.database.azure.com"
AZURE_DB_USER="..."
AZURE_DB_PASSWORD="..."
AZURE_DB_NAME="..."
YOUTUBE_API_KEY="..."
```

### 1. Ejecutar una extracción individual hacia Azure Blob (Fase 1)
Por ejemplo, para actualizar los datos de AENA o el clima en tiempo real:
```bash
# Tráfico de AENA
python ingestion/aena/aena_pasajeros_upload_blob.py

# Clima en tiempo real (últimas 24h)
python ingestion/clima/clima_realtime_upload_blob.py

# Ingesta de ISTAC
python ingestion/istac/istac_municipios_cifras_upload_blob.py
```

### 2. Ejecutar la carga completa a PostgreSQL (Fase 2)
Para volcar todos los datos crudos del Blob Storage a las tablas del esquema `bronze` en PostgreSQL:
```bash
python ingestion/postgres/run_all_ingestion.py
```
*(También es posible ejecutar cualquiera de los scripts `01_` a `07_` de forma individual si solo se requiere recargar una fuente concreta).*
