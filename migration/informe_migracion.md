# Informe de Migración: Capas Bronce y Plata a Azure

Este documento resume para el equipo la migración de datos completada desde Neon PostgreSQL hacia la infraestructura de Azure (Blob Storage y base de datos flexible).

---

## 1. Capa Bronce (Datos en Bruto / Raw)

Para optimizar el almacenamiento y reducir costes en la nube, hemos migrado el histórico en bruto (`raw_data`) de Neon a archivos binarios comprimidos (parquet) en **Azure Blob Storage**.

- **Destino**: Contenedor `bronce-raw` de la cuenta de almacenamiento `datalaketfmtenerife`.
- **Formato**: Parquet (compresión Snappy).
- **Proceso**: El script de Python extrae cada tabla desde Neon, la estructura como DataFrame de Pandas, la convierte a Parquet localmente y la sube al contenedor de Azure.
- **Script**: `AI_Dashboard_Core/migration/migrate_raw_to_azure_blob.py`

### Tablas Migradas a Bronce:
| Tabla de Origen | Registros | Archivo Parquet de Destino |
| :--- | :--- | :--- |
| `raw_data.limites_municipales` | 31 | `limites_municipales.parquet` |
| `raw_data.zonas_turisticas` | 163 | `zonas_turisticas.parquet` |
| `raw_data.gtfs_paradas` | 3.893 | `gtfs_paradas.parquet` |
| `raw_data.gtfs_rutas` | 867 | `gtfs_rutas.parquet` |
| `raw_data.youtube_videos` | 41 | `youtube_videos.parquet` |
| `raw_data.youtube_comments` | 3.100 | `youtube_comments.parquet` |
| `raw_data.estaciones_agrocabildo` | 67 | `estaciones_agrocabildo.parquet` |
| `raw_data.clima_horario_agrocabildo` | 1.212.197 | `clima_horario_agrocabildo.parquet` |

---

## 2. Capa Plata (Datos Procesados / Estandarizados)

El esquema procesado (`processed_data`) de Neon se ha migrado a la base de datos PostgreSQL de Azure en el esquema `silver` para servir como base para el modelado y cálculo de indicadores.

- **Destino**: Esquema `silver` en el servidor flexible PostgreSQL de Azure.
- **Características**:
  - Extensión espacial **PostGIS** habilitada.
  - Recreación de los **índices espaciales GIST** para todas las columnas de geometría (`geometry`).
  - Optimización en la inserción de la tabla de horarios (`gtfs_horarios`) mediante streaming por lotes y el protocolo nativo `COPY` de PostgreSQL (insertando 2.08 millones de filas en 68 segundos).
- **Script**: `AI_Dashboard_Core/migration/migrate_processed_to_azure_silver.py`

### Tablas Migradas a Plata (`silver`):
* `silver.limites_municipales` (31 filas - Espacial)
* `silver.zonas_turisticas` (163 filas - Espacial)
* `silver.gtfs_paradas` (3.893 filas - Espacial)
* `silver.gtfs_rutas` (867 filas - Espacial)
* `silver.gtfs_calendario` (3 filas)
* `silver.gtfs_calendario_excepciones` (28.081 filas)
* `silver.gtfs_rutas_atributos` (180 filas)
* `silver.gtfs_viajes` (74.567 filas)
* `silver.sentiment_results` (3.071 filas)
* `silver.gtfs_horarios` (2.082.154 filas)

---

## Exclusiones de la Migración
- **AEMET**: La tabla `clima_horario_aemet` ha sido excluida de la migración. Para los datos climatológicos se usarán exclusivamente los registros de **Agrocabildo** (almacenados en la capa bronce).
