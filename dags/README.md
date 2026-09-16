# 🌊 Airflow DAGs — TFM Tenerife Tourism Analytics

Esta carpeta contiene los **DAGs de Apache Airflow** que orquestan el pipeline completo de datos del proyecto TFM.

---

## Arquitectura de DAGs

```
dags/
├── dag_historical_full.py       ← Carga histórica completa (una vez)
├── dag_incremental_monthly.py   ← Actualización mensual automática
└── dag_social_refresh.py        ← Refresco manual de contenido social
```

---

## DAG 1 — `historical_full_pipeline`

**Cuándo ejecutar**: Una sola vez, para cargar todo el histórico desde cero.

**Trigger**: Manual desde la UI (`Trigger DAG ▶`)

### Flujo de tareas

```
start
  │
  ├── FASE 1: Ingesta a Blob (paralelo)
  │    ├── ingest_aena
  │    ├── ingest_alojamientos_oficiales
  │    ├── ingest_clima_historico
  │    ├── ingest_gtfs
  │    ├── ingest_istac (municipios + vivienda vacacional)
  │    ├── ingest_espacial (cabildo → enp → h3 → osm, secuencial)
  │    ├── ingest_tripadvisor  ⚠️
  │    ├── ingest_youtube      ⚠️
  │    ├── ingest_satelite     ⚠️ requiere GEE auth
  │    ├── ingest_booking      ⚠️ Selenium
  │    └── ingest_losviajeros  ⚠️ foro supervisado
  │
  │    join (none_failed_min_one_success → continúa aunque falle alguna ⚠️)
  │
  ├── FASE 2: Carga a PostgreSQL (secuencial)
  │    pg_01_vector → pg_02_mdt → pg_03_satelite → pg_04_booking
  │    → pg_05_tabular → pg_06_geocode_booking → pg_07_alojamientos_geocode
  │
  ├── FASE 3: dbt Silver (paralelo por dominio)
  │    silver_alojamiento │ silver_booking │ silver_clima │ silver_espacial
  │    silver_istac │ silver_losviajeros │ silver_movilidad
  │    silver_tripadvisor │ silver_youtube
  │
  ├── FASE 4: Analytics
  │    ├── check_ml_enabled (ShortCircuit — lee Variable 'run_heavy_ml')
  │    │    └── sentiment_batch │ sentiment_backfill │ aspects_batch
  │    │         geo_toponyms │ clustering_features
  │    └── accesibilidad_h3 (siempre — no requiere GPU)
  │
  └── FASE 5: dbt Gold (paralelo)
       gold_aena_pasajeros │ gold_h3_master │ gold_municipio_anual
       gold_municipio_empleo │ gold_municipio_master │ gold_municipio_mensual
       gold_sentimiento_h3 │ gold_turismo_hotelero_anual │ gold_turismo_hotelero_mensual
  │
 end
```

### Variables de Airflow necesarias

| Variable | Valor por defecto | Descripción |
|----------|------------------|-------------|
| `run_heavy_ml` | `false` | Activar tasks de GPU (sentiment, aspects, topics) |

### ⚡ Ingesta de Clima vía CKAN (Agrocabildo)

El histórico meteorológico y la ingesta incremental han sido migrados al catálogo abierto **CKAN del Cabildo** (`clima_ckan_bulk_upload_blob.py` y `clima_realtime_upload_blob.py`):
1. **Histórico Masivo**: Pasa de tardar 7-10 días a solo **minutos** mediante volcados JSON anuales consolidados por estación, eliminando el bloqueo del worker.
2. **Incremental Mensual**: Descarga concurrente multi-hilo del año corriente en **~30-50 segundos** con deduplicación y particionado Hive en Azure Blob Storage.
3. **Carga en PostgreSQL**: Se procesa directamente mediante streaming `COPY` con `PyArrow` en segundos.

---

## DAG 2 — `incremental_monthly_pipeline`

**Cuándo ejecutar**: Automáticamente el **día 5 de cada mes a las 06:00** (para dar margen a que los portales oficiales como ISTAC y Copernicus consoliden y publiquen los datos del mes vencido).

**Fuentes actualizadas**:
- ✅ Satélite (GEE — nuevas imágenes del mes anterior)
- ✅ ISTAC (nuevos indicadores estadísticos)
- ✅ Clima (últimas 24h acumuladas del mes)
- ✅ Alojamientos Oficiales (registro actualizado desde datos.canarias.es)
- ⚠️ AENA (Excel manual — ver instrucciones abajo)

### Flujo de tareas

```
start
  │
  ├── FASE 1: Ingesta incremental (dos ramas en paralelo)
  │    │
  │    ├── [Automático]
  │    │    ingest_satelite_monthly
  │    │    ingest_istac (municipios + vivienda vacacional)
  │    │    ingest_clima_realtime
  │    │    ingest_alojamientos
  │    │
  │    └── [Semi-manual — AENA]
  │         aena_check_ready (ShortCircuit) → ingest_aena → reset_aena_flag
  │
  │    join (none_failed_min_one_success)
  │
  ├── FASE 2: PostgreSQL (solo tablas afectadas, paralelo)
  │    pg_satelite │ pg_tabular │ pg_alojamientos_geocode
  │
  ├── FASE 3: dbt Silver (dominios afectados, paralelo)
  │    silver_espacial │ silver_istac │ silver_clima
  │    silver_alojamiento │ silver_movilidad
  │
  ├── FASE 4: Analytics
  │    analytics_accesibilidad_h3
  │
  └── FASE 5: dbt Gold (todos los modelos, paralelo)
       gold_aena_pasajeros │ gold_h3_master │ gold_municipio_anual
       gold_municipio_empleo │ gold_municipio_master │ gold_municipio_mensual
       gold_sentimiento_h3 │ gold_turismo_hotelero_anual │ gold_turismo_hotelero_mensual
```

### Instrucciones para AENA (cada mes)

AENA no tiene API pública — publica Excel mensuales en su web. Proceso:

1. Descarga el Excel desde [estadisticas.aena.es](https://estadisticas.aena.es)
2. Cópialo a `data/aena/` en el repositorio
3. En la **UI de Airflow** → Admin → Variables → edita `aena_upload_ready` = `true`
4. El DAG detecta la variable y ejecuta la ingesta de AENA automáticamente
5. La variable se resetea a `false` sola tras la ingesta exitosa

> **Nota**: El pipeline de satélite, ISTAC, clima y alojamientos **no espera a AENA** — corren en paralelo. AENA se une cuando la variable está lista.

---

## DAG 3 — `social_refresh_pipeline`

**Cuándo ejecutar**: Manualmente, cuando quieras refrescar reseñas y comentarios.

**Fuentes**:
- TripAdvisor (API Terra)
- YouTube (API Data v3)
- Booking.com (Selenium — Chrome headless)
- LosViajeros (scraper de foro, supervisado)

> 🏢 **Estrategia Comercial (Caso TUI)**:
> Para un despliegue en un entorno empresarial como TUI, la estrategia orquestada desde Airflow debe adaptarse:
> - **TripAdvisor, Booking y YouTube**: Se deben reemplazar los scrapers y APIs gratuitas actuales por integraciones con sus **APIs oficiales de pago** (enterprise). Airflow ejecutaría scripts adaptados a estas APIs para garantizar estabilidad, legalidad y velocidad.
> - **LosViajeros**: Al no existir API oficial, **se mantiene el scraper** actual como única vía de extracción, ejecutado como una tarea aislada en este DAG.

**Downstream**: silver social → NLP analytics (si `run_heavy_ml=true`) → gold h3/sentimiento

> ⚠️ Booking puede tardar **hasta 8 horas** — planifica el trigger con tiempo suficiente.

---

## Guía de Despliegue con Docker (Paso a Paso)

### 1. Requisitos Previos e Instalación de Docker Desktop (Windows)

Airflow corre como un conjunto de servicios Linux (PostgreSQL metadata, Scheduler y Webserver). Para ejecutarlo en Windows:

1. **Descargar Docker Desktop**: Instala la versión oficial gratuita desde [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop/).
2. **Activar WSL 2 en Windows**: Abre PowerShell como Administrador y ejecuta:
   ```powershell
   wsl --install --no-distribution
   ```
   *(Si Docker muestra "Virtualization support not detected", verifica que en la BIOS de tu portátil esté activa la virtualización; en Lenovo ThinkPad se encuentra en `Security` → `Virtualization` → `Intel Virtualization Technology [Enabled]`).*
3. **Optimización de Memoria RAM (Recomendado para equipos de 16 GB)**:
   Para evitar que WSL 2 consuma toda la memoria del sistema durante la compilación de imágenes pesadas, crea un archivo `.wslconfig` en tu carpeta de usuario (`C:\Users\<TuUsuario>\.wslconfig`):
   ```ini
   [wsl2]
   memory=5GB
   swap=4GB
   processors=4
   ```
4. **Iniciar Docker Desktop**: Abre la aplicación desde el menú de inicio y espera a que el icono de la ballena en la barra de tareas se ponga en **verde** (*"Engine running"*).

---

### 2. Soporte en el Editor Local (VS Code / Antigravity IDE)

Airflow se ejecuta dentro del contenedor Docker Linux, mientras que tu editor analiza el código con el `.venv` de Windows. Para evitar errores visuales de tipo `Import "airflow" could not be resolved` y disfrutar de autocompletado:

```powershell
# Instalar los stubs y definiciones de Airflow en el .venv local sin dependencias de servidor:
.venv\Scripts\pip.exe install apache-airflow==2.9.2 --no-deps --ignore-requires-python
```
*(Ya configurado en `.vscode/settings.json` con `reportMissingImports: "none"`).*

---

### 3. Inicialización del Stack (Solo la primera vez)

Desde la raíz del repositorio (`AI_Dashboard_Core`), inicializa la base de datos de metadatos de Airflow y genera el usuario administrador:

```powershell
docker compose up airflow-init
```

#### ¿Qué ocurre durante este paso?
* **Descarga y compilación de imágenes (~1 GB)**: Al ejecutarse por primera vez, Docker descarga las capas base de `apache/airflow:2.9.2` y `postgres:15-alpine`, y compila `Dockerfile.airflow` (con dbt, soporte geoespacial y Chromium para scraping).
* **Tiempo de espera normal (2 a 4 minutos)**: Verás indicadores como `[+] up 0/1` o barras de descarga. Es el comportamiento estándar la primera vez.
* **Mapeo de variables de entorno**: Docker lee automáticamente tu archivo `.env` del repositorio (inyectando `AZURE_STORAGE_CONNECTION_STRING`, `AZURE_DB_*`, API keys, etc.).
* **Mensaje de éxito**: El contenedor crea las tablas internas en PostgreSQL, genera el usuario administrador (`admin` / `admin`) y finaliza automáticamente con:
  ```text
  airflow-init exited with code 0
  ```

---

### 4. Arrancar Airflow en Segundo Plano

Una vez completada la inicialización, levanta todos los servicios:

```powershell
docker compose up -d
```

Para verificar que el servicio web está listo (~45-60 segundos):
```powershell
docker compose logs -f airflow-webserver
# Esperar a ver: "Listening at: http://0.0.0.0:8080" (pulsar Ctrl+C para salir del visor de logs)
```

---

### 5. Acceder a la Interfaz Web

1. Abre tu navegador en: **`http://localhost:8080`**
2. Inicia sesión con las credenciales por defecto:
   - **Usuario:** `admin`
   - **Contraseña:** `admin`
3. Verás en el panel los tres DAGs listos:
   - `historical_full_pipeline`
   - `incremental_monthly_pipeline`
   - `social_refresh_pipeline`

---

### 6. Configurar Variables de Airflow (Admin → Variables → +)

Crea las variables que controlan la ejecución condicional:

| Key | Value | Descripción |
| :--- | :--- | :--- |
| `run_heavy_ml` | `false` | `true` para activar inferencia pesada NLP (GPU / modelos grandes). |
| `aena_upload_ready` | `false` | Poner en `true` cuando se descargue un nuevo Excel de AENA en `data/aena/`. |

---

### 7. Comandos Frecuentes para el Día a Día

| Acción | Comando |
| :--- | :--- |
| **Arrancar Airflow** | `docker compose up -d` |
| **Ver logs en directo** | `docker compose logs -f` |
| **Ver estado de contenedores** | `docker compose ps` |
| **Detener Airflow** | `docker compose down` |
| **Reconstruir la imagen si cambian requisitos** | `docker compose up --build -d` |

---

## Verificación de parseo

```bash
docker compose exec airflow-scheduler python -c "
from airflow.models import DagBag
db = DagBag('/opt/airflow/dags')
if db.import_errors:
    print('ERRORES:', db.import_errors)
else:
    print('OK — DAGs:', list(db.dags.keys()))
"
```

---

## Estructura de directorios relacionados

```
AI_Dashboard_Core/
├── dags/                          ← Este directorio
│   ├── dag_historical_full.py
│   ├── dag_incremental_monthly.py
│   └── dag_social_refresh.py
├── ingestion/                     ← Scripts de ingesta por fuente
│   ├── postgres/                  ← Loaders a PostgreSQL (01_ → 07_)
│   └── <fuente>/                  ← Script de upload_blob.py por fuente
├── analytics/                     ← Scripts de análisis y ML
├── dbt_project/                   ← Modelos dbt silver/ y gold/
├── Dockerfile.airflow             ← Imagen extendida con dbt + deps
├── docker-compose.yml             ← Stack Airflow + Postgres metadata
├── airflow.env                    ← Config de Airflow
└── requirements-airflow.txt       ← Deps instaladas en la imagen
```
