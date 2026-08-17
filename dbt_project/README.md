# dbt_project — Transformaciones Silver

Proyecto **dbt** del TFM *AI Dashboard Core — Tenerife Tourism*. Gestiona todas las
transformaciones de la capa **Bronze → Silver** en Azure PostgreSQL.

---

## Requisitos previos

```bash
# Instalar dbt con el adaptador de PostgreSQL
pip install dbt-postgres

# Verificar instalación
dbt --version
```

Las variables de conexión se leen del fichero `.env` en la raíz del proyecto:

| Variable de entorno | Descripción |
|---|---|
| `AZURE_DB_HOST` | Host del servidor Azure PostgreSQL |
| `AZURE_DB_USER` | Usuario de la base de datos |
| `AZURE_DB_PASSWORD` | Contraseña |
| `AZURE_DB_NAME` | Nombre de la base de datos |

> **Nota**: el `profiles.yml` ya está configurado para leer estas variables con
> `env_var()`. No hay que editar `profiles.yml` manualmente.

---

## Estructura del proyecto

```
dbt_project/
├── dbt_project.yml          # Configuración global del proyecto dbt
├── profiles.yml             # Conexión a Azure PostgreSQL (lee del .env)
├── models/
│   └── silver/
│       ├── sources.yml      # Declaración de todas las tablas Bronze
│       ├── clima/           # Modelos de clima y meteorología
│       ├── espacial/        # Modelos de datos geoespaciales y movilidad
│       ├── istac/           # Modelos de estadísticas ISTAC
│       └── youtube/         # Modelos de NLP / redes sociales
```

---

## Cómo ejecutar

Todos los comandos se ejecutan **dentro de la carpeta `dbt_project/`**:

```bash
cd AI_Dashboard_Core/dbt_project
```

### Ejecutar todos los modelos Silver de una vez

```bash
dbt run --select silver.*
```

### Ejecutar un modelo concreto

```bash
dbt run --select silver_clima_horario_agrocabildo
```

### Ejecutar solo un grupo temático

```bash
# Solo clima
dbt run --select silver.clima.*

# Solo espacial + movilidad
dbt run --select silver.espacial.*

# Solo ISTAC
dbt run --select silver.istac.*

# Solo YouTube / NLP
dbt run --select silver.youtube.*
```

### Verificar la conexión antes de ejecutar

```bash
dbt debug
```

### Compilar sin ejecutar (útil para revisar el SQL generado)

```bash
dbt compile --select silver.*
# El SQL compilado queda en: dbt_project/target/compiled/
```

---

## Modelos disponibles

### `clima/` — Meteorología y clima

| Modelo | Tabla resultante | Fuente Bronze | Descripción |
|---|---|---|---|
| `silver_clima_horario_agrocabildo` | `silver.silver_clima_horario_agrocabildo` | `bronze.clima_horario_agrocabildo` | Lecturas de sensores diezminutales filtradas a **horas en punto**, eliminando códigos de error (-999, -9999) y valores extremos (<-50 o >1500). Columnas: `id_estacion`, `id_sensor`, `timestamp`, `valor_limpio`, `es_validado`, `es_extremo`. |
| `silver_estaciones_agrocabildo` | `silver.silver_estaciones_agrocabildo` | `bronze.estaciones_agrocabildo` | Metadatos limpios de estaciones meteorológicas. Descarta estaciones sin coordenadas. |
| `silver_era5land` | `silver.silver_era5land` | `bronze.era5land_consolidado` | Reanálisis ERA5-Land con conversión de unidades: Kelvin→°C, m→mm precipitación, componentes u/v→velocidad viento (m/s), J/m²→W/m² radiación. |
| `silver_gfs_hist` | `silver.silver_gfs_hist` | `bronze.hist_forecast_gfs_seamless_consolidado` | Histórico de forecast GFS seamless (Open-Meteo) con las mismas conversiones de unidades que ERA5. |

```bash
dbt run --select silver.clima.*
```

---

### `espacial/` — Geodatos y movilidad

| Modelo | Tabla resultante | Fuente Bronze | Descripción |
|---|---|---|---|
| `silver_limites_municipales` | `silver.silver_limites_municipales` | `bronze.limites_municipales` | Geometrías de los 31 municipios de Tenerife. Añade área en km² calculada con PostGIS y centroide (lon/lat) para joins rápidos sin geometría. |
| `silver_zonas_turisticas` | `silver.silver_zonas_turisticas` | `bronze.zonas_turisticas` | Polígonos de zonas turísticas con área calculada. |
| `silver_enp` | `silver.silver_enp` | `bronze.tenerife_espacios_naturales_protegidos` | Espacios Naturales Protegidos (Parque Nacional, Parque Rural, Reserva, Monumento Natural) con área en km². |
| `silver_gtfs_paradas` | `silver.silver_gtfs_paradas` | `bronze.gtfs_paradas` | Paradas de transporte público TITSA/TITF. Descarta paradas sin coordenadas válidas. La asignación a zona turística se hace en Gold con `ST_Within`. |
| `silver_gtfs_rutas` | `silver.silver_gtfs_rutas` | `bronze.gtfs_rutas` | Rutas de transporte público con tipo normalizado (Bus / Tren / Tram). |

> **Requisito**: PostGIS debe estar activado en la base de datos para los modelos
> que usan `ST_Area`, `ST_Centroid` y `ST_X/ST_Y`.

```bash
dbt run --select silver.espacial.*
```

---

### `istac/` — Estadísticas Instituto Canario

Todos los modelos de ISTAC leen de la misma tabla `bronze.istac_municipios` y la
pivotean en distintas granularidades temporales.

| Modelo | Tabla resultante | Granularidad | Variables principales |
|---|---|---|---|
| `silver_istac_estatico` | `silver.silver_istac_estatico` | Sin periodo | `superficie_km2` por municipio |
| `silver_istac_anual` | `silver.silver_istac_anual` | Anual | `poblacion_total`, `poblacion_15_64`, `poblacion_65_mas`, `edad_media`, `saldo_migratorio`, `pob_turistica_equiv` |
| `silver_istac_trimestral` | `silver.silver_istac_trimestral` | Trimestral | `empleo_hosteleria`, `empleo_servicios` |
| `silver_istac_mensual` | `silver.silver_istac_mensual` | Mensual | `pernoctaciones`, `viajeros_entrados`, `plazas_ofertadas`, `alojamientos_abiertos`, `tasa_ocupacion_plazas`, `paro_registrado`, `empresas_ss` |
| `silver_istac_municipios_cifras_tenerife` | `silver.silver_istac_municipios_cifras_tenerife` | Mixta | Vista consolidada con todos los indicadores por municipio |

```bash
dbt run --select silver.istac.*
```

---

### `youtube/` — NLP y redes sociales

| Modelo | Tabla resultante | Fuente Bronze | Descripción |
|---|---|---|---|
| `silver_youtube` | `silver.silver_youtube` | `bronze.youtube_videos` + `bronze.youtube_comments` | Videos con métricas de engagement calculadas (ratio likes+comentarios/visualizaciones) y conteo de comentarios válidos (sin texto vacío). |
| `silver_losviajeros` | `silver.silver_losviajeros` | `bronze.losviajeros_temas` + `bronze.losviajeros_mensajes` | Temas del foro LosViajeros.com con métricas de actividad (mensajes válidos, longitud media, fechas primera/última respuesta). |

```bash
dbt run --select silver.youtube.*
```

> **Tablas de output NLP — NO gestionadas por dbt:**
> Las tablas `silver.sentiment_results` y `silver.aspect_results` son escritas
> directamente por los scripts Python de `analytics/`. Su DDL de creación está en
> `sql/silver_sentiment_results_schema.sql` y `sql/silver_aspect_results_schema.sql`.
> Ejecutar `dbt run` sobre ellas borraría los resultados de inferencia ya calculados.

---

## Tablas Bronze declaradas en `sources.yml`

El fichero `models/silver/sources.yml` declara las siguientes fuentes:

```
bronze.estaciones_agrocabildo
bronze.clima_horario_agrocabildo
bronze.era5land_consolidado
bronze.hist_forecast_gfs_seamless_consolidado
bronze.leadtime_gfs_seamless_consolidado
bronze.limites_municipales
bronze.zonas_turisticas
bronze.tenerife_espacios_naturales_protegidos
bronze.gtfs_paradas
bronze.gtfs_rutas
bronze.youtube_videos
bronze.youtube_comments
bronze.losviajeros_temas
bronze.losviajeros_mensajes
bronze.istac_municipios
```

---

## Datos fuera de dbt (rásters)

Los datos satelitales y el MDT son archivos GeoTIFF almacenados en Azure Blob Storage.
**No son modelos dbt** porque dbt solo gestiona SQL sobre tablas relacionales.

| Dato | Formato | Bronze | Procesamiento Silver/Gold |
|---|---|---|---|
| Sentinel-2 NDVI/NDBI | GeoTIFF (20m, EPSG:32628) | Azure Blob + `data/Satelite_Sentinel2/` (30 composites trimestrales 2019-2026) | Script Python Issue #21 → estadísticas por municipio en `gold` |
| VIIRS luces nocturnas | GeoTIFF (~500m) | Azure Blob + `data/Satelite_VIIRS/` (88 meses 2019-2026) | Script Python Issue #24 → radianza por municipio en `gold` |
| MDT elevación | GeoTIFF | Azure Blob | Script Python → altitud media, pendiente, orientación por municipio en `gold` |

---

## Orden recomendado de ejecución

```bash
# 1. Verificar conexión
dbt debug

# 2. Ejecutar todo Silver (primera vez, puede tardar ~10-15 min por el volumen de clima)
dbt run --select silver.*

# 3. En ejecuciones posteriores, por grupos para mayor control
dbt run --select silver.istac.*
dbt run --select silver.espacial.*
dbt run --select silver.clima.*
dbt run --select silver.youtube.*
```
