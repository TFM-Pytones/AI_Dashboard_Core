# Pipeline de Movilidad: GTFS TITSA y Metropolitano

Este documento detalla la arquitectura y el flujo de datos para la ingesta y transformación de los datos abiertos de transporte público (GTFS) de TITSA y Metropolitano de Tenerife, pasando por la arquitectura Medallón (Bronze -> Silver).

## 1. Extracción e Ingesta a Blob Storage (Capa Raw)

El proceso automatizado se encuentra en `ingestion/titsa/titsa_gtfs_upload_blob.py`.

* **Origen**: Archivos ZIP en formato GTFS publicados en el portal de Datos Abiertos de Tenerife.
* **Procesamiento previo**: En lugar de utilizar librerías de alto nivel como `partridge` (que filtraban datos por fechas de calendario omitiendo viajes pasados o futuros), el script lee directamente del `.zip` los archivos CSV.
* **Limpieza de Tipos**: Se aplica la función `_castear_ids()` para forzar a que todos los IDs (`stop_id`, `route_id`, `trip_id`, etc.) sean de tipo `String`. Esto soluciona incompatibilidades críticas (Metropolitano usa letras, TITSA usa números) que impedían la escritura en Parquet.
* **Separación de Datos**:
  1. **Tabulares (Relacionales)**: Viajes, calendarios, horarios, atributos de rutas.
  2. **Espaciales (Vectoriales)**: Geometrías de las paradas (Puntos) y los recorridos (LineString). Generados usando `geopandas`.
* **Destino**: `bronce-raw` en Azure Blob Storage (7 archivos `.parquet` por operador).

## 2. Ingesta a PostgreSQL (Capa Bronze)

El traspaso desde el Blob Storage a PostgreSQL se realiza en dos scripts separados debido a la naturaleza de los datos:

* **`ingest_tabular_to_postgres.py`**: Ingesta las 5 tablas relacionales puras:
  * `bronze_titsa_viajes`
  * `bronze_titsa_horarios`
  * `bronze_titsa_calendario`
  * `bronze_titsa_calendario_excepciones`
  * `bronze_titsa_rutas_atributos`
* **`ingest_vector_to_postgres.py`**: Ingesta mediante **PostGIS** las 2 tablas con geometría:
  * `bronze_titsa_paradas` (Puntos)
  * `bronze_titsa_rutas` (LineString)

## 3. Transformación Analítica en dbt (Capa Silver)

El formato GTFS crudo en la capa Bronze está altamente normalizado (7 tablas interrelacionadas) para evitar redundancias, lo cual es ineficiente para el consumo en mapas o dashboards analíticos. 

En la **capa Silver**, hemos "aplanado" (denormalizado) toda la información en **únicamente dos tablas espaciales principales**:

### A. `silver_gtfs_paradas` (Modelo Espacial)
Unifica la geometría de cada parada de la isla y la enriquece cruzando los horarios, viajes y atributos.
* **Métricas añadidas**:
  * `lineas_disponibles`: Lista agregada de los nombres cortos de las líneas que operan en esa parada (Ej: `"110, 111, 415"`).
  * `total_expediciones_parada`: Cantidad total histórica de servicios (guaguas/tranvías) que tienen programada parada en esa marquesina.

### B. `silver_gtfs_rutas` (Modelo Espacial)
Contiene la geometría de los trazados de las líneas.
* **Métricas añadidas**:
  * `total_expediciones`: Número de viajes (trips) totales que componen esta ruta.

> [!NOTE]
> Al reducir de 7 a 2 tablas para la capa Silver, se ha decidido **agregar las frecuencias**. Si en fases posteriores del TFM (como el cálculo de isócronas minuto a minuto) se necesita la granularidad temporal exacta (a qué segundo pasa la guagua por la parada), se recomienda consultar directamente `bronze_titsa_horarios`, la cual contiene el nivel máximo de detalle.
