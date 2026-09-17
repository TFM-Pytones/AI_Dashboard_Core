# Pipeline de Movilidad: GTFS TITSA y Metropolitano de Tenerife

Documentación de la arquitectura y flujo de datos para la ingesta, almacenamiento y transformación de los datos abiertos de transporte público regular (GTFS) de las guaguas de **TITSA** y el **Tranvía de Tenerife (Metropolitano)** a través de la arquitectura Medallón (*Bronze → Silver*).

---

## 1. Extracción e Ingesta a Azure Blob Storage (Capa Raw)

El proceso automatizado se encuentra implementado en [`ingestion/gtfs/gtfs_upload_blob.py`](gtfs_upload_blob.py):

* **Origen de datos**: Archivos ZIP en formato estándar GTFS publicados en el portal de Datos Abiertos del Cabildo de Tenerife.
* **Procesamiento previo**: En lugar de utilizar librerías de alto nivel que filtran viajes por calendario activo, el script extrae y procesa directamente los ficheros CSV del archivo comprimido.
* **Tipado e interoperabilidad**: Se aplica la función `_castear_ids()` para homogeneizar todos los identificadores (`stop_id`, `route_id`, `trip_id`, etc.) como cadenas de texto (`VARCHAR`/`String`), resolviendo incompatibilidades entre operadores (el tranvía emplea identificadores alfanuméricos y TITSA números).
* **Separación de datos**:
  1. **Tabulares (relacionales)**: Viajes, calendarios, horarios y atributos de rutas.
  2. **Espaciales (vectoriales)**: Coordenadas de paradas (Puntos) y trazados de rutas (LineStrings), generados con `geopandas`.
* **Destino**: Contenedor `bronce-raw` en Azure Blob Storage (7 archivos `.parquet` por operador).

---

## 2. Ingesta a PostgreSQL (Capa Bronze)

El traspaso desde Azure Blob Storage hacia Azure Database for PostgreSQL se realiza mediante scripts de carga por lotes:

* **Tablas relacionales puras**:
  * `bronze_gtfs_horarios` (**1.359.365** filas): Horarios exactos de paso por parada (de los 2,08 millones de registros brutos extraídos del ZIP).
  * `bronze_gtfs_viajes` (**48.655** filas): Viajes programados por línea y servicio.
  * `bronze_gtfs_rutas_atributos` (**183** filas): Denominación comercial, color y operador de ruta.
  * `bronze_gtfs_calendario_excepciones` (**26.651** filas): Festivos y servicios especiales.
  * `bronze_gtfs_calendario` (**3** filas): Tipos de servicio base.
* **Tablas espaciales (PostGIS)**:
  * `bronze_gtfs_paradas` (**3.934** paradas): Puntos geolocalizados de paradas en EPSG:4326.
  * `bronze_gtfs_rutas` (**873** rutas): Geometrías lineales del viario por trayecto en EPSG:4326.

| Capa | Tabla PostgreSQL | Registros Verificados | Tipo y SRID | Descripción |
|---|---|:---:|---|---|
| **Bronze** | `bronze.bronze_gtfs_paradas` | **3.934** | PostGIS Point (4326) | Marquesinas y paradas insulares |
| **Bronze** | `bronze.bronze_gtfs_rutas` | **873** | PostGIS LineString (4326) | Trazados geométricos por trayecto |
| **Bronze** | `bronze.bronze_gtfs_rutas_atributos` | **183** | Relacional | Códigos comerciales y atributos de líneas |
| **Bronze** | `bronze.bronze_gtfs_viajes` | **48.655** | Relacional | Expediciones y viajes planificados |
| **Bronze** | `bronze.bronze_gtfs_horarios` | **1.359.365** | Relacional | Horarios de paso cronometrados |
| **Silver** | `silver.silver_gtfs_paradas` | **3.934** | PostGIS Point (4326) | Paradas enriquecidas con líneas y volumen diario |
| **Silver** | `silver.silver_gtfs_rutas` | **873** | PostGIS LineString (4326) | Rutas enriquecidas con total de viajes |

---

## 3. Transformación Analítica en dbt (Capa Silver)

El formato estándar GTFS crudo en Bronze está altamente normalizado (7 tablas interrelacionadas) para evitar redundancias, lo cual es ineficiente para el consumo en mapas o dashboards interactivos.

En la **capa Silver**, la información se ha desnormalizado y enriquecido en **dos tablas espaciales principales**:

### A. `silver_gtfs_paradas` (Modelo Espacial)
Unifica la geometría de cada parada de la isla y la enriquece cruzando horarios, viajes y líneas:
* **`lineas_disponibles`**: Cadena concatenada de los números cortos de las líneas que operan en esa parada (ej. `"110, 111, 415"`).
* **`total_expediciones_parada`**: Conteo agregado de expediciones diarias que efectúan parada en la marquesina.
* **`modo`**: Tipo de transporte (`Bus` o `Tram`).
* **`operador`**: Entidad operadora (`TITSA` o `Tranvía`).
* **`geometry`**: Punto PostGIS en SRID 4326.

### B. `silver_gtfs_rutas` (Modelo Espacial)
Contiene la geometría completa de los trazados de las líneas sobre la red viaria:
* **`route_short_name`**: Código comercial de la línea (ej. 110, 014, L1).
* **`total_expediciones`**: Número total de viajes que componen la ruta.
* **`operador`**: Empresa operadora (`TITSA` o `Tranvía`).
* **`geometry`**: Linestring PostGIS en SRID 4326.

> [!NOTE]
> Al reducir de 7 a 2 tablas para la capa Silver, se consolidan las frecuencias de paso. Si en análisis de accesibilidad avanzados se requiere la granularidad temporal exacta (segundo a segundo de paso), se puede consultar directamente `bronze_gtfs_horarios`.
