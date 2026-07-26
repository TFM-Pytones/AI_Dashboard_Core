# Módulo de Ingestión: Agrocabildo

Este módulo contiene todos los componentes necesarios para consumir datos meteorológicos en tiempo real e históricos desde la API oficial de **Agrocabildo (Cabildo de Tenerife)**, guardando backups locales en Parquet y subiendo los registros consolidados de forma particionada a **Azure Blob Storage (Capa Bronce / Raw)**.

---

## 🏗️ Arquitectura de Almacenamiento (Particionamiento)

Para evitar problemas de límite de memoria RAM en entornos locales y permitir descargas en paralelo sin colisiones por escritura concurrente, el histórico de clima se almacena de forma particionada por estación en el contenedor **`bronce-raw`** de Azure:

`clima_horario_agrocabildo/estacion_{id_estacion}.parquet`

- **Eficiencia en RAM**: Los scripts solo cargan y actualizan el archivo Parquet individual de la estación procesada (~1-2 MB por archivo) en lugar de un monolito gigante.
- **Paralelismo Seguro**: Múltiples ordenadores pueden procesar diferentes rangos de estaciones simultáneamente sin pisarse los datos de Azure.
- **Lectura Unificada**: Herramientas analíticas como dbt, Pandas y DuckDB pueden consultar la carpeta completa como si fuera una sola tabla grande usando rutas de comodín (ej. `clima_horario_agrocabildo/*.parquet`).

---

## 🗂️ Descripción de los Archivos

### 1. `agrocabildo_client.py` (Cliente API)
- **Función**: Librería base que se conecta con el servicio web de datos meteorológicos de Tenerife.
- **Detalles**:
  - Implementa control de velocidad de peticiones (**Rate Limit de 10 req/min**), obligando a esperar **6.5 segundos** entre llamadas para evitar bloqueos de IP (`HTTP 429`).
  - Gestiona la paginación y la conversión de respuestas JSON de la API.

### 2. `agrocabildo_ingestion.py` (Pipeline de Ingesta Diaria)
- **Función**: Script que se ejecuta en producción para descargar lecturas climáticas recientes y guardarlas.
- **Detalles**:
  - Lee las estaciones objetivo desde `estaciones-meteorologicas.csv`.
  - Descarga los datos de las últimas 12/24 horas de la API.
  - Actualiza el backup local general en `data/agrocabildo_hourly.parquet`.
  - Agrupa las lecturas por `id_estacion`, lee los parquets respectivos en Azure, añade el nuevo bloque, deduplica y los vuelve a subir de forma independiente.

### 3. `agrocabildo_historical_backfill.py` (Descarga Histórica)
- **Función**: Script diseñado para descargar el histórico de datos desde 2019 de todas las estaciones.
- **Detalles**:
  - Utiliza `backfill_progress.json` para llevar el control de qué estaciones, sensores y años se han descargado con éxito.
  - Sincroniza y fusiona el archivo de progreso con la nube al inicio y al final de cada ejecución.
  - Guarda y sube los datos directamente bajo la ruta particionada en Azure Blob Storage.

### 4. `agrocabildo_scheduler.py` (Orquestador Periódico)
- **Función**: Servicio ligero que ejecuta en bucle continuo la ingesta diaria cada 12 horas.

### 5. `test_azure_ingestion.py` (Prueba de Integración)
- **Función**: Script de validación rápida. Descarga una muestra de 2 estaciones en tiempo real y verifica la creación y actualización de sus respectivos parquets en Azure Blob Storage.

### 6. `backfill_progress.json` (Control de Estado)
- **Función**: Archivo de progreso local y remoto. Almacena las claves compuestas `[IDEstacion]_[IDSensor]_[Año]` completadas.

---

## 🚀 Cómo Ejecutar los Scripts

*(Asegúrate de estar dentro de tu entorno virtual `.venv` y de tener las variables en tu `.env`)*.

* **Ejecutar Ingesta Diaria incremental**:
  ```bash
  python ingestion/agrocabildo/agrocabildo_ingestion.py
  ```

* **Ejecutar Prueba de Conexión y Funcionamiento**:
  ```bash
  python ingestion/agrocabildo/test_azure_ingestion.py
  ```

* **Ejecutar el Backfill Histórico** (ejemplo de rango del índice 12 al 15, máximo 2 estaciones):
  ```bash
  python ingestion/agrocabildo/agrocabildo_historical_backfill.py --start-year 2019 --station-range 12-15 --max-stations 2
  ```
