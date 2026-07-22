# Módulo de Ingestión: Agrocabildo

Este módulo contiene todos los componentes necesarios para consumir datos meteorológicos en tiempo real e históricos desde la API oficial de **Agrocabildo (Cabildo de Tenerife)**, guardando backups locales en Parquet y subiendo los registros al esquema `raw_data` de la base de datos flexible en Azure.

---

## 🗂️ Descripción de los Archivos

### 1. `agrocabildo_client.py` (Cliente API)
- **Función**: Es la librería base que se conecta con el servicio web de datos meteorológicos de Tenerife.
- **Detalles**:
  - Implementa el control estricto de velocidad de peticiones (**Rate Limit de 10 req/min**), obligando a esperar **6.5 segundos** entre llamadas para evitar bloqueos de IP (`HTTP 429`).
  - Gestiona la paginación y la conversión de formatos de las respuestas JSON de la API.

### 2. `agrocabildo_ingestion.py` (Pipeline de Ingesta Diaria)
- **Función**: Es el script que se ejecuta en producción para descargar lecturas climáticas recientes y guardarlas de forma incremental.
- **Detalles**:
  - Lee el archivo `estaciones-meteorologicas.csv` para saber qué estaciones procesar.
  - Solicita los datos de las últimas 12/24 horas a la API.
  - Actualiza el backup local en formato Parquet (`AI_Dashboard_Core/data/agrocabildo_hourly.parquet`).
  - Inserta/actualiza los registros en Azure Database en la tabla `raw_data.clima_horario_agrocabildo` usando una estrategia de **UPSERT (`ON CONFLICT DO UPDATE`)** para evitar datos duplicados.

### 3. `agrocabildo_historical_backfill.py` (Descarga Histórica)
- **Función**: Script diseñado para descargar el histórico de datos desde el año 2019 de todas las estaciones instaladas antes de 2020.
- **Detalles**:
  - Utiliza el archivo `backfill_progress.json` para llevar el control de qué estaciones, sensores y años ya se han descargado con éxito.
  - Es **pausable y reanudable**: si se detiene, continuará exactamente en el último punto guardado.

### 4. `agrocabildo_scheduler.py` (Orquestador Local)
- **Función**: Un script ligero que ejecuta de forma cíclica la ingesta diaria.
- **Detalles**: Diseñado para pruebas locales continuas o para ser invocado por el servicio cron del sistema.

### 5. `test_azure_ingestion.py` (Prueba de Integración)
- **Función**: Script de prueba rápida para validar la conexión y el correcto funcionamiento del pipeline hacia el servidor de Azure.
- **Detalles**: Descarga una muestra corta de 2 estaciones y verifica que se crean las tablas y se insertan registros en la base de datos de Azure.

### 6. `backfill_progress.json` (Control de Estado)
- **Función**: Archivo JSON que almacena las marcas de las descargas históricas completadas con éxito.
- **Formato**: Lista de claves únicas compuestas por `[IDEstacion]_[IDSensor]_[Año]`.

### 7. `Manual_de_usuario_API_datos_meteorologicos.pdf`
- **Función**: Documentación PDF oficial provista por el Cabildo de Tenerife con las especificaciones técnicas y listados de sensores de su API meteorológica.

---

## 🚀 Cómo Ejecutar los Scripts

*(Asegúrate de estar dentro de tu entorno virtual y de tener las variables en tu `.env`)*.

* **Ejecutar Ingesta Diaria incremental**:
  ```bash
  python AI_Dashboard_Core/ingestion/agrocabildo/agrocabildo_ingestion.py
  ```

* **Ejecutar Prueba de Conexión a Azure**:
  ```bash
  python AI_Dashboard_Core/ingestion/agrocabildo/test_azure_ingestion.py
  ```
