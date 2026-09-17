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

A continuación se resume el catálogo de módulos de ingesta y sus volúmenes reales verificados en el Lakehouse (**Azure Blob Storage** y **Azure Database for PostgreSQL**):

| Módulo | Fuente / Proveedor | Capa Bronze (Raw) | Capa Silver (Limpia) | Documentación |
|---|---|---|---|---|
| [**`clima/`**](clima/README.md) | Agrocabildo (CKAN) | **68** estaciones, **136,4 M** lecturas | **57** estaciones maduras, **12,95 M** registros | [`clima/README.md`](clima/README.md) |
| [**`booking/`**](booking/README.md) | Booking.com (Scraping) | **4.099** establecimientos, **105.104** reseñas | **3.740** hoteles deduplicados, **73.888** reseñas | [`booking/README.md`](booking/README.md) |
| [**`tripadvisor/`**](tripadvisor/README.md) | TripAdvisor (Terra API) | **750** ubicaciones, **807** reseñas | **748** ubicaciones geolocalizadas, **807** reseñas | [`tripadvisor/README.md`](tripadvisor/README.md) |
| [**`losviajeros/`**](losviajeros/README.md) | LosViajeros.com (Foro) | **248** hilos, **167.274** mensajes brutos | **248** hilos, **168.035** mensajes procesados | [`losviajeros/README.md`](losviajeros/README.md) |
| [**`youtube/`**](youtube/README.md) | YouTube Data API v3 | **41** vídeos, **3.100** comentarios | **38** vídeos, **2.819** comentarios ($\ge 2022$) | [`youtube/README.md`](youtube/README.md) |
| [**`alojamientos_oficiales/`**](alojamientos_oficiales/README.md) | Gobierno de Canarias | **31.314** registros (30.589 VV, 314 H, 411 EH) | **31.314** oficiales geocodificados (263.769 plazas) | [`alojamientos_oficiales/README.md`](alojamientos_oficiales/README.md) |
| [**`gtfs/`**](gtfs/README.md) | TITSA / Tranvía | **3.934** paradas, **873** rutas, **1,36 M** horarios | **3.934** paradas PostGIS, **873** rutas con trazado | [`gtfs/README.md`](gtfs/README.md) |
| [**`espacial/`**](espacial/README.md) | Cabildo / GRAFCAN / H3 | **2.746** celdas H3 (buffer costero), 43 ENP, 125 BIC | **2.579** celdas H3 terrestres, 31 municipios, 17 zonas | [`espacial/README.md`](espacial/README.md) |
| [**`satelite/`**](satelite/README.md) | Sentinel-2 / VIIRS | **82.380** Sentinel stats, **241.648** VIIRS stats | **46.422** compuestos NDVI/NDBI trimestrales | [`satelite/README.md`](satelite/README.md) |
| [**`istac/`**](istac/README.md) | ISTAC (API REST) | **24** series municipales (demografía, empleo, EOH, VV) | **1.736** mensual, **682** trimestral, **124** anual | [`istac/README.md`](istac/README.md) |
| [**`aena/`**](aena/README.md) | AENA (Informes oficiales) | **182** registros brutos TFS/TFN | **110** registros mensuales armonizados | [`aena/README.md`](aena/README.md) |
| [**`postgres/`**](postgres/README.md) | Orquestador de carga | Scripts `01_` a `07_` en streaming `COPY` binario | Pipeline automatizado de carga a Azure PostgreSQL | [`postgres/README.md`](postgres/README.md) |

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
