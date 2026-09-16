# Ingesta Meteorológica: Red Agrocabildo (Capa Bronze)

Módulo encargado de la adquisición, estandarización y carga de series meteorológicas diezminutales e inventario físico de la red de **68 estaciones automáticas** y **378 sensores** del **Cabildo de Tenerife (Agrocabildo)**.

---

## 1. Evolución de la Arquitectura: Transición a CKAN Abierto

En versiones iniciales, el pipeline consumía la API REST heredada (`/api/meteo/latest`). Debido al control estricto de tasa (*rate limit* de 6.5s por petición y límite de 10 peticiones/minuto impuesta por el servidor), la extracción del histórico completo demoraba entre 7 y 10 días y el proceso incremental diario consumía varias horas.

**Nueva Arquitectura (CKAN Open Data Portal)**:
El pipeline ha sido completamente migrado al catálogo oficial de datos abiertos del Cabildo de Tenerife (**CKAN** en `datos.tenerife.es`):
* **Carga Masiva Histórica**: Descarga directa de volcados anuales completos normalizados en JSON por estación. El backfill completo de 136.4M de lecturas (2019-2026) se completa en minutos en vez de días.
* **Ingesta Incremental / Tiempo Real**: Descarga concurrente multi-hilo de los volcados del año en curso (2026, actualizado semanalmente por el Cabildo), fusionando y deduplicando automáticamente en Azure Blob Storage en **~30-50 segundos**.
* **Metadatos de Estaciones y Sensores**: Descarga directa de los datasets canónicos de CKAN (`estaciones-meteorologicas-de-tenerife` y `sensores-de-las-estaciones-meteorologicas-de-tenerife`), garantizando datos geográficos e inventario físico en menos de 2 segundos.
* **Carga de Alta Velocidad en PostgreSQL**: Migración del bucle lento de inserciones Pandas a la arquitectura streaming de **PyArrow + `COPY` nativo** (~118.000 filas/segundo).

```
Catálogo de Datos Abiertos de Tenerife (CKAN - datos.tenerife.es)
       │
       ├─► clima_metadatos_upload_blob.py ──► bronce-raw/clima/estaciones/ y sensores/
       │                                       (68 estaciones, 378 sensores físicos)
       │
       ├─► clima_realtime_upload_blob.py   ──► Ingesta incremental concurrente (año en curso)
       │                                       (Deduplicación e idempotencia en ~30-50s)
       │
       └─► clima_ckan_bulk_upload_blob.py  ──► Ingesta masiva histórica (2019-2026)
                                               (5.655 particiones Parquet, 136.4M registros)
       │
       ▼  Almacenamiento particionado en Azure Blob Storage
Contenedor: bronce-raw/clima/mediciones/año=YYYY/mes=MM/estacion_{id}.parquet
       │
       ▼  Carga por lotes / incremental (ingestion/postgres/05_ingest_tabular_to_postgres.py)
PostgreSQL: bronze.bronze_clima_horario_agrocabildo (Streaming COPY nativo)
       │
       ▼  Transformación y agregación espacial con dbt
PostgreSQL: silver.silver_estaciones_agrocabildo / silver.silver_clima_agrocabildo
```

---

## 2. Estrategia de Particionamiento Hive en Azure Blob Storage

Para evitar saturar la memoria RAM en entornos locales y posibilitar descargas en paralelo sin colisiones por escritura concurrente, las mediciones climáticas se almacenan bajo una estructura de carpetas particionadas estilo Hive:

`clima/mediciones/año=YYYY/mes=MM/estacion_{id_estacion}.parquet`

* **Consumo Eficiente de Memoria**: Cada partición mensual por estación pesa entre 50 KB y 500 KB, permitiendo que scripts y pipelines procesen solo la ventana temporal necesaria sin cargar Gigabytes de golpe.
* **Escrituras Idempotentes y Deduplicadas**: Permite reintentos aislados por estación y mes sin afectar al resto del histórico. La deduplicación se garantiza sobre la clave primaria `(id_estacion, id_sensor, timestamp)`.
* **Optimización y Mantenimiento**: Las 5.655 particiones históricas (2019 a 2026) se encuentran consolidadas en `bronce-raw/clima/mediciones/`.

---

## 3. Descripción de los Scripts

### 1. [`clima_metadatos_upload_blob.py`](file:///c:/Users/ROBERTO/Proyectos_Python/TFM_TUI_Tenerife/AI_Dashboard_Core/ingestion/clima/clima_metadatos_upload_blob.py) (Metadatos de Red vía CKAN)
Descarga el censo de estaciones e inventario físico de sensores directamente desde CKAN:
* **Estaciones (`estaciones-meteorologicas-de-tenerife`)**: Extrae `estacion_id`, `estacion_nombre`, `municipio_nombre`, `latitud`, `longitud`, `altitud` y `fecha_instalacion`. Destino: `clima/estaciones/estaciones_agrocabildo.parquet`.
  > [!NOTE]
  > **Filtro de Madurez en Capa Silver**: En la capa de transformación (`silver_estaciones_agrocabildo` y `silver_clima_agrocabildo`), se filtran únicamente las estaciones con `fecha_instalacion <= '2022-01-01'` (57 estaciones maduras de las 68 totales). Esto previene que estaciones instaladas entre 2022 y 2026 introduzcan discontinuidades o valores nulos en el cálculo de series históricas y modelos espaciales (como `gold_h3_master`).
* **Sensores (`sensores-de-las-estaciones-meteorologicas-de-tenerife`)**:
  - `clima/sensores/sensores_meteorologicos.parquet`: Catálogo canónico compatible con dbt (`id_weatherdatatype`, `alias`, `name`, `unit`).
  - `clima/sensores/sensores_inventario.parquet`: Censo físico detallado de los 378 sensores instalados con fabricante, modelo y tipo de instalación.

### 2. [`clima_realtime_upload_blob.py`](file:///c:/Users/ROBERTO/Proyectos_Python/TFM_TUI_Tenerife/AI_Dashboard_Core/ingestion/clima/clima_realtime_upload_blob.py) (Ingesta en Tiempo Real / Incremental)
* Descarga de forma concurrente multi-hilo (ThreadPoolExecutor) los volcados de 2026 para las 68 estaciones.
* Admite detección automática del último dato (`--auto`) o filtrado por ventana de días (`--days-back N`).
* Fusiona las nuevas lecturas con la partición existente en Azure Blob, deduplica por `(id_estacion, id_sensor, timestamp)` y sube el Parquet actualizado. Tiempo total: **~30-50 segundos**.

### 3. [`clima_ckan_bulk_upload_blob.py`](file:///c:/Users/ROBERTO/Proyectos_Python/TFM_TUI_Tenerife/AI_Dashboard_Core/ingestion/clima/clima_ckan_bulk_upload_blob.py) (Ingesta Masiva Histórica)
* Descarga sistemática de los volcados anuales completos desde 2019 hasta 2026 directamente de CKAN.
* Normaliza series diezminutales, genera particiones mensuales por estación y las almacena en Azure Blob Storage.
* Incorpora control de progreso y tolerancia a interrupciones en `clima_ckan_progress.json`.

### 4. [`promote_clima_to_production.py`](file:///c:/Users/ROBERTO/Proyectos_Python/TFM_TUI_Tenerife/AI_Dashboard_Core/ingestion/clima/promote_clima_to_production.py) (Promoción y Optimización a Producción)
* Sincroniza blobs masivamente lado servidor (`start_copy_from_url` con SAS token) a más de 300 blobs/segundo.
* Promueve y asegura la tabla de producción `bronze.bronze_clima_horario_agrocabildo` en Azure PostgreSQL.
* Genera los índices de alta velocidad:
  - `idx_clima_horario_ts` en `(timestamp)`
  - `idx_clima_horario_st_sensor_ts` en `(id_estacion, id_sensor, timestamp)`
* Ejecuta `ANALYZE` sobre la relación.

### 5. [`05_ingest_tabular_to_postgres.py`](file:///c:/Users/ROBERTO/Proyectos_Python/TFM_TUI_Tenerife/AI_Dashboard_Core/ingestion/postgres/05_ingest_tabular_to_postgres.py) (Cargador Tabular a PostgreSQL)
* Carga tanto los metadatos de estaciones y sensores como las lecturas particionadas usando streaming con `PyArrow` y comando `COPY` de PostgreSQL, reduciendo tiempos de ingesta a segundos.

---

## 4. Instrucciones de Ejecución

### Requisitos previos:
Configurar en el archivo `.env` las variables de Azure Blob Storage y Azure PostgreSQL:
```bash
AZURE_STORAGE_CONNECTION_STRING="DefaultEndpointsProtocol=https;AccountName=...;AccountKey=..."
AZURE_DB_HOST="servidor-postgres.postgres.database.azure.com"
AZURE_DB_USER="usuario"
AZURE_DB_PASSWORD="password"
AZURE_DB_NAME="database"
```

### 1. Ingesta de metadatos de la red:
```bash
python ingestion/clima/clima_metadatos_upload_blob.py
```

### 2. Ingesta incremental / tiempo real (ej. últimos 7 días o modo auto):
```bash
# Modo automático (detecta el último registro en Azure y rellena el hueco):
python ingestion/clima/clima_realtime_upload_blob.py --auto

# O especificando días hacia atrás:
python ingestion/clima/clima_realtime_upload_blob.py --days-back 7
```

### 3. Descarga histórica completa de la red (2019-2026):
```bash
python ingestion/clima/clima_ckan_bulk_upload_blob.py --years 2019-2026 --upload-blob --no-local
```

### 4. Sincronización y Promoción a Producción:
```bash
python ingestion/clima/promote_clima_to_production.py
```

### 5. Carga a Azure PostgreSQL (Capa Bronze):
```bash
python ingestion/postgres/05_ingest_tabular_to_postgres.py
```
