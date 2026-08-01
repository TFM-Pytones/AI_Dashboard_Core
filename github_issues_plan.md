# 📋 GitHub Issues — AI Dashboard TFM Tenerife

> **Proyecto**: AI-Dashboard para la Gestión de la Oferta Turística Georreferenciada de Tenerife  
> **Repositorio**: https://github.com/TFM-Pytones/AI_Dashboard_Core  
> **Inicio**: 5 de julio 2026 | **Entrega Final**: 13 de septiembre 2026  
> **Semanas totales**: ~10 semanas

---

## 🗓️ Calendario de Semanas

| Semana | Fechas | Fase |
|--------|--------|------|
| S1 | 5 – 11 julio | Fase 1 — Infraestructura |
| S2 | 12 – 18 julio | Fase 1 — Ingesta inicial |
| S3 | 19 – 25 julio | Fase 1 — Ingesta avanzada |
| S4 | 26 jul – 1 ago | Fase 2 — Limpieza y capa plata |
| S5 | 2 – 8 agosto | Fase 2 — Modelado dbt + Redacción |
| S6 | 9 – 15 agosto | Fase 3 — NLP e IA |
| S7 | 16 – 22 agosto | Fase 3 — Clustering + Satélite |
| S8 | 23 – 29 agosto | Fase 4 — LLM / IA Generativa |
| S9 | 30 ago – 5 sep | Fase 5 — Accesibilidad + Dashboard |
| S10 | 6 – 13 septiembre | Fase 5 — Validación + TFM Final |

---

## 📌 Decisión Metodológica Global: Periodo Temporal del Modelo

> ⚠️ **Esta decisión afecta a múltiples issues. Todos los miembros del equipo deben conocerla antes de comenzar cualquier ingesta histórica.**

### Periodo de análisis: **2019 + 2022 – 2025**

El modelo cubre el periodo **enero 2019 – diciembre 2025**, con las siguientes especificaciones:

| Año | Estado | Incluir en modelo | Razón |
|-----|--------|-------------------|--------|
| 2019 | Pre-COVID — año de referencia (~19M pernoctaciones) | ✅ Sí | Línea base normal |
| 2020 | COVID — colapso total (-75% pernoctaciones) | ❌ **Excluir** | Outlier exógeno |
| 2021 | Restricciones parciales (-45%) | ❌ **Excluir** | Outlier exógeno |
| 2022 | Recuperación fuerte | ✅ Sí | Normalización |
| 2023 | Normalización completa | ✅ Sí | Año representativo |
| 2024 | Post-COVID estabilizado | ✅ Sí | Año representativo |
| 2025 | Tendencia actual | ✅ Sí | Año representativo |
| 2026 (ene–jun) | Año incompleto | ⚠️ Solo descriptivo | No usar en regresión |

**Justificación académica** (para el TFM): *“Se excluyen los años 2020-2021 por constituir un período de disrupción exógena (pandemia COVID-19) que distorsionaría los coeficientes estructurales del modelo espacial MGWR. Las relaciones entre accesibilidad, entorno natural y demanda turística son patrones estructurales que no cambian con shocks temporales externos.”*

### Regla de aplicación por fuente

| Fuente | 2020-2021 | Regla |
|--------|-----------|-------|
| Pernoctaciones ISTAC (variable Y) | Outlier extremo | **Excluir del modelo**, sí descargar |
| NDVI / Sentinel-2 (vegetación) | Estable, no afectado | Incluir todo |
| NDBI (urbanización) | Estable, no afectado | Incluir todo |
| VIIRS luces nocturnas | Caída artificial enorme | **Excluir del modelo**, sí descargar |
| Reseñas / NLP (sentimiento) | Quejas COVID atípicas | Descargar todo, **etiquetar** con `periodo_covid = TRUE` |
| Meteo Agrocabildo / Open-Meteo | Sin efecto COVID | Incluir todo |
| GTFS transporte | Rutas reducidas en 2020 | Usar GTFS actual, no historico |
| 2026 (ene–jun) | Año incompleto | Solo descriptivo / validación out-of-sample |

---

## 🔵 FASE 1 — Aprovisionamiento e Ingesta de Datos (Capa Bronce)

> **Objetivo**: Levantar la infraestructura cloud, orquestar los pipelines ETL y volcar todos los datos externos a la capa Bronce (Azure Blob Storage) en formato particionado. Sin esta fase, ninguna otra puede avanzar.

---

### Issue #1 — Aprovisionamiento de la Base de Datos (Azure Blob Storage + PostgreSQL Flexible)

**Dificultad**: 🔴 Alta | **Importancia/Bloqueo**: 🔴 Alta | **Semana**: S1

#### Descripción
Este issue cubre el aprovisionamiento completo del backend de datos del proyecto sobre Microsoft Azure. Es la tarea más crítica del TFM: sin la infraestructura de almacenamiento operativa, ningún pipeline de ingesta puede ejecutarse.

#### Subtareas
- [ ] Crear un **Azure Resource Group** específico para el TFM (p.ej. `rg-tfm-tenerife`).
- [ ] Aprovisionar una **cuenta de Azure Blob Storage** con un contenedor llamado `bronce-raw`, configurado con acceso privado. Este contenedor recibirá todos los datos crudos particionados por fuente y fecha (e.g., `bronce-raw/agrocabildo/year=2025/month=06/`).
- [ ] Configurar el servidor **Azure Database for PostgreSQL – Flexible Server** (SKU mínimo: `Standard_B2ms`, 8 GB RAM) con:
  - Base de datos principal: `tfm_tenerife`
  - Zona horaria: `Atlantic/Canary`
  - Usuario admin y contraseña almacenados en `.env` y en Azure Key Vault (si se dispone).
- [ ] Habilitar la extensión **PostGIS** en la base de datos: `CREATE EXTENSION IF NOT EXISTS postgis;`
- [ ] Habilitar extensión **pgRouting**: `CREATE EXTENSION IF NOT EXISTS pgrouting;`
- [ ] Crear los esquemas lógicos de la arquitectura medallón:
  - `bronce` (tablas de staging y referencias a Blob)
  - `plata` (datos limpios y transformados)
  - `oro` (indicadores calculados y features de ML)
- [ ] Verificar conectividad desde la máquina virtual y desde el entorno local con `psql`.
- [ ] Documentar las cadenas de conexión en `infra/README_infra.md` (sin credenciales en texto plano).

#### Referencias
- Sección README `2.1 Arquitectura Medallón en Azure`
- Script de referencia: `infra/`

---

### Issue #3 — Despliegue de la Máquina Virtual Azure

**Dificultad**: 🟡 Media | **Importancia/Bloqueo**: 🔴 Alta | **Semana**: S1

#### Descripción
La Máquina Virtual (VM) es el nodo de ejecución central del proyecto: aloja Apache Airflow, ejecuta los DAGs de ingesta programados, los scripts de scraping y eventualmente servirá el dashboard de Streamlit. Debe estar operativa antes de semana 2.

#### Subtareas
- [ ] Crear una VM en Azure (Ubuntu Server 22.04 LTS recomendado), SKU mínimo `Standard_B2s` (2 vCPU, 4 GB RAM).
- [ ] Configurar **NSG (Network Security Group)** para permitir:
  - Puerto 22 (SSH) solo desde IP del equipo.
  - Puerto 8080 (Airflow WebUI) restringido al equipo.
  - Puerto 8501 (Streamlit) si se va a exponer.
- [ ] Instalar dependencias base mediante el script `setup.sh`:
  - Python 3.11+, pip, virtualenv
  - `git`, `curl`, `wget`
  - Dependencias del `requirements.txt`
- [ ] Clonar el repositorio y configurar el `.env` con las variables necesarias (ver `.env.example`).
- [ ] Configurar acceso SSH por clave pública (sin contraseña).
- [ ] Verificar que la VM tiene acceso a Azure Blob Storage y al servidor PostgreSQL (testar con `az storage blob list` y `psql`).
- [ ] Documentar el proceso en `infra/vm_setup.md`.

#### Referencias
- Sección README `2.2 Aprovisionamiento de Máquina Virtual`
- `setup.sh`, `requirements.txt`

---

### Issue #4 — Orquestación Inicial Apache Airflow / dbt

**Dificultad**: 🔴 Alta | **Importancia/Bloqueo**: 🔴 Alta | **Semana**: S1–S2

#### Descripción
Configurar Apache Airflow como orquestador de todos los pipelines ETL del proyecto. Airflow gestionará los DAGs de ingesta (Fase 1), transformación dbt (Fase 2) y modelos de IA (Fase 3). dbt se integrará como operador dentro de Airflow para gestionar las transformaciones de capa plata/oro.

#### Subtareas
- [ ] Instalar Apache Airflow 2.x en la VM con el backend de metadatos PostgreSQL (base de datos `airflow_db` separada en el mismo servidor Flexible).
- [ ] Configurar `airflow.cfg`: 
  - `executor = LocalExecutor` (para entorno monónodo)
  - `dags_folder` apuntando a `dags/`
  - Ajustar `parallelism` y `dag_concurrency` según recursos de VM.
- [ ] Crear un DAG de prueba (`dag_health_check.py`) que ejecute un `BashOperator` verificando conectividad con Blob Storage y PostgreSQL.
- [ ] Instalar dbt-core y el adaptador `dbt-postgres`:  
  `pip install dbt-core dbt-postgres`
- [ ] Configurar `dbt_project/profiles.yml` con la conexión al servidor PostgreSQL Flexible.
- [ ] Crear un operador Airflow personalizado o usar `BashOperator` para ejecutar `dbt run` y `dbt test` desde un DAG.
- [ ] Arrancar los servicios Airflow (`airflow webserver` y `airflow scheduler`) como servicios `systemd` persistentes.
- [ ] Verificar acceso a la WebUI de Airflow en `http://<VM_IP>:8080`.

#### Referencias
- Sección README `3.3 Orquestación ETL`
- `dags/`, `dbt_project/`

---

### Issue #5 — Extracción Microdatos Oficiales (Cabildo / ISTAC)

**Dificultad**: 🟡 Media | **Importancia/Bloqueo**: 🟡 Media | **Semana**: S2

#### Descripción
Descargar y almacenar los microdatos estadísticos oficiales de Tenerife publicados por el Instituto Canario de Estadística (ISTAC) y el Cabildo de Tenerife. Estos datos aportan el contexto demográfico y de oferta alojativa que alimentará los modelos analíticos.

#### Datos a extraer
- **ISTAC API / Descargas**: 
  - Estadísticas de viajeros y pernoctaciones por municipio y tipo de alojamiento.
  - Encuesta de ocupación hotelera (EOH) y de apartamentos turísticos (EOAP).
  - Estadísticas de afluencia por zonas turísticas de Tenerife.
- **Cabildo de Tenerife (datos abiertos)**: 
  - Oferta de establecimientos turísticos (hoteles, hostales, alojamientos rurales) con capacidad y categoría.
  - Datos de actividad económica por municipio.

#### Subtareas
- [ ] Explorar y documentar los endpoints disponibles de la **ISTAC API** (`https://datos.canarias.es/api/estadisticas/`) y descargar los datasets relevantes.
- [ ] Implementar el script `ingestion/microdatos/extract_istac.py` que descargue los datos en formato CSV/JSON y los convierta a Parquet particionado.
- [ ] Subir los ficheros Parquet resultantes a `bronce-raw/microdatos/istac/year=XXXX/`.
- [ ] Implementar `ingestion/microdatos/extract_cabildo.py` para los datos del Cabildo.
- [ ] Crear un DAG en Airflow (`dag_microdatos.py`) que ejecute estas extracciones de forma programada (mensual).
- [ ] Validar que los Parquet contienen los campos esperados con un script de validación en `validation/`.

#### Referencias
- Sección README `2.3 Extracción de Microdatos Tabulares y Espaciales`

---

### Issue #43 — Extracción Microdatos Tabulares Oficiales 2

**Dificultad**: 🟡 Media | **Importancia/Bloqueo**: 🟢 Baja | **Semana**: S2–S3

#### Descripción
Complemento del Issue #5. Cubre la extracción de microdatos tabulares adicionales no incluidos en la primera entrega, especialmente aquellos con formatos no estándar (Excel, ficheros zip, portales WMS/WFS).

#### Datos a extraer
- Datos de alojamiento turístico por municipio en formato Excel del Gobierno de Canarias.
- Tablas de demanda turística por origen geográfico (mercados emisores: UK, Alemania, Península).
- Estadísticas de empleo en el sector turístico por zona.
- Precios medios de alquiler vacacional por municipio (si disponibles en open data).

#### Subtareas
- [ ] Inventariar todas las fuentes tabulares secundarias identificadas durante la Fase 1.
- [ ] Implementar parsers para cada formato (`.xlsx`, `.csv` con codificación especial, `.zip`).
- [ ] Normalizar nombres de columnas y tipos de dato (fechas ISO 8601, códigos municipales INE).
- [ ] Almacenar en `bronce-raw/microdatos/complementarios/`.
- [ ] Actualizar el DAG `dag_microdatos.py` para incluir estas fuentes.

---

### Issue #6 — Estandarización de Coordenadas a EPSG:32628

**Dificultad**: 🟡 Media | **Importancia/Bloqueo**: 🔴 Alta | **Semana**: S2

#### Descripción
Todos los datos geoespaciales del proyecto deben estar en el mismo sistema de coordenadas proyectado para que los análisis espaciales sean correctos. La proyección oficial para Canarias es **EPSG:32628 (WGS 84 / UTM Zone 28N)**. Esta tarea establece la función de transformación estándar que todos los pipelines deben usar.

#### Subtareas
- [ ] Crear el módulo `ingestion/spatial/coordinate_utils.py` con una función `reproject_to_epsg32628(gdf: GeoDataFrame) -> GeoDataFrame` usando `geopandas` y `pyproj`.
- [ ] La función debe:
  - Detectar automáticamente el CRS de entrada.
  - Reproyectar al EPSG:32628 si no lo está.
  - Registrar un warning si el CRS de entrada es desconocido o nulo.
- [ ] Crear un índice espacial GIST en PostgreSQL para todas las tablas geométricas:  
  `CREATE INDEX idx_<tabla>_geom ON <tabla> USING GIST (geom);`
- [ ] Implementar test unitario en `validation/test_coordinate_utils.py` verificando la reproyección con un punto conocido de Tenerife (e.g., Teide: lon=-16.6437, lat=28.2727).
- [ ] Documentar el estándar de CRS en `docs/spatial_standards.md`.

#### Referencias
- Sección README `3.2 Estandarización de Sistemas de Coordenadas`

---

### Issue #7 — Ingesta de Red de Transporte (Ficheros GTFS — TITSA)

**Dificultad**: 🟡 Media | **Importancia/Bloqueo**: 🟡 Media | **Semana**: S2–S3

#### Descripción
Los ficheros GTFS (General Transit Feed Specification) de TITSA (Transportes Interurbanos de Tenerife) y el Metropolitano de Tenerife contienen la topología completa de la red de transporte público: rutas, paradas con coordenadas, horarios y calendarios de servicio. Son esenciales para el análisis de accesibilidad.

#### Datos GTFS a descargar
- **TITSA**: Fichero GTFS estático de TITSA Tenerife (disponible en `https://www.titsa.com/` o via `transitfeeds.com`).
- **Metropolitano de Tenerife**: GTFS del tranvía/metro ligero.
- Ficheros estándar: `agency.txt`, `routes.txt`, `trips.txt`, `stop_times.txt`, `stops.txt`, `calendar.txt`, `calendar_dates.txt`, `shapes.txt`.

#### Subtareas
- [ ] Implementar `ingestion/gtfs/download_gtfs.py` que descargue el fichero `.zip` GTFS de TITSA y lo descomprima localmente.
- [ ] Subir los ficheros `.txt` crudos a `bronce-raw/gtfs/titsa/fecha_descarga=YYYY-MM-DD/`.
- [ ] Crear un DAG en Airflow (`dag_gtfs_ingestion.py`) con trigger semanal para detectar actualizaciones del feed.
- [ ] Verificar integridad del GTFS con la librería `gtfs_kit` o `partridge`.
- [ ] Registrar en los metadatos de Bronce: fecha de descarga, número de rutas, número de paradas.

#### Referencias
- Sección README `2.4 Integración de Movilidad Pública (GTFS)`

---

### Issue #44 — Ingesta Espacial Espacios Naturales Protegidos (IDECanarias)

**Dificultad**: 🟡 Media | **Importancia/Bloqueo**: 🟡 Media | **Semana**: S2–S3

#### Descripción
Los Espacios Naturales Protegidos de Tenerife (Parque Nacional del Teide, Parque Rural Anaga, etc.) son capas espaciales clave para el análisis de capacidad de carga y redistribución turística. Se obtienen del geoportal **IDECanarias** via servicios WFS o descarga de Shapefiles.

#### Datos a extraer (IDECanarias)
- Límites de los **Espacios Naturales Protegidos** de Tenerife (polígonos).
- **Zonas Turísticas** delimitadas por el PGOU/PIOT.
- **Límites Municipales** de Tenerife (shapefile oficial).
- **Red Viaria** principal (opcional, para accesibilidad).

#### Subtareas
- [ ] Explorar el catálogo WFS de IDECanarias (`https://idecanarias.es/resources/es/`) e identificar las capas relevantes.
- [ ] Implementar `ingestion/spatial/extract_idecanarias.py` que descargue las capas via `owslib` (WFS) o requests y las guarde en GeoJSON/Parquet.
- [ ] Reproyectar al EPSG:32628 usando la función del Issue #6.
- [ ] Almacenar en `bronce-raw/spatial/idecanarias/`.
- [ ] Validar geometrías (sin geometrías nulas, sin auto-intersecciones) con `shapely`.

---

### Issue #42 — Ingesta Topográfica (MDT — Modelo Digital del Terreno)

**Dificultad**: 🟡 Media | **Importancia/Bloqueo**: 🟡 Media | **Semana**: S3

#### Descripción
El Modelo Digital del Terreno (MDT) de Tenerife en formato raster `.tif` permite calcular altitud, pendiente (slope) y orientación (aspect) para cada punto de la isla. Estos datos topoclimáticos son críticos para el análisis de distribución de temperaturas y la Calibración Topoclimática de la Fase 5.

#### Datos a extraer
- **MDT de Tenerife** (resolución 5m o 25m): disponible en el Centro Nacional de Información Geográfica (CNIG) o IDECanarias.
- Fichero(s) raster en formato GeoTIFF.

#### Subtareas
- [ ] Descargar el MDT de Tenerife del CNIG (`https://centrodedescargas.cnig.es/`).
- [ ] Almacenar el fichero raster crudo en `bronce-raw/topografia/mdt/`.
- [ ] Implementar `ingestion/spatial/extract_mdt.py` con `rasterio` para verificar el CRS del raster y registrar metadatos (resolución, extent, nodata value).
- [ ] Verificar que el raster cubre todo el territorio de Tenerife.
- [ ] Documentar resolución espacial y fuente en `docs/data_sources.md`.

#### Referencias
- Sección README `3.3 Geoprocesamiento con rasterio`

---

### Issue #8 — Parseo de GTFS a Tablas

**Dificultad**: 🟡 Media | **Importancia/Bloqueo**: 🟡 Media | **Semana**: S3

#### Descripción
Transformar los ficheros GTFS planos (`.txt` en CSV) a tablas estructuradas en la base de datos PostgreSQL (esquema `bronce`). Esto permite consultas SQL eficientes sobre la red de transporte y sienta las bases para el análisis de accesibilidad.

#### Subtareas
- [ ] Implementar `ingestion/gtfs/parse_gtfs_to_db.py` que lea cada fichero GTFS e inserte los datos en las tablas correspondientes del esquema `bronce`:
  - `bronce.gtfs_stops` (paradas con geometría `POINT`)
  - `bronce.gtfs_routes`
  - `bronce.gtfs_trips`
  - `bronce.gtfs_stop_times`
  - `bronce.gtfs_shapes` (geometría `LINESTRING`)
  - `bronce.gtfs_calendar`
- [ ] Para `stops`, generar el campo `geom` como `ST_SetSRID(ST_MakePoint(stop_lon, stop_lat), 4326)` y reproyectar a EPSG:32628.
- [ ] Para `shapes`, agrupar por `shape_id` y generar la `LINESTRING` ordenando por `shape_pt_sequence`.
- [ ] Crear índices GIST sobre las geometrías.
- [ ] Validar número de filas insertadas vs. número de líneas en el CSV original.

---

### Issue #9 — Recopilación Datos Meteo Agrocabildo y Open-Meteo

**Dificultad**: 🟡 Media | **Importancia/Bloqueo**: 🟡 Media | **Semana**: S3

#### Descripción
Ingesta de datos climáticos históricos y en tiempo real desde dos fuentes complementarias: la red de estaciones de **Agrocabildo** (red oficial de Tenerife) y la **Open-Meteo API** (reanálisis ERA5-Land y predicciones). Estos datos alimentarán el modelo de Calibración Topoclimática y la validación cruzada.

> 📌 **Periodo temporal**: Los datos meteorológicos **no se ven afectados por el COVID** (la atmósfera no para). Descargar el **periodo completo 2019 – junio 2026** sin exclusiones.

#### Datos de Agrocabildo
- Temperatura, humedad relativa, precipitación, velocidad del viento, radiación solar.
- Resolución: horaria por estación meteorológica.
- Fuente: `https://www.agrocabildo.org/` (scraping o API si disponible).
- **Histórico a descargar**: enero 2019 – junio 2026.

#### Datos Open-Meteo
- Endpoint: `https://api.open-meteo.com/v1/forecast` y `https://archive-api.open-meteo.com/v1/era5`.
- Variables: `temperature_2m`, `precipitation`, `windspeed_10m`, `relative_humidity_2m`, `shortwave_radiation`.
- Resolución: horaria, interpolada a la ubicación de cada estación Agrocabildo.
- **Histórico ERA5**: enero 2019 – junio 2026 (ERA5 disponible desde 1940).

#### Subtareas
- [ ] Revisar y adaptar el script existente de ingesta de Agrocabildo (del trabajo previo: conversación `be739dd1`).
- [ ] Implementar `ingestion/open_meteo/extract_open_meteo.py` con llamadas a la Archive API de Open-Meteo para los puntos de las estaciones Agrocabildo.
- [ ] **Periodo de descarga**: configurar el rango `start_date=2019-01-01`, `end_date=2026-06-30` en los scripts de ingesta.
- [ ] Guardar resultados en `bronce-raw/meteo/agrocabildo/` y `bronce-raw/meteo/open_meteo/` en formato Parquet particionado por año/mes.
- [ ] Crear DAG `dag_meteo_ingestion.py` con trigger diario.
- [ ] Validar que no hay gaps temporales superiores a 24h en la serie.

#### Referencias
- Conversación previa: `be739dd1-bac7-429c-8078-7ec6026222c3`
- Sección README `2.5 Automatización de Ingesta Ambiental`

---

### Issue #10 — Extracción Satelital (Copernicus / Sentinel) ✅ IMPLEMENTADO

**Dificultad**: 🔴 Alta | **Importancia/Bloqueo**: 🟡 Media | **Semana**: S3

> ✅ **Estado**: Scripts implementados. Pendiente lanzar exports en GEE y descargar resultados.
> 📄 **Decisiones técnicas**: Ver `ingestion/copernicus/DECISIONES_TECNICAS.md`

#### Descripción
Generación de composites satelitales multiespectrales para Tenerife usando **Google Earth Engine (GEE)** como motor de procesamiento. Los composites alimentan el cálculo de NDVI (vegetación), NDBI (urbanización) y luces nocturnas VIIRS en la Fase 3.

Se abandonó el enfoque original de descarga de escenas individuales (una por mes) debido a dos fenómenos climáticos específicos de Tenerife que invalidan el filtro simple de nubosidad `< 20%`:
- **"Panza de burro"**: estratocúmulos persistentes en la vertiente norte (6-8 meses/año en municipios como Anaga, La Orotava, Acentejo). Un filtro `< 20%` eliminaría casi todas las escenas de esas zonas.
- **Calima sahariana**: polvo del Sáhara que pasa el filtro de nubes SCL y sesga los valores NDVI/NDBI, especialmente en verano (Q3).

La solución adoptada es el **composite de mediana trimestral** en GEE, que combina todos los píxeles válidos del trimestre eliminando nubes, sombras y calima.

> 📌 **Periodo temporal**:
> - **Sentinel-2 (NDVI, NDBI)**: **2019-01 → último Q completo disponible** (auto-calculado en el script). La vegetación no se ve afectada por el COVID — incluir todos los años.
> - **VIIRS Night Lights**: **2019-01 → último mes completo disponible** (~2 meses de latencia NASA). Los años 2020-2021 se etiquetan `periodo_covid=1` e `incluir_en_modelo=0` — caída artificial por COVID excluida del modelo MGWR.

#### Estrategia de datos — Sentinel-2 via GEE

**Producto**: `COPERNICUS/S2_SR_HARMONIZED` (Sentinel-2 L2A Surface Reflectance)
**Granularidad**: composite de mediana **trimestral** (Q1=ene-mar, Q2=abr-jun, Q3=jul-sep, Q4=oct-dic)
**Total composites**: 30 (2019 Q1 → 2026 Q2)

**Triple filtrado de calidad por píxel:**
1. **SCL (Scene Classification Layer)**: elimina nubes (media/alta probabilidad), cirrus y sombras de nubes. Los valores SCL excluidos son: `1` (saturado), `3` (sombra nube), `8` (nubes media), `9` (nubes alta), `10` (cirrus).
2. **AOT (Aerosol Optical Thickness)**: filtra calima sahariana. Umbral: `AOT < 0.3` (DN < 300). La banda AOT está disponible como auxiliar en Sentinel-2 L2A.
3. **B02 Azul (490 nm)**: refuerzo de detección de calima. El polvo sahariano eleva la reflectancia azul en superficies oscuras. Umbral: `B02 < 0.18` (DN < 1800).

**Bandas exportadas** (GeoTIFF multiband por composite):
- `NDVI = (B08 - B04) / (B08 + B04)` → capa de vegetación calculada en GEE
- `NDBI = (B11 - B08) / (B11 + B08)` → capa de urbanización calculada en GEE
- `B02_blue` → capa azul de control de calidad visual

**Resolución de exportación**: 20m (vs 10m nativo → equilibrio calidad/tamaño; Tenerife ~2045 km²)
**CRS**: EPSG:32628 (WGS 84 / UTM zone 28N — sistema oficial Canarias)

#### Estrategia de datos — VIIRS Luces Nocturnas

**Producto GEE**: `NOAA/VIIRS/DNB/MONTHLY_V1/VCMSLCFG`, banda `avg_rad` (nW/cm²/sr)
**Producto NASA alternativo**: VNP46A2, tile `h17v05` (cubre Tenerife)
**Granularidad**: composite **mensual** (ya vienen procesados por NASA/NOAA)
**Total archivos**: 90 meses (2019/01 → 2026/06)
**Fuente recomendada**: GEE (más sencillo, sin cuenta NASA)

#### Archivos implementados

| Archivo | Descripción |
|---------|-------------|
| `ingestion/copernicus/download_sentinel2_gee.py` | Pipeline GEE Sentinel-2: exports trimestrales, CLI completo |
| `ingestion/copernicus/download_viirs.py` | Pipeline VIIRS: fuente GEE o NASA LAADS DAAC, upload Azure |
| `ingestion/copernicus/DECISIONES_TECNICAS.md` | Justificación técnica y científica de las decisiones adoptadas |
| `ingestion/copernicus/README.md` | Guía de uso de los scripts |

#### Subtareas

- [x] Analizar fenómenos climáticos específicos de Tenerife (panza de burro + calima) y su impacto en la calidad de datos Sentinel-2.
- [x] Seleccionar estrategia de composite trimestral via GEE como solución.
- [x] Implementar `ingestion/copernicus/download_sentinel2_gee.py` con triple filtrado (SCL + AOT + B02).
- [x] Implementar `ingestion/copernicus/download_viirs.py` con fuentes GEE y NASA LAADS DAAC.
- [x] Actualizar `.env.example` con `GEE_PROJECT_ID` y `EARTHDATA_TOKEN`.
- [ ] Registrar cuenta y proyecto en **Google Earth Engine** (`https://earthengine.google.com/`).
- [ ] Autenticar GEE: `earthengine authenticate` (una vez por máquina).
- [ ] Test con un composite de prueba: `python download_sentinel2_gee.py --export --dry-run`.
- [ ] Lanzar los **30 exports** Sentinel-2 a Google Drive: `python download_sentinel2_gee.py --export`.
- [ ] Monitorizar tasks en GEE (`--status`) y descargar GeoTIFFs de Google Drive.
- [ ] Mover GeoTIFFs a `data/bronce/spatial/satelite/sentinel2/` y ejecutar `--upload-azure`.
- [ ] Lanzar exports VIIRS: `python download_viirs.py --source gee --export`.
- [ ] Descargar GeoTIFFs VIIRS de Drive, mover a `data/bronce/spatial/satelite/viirs/` y ejecutar `--upload-azure`.
- [ ] Verificar cobertura de píxeles válidos por trimestre (% NaN esperado mayor en Q3 norte de Tenerife).
- [ ] Documentar en el TFM la estrategia de composite y el impacto de la panza de burro como limitación metodológica controlada.

#### Almacenamiento Azure Blob

```
bronce-raw/
  satelite/
    sentinel2/
      year=2019/quarter=Q1/tenerife_ndvi_ndbi_2019_Q1.tif
      year=2019/quarter=Q2/tenerife_ndvi_ndbi_2019_Q2.tif
      ...
      year=2026/quarter=Q2/tenerife_ndvi_ndbi_2026_Q2.tif
    viirs/
      year=2019/month=01/tenerife_viirs_2019_01.tif
      ...
      year=2026/month=06/tenerife_viirs_2026_06.tif
```

#### Tamaño estimado en Bronce

| Dato | Archivos | Tamaño estimado |
|------|----------|-----------------|
| Sentinel-2 (NDVI+NDBI+B02) | 30 GeoTIFF | ~6-10 GB |
| VIIRS luces nocturnas | 90 GeoTIFF | ~2.5 GB |
| **Total bronce satélite** | **120 archivos** | **~9-13 GB** |

#### Referencias
- Sección README `4.3 Monitorización Ambiental por Satélite`
- [GEE Sentinel-2 SR Harmonized](https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S2_SR_HARMONIZED)
- [GEE VIIRS Monthly](https://developers.google.com/earth-engine/datasets/catalog/NOAA_VIIRS_DNB_MONTHLY_V1_VCMSLCFG)
- [NASA LAADS VNP46A2](https://ladsweb.modaps.eosdis.nasa.gov/missions-and-measurements/products/VNP46A2/)
- `ingestion/copernicus/DECISIONES_TECNICAS.md`

---


### Issue #12 — Scraping Plataformas de Reservas (TripAdvisor / Booking)

**Dificultad**: 🔴 Alta | **Importancia/Bloqueo**: 🟡 Media | **Semana**: S3

#### Descripción
Extracción automatizada de reseñas de alojamientos turísticos en Tenerife desde plataformas de opinión. Las reseñas son el corpus de texto que alimentará los modelos de Análisis de Sentimiento (Fase 3). Es importante respetar los Terms of Service y usar técnicas de scraping responsable (rate limiting, User-Agent real).

#### Datos a extraer
- **TripAdvisor**: Reseñas de hoteles en Tenerife (título, texto, puntuación, fecha, idioma del reseñador, nombre del establecimiento, municipio).
- **Booking.com**: Comentarios de propiedades con mínimo N reseñas (threshold a definir).
- Campos mínimos por reseña: `platform`, `hotel_name`, `municipality`, `review_text`, `rating`, `review_date`, `language`, `reviewer_origin`, **`periodo_covid BOOLEAN`**.
- **Periodo de extracción histórica**: 2019 – junio 2026 (extraer todo, etiquetar 2020-2021 con `periodo_covid = TRUE` para filtrar en Fase 3).

#### Subtareas
- [ ] Investigar si existe una API oficial o semi-oficial de TripAdvisor/Booking para datos de reseñas (preferible a scraping directo).
- [ ] Implementar `ingestion/scraping/scraper_tripadvisor.py` con `selenium` o `playwright` + rotación de headers.
- [ ] Implementar `ingestion/scraping/scraper_booking.py`.
- [ ] Guardar reseñas crudas en `bronce-raw/reseñas/tripadvisor/` y `bronce-raw/reseñas/booking/` en Parquet, particionado por municipio y mes de extracción.
- [ ] Implementar backoff exponencial y respetar `robots.txt`.
- [ ] Crear DAG `dag_scraping.py` con trigger mensual.

> ⚠️ **Nota legal**: Revisar Terms of Service de cada plataforma. Considerar alternativas como datasets de reseñas públicos de Kaggle o Google Maps API.

---

### Issue #13 — Integración APIs de Google y YouTube

**Dificultad**: 🟡 Media | **Importancia/Bloqueo**: 🟢 Baja | **Semana**: S3

#### Descripción
Extracción de comentarios de YouTube sobre turismo en Tenerife y datos de Google Maps (valoraciones de lugares turísticos). Los datos de YouTube complementan las reseñas de plataformas de alojamiento con opiniones más informales y en vídeo.

#### Datos a extraer
- **YouTube Data API v3**: 
  - Vídeos sobre turismo en Tenerife (búsqueda por keywords: "Tenerife turismo", "Tenerife travel", etc.)
  - Comentarios de esos vídeos.
  - Salida esperada: `youtube_videos.parquet`, `youtube_comments.parquet`.
- **Google Maps / Places API** (opcional): Ratings y número de reseñas de POIs turísticos clave.

#### Subtareas
- [ ] Configurar credenciales de **Google Cloud Project** con YouTube Data API v3 habilitada.
- [ ] Implementar `ingestion/apis/extract_youtube.py`:
  - Búsqueda de vídeos por keywords con filtro de idioma y región.
  - Extracción paginada de comentarios (`commentThreads.list`).
  - Guardar en `bronce-raw/social/youtube/`.
- [ ] Gestionar los límites de cuota de la API (10.000 unidades/día) con lógica de reintentos.
- [ ] Implementar DAG `dag_youtube_ingestion.py` con trigger semanal.

---

### Issue #14 — Extracción de Foros (Los Viajeros y Google Maps)

**Dificultad**: 🟡 Media | **Importancia/Bloqueo**: 🟢 Baja | **Semana**: S3

#### Descripción
Complemento textual al scraping de plataformas hoteleras. Los foros de viajeros (losviajeros.com) contienen opiniones más detalladas y no estructuradas sobre experiencias turísticas en Tenerife.

#### Subtareas
- [ ] Implementar `ingestion/scraping/scraper_losviajeros.py` para extraer hilos del foro sobre Tenerife.
- [ ] Extraer: título del hilo, texto de cada mensaje, fecha, usuario (anonimizado), número de respuestas.
- [ ] Almacenar en `bronce-raw/social/foros/losviajeros/`.
- [ ] Implementar extracción de reseñas de Google Maps para POIs turísticos de Tenerife via Places API.
- [ ] Guardar en `bronce-raw/social/google_maps/`.

---

### Issue #15 — Redacción TFM Fase 1

**Dificultad**: 🟢 Baja | **Importancia/Bloqueo**: 🟢 Baja | **Semana**: S2–S3

#### Descripción
Redacción de los capítulos del TFM correspondientes a la Fase 1: Introducción, Contexto de Negocio, Descripción de la Arquitectura y Fuentes de Datos.

#### Subtareas
- [ ] Redactar **Capítulo 1** — Introducción y Contexto de Negocio:
  - 1.1 Resumen Ejecutivo
  - 1.2 El Problema de Negocio en Tenerife
  - 1.3 Objetivos Generales y Específicos
  - 1.4 Preguntas Estratégicas (caso TUI)
  - 1.5 Justificación del Aporte Diferencial
- [ ] Redactar **Capítulo 2** — Configuración de Infraestructura:
  - Arquitectura Medallón
  - Descripción de fuentes de datos con fichas técnicas
  - Diagrama de arquitectura (Excalidraw o draw.io exportado a PDF)
- [ ] Crear directorio `docs/tfm/` y guardar borradores en Markdown.
- [ ] Reunión de revisión con compañeros al final de S3.

---

## 🟡 FASE 2 — Limpieza, Transformación y Carga a Capa Plata

> **Objetivo**: Tomar los datos crudos de la Capa Bronce, limpiarlos, estructurarlos y subirlos a la Capa Plata (esquema `plata` en PostgreSQL). Cada miembro del equipo es responsable de limpiar y cargar su propia fuente de datos. Se procesan los datos geoespaciales del MDT, se normalizan las fuentes y se indexa la base de datos para análisis eficiente.

---

### Issue #2 — Habilitación y Modelado en PostGIS

**Dificultad**: 🟡 Media | **Importancia/Bloqueo**: 🔴 Alta | **Semana**: S4

#### Descripción
Diseñar y crear el Data Warehouse espacial en PostgreSQL con PostGIS. Define el esquema relacional completo de las capas Plata y Oro: tablas limpias con tipos espaciales, relaciones foreign key y la convención de nomenclatura del proyecto. **Primera tarea de la Fase 2: debe completarse antes que todas las ETLs.**

#### Subtareas
- [ ] Crear el script `sql/01_schema_plata.sql` con la definición DDL de todas las tablas de la capa Plata:
  - `plata.municipios` (límites municipales: `MULTIPOLYGON`)
  - `plata.espacios_naturales` (`MULTIPOLYGON`)
  - `plata.zonas_turisticas` (`MULTIPOLYGON`)
  - `plata.paradas_transporte` (`POINT`)
  - `plata.rutas_transporte` (`MULTILINESTRING`)
  - `plata.estaciones_meteo` (`POINT` — estaciones Agrocabildo con coordenadas)
  - `plata.alojamientos` (datos de oferta con `POINT`)
  - `plata.reseñas` (textos limpios con campos `texto_limpio`, `rating`, `plataforma`, `municipio_cod`, `idioma`, `fecha_reseña`)
  - `plata.meteo_horaria` (series temporales por estación y hora)
  - `plata.mdt_stats` (estadísticas topográficas por hexágono H3: altitud, pendiente, orientación)
  - `plata.h3_grid` (rejilla H3 sobre Tenerife — ver Issue #50)
  - `plata.gtfs_calendario` (servicio de rutas GTFS por día de la semana)
- [ ] Crear el script `sql/02_schema_oro.sql` con las tablas de la Capa Oro:
  - `oro.features_h3`, `oro.sentimiento_reseñas`, `oro.topicos_reseñas`
  - `oro.ndvi_h3`, `oro.ndbi_h3`, `oro.viirs_h3`
  - `oro.clusters_h3`, `oro.brechas_mercado`
  - `oro.isocronas`, `oro.topoclima_h3`
  - `oro.kpis_municipio`, `oro.kpis_h3`
  - `oro.mgwr_coeficientes`, `oro.regression_dataset`
- [ ] Definir la convención de nombres de columnas: snake_case, sin tildes, fechas como `TIMESTAMPTZ`, códigos municipales como `VARCHAR(5)` (INE).
- [ ] Ejecutar los scripts DDL en el servidor PostgreSQL y verificar que los esquemas se crean correctamente.
- [ ] Documentar el modelo de datos en `docs/data_model.md` con diagrama ER (usar dbdiagram.io o draw.io).
- [ ] Compartir con el equipo y verificar que todos tienen acceso de lectura/escritura a los tres esquemas.

#### Referencias
- Sección README `3.1 Diseño del Data Warehouse Espacial`

---

### Issue #45 — Geoprocesamiento MDT: Altitud, Pendiente y Orientación

**Dificultad**: 🟡 Media | **Importancia/Bloqueo**: 🟡 Media | **Semana**: S4

#### Descripción
Procesar el raster MDT descargado en Fase 1 (Issue #42) para extraer las tres variables topográficas clave: **altitud**, **pendiente** (slope en grados) y **orientación** (aspect en grados desde el norte). Se muestrean sobre la rejilla H3 para alimentar la Calibración Topoclimática y el modelo MGWR.

#### Subtareas
- [ ] Instalar dependencias: `pip install rasterio richdem rasterstats numpy`.
- [ ] Implementar `ingestion/spatial/process_mdt.py`:
  - Cargar el raster GeoTIFF del MDT con `rasterio.open()`.
  - Reproyectar a EPSG:32628 si no lo está usando `rasterio.warp`.
  - Calcular el raster de **pendiente**: `richdem.TerrainAttribute(dem, attrib='slope_degrees')`.
  - Calcular el raster de **orientación**: `richdem.TerrainAttribute(dem, attrib='aspect')`.
  - Guardar los tres rasters resultantes en `plata/satelite/mdt/` como GeoTIFF.
- [ ] Muestrear los valores de los tres rasters sobre cada hexágono H3 de `plata.h3_grid` usando `rasterstats.zonal_stats()`:
  - Para cada hexágono: media, min y max de altitud, pendiente y orientación.
- [ ] Almacenar en `plata.mdt_stats`: `h3_index`, `altitud_media`, `altitud_max`, `pendiente_media`, `pendiente_max`, `orientacion_media`.
- [ ] Crear índice BTREE en `h3_index` para joins futuros.
- [ ] Validar: el Teide debe aparecer como el hexágono con mayor `altitud_max` (~3715m).

#### Dependencias
- Requiere Issue #50 (rejilla H3) para el muestreo por hexágono.

---

### Issue #46 — ETL de Datos Climáticos (Agrocabildo + Open-Meteo → Plata)

**Dificultad**: 🟡 Media | **Importancia/Bloqueo**: 🟡 Media | **Semana**: S4

#### Descripción
Limpiar y consolidar en la capa Plata los datos meteorológicos ingeridos en Bronce (Issue #9): estaciones **Agrocabildo** y **Open-Meteo ERA5**. El resultado es `plata.meteo_horaria`: una tabla limpia, sin gaps críticos, con metadatos de estación, lista para la Calibración Topoclimática.

#### Subtareas
- [ ] Implementar `ingestion/etl/etl_meteo.py`:
  - Leer los Parquet de `bronce-raw/meteo/agrocabildo/` y `bronce-raw/meteo/open_meteo/`.
  - **Normalizar nombres de columnas**: unificar a `temp_c`, `humedad_pct`, `precip_mm`, `viento_kmh`, `radiacion_wm2`.
  - **Normalizar timestamps**: convertir a `TIMESTAMPTZ` en zona `Atlantic/Canary`.
  - **Detectar y marcar outliers**: temperatura fuera de [-5°C, 45°C] → campo `es_outlier = TRUE` (no eliminar).
  - **Imputar gaps**: gaps ≤ 3h → interpolación lineal; > 3h → `NULL` con flag `gap_imputado = FALSE`.
  - **Merge de fuentes**: Agrocabildo como fuente primaria; Open-Meteo como validación cruzada cuando no hay dato real.
- [ ] Insertar en `plata.meteo_horaria`: `estacion_id`, `fuente`, `datetime`, `temp_c`, `humedad_pct`, `precip_mm`, `viento_kmh`, `radiacion_wm2`, `es_outlier`, `gap_imputado`.
- [ ] Crear tabla `plata.estaciones_meteo` con la geometría `POINT` de cada estación Agrocabildo.
- [ ] Generar informe de calidad: % de gaps y % de outliers por estación → guardar en `validation/reports/meteo_quality.json`.

---

### Issue #47 — ETL de Redes de Transporte (GTFS → Plata)

**Dificultad**: 🟡 Media | **Importancia/Bloqueo**: 🟡 Media | **Semana**: S4

#### Descripción
Transformar los datos GTFS de TITSA ya parseados en `bronce` (Issue #8) a la capa Plata con geometrías limpias, validadas y en EPSG:32628. Las paradas y rutas deben quedar como entidades geoespaciales consultables para el análisis de accesibilidad.

#### Subtareas
- [ ] Implementar `ingestion/etl/etl_gtfs.py`:
  - **Paradas** → `plata.paradas_transporte`:
    - Filtrar coordenadas fuera del bbox de Tenerife (lat 27.9–28.6, lon -17.0–-16.0).
    - Generar geometría `POINT` en EPSG:32628: `ST_Transform(ST_SetSRID(ST_MakePoint(stop_lon, stop_lat), 4326), 32628)`.
    - Asignar `municipio_cod` via spatial join con `plata.municipios`.
    - Campos: `stop_id`, `stop_name`, `geom`, `municipio_cod`.
  - **Rutas** → `plata.rutas_transporte`:
    - Construir `LINESTRING` por `shape_id` ordenando por `shape_pt_sequence`.
    - Validar geometrías con `ST_IsValid()` y corregir con `ST_MakeValid()`.
    - Campos: `route_id`, `route_short_name`, `route_long_name`, `tipo_transporte`, `geom`.
  - **Calendario** → `plata.gtfs_calendario`:
    - Consolidar `calendar.txt` + `calendar_dates.txt` en una tabla de servicio activo por día.
- [ ] Verificar que el número de paradas resultante coincide (± 2%) con el GTFS original.
- [ ] Visualizar las rutas sobre un mapa de Tenerife para validación visual.

---

### Issue #48 — Preprocesamiento de Texto (Scraping → Plata)

**Dificultad**: 🟡 Media | **Importancia/Bloqueo**: 🟡 Media | **Semana**: S4–S5

#### Descripción
Limpiar y normalizar el corpus de texto extraído en Fase 1 (reseñas TripAdvisor, Booking, YouTube, foros) para prepararlo para los modelos NLP de Fase 3. Un texto sucio degrada la calidad del análisis de sentimiento y el modelado de tópicos.

#### Subtareas
- [ ] Implementar `ingestion/etl/etl_textos.py`:
  - Leer todos los Parquet de `bronce-raw/reseñas/` y `bronce-raw/social/`.
  - **Deduplicación**: eliminar reseñas con mismo texto + fecha + establecimiento.
  - **Filtrado mínimo**: eliminar textos < 15 caracteres o que sean solo emojis/puntuación.
  - **Normalización**:
    - Eliminar HTML tags (`<br>`, `&amp;`) con `BeautifulSoup`.
    - Normalizar espacios y saltos de línea.
    - Convertir a Unicode NFC.
    - ⚠️ NO aplicar stemming ni eliminar stopwords (los transformers lo manejan internamente).
  - **Detección de idioma**: usar `langdetect` para asignar `idioma` (`es`, `en`, `de`, `fr`…). Si confianza < 0.8 → `idioma_incierto = TRUE`.
  - **Asociación geográfica**: vincular cada reseña a `municipio_cod` via lookup del nombre del establecimiento. Si no se puede asociar → `municipio_cod = NULL`.
  - **Etiquetado periodo COVID**: añadir campo `periodo_covid BOOLEAN = TRUE` para todas las reseñas con `fecha_reseña` entre `2020-01-01` y `2021-12-31`. Estos registros se incluyen en Plata pero los modelos NLP de Fase 3 los procesarán por separado para no contaminar el corpus de entrenamiento principal.
- [ ] Insertar en `plata.reseñas`: `reseña_id`, `plataforma`, `establecimiento_nombre`, `municipio_cod`, `texto_limpio`, `rating`, `fecha_reseña`, `idioma`, `idioma_incierto`, **`periodo_covid`**.
- [ ] Generar estadísticas del corpus separadas por periodo: pre-COVID (2019), COVID (2020-2021), post-COVID (2022-2026).

---

### Issue #49 — ETL de Cartografía Base (IDECanarias → Plata)

**Dificultad**: 🟡 Media | **Importancia/Bloqueo**: 🔴 Alta | **Semana**: S4

#### Descripción
Transformar las capas espaciales de IDECanarias (Issue #44) y los microdatos de oferta alojativa (Issue #5) a tablas limpias en la capa Plata. Estas capas son la **base geográfica de referencia** de todos los demás análisis: sin ellas no hay joins espaciales posibles.

#### Subtareas
- [ ] Implementar `ingestion/etl/etl_cartografia.py`:
  - **Límites Municipales** → `plata.municipios`:
    - Reproyectar a EPSG:32628 (función del Issue #6).
    - Validar y reparar geometrías con `make_valid()`.
    - Campos: `municipio_cod` (INE), `municipio_nombre`, `area_km2`, `geom MULTIPOLYGON`.
    - Calcular `area_km2` con `ST_Area(geom) / 1e6`.
  - **Espacios Naturales Protegidos** → `plata.espacios_naturales`:
    - Campos: `enp_id`, `enp_nombre`, `categoria` (Parque Nacional, Parque Rural, Reserva…), `area_km2`, `geom`.
  - **Zonas Turísticas** → `plata.zonas_turisticas`:
    - Campos: `zona_id`, `zona_nombre`, `municipio_cod`, `area_km2`, `geom`.
  - **Oferta Alojativa** → `plata.alojamientos`:
    - Limpiar datos de hoteles, apartamentos y alojamientos rurales de ISTAC + Cabildo.
    - Geocodificar establecimientos sin coordenadas usando el centroide del municipio como aproximación.
    - Campos: `establecimiento_id`, `nombre`, `tipo`, `categoria_estrellas`, `n_plazas`, `municipio_cod`, `geom POINT`.
- [ ] Crear índices GIST en todas las geometrías.
- [ ] Validar: COUNT(*) de municipios debe ser 42. La unión de todos debe cubrir Tenerife sin huecos (`ST_Union`).

#### Dependencias
- Es **prerrequisito** de Issue #50 (H3 Grid necesita `plata.municipios`).

---

### Issue (NUEVO) — ETL Estadísticas Turísticas ISTAC → Plata

**Dificultad**: 🟡 Media | **Importancia/Bloqueo**: 🔴 Alta | **Semana**: S4

#### Descripción
Los Issues #5 y #43 ingieren los microdatos del ISTAC a la Capa Bronce, y el Issue #49 sube la oferta alojativa a Plata. Pero **nadie tiene asignado llevar las series estadísticas de demanda turística** (pernoctaciones, viajeros, tasa de ocupación por municipio y mes) a una tabla de Plata estructurada. Sin esta tabla, el Issue #31 (Dataset de Regresión) no tiene variable dependiente `Y` y la MGWR (#32) no puede ejecutarse. Este ETL es crítico para el núcleo analítico del TFM.

#### Datos a procesar (de Bronce → Plata)
- **Encuesta de Ocupación Hotelera (EOH)**: pernoctaciones y viajeros por municipio, mes y tipo de alojamiento.
- **Encuesta de Ocupación de Apartamentos (EOAP)**: equivalente para apartamentos turísticos.
- **Estadísticas de afluencia por zona turística**: visitantes por zona y temporada.
- **Periodo a descargar**: 2019 – junio 2026 (completo, incluyendo años COVID).
- **Periodo para el modelo de regresión**: **2019 + 2022–2025** (excluir 2020, 2021 y 2026 del campo `incluir_en_modelo`).

> 📌 **Decisión de periodo**: se descargan todos los años (2019–2026) para análisis descriptivo completo, pero se añade el campo `incluir_en_modelo BOOLEAN` que vale `FALSE` para 2020, 2021 y 2026 (año incompleto). El Issue #31 filtrará por este campo al construir el dataset de regresión.

#### Subtareas
- [ ] Implementar `ingestion/etl/etl_estadisticas_istac.py`:
  - Leer los Parquet de `bronce-raw/microdatos/istac/` descargados en Issue #5.
  - **Normalizar códigos municipales**: asegurar que `municipio_cod` coincide con el formato INE de 5 dígitos de `plata.municipios`.
  - **Normalizar fechas**: convertir todos los periodos (trimestres, meses) a una columna `año` INT y `mes` INT.
  - **Limpiar valores**: identificar y excluir registros con código de confidencialidad ISTAC (`.` o `*` en el original).
  - **Etiquetar periodo COVID**: añadir campo `incluir_en_modelo BOOLEAN`:
    - `FALSE` para años 2020 y 2021 (outliers COVID).
    - `FALSE` para año 2026 (año incompleto, solo descriptivo).
    - `TRUE` para 2019 y 2022–2025.
  - **Calcular campos derivados**:
    - `estancia_media = pernoctaciones / viajeros` (si viajeros > 0).
    - `tasa_ocupacion_estimada` (si está disponible en la fuente).
- [ ] Crear e insertar en `plata.estadisticas_turismo`:
  ```sql
  CREATE TABLE plata.estadisticas_turismo (
    id            SERIAL PRIMARY KEY,
    municipio_cod VARCHAR(5) REFERENCES plata.municipios(municipio_cod),
    año           INT,
    mes           INT,   -- NULL si el dato es anual
    tipo_alojamiento VARCHAR(50),  -- 'hotel', 'apartamento', 'rural', 'total'
    viajeros      NUMERIC,
    pernoctaciones NUMERIC,
    estancia_media NUMERIC,
    tasa_ocupacion NUMERIC,   -- % (0-100), puede ser NULL
    fuente        VARCHAR(20) DEFAULT 'ISTAC'
  );
  ```
- [ ] Crear índices BTREE en `municipio_cod`, `año` y `mes`.
- [ ] Validar que el total de pernoctaciones anuales de Tenerife cuadra con las cifras publicadas por el ISTAC en su web.
- [ ] Documentar en `docs/data_sources.md` las variables disponibles, su periodicidad y las limitaciones de confidencialidad.

#### Por qué es crítico
> ⚠️ Sin `plata.estadisticas_turismo`, los siguientes issues **no tienen datos**:
> - **#31** (Dataset de Regresión): no tiene variable `Y` (pernoctaciones por hexágono).
> - **#32** (MGWR): el modelo no puede calibrarse.
> - **#27** (Brechas de Mercado): el PTNA necesita la demanda real como denominador.
> - **KPIs estratégicos**: el Índice de Saturación Turística necesita pernoctaciones.

---

### Issue #50 — Cuadrícula Espacial Base (H3 / Hexágonos sobre Tenerife)

**Dificultad**: 🟡 Media | **Importancia/Bloqueo**: 🔴 Alta | **Semana**: S4

#### Descripción
Generar la rejilla de hexágonos H3 de Uber que cubre todo el territorio de Tenerife. Es la **unidad espacial de agregación universal** del proyecto: todos los análisis de Fase 3 (NDVI, sentimiento, clustering, accesibilidad, MGWR) almacenarán sus resultados por `h3_index`. **Sin esta tabla la Fase 3 no puede comenzar.**

La **resolución 8** genera hexágonos de ~0.74 km², produciendo entre 2.000 y 3.000 hexágonos para Tenerife: granularidad suficiente para análisis zonal manteniendo un volumen computacionalmente manejable.

#### Subtareas
- [ ] Instalar: `pip install h3`.
- [ ] Implementar `ingestion/spatial/create_h3_grid.py`:
  - Cargar el polígono exterior de Tenerife desde `plata.municipios` (unión con `ST_Union`).
  - Exportar a GeoJSON.
  - Generar hexágonos de **resolución 8** con `h3.polyfill_geojson(geojson, resolution=8)`.
  - Convertir cada índice H3 a polígono: `h3.h3_to_geo_boundary(h3_index, geo_json=True)`.
  - Reproyectar de WGS84 a EPSG:32628.
- [ ] Crear tabla `plata.h3_grid`:
  - `h3_index VARCHAR(15) PRIMARY KEY`
  - `resolution INT DEFAULT 8`
  - `geom GEOMETRY(POLYGON, 32628)`
  - `municipio_cod VARCHAR(5)` (municipio con mayor área de solape, via spatial join)
  - `en_tierra BOOLEAN` (TRUE si > 50% del hexágono es tierra firme)
- [ ] Ejecutar spatial join con `plata.municipios` para asignar `municipio_cod`.
- [ ] Marcar `en_tierra = FALSE` para hexágonos mayoritariamente en el mar y excluirlos de análisis.
- [ ] Crear índice GIST en `geom` e índices BTREE en `h3_index` y `municipio_cod`.
- [ ] Validar: visualizar la rejilla sobre mapa base de Tenerife y verificar cobertura completa.
- [ ] Generar variante de **resolución 9** (opcional) para zonas costeras.

#### Dependencias bloqueadas
> ⚠️ Los siguientes issues **no pueden comenzar** hasta que este esté completado:
> #45, #20, #22, #23, #24, #25, #26, #27, #29, #30, #31, #32 y Calibración Topoclimática.

#### Dependencias previas
- Requiere Issue #49 (necesita `plata.municipios` para generar la unión territorial).

---

### Issue #51 — Indexación y Optimización de la Base de Datos

**Dificultad**: 🟡 Media | **Importancia/Bloqueo**: 🟡 Media | **Semana**: S5

#### Descripción
Una vez cargadas todas las tablas de la capa Plata, optimizar la base de datos para que las consultas de Fase 3 (joins espaciales, series temporales, agregaciones por H3) sean eficientes. Sin esta optimización, los joins geoespaciales complejos sobre tablas grandes pueden tardar minutos en lugar de segundos.

#### Subtareas
- [ ] Crear todos los **índices GIST espaciales** pendientes:
  ```sql
  CREATE INDEX idx_municipios_geom ON plata.municipios USING GIST (geom);
  CREATE INDEX idx_paradas_geom ON plata.paradas_transporte USING GIST (geom);
  CREATE INDEX idx_rutas_geom ON plata.rutas_transporte USING GIST (geom);
  CREATE INDEX idx_alojamientos_geom ON plata.alojamientos USING GIST (geom);
  CREATE INDEX idx_h3_grid_geom ON plata.h3_grid USING GIST (geom);
  CREATE INDEX idx_espacios_naturales_geom ON plata.espacios_naturales USING GIST (geom);
  ```
- [ ] Crear **índices BTREE** en columnas de filtro frecuente:
  ```sql
  CREATE INDEX idx_meteo_datetime ON plata.meteo_horaria (datetime);
  CREATE INDEX idx_meteo_estacion ON plata.meteo_horaria (estacion_id);
  CREATE INDEX idx_reseñas_municipio ON plata.reseñas (municipio_cod);
  CREATE INDEX idx_reseñas_fecha ON plata.reseñas (fecha_reseña);
  CREATE INDEX idx_h3_grid_municipio ON plata.h3_grid (municipio_cod);
  CREATE INDEX idx_mdt_h3 ON plata.mdt_stats (h3_index);
  ```
- [ ] Ejecutar `VACUUM ANALYZE` en todas las tablas de `bronce`, `plata` y `oro`.
- [ ] Crear **vistas materializadas** para consultas repetidas del dashboard:
  - `plata.vw_paradas_por_h3`: conteo de paradas GTFS por hexágono.
  - `oro.vw_dashboard_kpis`: KPIs por municipio (refrescar cada 24h).
- [ ] Benchmarking con `EXPLAIN ANALYZE`: ejecutar 5 consultas representativas antes y después, registrar mejora en `docs/db_performance.md`.
- [ ] Documentar todos los índices en `sql/03_indices.sql` para reproducibilidad.

---

## 🔴 FASE 3 — NLP, Inteligencia Artificial y Clustering (Capa Oro)

> **Objetivo**: Aplicar modelos de Machine Learning y Deep Learning sobre los datos de la Capa Plata para generar inteligencia: análisis de sentimiento, tópicos, índices ambientales y clustering espacial. Los resultados van a la Capa Oro.

---

### Issue #16 — Setup Entorno Hugging Face y Modelos

**Dificultad**: 🟡 Media | **Importancia/Bloqueo**: 🔴 Alta | **Semana**: S6

#### Descripción
Configurar el entorno Python en la VM Azure para ejecutar modelos de Hugging Face. Los modelos transformers requieren dependencias específicas (`transformers`, `torch`, `datasets`) y suficiente RAM/GPU para inferencia por lotes sobre el corpus de reseñas.

#### Modelos a configurar
- **Análisis de Sentimiento**: `nlptown/bert-base-multilingual-uncased-sentiment` o `cardiffnlp/twitter-xlm-roberta-base-sentiment`.
- **Extracción de Aspectos**: `pyabsa` (PyABSA — Aspect-Based Sentiment Analysis).
- **Modelado de Tópicos**: `BERTopic` (con embeddings de `sentence-transformers`).

#### Subtareas
- [ ] Instalar dependencias en el entorno virtual de la VM:
  ```
  pip install transformers torch datasets sentence-transformers bertopic pyabsa
  ```
- [ ] Verificar disponibilidad de GPU (si la VM tiene GPU): `torch.cuda.is_available()`. Si no hay GPU, configurar inferencia en CPU con batch_size reducido.
- [ ] Descargar y cachear los modelos en la VM para evitar descargas repetidas: `model.save_pretrained('./models/sentiment/')`.
- [ ] Crear script de prueba `analytics/nlp/test_models.py` que ejecute inferencia en 10 reseñas de muestra y verifique la salida.
- [ ] Documentar los modelos usados y justificación en `docs/models.md`.

---

### Issue #17 — Inferencia de Sentimiento por Lotes

**Dificultad**: 🟡 Media | **Importancia/Bloqueo**: 🟡 Media | **Semana**: S6

#### Descripción
Ejecutar el modelo de análisis de sentimiento multilingüe sobre todo el corpus de reseñas (TripAdvisor, Booking, YouTube, foros). La inferencia debe ser eficiente (por lotes) y almacenar los resultados en la Capa Oro.

#### Subtareas
- [ ] Implementar `analytics/nlp/sentiment_batch.py`:
  - Cargar reseñas desde `plata.reseñas` en batches de 32-64.
  - Aplicar el modelo de sentimiento y obtener: `label` (positivo/negativo/neutro), `score` (confianza).
  - Detectar automáticamente el idioma de cada reseña con `langdetect`.
- [ ] Almacenar resultados en `oro.sentimiento_reseñas`: `reseña_id`, `sentiment_label`, `sentiment_score`, `idioma`, `modelo_version`.
- [ ] Crear DAG `dag_sentiment.py` en Airflow.
- [ ] Generar reporte estadístico: distribución de sentimentos por municipio, por plataforma, por idioma.

---

### Issue #18 — Configuración de Extracción de Aspectos (pyabsa)

**Dificultad**: 🔴 Alta | **Importancia/Bloqueo**: 🟡 Media | **Semana**: S6

#### Descripción
Aplicar Aspect-Based Sentiment Analysis (ABSA) con `pyabsa` para identificar qué aspectos específicos del turismo (limpieza, ubicación, precio, transporte, naturaleza) mencionan los usuarios y con qué sentimiento.

#### Subtareas
- [ ] Configurar `pyabsa` con el checkpoint multilingüe disponible.
- [ ] Definir los aspectos turísticos de interés: `["precio", "limpieza", "ubicación", "transporte", "naturaleza", "gastronomía", "servicio"]`.
- [ ] Implementar `analytics/nlp/aspect_extraction.py` que procese el corpus de reseñas y extraiga tuplas `(aspecto, sentimiento, frase_contexto)`.
- [ ] Almacenar en `oro.aspectos_reseñas`.
- [ ] Generar heatmap de aspectos por municipio (¿qué se critica/valora en cada zona?).

---

### Issue #19 — Modelado de Tópicos (BERTopic)

**Dificultad**: 🔴 Alta | **Importancia/Bloqueo**: 🟡 Media | **Semana**: S6

#### Descripción
Aplicar `BERTopic` para descubrir los temas latentes en el corpus de reseñas turísticas. BERTopic combina embeddings de sentence-transformers con UMAP + HDBSCAN para clustering de textos.

#### Subtareas
- [ ] Implementar `analytics/nlp/topic_modeling.py`:
  - Generar embeddings del corpus con `sentence-transformers` (`paraphrase-multilingual-MiniLM-L12-v2`).
  - Entrenar el modelo BERTopic con `min_topic_size=10`.
  - Obtener los N tópicos principales y sus palabras representativas.
- [ ] Asignar un tópico a cada reseña y almacenar en `oro.topicos_reseñas`.
- [ ] Generar visualizaciones: `topic_model.visualize_topics()`, `topic_model.visualize_barchart()`.
- [ ] Interpretar y etiquetar manualmente los tópicos (p.ej. "Playa y sol", "Naturaleza Teide", "Transporte deficiente").

---

### Issue #20 — Georreferenciación de Tópicos y Sentimientos

**Dificultad**: 🟡 Media | **Importancia/Bloqueo**: 🟡 Media | **Semana**: S7

#### Descripción
Vincular los resultados de NLP (sentimiento, tópicos, aspectos) a la dimensión espacial mediante el municipio del alojamiento reseñado. Genera mapas de calor de sentimiento y distribución de tópicos por territorio.

#### Subtareas
- [ ] Join en PostgreSQL de `oro.sentimiento_reseñas` con `plata.alojamientos` (que tiene municipio + geometría).
- [ ] Agregar sentimiento medio y distribución de tópicos por municipio → `oro.sentimiento_municipio`.
- [ ] Agregar por hexágono H3 (resolución 8) → `oro.sentimiento_h3`.
- [ ] Crear script `analytics/spatial/georeference_nlp.py`.
- [ ] Generar mapas coropléticos con `geopandas` + `matplotlib` para validación visual.

---

### Issue #21 — Preprocesamiento de Imágenes Sentinel

**Dificultad**: 🔴 Alta | **Importancia/Bloqueo**: 🔴 Alta | **Semana**: S6–S7

#### Descripción
Preprocesar las imágenes Sentinel-2 descargadas en Bronce para obtener reflectancias de superficie limpias y recortar al extent de Tenerife. Este paso es obligatorio antes de calcular los índices NDVI y NDBI.

#### Subtareas
- [ ] Implementar `analytics/satellite/preprocess_sentinel.py` con `rasterio`:
  - Cargar las bandas B04 (Rojo), B08 (NIR), B11 (SWIR), B03 (Verde).
  - Recortar al bounding box de Tenerife con una máscara vectorial (`municipios` de la capa Plata).
  - Escalar los valores DN a reflectancias de superficie (dividir por 10000 para L2A).
  - Enmascarar píxeles de nubes usando la banda SCL (Scene Classification Layer).
- [ ] Guardar los rasters preprocesados en `plata/satelite/sentinel2/<fecha>/`.
- [ ] Calcular estadísticas básicas por banda (min, max, media, desviación).

---

### Issue #22 — Cálculo del Índice NDVI (Vegetación)

**Dificultad**: 🟡 Media | **Importancia/Bloqueo**: 🟡 Media | **Semana**: S7

#### Descripción
Calcular el índice NDVI (Normalized Difference Vegetation Index) para monitorizar la cobertura vegetal de Tenerife a lo largo del tiempo. El NDVI es un indicador clave de la presión turística sobre espacios naturales.

**Fórmula**: `NDVI = (NIR - RED) / (NIR + RED)` → `(B08 - B04) / (B08 + B04)`

#### Subtareas
- [ ] Implementar `analytics/satellite/calculate_ndvi.py`.
- [ ] Calcular NDVI para todas las escenas disponibles.
- [ ] Muestrear el NDVI medio por hexágono H3 y por Espacio Natural Protegido.
- [ ] Almacenar en `oro.ndvi_h3`: `h3_index`, `fecha_escena`, `ndvi_medio`, `ndvi_std`.
- [ ] Calcular serie temporal de NDVI para detectar tendencias de deforestación o recuperación.

---

### Issue #23 — Cálculo del Índice NDBI (Urbanización)

**Dificultad**: 🟡 Media | **Importancia/Bloqueo**: 🟡 Media | **Semana**: S7

#### Descripción
Calcular el índice NDBI (Normalized Difference Built-up Index) para cuantificar la densidad de superficie construida/urbanizada en Tenerife, indicador de presión turística e infraestructura alojativa.

**Fórmula**: `NDBI = (SWIR - NIR) / (SWIR + NIR)` → `(B11 - B08) / (B11 + B08)`

#### Subtareas
- [ ] Implementar `analytics/satellite/calculate_ndbi.py`.
- [ ] Muestrear por hexágono H3 → `oro.ndbi_h3`.
- [ ] Comparar NDBI con datos de oferta alojativa para validar correlación.
- [ ] Generar mapa de clasificación: bajo NDBI + alto NDVI = zona natural; alto NDBI = zona urbana/turística.

---

### Issue #24 — Procesamiento de Noches VIIRS (Luces Nocturnas)

**Dificultad**: 🟡 Media | **Importancia/Bloqueo**: 🟡 Media | **Semana**: S7

#### Descripción
Procesar el producto de luces nocturnas **VIIRS VNP46** de NASA para estimar la actividad económica y la intensidad de ocupación turística nocturna en distintas zonas de Tenerife.

> ⚠️ **Decisión de periodo**: Los años 2020 y 2021 muestran una caída artificial de radianza de ~60-70% por el COVID (cierre de hoteles, toque de queda). **Incluir esos años en el modelo de regresión haría que el VIIRS parezca un indicador negativo de turismo.** Solución: etiquetar pero **NO usar en el modelo de regresión** (#31).

#### Subtareas
- [ ] Implementar `analytics/satellite/process_viirs.py` con `rasterio` y `h5py` (formato HDF5 de NASA).
- [ ] Extraer la capa de radianza nocturna `DNB_At_Sensor_Radiance` del composite mensual para **todo el periodo 2019–2025**.
- [ ] Recortar al extent de Tenerife.
- [ ] Muestrear por hexágono H3 → `oro.viirs_h3`: `h3_index`, `año`, `mes`, `radianza_media`, **`incluir_en_modelo BOOLEAN`** (FALSE para 2020 y 2021).
- [ ] Al calcular el VIIRS medio para el dataset de regresión (#31), filtrar con `WHERE incluir_en_modelo = TRUE` (2019 + 2022–2025).
- [ ] Correlacionar con datos de pernoctaciones de ISTAC (mismos años) para validar el proxy de actividad turística.

---

### Issue #25 — Preparación de Datos Geométricos (Features para Clustering)

**Dificultad**: 🟡 Media | **Importancia/Bloqueo**: 🔴 Alta | **Semana**: S7

#### Descripción
Construir la tabla de features geoespaciales consolidadas por hexágono H3 que servirá como input al clustering HDBSCAN. Esta tabla agrega todos los indicadores calculados hasta este punto.

#### Subtareas
- [ ] Crear `analytics/clustering/build_features.py` que realice el join de:
  - `oro.sentimiento_h3` (sentimiento medio por hexágono)
  - `oro.ndvi_h3` (vegetación)
  - `oro.ndbi_h3` (urbanización)
  - `oro.viirs_h3` (actividad nocturna)
  - `plata.mdt_stats` (altitud, pendiente, orientación)
  - `plata.alojamientos` (count y capacidad de alojamientos por hexágono)
  - `plata.paradas_transporte` (count de paradas GTFS por hexágono)
- [ ] Normalizar las features (StandardScaler o MinMaxScaler).
- [ ] Almacenar en `oro.features_h3`: una fila por hexágono con todas las features normalizadas.
- [ ] Generar estadísticas descriptivas y detectar hexágonos con valores nulos (> 50% NaN → excluir).

---

### Issue #26 — Clustering Espacial de Densidad (HDBSCAN)

**Dificultad**: 🔴 Alta | **Importancia/Bloqueo**: 🟡 Media | **Semana**: S7

#### Descripción
Aplicar el algoritmo **HDBSCAN** (Hierarchical Density-Based Spatial Clustering of Applications with Noise) sobre las features geoespaciales para identificar aglomeraciones de actividad turística, zonas saturadas y áreas de bajo aprovechamiento.

#### Subtareas
- [ ] Implementar `analytics/clustering/hdbscan_clustering.py`:
  - Cargar `oro.features_h3`.
  - Aplicar HDBSCAN con `min_cluster_size=5`, `metric='euclidean'` (o `haversine` para coords geográficas).
  - Experimentar con diferentes valores de `min_samples` para ajustar sensibilidad.
- [ ] Almacenar asignaciones de cluster por hexágono en `oro.clusters_h3`: `h3_index`, `cluster_id`, `cluster_prob`.
- [ ] Visualizar clusters en mapa interactivo con `folium` o `kepler.gl`.
- [ ] Interpretar los clusters: ¿cuáles representan zonas saturadas? ¿cuáles, zonas de oportunidad?

---

### Issue #27 — Detección de Brechas de Mercado

**Dificultad**: 🔴 Alta | **Importancia/Bloqueo**: 🟡 Media | **Semana**: S7

#### Descripción
Identificar zonas del interior de Tenerife con alta capacidad turística potencial (buenos indicadores naturales, bajo NDBI, buena accesibilidad) pero baja oferta alojativa actual. Esto constituye el núcleo analítico del caso TUI.

#### Subtareas
- [ ] Definir el índice de **Potencial Turístico No Aprovechado (PTNA)**:
  - `PTNA = (NDVI_norm * peso_naturaleza) + (Accesibilidad_norm * peso_acceso) - (NDBI_norm * peso_urbanizacion) - (Oferta_norm * peso_oferta)`
  - Los pesos se calibran con la MGWR (Issue #32).
- [ ] Implementar `analytics/clustering/market_gap_detection.py`.
- [ ] Generar ranking de hexágonos con mayor PTNA → candidatos a desarrollo turístico sostenible.
- [ ] Almacenar en `oro.brechas_mercado`.
- [ ] Validar resultados cualitativamente con conocimiento del territorio.

---

## 🟠 FASE 4 — Integración de IA Generativa (LLM)

> **Objetivo**: Conectar los resultados analíticos con un modelo de lenguaje grande (LLM) para generar narrativas automáticas, informes ejecutivos e insights en lenguaje natural, o implementar un agente Text-to-SQL.

---

### Issue #34 — Redacción Pasos Fase 2 (y planificación Fase 4)

**Dificultad**: 🟢 Baja | **Importancia/Bloqueo**: 🟢 Baja | **Semana**: S5–S6

#### Descripción
Redacción de la documentación del TFM correspondiente a la Fase 2 (Estructuración y Data Warehouse) y planificación técnica de la Fase 4 (LLM). Incluye la decisión entre Opción 1 (Generative Summarization) y Opción 2 (Text-to-SQL Agent).

#### Subtareas
- [ ] Redactar Capítulo 3 del TFM: Estructuración, Data Warehouse y Topología Geoespacial.
- [ ] Redactar Capítulo 4 del TFM: Analítica Avanzada (resultados preliminares de NLP y satélite).
- [ ] **Decisión de Diseño**: ¿Opción 1 (informes narrativos) u Opción 2 (agente conversacional Text-to-SQL)?
  - Propuesta: Opción 2 es más diferencial y técnicamente avanzada para un TFM de máster.
- [ ] Documentar la decisión en `docs/llm_architecture.md`.

---

### Issue (NUEVO) — Setup LLM: Configuración de Azure OpenAI / Groq / Ollama

**Dificultad**: 🟡 Media | **Importancia/Bloqueo**: 🔴 Alta | **Semana**: S8

#### Descripción
Configurar el acceso al modelo de lenguaje (LLM) que se usará en la Fase 4. El proyecto contempla dos opciones de backend LLM: Azure OpenAI (API comercial) o modelos open source via Groq (cloud) u Ollama (local). Se recomienda Groq por latencia y coste.

#### Subtareas
- [ ] **Opción A (Azure OpenAI)**: Crear un recurso Azure OpenAI en el portal, desplegar el modelo `gpt-4o` o `gpt-4-turbo` y obtener el endpoint y API key.
- [ ] **Opción B (Groq)**: Registrar cuenta en `console.groq.com`, obtener API key, instalar `groq` Python SDK. Modelos disponibles: `llama-3.1-70b-versatile`, `mixtral-8x7b`.
- [ ] **Opción C (Ollama local)**: Instalar Ollama en la VM y descargar `llama3:8b` o `mistral:7b`.
- [ ] Crear `analytics/llm/llm_client.py` con una clase `LLMClient` que abstraiga el backend (configurable via `.env`).
- [ ] Test de conectividad: enviar un prompt de prueba y verificar respuesta.

---

### Issue (NUEVO) — Text-to-SQL Agent (LangChain + PostgreSQL)

**Dificultad**: 🔴 Alta | **Importancia/Bloqueo**: 🟡 Media | **Semana**: S8

#### Descripción
Implementar un agente conversacional que transforme preguntas en lenguaje natural en consultas SQL contra la base de datos PostgreSQL con PostGIS. Permitirá a los usuarios de TUI consultar el dashboard con preguntas como "¿Qué municipios tienen mayor sentimiento negativo sobre transporte?" o "¿Qué zonas del interior tienen potencial turístico no aprovechado?".

#### Subtareas
- [ ] Instalar LangChain: `pip install langchain langchain-community langchain-openai`.
- [ ] Configurar `SQLDatabase` de LangChain apuntando al esquema `oro` y `plata` de PostgreSQL.
- [ ] Implementar `analytics/llm/text_to_sql_agent.py`:
  - Crear el agente con `create_sql_agent` de LangChain.
  - Inyectar el esquema de tablas en el system prompt.
  - Incluir ejemplos few-shot de preguntas → SQL correctas.
- [ ] Crear una interfaz de chat mínima con `gradio` o integrarla directamente en Streamlit.
- [ ] Testear con al menos 10 preguntas de negocio del caso TUI.
- [ ] Documentar limitaciones y casos de error en `docs/llm_agent.md`.

---

### Issue (NUEVO) — Generación de Informes Narrativos Automáticos

**Dificultad**: 🟡 Media | **Importancia/Bloqueo**: 🟢 Baja | **Semana**: S8

#### Descripción
Generar informes ejecutivos en lenguaje natural a partir de los KPIs calculados, usando el LLM como motor de narrativas. Estos informes se integrarán en el dashboard de Streamlit como sección "Informe Automático".

#### Subtareas
- [ ] Implementar `analytics/llm/report_generator.py`:
  - Extraer los KPIs principales de la Capa Oro (top 5 municipios por PTNA, distribución de sentimiento, clusters detectados).
  - Construir un prompt estructurado con los datos en formato tabular.
  - Enviar al LLM y recibir el informe narrativo.
- [ ] Generar informes por municipio y por cluster de actividad turística.
- [ ] Almacenar los informes generados en `oro.informes_llm`.

---

## 🟢 FASE 5 — Topoclima, Accesibilidad y Presentación Final

> **Objetivo**: Completar los análisis de accesibilidad y calibración topoclimática, construir el dashboard final de Streamlit e integrar todos los resultados. Redacción y entrega del TFM.

---

### Issue #28 — Setup del Motor de Rutas (pgRouting / OpenRouteService)

**Dificultad**: 🔴 Alta | **Importancia/Bloqueo**: 🔴 Alta | **Semana**: S9

#### Descripción
Configurar el motor de enrutamiento que calculará isócronas de accesibilidad y rutas óptimas. Se contemplan dos opciones: **pgRouting** (in-database, usa la red GTFS/OSM en PostgreSQL) y **OpenRouteService** (servicio externo via API o instancia propia).

#### Subtareas
- [ ] Verificar que la extensión pgRouting está habilitada en PostgreSQL (`CREATE EXTENSION pgrouting;`).
- [ ] Importar la red de calles de Tenerife desde **OpenStreetMap** con `osm2pgrouting` o `osm2pgsql`.
- [ ] Construir la topología de red: `SELECT pgr_createTopology('ways', 0.00001)`.
- [ ] **Alternativa ORS**: Desplegar una instancia de OpenRouteService en Docker en la VM, con los datos de Tenerife de OSM.
- [ ] Verificar que el motor de rutas responde correctamente calculando una ruta de prueba entre dos puntos conocidos de Tenerife.

#### Referencias
- Sección README `4.5 Modelado de Accesibilidad y Enrutamiento`

---

### Issue #29 — Generación de Isócronas de Accesibilidad

**Dificultad**: 🟡 Media | **Importancia/Bloqueo**: 🟡 Media | **Semana**: S9

#### Descripción
Calcular isócronas (polígonos de alcance temporal) desde los principales atractivos turísticos y paradas de transporte para cuantificar la accesibilidad desde cada zona de Tenerife. Las isócronas se generan para 15, 30 y 60 minutos en coche y/o transporte público.

#### Subtareas
- [ ] Definir los puntos de origen: paradas de transporte TITSA, centros de interés turístico, accesos a Espacios Naturales Protegidos.
- [ ] Implementar `analytics/accessibility/generate_isochrones.py` usando la API de ORS o pgRouting.
- [ ] Generar isócronas para tiempos de 15, 30 y 60 minutos.
- [ ] Almacenar las isócronas como polígonos en `oro.isocronas`: `origen_id`, `tiempo_min`, `modo_transporte`, `geom`.
- [ ] Validar visualmente las isócronas en un mapa con `folium`.

---

### Issue #30 — Integración de Métricas de Accesibilidad

**Dificultad**: 🟡 Media | **Importancia/Bloqueo**: 🟡 Media | **Semana**: S9

#### Descripción
Integrar los datos de isócronas con la tabla de features por hexágono H3 para obtener un índice de accesibilidad cuantitativo por zona. Este índice enriquece el análisis de brechas de mercado.

#### Subtareas
- [ ] Para cada hexágono H3, calcular:
  - `n_paradas_15min`: número de paradas de transporte público a ≤ 15 min.
  - `n_attractions_30min`: número de atractivos turísticos a ≤ 30 min.
  - `tiempo_a_aeropuerto`: tiempo estimado al aeropuerto más cercano (TFN o TFS).
- [ ] Implementar `analytics/accessibility/accessibility_metrics.py` con joins espaciales en PostGIS (`ST_Within`, `ST_Intersects`).
- [ ] Actualizar `oro.features_h3` con las métricas de accesibilidad.
- [ ] Correlacionar accesibilidad con oferta alojativa y PTNA.

---

### Issue #31 — Construcción del Dataset de Regresión

**Dificultad**: 🟡 Media | **Importancia/Bloqueo**: 🔴 Alta | **Semana**: S9

#### Descripción
Preparar el dataset final para la regresión MGWR. La variable dependiente es el nivel de actividad turística (pernoctaciones, VIIRS) por hexágono y las variables independientes son todos los indicadores calculados.

> 📌 **Periodo del modelo**: **2019 + 2022–2025** (6 años de datos limpios). Excluir 2020-2021 (COVID) y 2026 (año incompleto). Justificación en la Decisión Metodológica Global al inicio del documento.

#### Subtareas
- [ ] **Filtrar por periodo**: en todos los joins, aplicar `WHERE incluir_en_modelo = TRUE` sobre las tablas `plata.estadisticas_turismo` y `oro.viirs_h3`.
- [ ] Definir variable dependiente `Y`: **pernoctaciones anuales medias** por hexágono H3 para el periodo 2019 + 2022–2025 (de `plata.estadisticas_turismo`), normalizada por km² del hexágono.
  - Alternativa si faltan datos ISTAC a nivel hexágono: usar `radianza_media` de VIIRS (mismo periodo filtrado) como proxy.
- [ ] Definir variables independientes `X` (todas calculadas como medias del mismo periodo 2019 + 2022–2025):
  - `ndvi_medio` (vegetación — todos los años, COVID incluido, es estable)
  - `ndbi_medio` (urbanización — ídem)
  - `sentimiento_medio` (solo reseñas con `periodo_covid = FALSE`)
  - `altitud_media`, `pendiente_media`, `orientacion_media` (topografía — estática, un solo valor)
  - `n_paradas_15min`, `tiempo_a_aeropuerto` (accesibilidad — dato actual del GTFS)
  - `n_plazas`, `n_establecimientos` (oferta alojativa actual)
  - `zona_climatica` (topoclima — dato estático)
- [ ] Implementar `analytics/regression/build_regression_dataset.py` con el filtro de periodo explícito.
- [ ] Documentar en el script el motivo de exclusión de 2020-2021 con un comentario para el TFM.
- [ ] Exportar a CSV (`data/regression_dataset_2019_2022_2025.csv`) y a tabla `oro.regression_dataset`.
- [ ] Analizar correlaciones y VIF (Variance Inflation Factor) para detectar multicolinealidad.

---

### Issue #32 — Evaluación MGWR (Regresión Geográficamente Ponderada)

**Dificultad**: 🔴 Alta | **Importancia/Bloqueo**: 🟡 Media | **Semana**: S9

#### Descripción
Aplicar **MGWR (Multiscale Geographically Weighted Regression)** para modelar cómo los factores de éxito turístico varían espacialmente en Tenerife. La MGWR permite que cada variable tenga su propio ancho de banda, capturando la heterogeneidad espacial del turismo.

> 📌 **Periodo del modelo**: el dataset de entrada (`oro.regression_dataset`) ya viene filtrado con el periodo **2019 + 2022–2025**. La MGWR modela patrones estructurales espaciales, no series temporales, por lo que el dataset se usará con valores medios por hexágono sobre ese periodo.

#### Subtareas
- [ ] Instalar `mgwr` Python package: `pip install mgwr`.
- [ ] Implementar `analytics/regression/run_mgwr.py`:
  - Cargar `oro.regression_dataset` (ya filtrado por periodo correcto).
  - Verificar que ninguna observación tiene `año` ∈ {2020, 2021, 2026} como fuente de datos.
  - Configurar y ejecutar el modelo MGWR.
  - Obtener coeficientes locales por hexágono y sus significancias.
- [ ] Evaluar el modelo: R² global, AIC, residuos espaciales.
- [ ] Comparar con OLS global para cuantificar la mejora del enfoque espacial.
- [ ] Documentar en el TFM la justificación del periodo elegido (sección de Metodología).
- [ ] Almacenar coeficientes locales en `oro.mgwr_coeficientes`.

---

### Issue #33 — Extracción e Interpretación de Coeficientes Locales MGWR

**Dificultad**: 🟡 Media | **Importancia/Bloqueo**: 🟡 Media | **Semana**: S9

#### Descripción
Interpretar los coeficientes locales de la MGWR para generar recomendaciones estratégicas diferenciadas por zona. Cada coeficiente indica cuánto influye cada factor (accesibilidad, naturaleza, precio) en el éxito turístico de cada hexágono específico.

#### Subtareas
- [ ] Visualizar mapas de coeficientes locales para cada variable independiente.
- [ ] Identificar zonas donde el coeficiente de "naturaleza" (NDVI) es el factor dominante vs. zonas donde lo es "accesibilidad".
- [ ] Generar tabla de recomendaciones por zona:
  - "En el hexágono X, mejorar la accesibilidad en transporte tendría el mayor impacto positivo."
- [ ] Integrar estas recomendaciones como input al LLM para informes narrativos (Issue Informes Narrativos).
- [ ] Documentar resultados en el Capítulo 5 del TFM.

---

### Issue (NUEVO) — Dashboard Streamlit: Desarrollo y Despliegue

**Dificultad**: 🔴 Alta | **Importancia/Bloqueo**: 🔴 Alta | **Semana**: S9–S10

#### Descripción
Desarrollar el dashboard interactivo final en Streamlit que integre todos los resultados del proyecto. El dashboard es el producto final entregable para TUI y debe ser visualmente impactante y navegable.

#### Páginas del dashboard
1. **Overview KPIs**: Métricas globales del turismo en Tenerife (n° establecimientos, pernoctaciones, sentimiento medio).
2. **Mapa de Calor Turístico**: Mapa H3 interactivo con capa de sentimiento, NDVI, NDBI, accesibilidad (toggle por capa).
3. **Análisis NLP**: Distribución de sentimientos por municipio, nube de tópicos, top aspectos.
4. **Brechas de Mercado**: Mapa de hexágonos con mayor PTNA (potencial no aprovechado).
5. **Accesibilidad**: Visualización de isócronas y métricas de conectividad.
6. **Simulador de Flujos**: Algoritmo gravitatorio (punto extra) para modelar redistribución turística.
7. **Asistente IA (opcional)**: Chat interface con el agente Text-to-SQL.

#### Subtareas
- [ ] Crear `frontend/app.py` como punto de entrada principal del dashboard.
- [ ] Implementar navegación con `st.sidebar`.
- [ ] Integrar mapas con `pydeck` o `folium` embebido en Streamlit.
- [ ] Conectar a PostgreSQL con `SQLAlchemy` para consultas en tiempo real.
- [ ] Desplegar en la VM Azure como servicio `systemd` en puerto 8501.
- [ ] Realizar pruebas de carga con al menos 3 usuarios concurrentes.

---

### Issue (NUEVO) — Redacción Final y Entrega del TFM

**Dificultad**: 🟡 Media | **Importancia/Bloqueo**: 🟢 Baja | **Semana**: S10

#### Descripción
Completar la redacción del TFM con todos los capítulos, resultados, conclusiones y referencias. Revisar el documento completo, generar el PDF y preparar la defensa oral.

#### Subtareas
- [ ] Completar Capítulo 5 (Integración LLM) y Capítulo 6 (Productivización).
- [ ] Completar Capítulo 7: Pruebas, Validación, Análisis Territorial y Conclusiones.
- [ ] Revisar ortografía, formato APA de referencias, numeración de figuras y tablas.
- [ ] Generar el PDF final con LaTeX o Word.
- [ ] Preparar presentación de defensa (20 diapositivas máximo).
- [ ] Subir código final al repositorio con tag `v1.0.0` y documentar en `README.md`.

---

## 📊 Resumen de Issues por Fase y Semana

| Issue | Título | Fase | Dificultad | Bloqueo | Semana |
|-------|--------|------|-----------|---------|--------|
| #1 | Aprovisionamiento BD (Blob + PostgreSQL) | 1 | 🔴 Alta | 🔴 Alta | S1 |
| #3 | Despliegue VM Azure | 1 | 🟡 Media | 🔴 Alta | S1 |
| #4 | Orquestación Airflow/dbt | 1 | 🔴 Alta | 🔴 Alta | S1-S2 |
| #5 | Extracción Microdatos ISTAC/Cabildo | 1 | 🟡 Media | 🟡 Media | S2 |
| #43 | Microdatos Tabulares 2 | 1 | 🟡 Media | 🟢 Baja | S2-S3 |
| #6 | Estandarización EPSG:32628 | 1 | 🟡 Media | 🔴 Alta | S2 |
| #7 | Ingesta GTFS TITSA | 1 | 🟡 Media | 🟡 Media | S2-S3 |
| #44 | Ingesta Espacios Naturales IDECanarias | 1 | 🟡 Media | 🟡 Media | S2-S3 |
| #42 | Ingesta Topográfica MDT | 1 | 🟡 Media | 🟡 Media | S3 |
| #8 | Parseo GTFS a Tablas | 1 | 🟡 Media | 🟡 Media | S3 |
| #9 | Datos Meteo Agrocabildo + Open-Meteo | 1 | 🟡 Media | 🟡 Media | S3 |
| #10 | Extracción Satelital Copernicus | 1 | 🔴 Alta | 🟡 Media | S3 |
| #12 | Scraping Plataformas Reservas | 1 | 🔴 Alta | 🟡 Media | S3 |
| #13 | APIs Google y YouTube | 1 | 🟡 Media | 🟢 Baja | S3 |
| #14 | Extracción Foros | 1 | 🟡 Media | 🟢 Baja | S3 |
| #15 | Redacción TFM Fase 1 | 1 | 🟢 Baja | 🟢 Baja | S2-S3 |
| #2 | Modelado PostGIS Capa Plata | 2 | 🟡 Media | 🔴 Alta | S4 |
| NUEVO | Modelos dbt Capa Plata | 2 | 🔴 Alta | 🔴 Alta | S4-S5 |
| NUEVO | Geoprocesamiento MDT (Slope/Aspect) | 2 | 🟡 Media | 🟡 Media | S4-S5 |
| #16 | Setup Hugging Face + Modelos | 3 | 🟡 Media | 🔴 Alta | S6 |
| #17 | Inferencia Sentimiento por Lotes | 3 | 🟡 Media | 🟡 Media | S6 |
| #18 | Extracción Aspectos (pyabsa) | 3 | 🔴 Alta | 🟡 Media | S6 |
| #19 | Modelado Tópicos BERTopic | 3 | 🔴 Alta | 🟡 Media | S6 |
| #20 | Georreferenciación NLP | 3 | 🟡 Media | 🟡 Media | S7 |
| #21 | Preprocesamiento Sentinel | 3 | 🔴 Alta | 🔴 Alta | S6-S7 |
| #22 | Índice NDVI | 3 | 🟡 Media | 🟡 Media | S7 |
| #23 | Índice NDBI | 3 | 🟡 Media | 🟡 Media | S7 |
| #24 | Luces Nocturnas VIIRS | 3 | 🟡 Media | 🟡 Media | S7 |
| #25 | Preparación Features Geométricas | 3 | 🟡 Media | 🔴 Alta | S7 |
| #26 | Clustering HDBSCAN | 3 | 🔴 Alta | 🟡 Media | S7 |
| #27 | Detección Brechas de Mercado | 3 | 🔴 Alta | 🟡 Media | S7 |
| #34 | Redacción Fase 2 + Plan Fase 4 | 4 | 🟢 Baja | 🟢 Baja | S5-S6 |
| NUEVO | Setup LLM (Azure OpenAI / Groq) | 4 | 🟡 Media | 🔴 Alta | S8 |
| NUEVO | Text-to-SQL Agent LangChain | 4 | 🔴 Alta | 🟡 Media | S8 |
| NUEVO | Generación Informes Narrativos | 4 | 🟡 Media | 🟢 Baja | S8 |
| #28 | Setup Motor Rutas (pgRouting/ORS) | 5 | 🔴 Alta | 🔴 Alta | S9 |
| #29 | Isócronas de Accesibilidad | 5 | 🟡 Media | 🟡 Media | S9 |
| #30 | Métricas de Accesibilidad | 5 | 🟡 Media | 🟡 Media | S9 |
| #31 | Dataset de Regresión | 5 | 🟡 Media | 🔴 Alta | S9 |
| #32 | Evaluación MGWR | 5 | 🔴 Alta | 🟡 Media | S9 |
| #33 | Coeficientes Locales MGWR | 5 | 🟡 Media | 🟡 Media | S9 |
| NUEVO | Dashboard Streamlit | 5 | 🔴 Alta | 🔴 Alta | S9-S10 |
| NUEVO | Redacción Final y Entrega TFM | 5 | 🟡 Media | 🟢 Baja | S10 |

---

## ⚙️ TAREAS TRANSVERSALES — Gestión del Equipo e Infraestructura de Proyecto

> **Objetivo**: Garantizar que el equipo pueda trabajar en paralelo sin conflictos, con un entorno reproducible y con validaciones automáticas entre capas. Estas tareas son transversales a todas las fases.

---

### Issue (NUEVO) — Backup Automático de la Base de Datos PostgreSQL

**Dificultad**: 🟢 Baja | **Importancia/Bloqueo**: 🔴 Alta | **Semana**: S1

#### Descripción
En 10 semanas de trabajo se acumulan semanas de limpieza, transformaciones y modelos en las capas Plata y Oro. **Si el servidor PostgreSQL de Azure falla o se corrompe sin backup configurado, el proyecto muere.** Azure Database for PostgreSQL Flexible Server incluye backup automático activable desde el portal en menos de 5 minutos, pero alguien tiene que configurarlo conscientemente desde el inicio del proyecto (S1), no cuando ya hay datos.

#### Subtareas
- [ ] En el portal de Azure, acceder al servidor PostgreSQL Flexible → **Backup and restore** → activar:
  - **Retención de backups**: 7 días mínimo (máximo 35 días disponible en el tier Standard).
  - **Redundancia de backup**: seleccionar **Geo-redundant** para protección ante fallos de la región Azure.
- [ ] Verificar que los backups automáticos se están generando: comprobar en el portal que existe al menos un backup completado tras 24h.
- [ ] Realizar un **test de restore**: crear una base de datos de prueba `tfm_restore_test` restaurando desde el backup más reciente. Verificar que los esquemas y tablas son correctos.
- [ ] Configurar una **alerta de backup fallido** en Azure Monitor:
  - Ir a Azure Monitor → Alerts → crear alerta sobre métrica `backup_storage_used` o evento de tipo `BackupFailed`.
  - Configurar acción: envío de email al grupo del equipo.
- [ ] Documentar el procedimiento de restore en `docs/disaster_recovery.md` para que cualquier miembro del equipo pueda recuperar los datos en caso de emergencia.
- [ ] Establecer una política de **snapshot manual** antes de operaciones de riesgo (migraciones de esquema, `DROP TABLE`, cambios masivos de datos):
  ```sql
  -- Antes de cualquier operación destructiva:
  -- 1. Anotar en el canal del equipo: "Voy a ejecutar X, hay backup del DD/MM"
  -- 2. Verificar el backup más reciente en el portal Azure
  -- 3. Ejecutar la operación
  ```

> 💡 **Coste**: Los backups geo-redundantes de PostgreSQL Flexible tienen un coste de ~$0.10/GB/mes. Para el volumen esperado del proyecto (< 50 GB), el coste total es < $5/mes.

---

### Issue (NUEVO) — Monitorización y Alertas de los DAGs de Airflow

**Dificultad**: 🟢 Baja | **Importancia/Bloqueo**: 🔴 Alta | **Semana**: S2

#### Descripción
Sin alertas configuradas en Airflow, un pipeline de ingesta puede fallar silenciosamente durante días o semanas. En un proyecto con 10+ DAGs ejecutándose en paralelo, lo descubres cuando llegas a la Fase 3 y el dato no está, o está desactualizado. Configurar alertas de fallo por email es trivial en Airflow (< 30 minutos) y evita semanas de re-ingesta.

#### Subtareas
- [ ] Configurar el servidor SMTP en `airflow.cfg` para envío de emails:
  ```ini
  [smtp]
  smtp_host = smtp.gmail.com
  smtp_starttls = True
  smtp_ssl = False
  smtp_user = tfm.pytones@gmail.com
  smtp_password = <app_password>
  smtp_port = 587
  smtp_mail_from = tfm.pytones@gmail.com
  ```
- [ ] Configurar `default_args` en **todos los DAGs** del proyecto con callback de fallo:
  ```python
  from airflow.utils.email import send_email

  def notify_failure(context):
      send_email(
          to=['equipo@tfm-tenerife.com'],
          subject=f"❌ DAG FALLIDO: {context['dag'].dag_id}",
          html_content=f"""
              <b>DAG:</b> {context['dag'].dag_id}<br>
              <b>Task:</b> {context['task_instance'].task_id}<br>
              <b>Fecha:</b> {context['execution_date']}<br>
              <b>Log:</b> {context['task_instance'].log_url}
          """
      )

  default_args = {
      'owner': 'tfm-team',
      'retries': 2,
      'retry_delay': timedelta(minutes=5),
      'on_failure_callback': notify_failure,
      'email_on_failure': True,
      'email': ['equipo@tfm-tenerife.com']
  }
  ```
- [ ] Configurar `retries: 2` y `retry_delay: 5min` en todos los DAGs para errores transitorios de red/API.
- [ ] Crear un DAG especial `dag_health_check.py` con trigger diario que:
  - Verifica conectividad con Azure Blob Storage.
  - Verifica conectividad con PostgreSQL.
  - Verifica que los Parquet más recientes de cada fuente tienen fecha ≤ 48h.
  - Si algo falla, envía alerta de email.
- [ ] Configurar el **SLA de los DAGs críticos** en Airflow: si `dag_meteo_ingestion` no termina en 2h, enviar alerta.
- [ ] Revisar la WebUI de Airflow (`http://<VM_IP>:8080`) al menos una vez al día durante la Fase 1 y 2.

**Dificultad**: 🟢 Baja | **Importancia/Bloqueo**: 🔴 Alta | **Semana**: S1

#### Descripción
Sin una guía de onboarding clara, cada compañero perderá horas configurando su entorno local o la VM. Este issue crea el documento `CONTRIBUTING.md` y un script de setup que permita a cualquier miembro del equipo tener el proyecto funcionando en menos de 30 minutos desde cero.

#### Subtareas
- [ ] Crear `CONTRIBUTING.md` en la raíz del repositorio con:
  - Requisitos previos (Python 3.11+, Git, acceso a Azure, credenciales).
  - Pasos para clonar el repo y configurar el `.env` desde `.env.example`.
  - Cómo crear el entorno virtual: `python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`.
  - Cómo conectarse a la VM Azure por SSH.
  - Cómo acceder a la WebUI de Airflow.
- [ ] Verificar que `setup.sh` funciona en Ubuntu 22.04 limpio (ejecutar en VM nueva de prueba).
- [ ] Documentar las variables de entorno obligatorias en `.env.example` con comentarios explicativos para cada una.
- [ ] Añadir sección de troubleshooting con los errores más comunes (e.g., problemas de SSL con PostgreSQL, cuotas de API).
- [ ] Crear una checklist de "primer día" en la wiki de GitHub.

---

### Issue (NUEVO) — Política Git: Estrategia de Ramas y Code Review

**Dificultad**: 🟢 Baja | **Importancia/Bloqueo**: 🔴 Alta | **Semana**: S1

#### Descripción
Con varios compañeros trabajando en paralelo sobre el mismo repositorio, sin una política de ramas clara se producirán conflictos en `main` y regresiones difíciles de rastrear. Este issue define y documenta la convención Git del equipo.

#### Subtareas
- [ ] Definir la estrategia de ramas:
  - `main`: rama protegida, solo código revisado y funcional.
  - `develop`: rama de integración continua.
  - `feature/<issue-numero>-<descripcion-corta>`: ramas de trabajo individual (e.g., `feature/7-ingesta-gtfs`).
  - `hotfix/<descripcion>`: correcciones urgentes sobre `main`.
- [ ] Configurar las reglas de protección de rama en GitHub:
  - Requerir al menos 1 Pull Request review antes de merge a `develop`.
  - Prohibir push directo a `main`.
- [ ] Definir la convención de commits: `tipo(scope): descripción` (Conventional Commits).
  - Tipos: `feat`, `fix`, `data`, `docs`, `refactor`, `test`, `chore`.
  - Ejemplo: `feat(gtfs): add TITSA stop ingestion pipeline`.
- [ ] Crear la plantilla de Pull Request en `.github/PULL_REQUEST_TEMPLATE.md`.
- [ ] Crear la plantilla de Issue en `.github/ISSUE_TEMPLATE/`.
- [ ] Comunicar y consensuar la política con todos los miembros del equipo en S1.

---

### Issue (NUEVO) — Backfill Histórico de Datos

**Dificultad**: 🟡 Media | **Importancia/Bloqueo**: 🔴 Alta | **Semana**: S2–S3

#### Descripción
Para que los análisis temporales (estacionalidad, tendencias de NDVI, series meteo) sean estadísticamente robustos, se necesitan al menos 2 años de datos históricos. El repositorio ya incluye el script `run_backfill_sequence.sh`, que debe ejecutarse, validarse y documentarse como parte de la ingesta inicial.

#### Subtareas
- [ ] Revisar y actualizar `run_backfill_sequence.sh` para que cubra todas las fuentes de datos con histórico disponible:
  - Meteo Agrocabildo: histórico disponible desde la web.
  - Open-Meteo ERA5: disponible desde 1940, solicitar mínimo 2024–2025.
  - ISTAC: estadísticas anuales y trimestrales históricas.
  - Sentinel-2: imágenes del año anterior al inicio del proyecto.
  - VIIRS Night Lights: composites mensuales históricos.
- [ ] Ejecutar el backfill de forma ordenada por fuente y verificar que los Parquet resultantes se guardan correctamente en `bronce-raw/`.
- [ ] Registrar en un fichero `bronce-raw/backfill_log.json` el rango de fechas cubierto por cada fuente.
- [ ] Validar que no hay solapamiento ni duplicados entre el backfill y la ingesta incremental diaria/semanal.
- [ ] Estimar el volumen de datos generado y verificar que no se superan los límites de la cuenta de Blob Storage.

---

### Issue (NUEVO) — Validación de Calidad de Datos entre Capas (Great Expectations)

**Dificultad**: 🟡 Media | **Importancia/Bloqueo**: 🔴 Alta | **Semana**: S4–S5

#### Descripción
El directorio `validation/` existe en el repositorio pero no hay ningún issue que lo desarrolle. Se necesita un sistema de validación automática que compruebe la calidad de los datos antes de permitir que pasen de Bronce a Plata y de Plata a Oro. Sin esto, los modelos de ML pueden entrenarse con datos corruptos sin que nadie lo detecte.

#### Herramienta recomendada
**Great Expectations** (`great_expectations`): framework de validación declarativa de datos compatible con Pandas y SQL.

#### Subtareas
- [ ] Instalar Great Expectations: `pip install great-expectations`.
- [ ] Inicializar el proyecto GE: `great_expectations init` en el directorio `validation/`.
- [ ] Crear **Expectation Suites** (conjuntos de reglas) para cada fuente de datos clave:
  - `suite_gtfs_stops`: coordenadas en rango válido para Tenerife (lat 27.9–28.6, lon -17.0–-16.0), sin `stop_id` duplicados.
  - `suite_meteo_agrocabildo`: temperatura entre -5°C y 45°C, sin gaps > 48h.
  - `suite_reseñas`: `review_text` no nulo, longitud > 10 caracteres, `rating` entre 1 y 5.
  - `suite_sentinel_ndvi`: valores NDVI entre -1 y 1, cobertura > 80% del territorio.
  - `suite_plata_alojamientos`: sin duplicados por `establishment_id`, geometría dentro de bbox de Tenerife.
- [ ] Integrar las validaciones como paso previo en los DAGs de Airflow (si el checkpoint falla, el DAG se detiene con alerta).
- [ ] Generar el reporte HTML de validación en `validation/reports/` tras cada ejecución.

---

### Issue (NUEVO) — Creación de la Rejilla H3 sobre Tenerife

**Dificultad**: 🟡 Media | **Importancia/Bloqueo**: 🔴 Alta | **Semana**: S4

#### Descripción
**Esta es la tarea más crítica de la transición Bronce→Plata.** Todos los análisis de la Fase 3 (NDVI, sentimiento, clustering HDBSCAN, luces VIIRS, accesibilidad) agregan sus resultados por **hexágono H3** de Uber. Sin la rejilla H3 generada y almacenada en PostgreSQL, ninguno de esos pipelines puede ejecutarse.

La **resolución 8** de H3 genera hexágonos de ~0.74 km² de área media, suficientemente granular para el análisis a escala municipal/zonal de Tenerife, manteniendo un número manejable de celdas (~2.000–3.000 hexágonos para cubrir la isla).

#### Subtareas
- [ ] Instalar la librería H3 de Uber: `pip install h3`.
- [ ] Implementar `ingestion/spatial/create_h3_grid.py`:
  - Cargar el polígono del límite exterior de Tenerife desde `plata.municipios` (unión de todos los municipios).
  - Generar todos los hexágonos H3 de **resolución 8** que intersecten con el polígono de Tenerife usando `h3.polyfill_geojson()`.
  - Opcionalmente generar también resolución 9 (área ~0.1 km²) para análisis más granulares en zonas costeras turísticas.
- [ ] Crear la tabla `plata.h3_grid` con los campos:
  - `h3_index VARCHAR(15) PRIMARY KEY`
  - `resolution INT` (8 o 9)
  - `geom GEOMETRY(POLYGON, 32628)` (polígono del hexágono en EPSG:32628)
  - `municipio_cod VARCHAR` (código INE del municipio dominante, via spatial join)
  - `en_tierra BOOLEAN` (true si el hexágono tiene > 50% de área en tierra firme)
- [ ] Crear índice GIST sobre `geom` y índice BTREE sobre `h3_index`.
- [ ] Ejecutar un spatial join con `plata.municipios` para asignar el municipio correspondiente a cada hexágono.
- [ ] Filtrar y marcar los hexágonos que caen mayoritariamente en el mar (`en_tierra = false`) para excluirlos de los análisis.
- [ ] Validar el resultado: visualizar la rejilla sobre un mapa de Tenerife y verificar que cubre el territorio completo.
- [ ] Añadir este paso como la **primera tarea** del DAG `dag_dbt_plata.py` (debe ejecutarse antes que cualquier agregación por hexágono).

#### Dependencias bloqueadas por esta tarea
> ⚠️ Los siguientes issues **no pueden empezar** hasta que este esté completado:
> #20, #22, #23, #24, #25, #26, #27, #29, #30, #31, #32

---

## ➕ TAREAS ADICIONALES IDENTIFICADAS (por Fase)

> Issues adicionales detectados al revisar el README completo que no estaban cubiertos.

---

### Issue (NUEVO) — Consolidación de KPIs Estratégicos (Capa Oro)

**Dificultad**: 🟡 Media | **Importancia/Bloqueo**: 🔴 Alta | **Semana**: S9

#### Descripción
El README (sección 6.1) menciona explícitamente: *"Consolidación de métricas de negocio para la toma de decisiones traducido del modelo matemático implementado en Python."* Los KPIs son la capa de abstracción final entre los análisis técnicos y las decisiones de negocio de TUI. Sin ellos, el dashboard no tiene qué mostrar más allá de datos crudos.

#### KPIs a definir y calcular
- **Índice de Saturación Turística (IST)** por municipio: `pernoctaciones / capacidad_alojativa`.
- **Índice de Potencial Turístico No Aprovechado (PTNA)** por hexágono H3 (ver Issue #27).
- **Score de Sentimiento Neto (SSN)** por municipio: `(positivas - negativas) / total_reseñas`.
- **Índice de Accesibilidad Compuesta (IAC)** por hexágono: media ponderada de isócronas y paradas.
- **Variación Estacional de Demanda**: ratio pernoctaciones temporada alta vs. baja.
- **Presión sobre Espacios Naturales**: % de hexágonos con NDVI < 0.3 dentro de ENP.

#### Subtareas
- [ ] Crear `analytics/kpis/calculate_kpis.py` que calcule todos los KPIs a partir de las tablas de la Capa Oro.
- [ ] Almacenar resultados en `oro.kpis_municipio` y `oro.kpis_h3`.
- [ ] Definir los umbrales de alerta para cada KPI (e.g., IST > 0.85 = zona saturada, IST < 0.3 = zona infrautilizada).
- [ ] Crear una vista SQL `oro.vw_dashboard_kpis` que consolide todos los KPIs para consumo directo desde el dashboard.
- [ ] Documentar la fórmula y la fuente de datos de cada KPI en `docs/kpis_definition.md`.
- [ ] Crear DAG `dag_kpis.py` en Airflow que recalcule los KPIs al finalizar cada ejecución de dbt.

---

### Issue (NUEVO) — Calibración Topoclimática de Tenerife

**Dificultad**: 🔴 Alta | **Importancia/Bloqueo**: 🟡 Media | **Semana**: S9

#### Descripción
El README (sección 4.6) menciona explícitamente: *"Calibración Topoclimática: Ajuste dinámico térmico basado en gradientes de altitud, vientos alisios (orientación) y sombras proyectadas."* Este análisis diferencia el TFM de cualquier estudio turístico convencional: modela cómo las condiciones climáticas reales varían por zona de Tenerife en función de la topografía, lo que impacta directamente en la experiencia turística.

#### Contexto técnico
Tenerife tiene una variabilidad climática excepcional en poco espacio: desde el árido sur (Playa de las Américas) hasta el húmedo norte (Anaga), con el Teide dominando el centro. Los vientos alisios del norte crean un efecto de sombra orográfica que condiciona el microclima de cada zona. Este análisis cruza:
- **Altitud** (del MDT): gradiente térmico vertical (~6.5°C/1000m).
- **Orientación** (aspect del MDT): norte = húmedo/nublado (barlovento), sur = seco/soleado (sotavento).
- **Datos meteo reales de Agrocabildo**: temperatura y humedad por estación.

#### Subtareas
- [ ] Implementar `analytics/topoclima/topoclimate_calibration.py`:
  - Modelar el gradiente térmico vertical: `T_estimada(h) = T_estacion - (h - h_estacion) * 0.0065`.
  - Crear un campo `zona_climatica` por hexágono: `{norte_humedo, norte_semi, cumbre, sur_seco, sur_costero}` basado en orientación + altitud.
  - Para cada hexágono H3, calcular la temperatura y humedad estimada corregida topoclimáticamente interpolando desde las estaciones Agrocabildo más cercanas.
- [ ] Almacenar en `oro.topoclima_h3`: `h3_index`, `temp_media_estimada`, `humedad_estimada`, `zona_climatica`, `horas_sol_estimadas`.
- [ ] Validar el modelo comparando las estimaciones de hexágonos con estación Agrocabildo propia vs. el valor real medido (error esperado < 1.5°C).
- [ ] Integrar `zona_climatica` como feature adicional en `oro.features_h3` para enriquecer el clustering y la MGWR.
- [ ] Generar mapa de zonificación climática de Tenerife como figura del TFM.

---

### Issue (NUEVO) — Simulador de Redistribución de Flujos Turísticos (Modelo Gravitatorio)

**Dificultad**: 🔴 Alta | **Importancia/Bloqueo**: 🟢 Baja | **Semana**: S9–S10

#### Descripción
El README (sección 6.4) describe: *"Algoritmos gravitatorios para modelar el impacto de trasladar demanda turística a zonas rurales del interior."* Este simulador es el producto más diferencial del proyecto: permite a TUI responder preguntas del tipo *"Si mejoramos el transporte al municipio de Vilaflor, ¿cuánta demanda turística se desviaría desde el sur saturado?"*

#### Modelo Gravitatorio de Wilson
El modelo de gravedad adaptado al turismo estima el flujo turístico entre una zona origen O (aeropuerto / zonas costeras) y una zona destino D (interior) como:

`F(O→D) = k * (Atractivo_D ^ α) / (Distancia(O,D) ^ β)`

Donde:
- `Atractivo_D` = función del PTNA, sentimiento, NDVI y capacidad alojativa de D.
- `Distancia(O,D)` = tiempo de viaje en minutos (de las isócronas del Issue #29).
- `α` y `β` = exponentes a calibrar con datos reales de pernoctaciones.

#### Subtareas
- [ ] Implementar `analytics/simulation/gravity_model.py`:
  - Definir la función de atractivo por hexágono a partir de `oro.kpis_h3`.
  - Calcular la matriz de distancias-tiempo entre todos los pares de hexágonos usando las isócronas.
  - Calibrar los exponentes `α` y `β` minimizando el error con las pernoctaciones reales de ISTAC.
- [ ] Implementar la función de simulación `simulate_redistribution(scenario: dict) -> DataFrame` que reciba un escenario (e.g., `{"mejora_accesibilidad": "vilaflor", "reduccion_tiempo_min": 15}`) y devuelva la redistribución de flujos estimada.
- [ ] Exponer el simulador en el dashboard de Streamlit como un panel interactivo con sliders:
  - "Reducir tiempo de transporte a zona X en N minutos → efecto esperado en pernoctaciones."
  - "Aumentar capacidad alojativa en zona Y en N plazas → efecto en distribución."
- [ ] Validar el modelo en el escenario actual (sin modificaciones) y comparar con la distribución real de pernoctaciones (error < 20%).
- [ ] Documentar la metodología en el Capítulo 6 del TFM.

---

### Issue (NUEVO) — Análisis Territorial Final de Tenerife (Informe de Resultados)

**Dificultad**: 🟡 Media | **Importancia/Bloqueo**: 🟢 Baja | **Semana**: S10

#### Descripción
El README (sección 7.2) incluye: *"Análisis Territorial de Tenerife: Informes de resultados."* Este issue cubre la elaboración del informe analítico territorial que sintetiza todos los hallazgos del proyecto en un documento ejecutivo dirigido a TUI. Es el entregable analítico final, distinto de la memoria académica del TFM.

#### Subtareas
- [ ] Redactar el **Informe Ejecutivo Territorial** (máx. 20 páginas) con las siguientes secciones:
  1. Diagnóstico del turismo actual en Tenerife: distribución de la demanda, zonas saturadas.
  2. Análisis de sentimiento por zona: ¿qué valoran y qué critican los turistas en cada municipio?
  3. Mapa de brechas de mercado: zonas de alto potencial no aprovechado con datos.
  4. Análisis de accesibilidad: barreras de transporte para el turismo interior.
  5. Simulación de escenarios: impacto de 3 intervenciones concretas (p.ej. mejora transporte Anaga, nueva oferta rural Teno, campaña marketing norte).
  6. Recomendaciones estratégicas para TUI basadas en los coeficientes MGWR.
- [ ] Incluir al menos 10 mapas/visualizaciones de alta calidad exportadas del dashboard.
- [ ] Generar el informe automáticamente con el LLM (Issue Informes Narrativos) y revisarlo manualmente.
- [ ] Guardar en `docs/informe_territorial_tenerife.pdf`.

---

### Issue (NUEVO) — Pruebas de Estrés del Dashboard y Validación Final

**Dificultad**: 🟡 Media | **Importancia/Bloqueo**: 🟢 Baja | **Semana**: S10

#### Descripción
El README (sección 7.1) incluye explícitamente: *"Depuración y Pruebas de Estrés: Control de concurrencia y optimización de rendimiento de carga."* Antes de la entrega final, el dashboard debe someterse a pruebas de carga para asegurar que responde con fluidez ante múltiples usuarios simultáneos (simulando una demo ante el tribunal o ante TUI).

#### Subtareas
- [ ] Identificar las consultas SQL más costosas del dashboard con `EXPLAIN ANALYZE` y optimizarlas:
  - Añadir índices faltantes.
  - Materalizar vistas pesadas como `MATERIALIZED VIEW`.
  - Limitar el número de hexágonos devueltos por consulta con paginación espacial.
- [ ] Ejecutar pruebas de carga con **Locust** (`pip install locust`):
  - Simular 10 usuarios concurrentes navegando el dashboard durante 5 minutos.
  - Registrar tiempo de respuesta p50, p95 y p99 para cada página.
  - Objetivo: p95 < 3 segundos para todas las páginas.
- [ ] Verificar que el servicio Airflow y el scheduler siguen operativos bajo carga del dashboard.
- [ ] Comprobar que los endpoints LLM (Text-to-SQL) responden en < 10 segundos.
- [ ] Documentar los resultados de las pruebas en `docs/stress_test_report.md`.
- [ ] Crear un script de smoke test `validation/smoke_test_dashboard.py` que verifique que las páginas principales del dashboard responden con HTTP 200.

---

## 📊 Resumen Completo de Issues (Actualizado)

| Issue | Título | Fase | Dificultad | Bloqueo | Semana |
|-------|--------|------|-----------|---------|--------|
| #1 | Aprovisionamiento BD (Blob + PostgreSQL) | 1 | 🔴 Alta | 🔴 Alta | S1 |
| #3 | Despliegue VM Azure | 1 | 🟡 Media | 🔴 Alta | S1 |
| #4 | Orquestación Airflow/dbt | 1 | 🔴 Alta | 🔴 Alta | S1-S2 |
| NUEVO | Onboarding del Equipo (CONTRIBUTING.md) | 1 | 🟢 Baja | 🔴 Alta | S1 |
| NUEVO | Política Git y Code Review | 1 | 🟢 Baja | 🔴 Alta | S1 |
| #5 | Extracción Microdatos ISTAC/Cabildo | 1 | 🟡 Media | 🟡 Media | S2 |
| #43 | Microdatos Tabulares 2 | 1 | 🟡 Media | 🟢 Baja | S2-S3 |
| #6 | Estandarización EPSG:32628 | 1 | 🟡 Media | 🔴 Alta | S2 |
| #7 | Ingesta GTFS TITSA | 1 | 🟡 Media | 🟡 Media | S2-S3 |
| #44 | Ingesta Espacios Naturales IDECanarias | 1 | 🟡 Media | 🟡 Media | S2-S3 |
| NUEVO | Backfill Histórico de Datos | 1 | 🟡 Media | 🔴 Alta | S2-S3 |
| #42 | Ingesta Topográfica MDT | 1 | 🟡 Media | 🟡 Media | S3 |
| #8 | Parseo GTFS a Tablas | 1 | 🟡 Media | 🟡 Media | S3 |
| #9 | Datos Meteo Agrocabildo + Open-Meteo | 1 | 🟡 Media | 🟡 Media | S3 |
| #10 | Extracción Satelital Copernicus | 1 | 🔴 Alta | 🟡 Media | S3 |
| #12 | Scraping Plataformas Reservas | 1 | 🔴 Alta | 🟡 Media | S3 |
| #13 | APIs Google y YouTube | 1 | 🟡 Media | 🟢 Baja | S3 |
| #14 | Extracción Foros | 1 | 🟡 Media | 🟢 Baja | S3 |
| #15 | Redacción TFM Fase 1 | 1 | 🟢 Baja | 🟢 Baja | S2-S3 |
| #2 | Modelado PostGIS Capa Plata | 2 | 🟡 Media | 🔴 Alta | S4 |
| #45 | Geoprocesamiento MDT (Altitud/Pendiente/Orientación) | 2 | 🟡 Media | 🟡 Media | S4 |
| #46 | ETL Datos Climáticos (Agrocabildo + Open-Meteo) | 2 | 🟡 Media | 🟡 Media | S4 |
| #47 | ETL Redes de Transporte (GTFS) | 2 | 🟡 Media | 🟡 Media | S4 |
| #48 | Preprocesamiento de Texto (Scraping) | 2 | 🟡 Media | 🟡 Media | S4-S5 |
| #49 | ETL Cartografía Base (IDECanarias) | 2 | 🟡 Media | 🔴 Alta | S4 |
| NUEVO | ETL Estadísticas Turísticas ISTAC → Plata | 2 | 🟡 Media | 🔴 Alta | S4 |
| #50 | Cuadrícula Espacial H3 / Hexágonos | 2 | 🟡 Media | 🔴 Alta | S4 |
| #51 | Indexación y Optimización Base de Datos | 2 | 🟡 Media | 🟡 Media | S5 |
| NUEVO | Validación Calidad Datos (Great Expectations) | 2 | 🟡 Media | 🔴 Alta | S4-S5 |
| NUEVO | Backup Automático PostgreSQL | Trans. | 🟢 Baja | 🔴 Alta | S1 |
| NUEVO | Monitorización y Alertas Airflow | Trans. | 🟢 Baja | 🔴 Alta | S2 |
| #16 | Setup Hugging Face + Modelos | 3 | 🟡 Media | 🔴 Alta | S6 |
| #17 | Inferencia Sentimiento por Lotes | 3 | 🟡 Media | 🟡 Media | S6 |
| #18 | Extracción Aspectos (pyabsa) | 3 | 🔴 Alta | 🟡 Media | S6 |
| #19 | Modelado Tópicos BERTopic | 3 | 🔴 Alta | 🟡 Media | S6 |
| #20 | Georreferenciación NLP | 3 | 🟡 Media | 🟡 Media | S7 |
| #21 | Preprocesamiento Sentinel | 3 | 🔴 Alta | 🔴 Alta | S6-S7 |
| #22 | Índice NDVI | 3 | 🟡 Media | 🟡 Media | S7 |
| #23 | Índice NDBI | 3 | 🟡 Media | 🟡 Media | S7 |
| #24 | Luces Nocturnas VIIRS | 3 | 🟡 Media | 🟡 Media | S7 |
| #25 | Preparación Features Geométricas | 3 | 🟡 Media | 🔴 Alta | S7 |
| #26 | Clustering HDBSCAN | 3 | 🔴 Alta | 🟡 Media | S7 |
| #27 | Detección Brechas de Mercado | 3 | 🔴 Alta | 🟡 Media | S7 |
| #34 | Redacción Fase 2 + Plan Fase 4 | 4 | 🟢 Baja | 🟢 Baja | S5-S6 |
| NUEVO | Setup LLM (Azure OpenAI / Groq) | 4 | 🟡 Media | 🔴 Alta | S8 |
| NUEVO | Text-to-SQL Agent LangChain | 4 | 🔴 Alta | 🟡 Media | S8 |
| NUEVO | Generación Informes Narrativos | 4 | 🟡 Media | 🟢 Baja | S8 |
| #28 | Setup Motor Rutas (pgRouting/ORS) | 5 | 🔴 Alta | 🔴 Alta | S9 |
| #29 | Isócronas de Accesibilidad | 5 | 🟡 Media | 🟡 Media | S9 |
| #30 | Métricas de Accesibilidad | 5 | 🟡 Media | 🟡 Media | S9 |
| #31 | Dataset de Regresión | 5 | 🟡 Media | 🔴 Alta | S9 |
| #32 | Evaluación MGWR | 5 | 🔴 Alta | 🟡 Media | S9 |
| #33 | Coeficientes Locales MGWR | 5 | 🟡 Media | 🟡 Media | S9 |
| NUEVO | Consolidación KPIs Estratégicos | 5 | 🟡 Media | 🔴 Alta | S9 |
| NUEVO | Calibración Topoclimática | 5 | 🔴 Alta | 🟡 Media | S9 |
| NUEVO | Dashboard Streamlit | 5 | 🔴 Alta | 🔴 Alta | S9-S10 |
| NUEVO | Simulador de Flujos Gravitatorio | 5 | 🔴 Alta | 🟢 Baja | S9-S10 |
| NUEVO | Análisis Territorial Final (Informe) | 5 | 🟡 Media | 🟢 Baja | S10 |
| NUEVO | Pruebas de Estrés del Dashboard | 5 | 🟡 Media | 🟢 Baja | S10 |
| NUEVO | Redacción Final y Entrega TFM | 5 | 🟡 Media | 🟢 Baja | S10 |

**Total: 58 issues** | 🔴 Alta dificultad: 15 | 🟡 Media: 33 | 🟢 Baja: 10

---

*Documento generado para: TFM AI-Dashboard Tenerife | Repositorio: TFM-Pytones/AI_Dashboard_Core*
