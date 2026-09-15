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
  * `bronze_gtfs_viajes`: Viajes programados por línea y servicio.
  * `bronze_gtfs_horarios`: Horarios exactos de paso por parada.
  * `bronze_gtfs_calendario`: Días de operación regulares.
  * `bronze_gtfs_calendario_excepciones`: Festivos y servicios especiales.
  * `bronze_gtfs_rutas_atributos`: Denominación, color y operador de ruta.
* **Tablas espaciales (PostGIS)**:
  * `bronze_gtfs_paradas`: Puntos geolocalizados de paradas.
  * `bronze_gtfs_rutas`: Geometrías lineales del viario por trayecto.

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
