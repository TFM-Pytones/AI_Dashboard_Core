# Ingesta del Registro Oficial de Turismo de Canarias (Capa Bronze)

Documentación técnica del pipeline de descarga, filtrado insular y carga de los registros oficiales de alojamientos turísticos reglados del Gobierno de Canarias (**Registro General Turístico**), abarcando **Hoteles**, **Extrahoteleros** y **Viviendas Vacacionales (VV)**.

---

## 1. Arquitectura y Flujo de Datos

El pipeline se ejecuta 100% en la nube (Azure Blob Storage y Azure PostgreSQL), asegurando que el estado y las coordenadas geocodificadas se compartan de forma centralizada:

```
Portal de Datos Abiertos de Canarias (datos.canarias.es)
       │ (CSVs: Hoteles, Extrahoteleros, Vivienda Vacacional)
       ▼
alojamientos_oficiales_download.py  (Extracción 100% en streaming de memoria)
       │  - Filtro insular: direccion_isla_nombre == 'Tenerife'
       │  - Serialización directa a Parquet Snappy (io.BytesIO)
       ▼
Azure Blob Storage: bronce-raw/alojamientos_oficiales/*.parquet
       │
       ▼  Carga masiva (ingestion/postgres/05_ingest_tabular_to_postgres.py)
Azure PostgreSQL: bronze.bronze_registro_*
       │
       ▼  Geocodificación Centralizada (ingestion/postgres/07_alojamientos_oficiales_geocode.py)
       │  - Lectura de caché persistente en Azure PostgreSQL: bronze.bronze_registro_geocoding_lookup
       │  - Limpieza de topónimos (ej. "Orotava (La)" -> "La Orotava") y siglas viales
       │  - Geocodificación de pendientes vía Nominatim (OSM) / ArcGIS Fallback
       │  - Persistencia de nuevas coordenadas en bronze.bronze_registro_geocoding_lookup
       ▼
Transformación dbt (dbt_project/models/silver/alojamiento/silver_alojamientos_oficiales.sql)
       │  - Cruce de registros con la tabla de lookup en Azure PostgreSQL
       ▼
Azure PostgreSQL: silver.silver_alojamientos_oficiales (Geometrías PostGIS EPSG:4326)
```

---

## 2. Conjuntos de Datos Oficiales Ingeridos

Los datos se obtienen directamente desde los endpoints oficiales de datos abiertos del Gobierno de Canarias:

| Nombre del Dataset | Tipología Turística | Archivo Parquet en Blob | Tabla Bronze PostgreSQL | Registros Verificados |
|---|---|---|---|:---:|
| **`registro_hoteles`** | Hoteles urbanos, de costa y rurales | `alojamientos_oficiales/registro_hoteles_tenerife.parquet` | `bronze.bronze_registro_hoteles` | **314** |
| **`registro_extrahoteleros`** | Apartamentos turísticos, bungalows, villas | `alojamientos_oficiales/registro_extrahoteleros_tenerife.parquet` | `bronze.bronze_registro_extrahoteleros` | **411** |
| **`registro_viviendas_vacacionales`** | Viviendas vacacionales regladas (Decreto 113/2015) | `alojamientos_oficiales/registro_viviendas_vacacionales_tenerife.parquet` | `bronze.bronze_registro_viviendas_vacacionales` | **30.589** |
| **Total Consolidado Silver** | **Unificado en `silver.silver_alojamientos_oficiales`** | — | — | **31.314** *(263.769 plazas)* |

Además, la tabla de soporte `bronze.bronze_registro_geocoding_lookup` centraliza **9.397** resoluciones de coordenadas geocodificadas para los registros que carecían de lat/lon nativa.

---

## 3. Componentes Técnicos y Gestión de Coordenadas

### 1. [`alojamientos_oficiales_download.py`](file:///c:/Users/ROBERTO/Proyectos_Python/TFM_TUI_Tenerife/AI_Dashboard_Core/ingestion/alojamientos_oficiales/alojamientos_oficiales_download.py)
* **Descarga en Streaming**: Consume los CSVs delimitados por punto y coma (`;`) directamente en streams de memoria (`io.BytesIO`), sin escribir archivos temporales en disco local.
* **Aislamiento Territorial**: Aplica el filtro estricto `df['direccion_isla_nombre'] == 'Tenerife'` para descartar registros del resto de islas del archipiélago.
* **Compresión Eficiente**: Serializa el resultado en formato Apache Parquet con compresión Snappy, reduciendo drásticamente el ancho de banda y tiempo de carga.
* **Subida Idempotente**: Publica los archivos directamente en el contenedor `bronce-raw` con `overwrite=True`.

### 2. Gestión Centralizada de Caché en Azure PostgreSQL (`bronze_registro_geocoding_lookup`)
A diferencia de un archivo JSON local, la caché de geocodificación está **centralizada directamente en Azure Database for PostgreSQL** en la tabla:
`bronze.bronze_registro_geocoding_lookup`

* **Sincronización Multi-Entorno**: Permite que cualquier entorno de ejecución (máquina local de desarrollo o máquina virtual Azure `mv-orquestador-tfm`) consulte y actualice las coordenadas ya resueltas sin desincronizaciones de archivos locales.
* **Consumo por dbt**: El modelo [`silver_alojamientos_oficiales.sql`](file:///c:/Users/ROBERTO/Proyectos_Python/TFM_TUI_Tenerife/AI_Dashboard_Core/dbt_project/models/silver/alojamiento/silver_alojamientos_oficiales.sql) realiza un cruce SQL directo contra esta tabla de lookup en Azure para asignar latitud y longitud a aquellos establecimientos que en el censo oficial carecían de coordenadas válidas.

*(Nota: El archivo local `geocode_cache.json` corresponde a un volcado histórico de desarrollo previo a la migración de la caché a la tabla relacional de PostgreSQL).*

---

## 4. Instrucciones de Ejecución

### Requisitos previos:
Configura las credenciales en tu archivo `.env`:
```bash
AZURE_STORAGE_CONNECTION_STRING="DefaultEndpointsProtocol=https;AccountName=...;AccountKey=..."
AZURE_DB_HOST="...postgres.database.azure.com"
AZURE_DB_USER="..."
AZURE_DB_PASSWORD="..."
AZURE_DB_NAME="..."
```

### 1. Descargar registros oficiales y subirlos a Azure Blob Storage:
```bash
python ingestion/alojamientos_oficiales/alojamientos_oficiales_download.py
```

### 2. Cargar registros en Azure PostgreSQL (Capa Bronze):
```bash
python ingestion/postgres/05_ingest_tabular_to_postgres.py
```

### 3. Geocodificar direcciones pendientes y actualizar la tabla de lookup en Azure:
```bash
python ingestion/postgres/07_alojamientos_oficiales_geocode.py
```
