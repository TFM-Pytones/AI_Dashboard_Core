# Ingesta de Ubicaciones y Reseñas: TripAdvisor (Capa Bronze)

Documentación técnica del pipeline de integración contra la API de TripAdvisor (Terra API) para la extracción, filtrado geoespacial y almacenamiento estructurado de hoteles, restaurantes y opiniones de viajeros en la isla de Tenerife.

---

## 1. Arquitectura y Flujo de Datos

```
API de TripAdvisor / Terra API (https://terra.tripadvisor.com/api)
       │
       ▼  Filtrado geoespacial estricto con PostGIS (ST_Contains isla de Tenerife)
tripadvisor_upload_blob.py
       │  - Cuota segura: 900 peticiones/día
       │  - Descarte previo de homónimos fuera de la isla antes de descargar reseñas
       │  - Reintentos con Retry-After y exponential backoff
       ▼
Azure Blob Storage: bronce-raw/tripadvisor/
       ├── ubicaciones_raw_*.json
       └── resenas_raw_*.json
       │
       ▼  Consolidación y Deduplicación (tripadvisor_json_to_parquet.py)
Azure Blob Storage: bronce-raw/tripadvisor/
       ├── tripadvisor_ubicaciones.parquet
       └── tripadvisor_resenas.parquet
       │
       ▼  Carga en Base de Datos (ingestion/postgres/05_ingest_tabular_to_postgres.py)
PostgreSQL:
       ├── bronze.bronze_tripadvisor_ubicaciones
       └── bronze.bronze_tripadvisor_resenas
       │
       ▼  Modelado en dbt
PostgreSQL: silver.silver_tripadvisor_hoteles / silver_tripadvisor_resenas
```

---

## 2. Descripción de los Scripts

### 1. [`tripadvisor_upload_blob.py`](file:///c:/Users/ROBERTO/Proyectos_Python/TFM_TUI_Tenerife/AI_Dashboard_Core/ingestion/tripadvisor/tripadvisor_upload_blob.py) — Extracción y Filtrado Espacial
* **Optimización de Cuota API**: TripAdvisor impone límites estrictos en el plan gratuito/desarrollador (~1.000 llamadas diarias). El script establece un techo de seguridad de 900 llamadas/día para evitar la suspensión de la clave.
* **Filtro Espacial Previo (PostGIS)**: Antes de consumir peticiones descargando reseñas de un establecimiento, el script valida si sus coordenadas caen dentro del polígono geográfico de Tenerife (`ST_Contains` sobre los límites insulares de PostGIS). Esto evita consumir cuota en negocios homónimos situados en la península u otras islas.
* **Control de Tasa y Reintentos**: Inspecciona los encabezados `Retry-After` en respuestas `HTTP 429` y reintenta con retroceso exponencial ante errores temporales (`500`, `502`, `503`, `504`).
* **Salida**: Genera volcados JSON particionados por fecha en `bronce-raw/tripadvisor/`.

### 2. [`tripadvisor_json_to_parquet.py`](file:///c:/Users/ROBERTO/Proyectos_Python/TFM_TUI_Tenerife/AI_Dashboard_Core/ingestion/tripadvisor/tripadvisor_json_to_parquet.py) — Consolidación a Parquet
* **Unificación de Lotes**: Agrupa todos los archivos de ubicaciones y reseñas fragmentados en el Data Lake.
* **Deduplicación**:
  * En ubicaciones: descarta duplicados manteniendo el registro más reciente por `location_id`.
  * En reseñas: extrae el `review_id` y deduplica garantizando unicidad.
* **Normalización de Esquema**: Convierte el objeto anidado `resena_raw` a texto JSON para evitar conflictos de esquema de tipos mixtos en Apache Parquet.
* **Publicación**: Genera `tripadvisor_ubicaciones.parquet` y `tripadvisor_resenas.parquet`.

---

## 3. Esquema en Capa Bronze y Silver

* **`bronze_tripadvisor_ubicaciones`**: Identificador de ubicación, nombre comercial, dirección, latitud, longitud, categoría (hotel o restaurante), teléfono y calificación promedio.
* **`bronze_tripadvisor_resenas`**: Identificador de reseña (`review_id`), identificador de establecimiento (`location_id`), texto de la opinión, puntuación numérica (1 a 5 burbujas), fecha de publicación y metadatos brutos en JSON.

En la capa **Silver**, dbt normaliza las escalas de valoración, limpia caracteres especiales y cruza los establecimientos con la malla hexagonal H3.

---

## 4. Instrucciones de Ejecución

### Requisitos previos en `.env`:
```bash
TRIPADVISOR_KEY="tu_clave_api_terra"
AZURE_STORAGE_CONNECTION_STRING="DefaultEndpointsProtocol=https;AccountName=...;AccountKey=..."
AZURE_DB_HOST="...postgres.database.azure.com"
AZURE_DB_USER="..."
AZURE_DB_PASSWORD="..."
AZURE_DB_NAME="..."
```

### 1. Ejecutar extracción desde la API:
```bash
python ingestion/tripadvisor/tripadvisor_upload_blob.py
```

### 2. Consolidar JSONs a Parquet en Azure Blob Storage:
```bash
python ingestion/tripadvisor/tripadvisor_json_to_parquet.py
```

### 3. Cargar a Azure PostgreSQL:
```bash
python ingestion/postgres/05_ingest_tabular_to_postgres.py
```
