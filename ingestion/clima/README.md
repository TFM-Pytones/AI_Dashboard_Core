# Ingesta Meteorológica: Red Agrocabildo (Capa Bronze)

Módulo encargado de la adquisición, estandarización y carga de series meteorológicas en tiempo real e históricas procedentes de la red de **67 estaciones automáticas** del **Cabildo de Tenerife (Agrocabildo)**.

---

## 1. Arquitectura y Flujo de Datos

```
API Oficial de Datos Meteorológicos (https://datos.tenerife.es/api/meteo/latest)
       │
       ├─► clima_metadatos_upload_blob.py ──► bronce-raw/clima/estaciones/ y sensores/
       │
       ├─► clima_realtime_upload_blob.py   ──► Ingesta incremental (últimas 24h)
       │
       └─► clima_historical_upload_blob.py ──► Backfill histórico continuo (2019-2026)
                                               (Con checkpointing en backfill_progress.json)
       │
       ▼  Almacenamiento particionado en Azure Blob Storage
Contenedor: bronce-raw/clima/mediciones/año=YYYY/mes=MM/estacion_{id}.parquet
       │
       ▼  Carga por lotes / incremental (ingestion/postgres/05_ingest_tabular_to_postgres.py)
PostgreSQL: bronze.bronze_clima_horario_agrocabildo
       │
       ▼  Transformación y agregación espacial con dbt
PostgreSQL: silver.silver_clima_estaciones / silver_clima_diario_h3
```

---

## 2. Estrategia de Particionamiento Hive en Azure Blob Storage

Para evitar saturar la memoria RAM en entornos locales y posibilitar descargas en paralelo sin colisiones por escritura concurrente, las mediciones climáticas se almacenan bajo una estructura de carpetas particionadas estilo Hive:

`clima/mediciones/año=YYYY/mes=MM/estacion_{id_estacion}.parquet`

* **Consumo Eficiente de Memoria**: Cada partición mensual por estación pesa entre 50 KB y 500 KB, permitiendo que scripts y pipelines procesen solo la ventana temporal necesaria sin cargar Gigabytes de golpe.
* **Escrituras Idempotentes**: Permite reintentos aislados por estación y mes sin afectar al resto del histórico.
* **Optimización de Particiones Existentes**: El script [`repartition_clima_azure.py`](file:///c:/Users/ROBERTO/Proyectos_Python/TFM_TUI_Tenerife/AI_Dashboard_Core/ingestion/clima/repartition_clima_azure.py) analiza y migra automáticamente cualquier blob no particionado antiguo al esquema `año=YYYY/mes=MM/`.

---

## 3. Descripción de los Scripts

### 1. [`clima_client.py`](file:///c:/Users/ROBERTO/Proyectos_Python/TFM_TUI_Tenerife/AI_Dashboard_Core/ingestion/clima/clima_client.py) (Cliente API Base)
Librería cliente que encapsula las peticiones HTTP contra la API v2.0.0 de datos meteorológicos:
* **Control Estricto de Tasa (*Rate Limiting*)**: Aplica un intervalo mínimo obligatorio de **6.5 segundos** entre llamadas consecutivas para respetar la cuota del Cabildo de **máximo 10 peticiones/minuto**.
* **Gestión de Errores y Reintentos**: Manejo automatizado de respuestas `HTTP 429` (Too Many Requests) con esperas progresivas exponenciales (20s, 40s, 60s...) y capturas de excepciones de red con timeout de 60 segundos.

### 2. [`clima_metadatos_upload_blob.py`](file:///c:/Users/ROBERTO/Proyectos_Python/TFM_TUI_Tenerife/AI_Dashboard_Core/ingestion/clima/clima_metadatos_upload_blob.py) (Metadatos de Red)
Descarga el inventario de la red y lo serializa a Parquet:
* **Estaciones (`/stations`)**: Identificador (`estacion_id`), nombre, municipio, latitud, longitud, altitud y fecha de instalación. Destino: `clima/estaciones/estaciones_agrocabildo.parquet`.
* **Sensores (`/measures`)**: Catálogo de magnitudes medidas (temperatura, humedad, precipitación, radiación solar, velocidad y dirección del viento, presión atmosférica). Destino: `clima/sensores/sensores_meteorologicos.parquet`.

### 3. [`clima_realtime_upload_blob.py`](file:///c:/Users/ROBERTO/Proyectos_Python/TFM_TUI_Tenerife/AI_Dashboard_Core/ingestion/clima/clima_realtime_upload_blob.py) (Ingesta en Tiempo Real)
* Descarga las lecturas de las últimas 24 horas para las 67 estaciones activas.
* Fusiona las nuevas lecturas con el archivo de la partición actual en Azure, deduplica por clave primaria `(estacion_id, sensor_id, timestamp)` y vuelve a subir el Parquet actualizado.

### 4. [`clima_historical_upload_blob.py`](file:///c:/Users/ROBERTO/Proyectos_Python/TFM_TUI_Tenerife/AI_Dashboard_Core/ingestion/clima/clima_historical_upload_blob.py) (Backfill Histórico)
* Descarga sistemática del histórico completo desde el 1 de enero de 2019.
* **Tolerancia a Fallos y Checkpointing**: Persiste el progreso en `backfill_progress.json` guardando la tupla `[estacion_id]_[sensor_id]_[año]`. Al reiniciar una corrida interrumpida, retoma exactamente donde se detuvo.
* Permite filtrado por rango de estaciones mediante argumentos `--station-range` o `--max-stations`.

### 5. [`repartition_clima_azure.py`](file:///c:/Users/ROBERTO/Proyectos_Python/TFM_TUI_Tenerife/AI_Dashboard_Core/ingestion/clima/repartition_clima_azure.py) (Mantenimiento del Data Lake)
* Script de utilidad que descarga blobs de mediciones antiguos sin particionar, extrae año y mes de la columna `timestamp`, y los re-sube bajo la estructura `año=YYYY/mes=MM/`, eliminando el blob monolítico original.

---

## 4. Instrucciones de Ejecución

### Requisitos previos:
Asegúrate de definir en `.env` la cadena de conexión de Azure:
```bash
AZURE_STORAGE_CONNECTION_STRING="DefaultEndpointsProtocol=https;AccountName=...;AccountKey=..."
```

### 1. Ingesta de metadatos de la red:
```bash
python ingestion/clima/clima_metadatos_upload_blob.py
```

### 2. Ingesta en tiempo real (últimas 24 horas):
```bash
python ingestion/clima/clima_realtime_upload_blob.py
```

### 3. Backfill histórico (ejemplo para estaciones 1 a 10):
```bash
python ingestion/clima/clima_historical_upload_blob.py --start-year 2019 --station-range 1-10
```

### 4. Cargar a Azure PostgreSQL (Capa Bronze):
Para volcar las mediciones y metadatos a las tablas `bronze_clima_horario_agrocabildo`, `bronze_estaciones_agrocabildo` y `bronze_sensores_meteorologicos`:
```bash
python ingestion/postgres/05_ingest_tabular_to_postgres.py
```
