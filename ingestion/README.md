# ingestion/ — Módulo de Adquisición e Ingesta de Datos (Capa Bronze / Raw)

Módulo encargado de la captura automatizada de datos desde fuentes externas heterogéneas, su almacenamiento estructurado en el Data Lake (**Azure Blob Storage**) y su posterior carga en el esquema `bronze.*` de **Azure Database for PostgreSQL (PostGIS)**.

---

## Arquitectura de Ingesta en Dos Fases

El pipeline de ingesta sigue un patrón desacoplado en dos niveles para garantizar escalabilidad, tolerancia a fallos e idempotencia:

```
                                  ARQUITECTURA DE INGESTA
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ FASE 1: Extracción hacia Azure Blob Storage (Raw Landing Zone: contenedor bronce-raw)   │
│                                                                                        │
│  APIs / Web Scraping / WFS / Satélite                                                  │
│  ├── aena/                  ──> aena_pasajeros_upload_blob.py     ──> aena/*.parquet   │
│  ├── alojamientos_oficiales/──> alojamientos_oficiales_download.py──> alojamientos_oficiales/*.parquet│
│  ├── booking/               ──> booking_scraper.py (Selenium)     ──> booking/*.parquet│
│  ├── clima/                 ──> clima_*_upload_blob.py (CKAN)     ──> clima/mediciones/│
│  ├── espacial/              ──> *_upload_blob.py (H3, ENP, POIs)  ──> espacial/*       │
│  ├── gtfs/                  ──> gtfs_upload_blob.py (TITSA/TITF)  ──> gtfs/*.parquet   │
│  ├── istac/                 ──> istac_*_upload_blob.py            ──> istac/*.parquet  │
│  ├── satelite/              ──> sentinel2/viirs_upload_blob.py    ──> satelite/*.tif   │
│  ├── tripadvisor/           ──> tripadvisor_upload_blob.py        ──> tripadvisor/*.parquet│
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

## Módulos y Fuentes de Datos Disponibles

Cada subcarpeta cuenta con su propia documentación detallada en un `README.md` específico:

1. [**`aena/`**](aena/README.md) — Estadísticas de pasajeros comerciales, vuelos y carga para TFS y TFN.
2. [**`alojamientos_oficiales/`**](alojamientos_oficiales/README.md) — Registros oficiales del Gobierno de Canarias (Hoteles, Extrahoteleros y VV).
3. [**`booking/`**](booking/README.md) — Scraping automatizado y ético de establecimientos y opiniones en Booking.com.
4. [**`clima/`**](clima/README.md) — Adquisición en tiempo real e histórica de las 68 estaciones de Agrocabildo vía CKAN con particionamiento Hive.
5. [**`espacial/`**](espacial/README.md) — Generación de la Malla H3 (Res 8, 2.746 celdas con buffer costero), ENP, zonas turísticas y POIs OSM.
6. [**`gtfs/`**](gtfs/README.md) — Transporte público regular insular de TITSA y Metropolitano de Tenerife.
7. [**`istac/`**](istac/README.md) — Series estadísticas municipales del ISTAC (demografía, empleo, EOH, vivienda vacacional).
8. [**`losviajeros/`**](losviajeros/README.md) — Corpus cualitativo de hilos y 167.000 mensajes del foro de viajeros LosViajeros.com.
9. [**`postgres/`**](postgres/README.md) — Orquestación del pipeline de carga por lotes hacia el esquema `bronze.*` en Azure PostgreSQL.
10. [**`satelite/`**](satelite/README.md) — Teledetección con Sentinel-2 (NDVI/NDBI libres de nubes y calima) y VIIRS (luces nocturnas).
11. [**`tripadvisor/`**](tripadvisor/README.md) — Extracción vía Terra API con filtrado espacial PostGIS y consolidación a Parquet.
12. [**`youtube/`**](youtube/README.md) — Extracción de vídeos turísticos y comentarios de viajeros mediante YouTube Data API v3.

---

## Guía de Ejecución

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
