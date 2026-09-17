# dbt_project — Transformaciones Silver y Gold (Medallion Pipeline)

Proyecto **dbt** del Trabajo Fin de Máster *AI Dashboard Core — Tenerife Tourism*. Gestiona el ciclo completo de transformación y enriquecimiento analítico del Data Lakehouse en **Azure PostgreSQL**: desde los datos crudos (**Bronze → Silver**) hasta las tablas maestras multidimensionales (**Silver → Gold**).

---

## 1. Requisitos previos y configuración

### Instalación
El proyecto requiere `dbt-core` con el adaptador de PostgreSQL:

```bash
pip install dbt-postgres
```

### Variables de conexión (.env)
Las credenciales de acceso se gestionan a través del fichero `.env` en la raíz del repositorio. El archivo `profiles.yml` está configurado para leerlas automáticamente mediante `env_var()`:

| Variable | Descripción |
|---|---|
| `AZURE_DB_HOST` | Host del servidor Azure Database for PostgreSQL Flexible |
| `AZURE_DB_PORT` | Puerto de conexión (por defecto `5432`) |
| `AZURE_DB_USER` | Usuario administrador de la base de datos |
| `AZURE_DB_PASSWORD` | Contraseña |
| `AZURE_DB_NAME` | Nombre de la base de datos analítica |

> **Nota:** No es necesario modificar `profiles.yml`. Para verificar la conectividad con la base de datos ejecuta `dbt debug` (o `python run_dbt.py debug`).

---

## 2. Estructura del proyecto dbt

```
dbt_project/
├── dbt_project.yml              # Configuración global del proyecto y esquemas
├── profiles.yml                 # Perfil de conexión a Azure PostgreSQL (vía .env)
└── models/
    ├── silver/                  # CAPA SILVER: Limpieza, tipado y reproyección EPSG:32628
    │   ├── sources.yml          # Declaración de todas las fuentes Bronze (raw)
    │   ├── alojamiento/         # Registros oficiales de turismo georreferenciados
    │   ├── booking/             # Establecimientos y reseñas de Booking.com
    │   ├── tripadvisor/         # Ubicaciones y reseñas de TripAdvisor
    │   ├── clima/               # Lecturas horarias y metadatos de estaciones Agrocabildo
    │   ├── espacial/            # Malla H3, límites municipales, ENP, zonas turísticas y POIs
    │   ├── istac/               # Microdatos ISTAC (demografía, empleo, turismo)
    │   ├── movilidad/           # Pasajeros AENA y red de transporte público GTFS (TITSA)
    │   ├── losviajeros/         # Hilos y mensajes depurados del foro LosViajeros.com
    │   └── youtube/             # Vídeos y comentarios de YouTube
    └── gold/                    # CAPA GOLD: Modelos analíticos maestros y KPIs
        ├── sources.yml          # Fuentes externas Gold (salidas de notebooks NLP)
        ├── gold_h3_master.sql               # Tabla maestra territorial H3 (60+ indicadores)
        ├── gold_sentimiento_h3.sql          # Sentimiento y quejas agregadas por hexágono
        ├── gold_municipio_master.sql        # Tabla maestra municipal 31 mun (con PostGIS)
        ├── gold_municipio_anual.sql         # Serie temporal anual con variaciones YoY
        ├── gold_municipio_mensual.sql       # Serie continua 56 meses para estacionalidad
        ├── gold_municipio_empleo.sql        # Afiliación trimestral (asalariados vs autónomos)
        ├── gold_turismo_hotelero_mensual.sql# Encuesta hotelera EOH en polos turísticos
        ├── gold_turismo_hotelero_anual.sql  # Población Turística Equivalente (PTE ISTAC)
        └── gold_aena_pasajeros.sql          # Tráfico mensual de pasajeros en TFS y TFN
```

---

## 3. Cómo ejecutar

Puedes ejecutar dbt de dos formas:

### Opción A (Recomendada en Windows — Script raíz)
Desde la carpeta raíz del proyecto, sin necesidad de cambiar de directorio ni activar entornos manualmente:

```bash
# Verificar conexión a Azure PostgreSQL
python run_dbt.py debug

# Ejecutar todos los modelos Gold
python run_dbt.py run --select gold.*

# Ejecutar todos los modelos Silver
python run_dbt.py run --select silver.*

# Ejecutar un modelo concreto
python run_dbt.py run --select gold_municipio_master

# Pasar los tests de calidad de datos
python run_dbt.py test
```

### Opción B (Estándar dbt — Dentro de `dbt_project/`)
Entrando en el directorio del proyecto dbt:

```bash
cd dbt_project

# Verificar conexión
dbt debug

# Ejecutar por capas
dbt run --select silver.*
dbt run --select gold.*

# Ejecutar por dominios o tags temáticos
dbt run --select tag:gold
dbt run --select tag:municipio
dbt run --select tag:clima
dbt run --select tag:espacial

# Validar aserciones y calidad
dbt test
```

---

## 4. Catálogo de modelos Gold (Capa Analítica de Explotación)

La capa Gold implementa una **arquitectura analítica en tres niveles territoriales/temporales** diseñada para alimentar el dashboard interactivo y los modelos de machine learning:

| Modelo Gold | Nivel Territorial | Granularidad / Filas | Descripción y Variables Clave |
|---|---|---|---|
| **`gold_h3_master`** | Microespacial | 2.579 hexágonos H3 (Res 8) | **Columna vertebral del TFM.** Cruza más de 60 indicadores por celda: oferta oficial (hoteles, VV), plataformas (Booking, TripAdvisor), POIs, paradas bus GTFS, relieve MDT (altitud, pendiente, hillshade), satélite Sentinel-2 (NDVI, NDBI) y VIIRS (2022-2026), clima Agrocabildo IDW con gradiente térmico y **horas de sol reales OMM ($\ge 120\text{ W/m}^2$)**, ENP y distancia euclidiana a la costa. |
| **`gold_sentimiento_h3`** | Microespacial | Hexágonos con reviews | Sentimiento medio ponderado (1-5) y queja principal modal a partir de más de 55.000 reseñas geolocalizadas de Booking y TripAdvisor. |
| **`gold_municipio_master`** | Mesomunicipal | 31 municipios (0% nulos) | **Tabla maestra municipal con MultiPolygon PostGIS (SRID 4326).** Foto estructural de oferta, empleo CNAE 2026, renta, demografía, ratios de sobrecarga (`plazas_por_1000_hab`) y métricas de evolución histórica continua 2022 vs 2026. |
| **`gold_municipio_anual`** | Mesomunicipal | 155 filas (31 mun × 5 años) | Series históricas anuales con variaciones interanuales (`LAG` YoY) de desempleo, afiliación y plazas/ingresos de vivienda vacacional. |
| **`gold_municipio_mensual`** | Mesomunicipal | 1.736 filas (31 mun × 56 meses) | Serie continua mes a mes para análisis de estacionalidad multivariante y variación YoY mensual `LAG(..., 12)`. |
| **`gold_municipio_empleo`** | Mesomunicipal | 558 filas (31 mun × 18 trimestres) | Radiografía laboral continua trimestral (2022-2026): régimen general (asalariados) vs. cuenta propia (autónomos) y ratios de resiliencia empresarial. |
| **`gold_turismo_hotelero_mensual`** | Polos Turísticos | 330 filas (6 polos × 55 meses) | Flujos hoteleros tradicionales de la Encuesta de Ocupación Hotelera (EOH): viajeros, pernoctaciones, plazas, tasa de ocupación y estancia media. |
| **`gold_turismo_hotelero_anual`** | Polos Turísticos | 24 filas (6 polos × 4 años) | **Población Turística Equivalente (PTE)** del ISTAC y ratio de sobrecarga demográfica flotante sobre residentes censados. |
| **`gold_aena_pasajeros`** | Macroinsular | 110 filas mensuales | Tráfico aéreo mensual y operaciones en TFS (Sur, internacional) y TFN (Norte, nacional/interinsular) para medir la estacionalidad de llegada de demanda. |

---

## 5. Catálogo de modelos Silver (Limpieza y Estandarización)

La capa Silver toma las tablas crudas de la capa `bronze.*`, descarta registros corruptos, estandariza tipados y proyecta todas las capas vectoriales al sistema oficial de Canarias (**EPSG:32628**):

### `alojamiento/` & Plataformas OTAs
* `silver_alojamientos_oficiales`: Registros oficiales de turismo (hoteles, extrahoteleros, viviendas vacacionales) georreferenciados con PostGIS.
* `silver_booking_establishments`: Establecimientos de Booking.com con coordenadas validadas y tipología.
* `silver_booking_reviews`: Reseñas limpias con puntuación normalizada y fecha estructurada.
* `silver_tripadvisor_ubicaciones`: Establecimientos turísticos de TripAdvisor georreferenciados.
* `silver_tripadvisor_resenas`: Opiniones depuradas de TripAdvisor con ratings de viajeros.

### `espacial/` & Geodatos
* `silver_h3_grid`: Malla poligonal hexagonal Uber H3 (Res 8). Filtra espacialmente la capa `bronze_h3_grid` (2.746 hexágonos con buffer costero de 1,1 km) descartando 163 celdas oceánicas de buffer y 4 celdas residuales marinas sin MDT/NDVI, consolidando exactamente **2.579 celdas terrestres y litorales** 100% completas con centroides canónicos, relieve MDT (altitud, pendiente) y ENP.
* `silver_limites_municipales`: Polígonos de los **31 municipios oficiales de Tenerife** con área calculada y centroide.
* `silver_zonas_turisticas`: Delimitaciones de zonas turísticas oficiales de IDECanarias.
* `silver_enp`: Espacios Naturales Protegidos clasificados con cálculo de superficie.
* `silver_osm_pois` y `silver_puntos_interes_unificados`: Puntos de interés categorizados (restauración, ocio, cultura, naturaleza).
* `silver_bienes_interes_culturales`: Bienes de Interés Cultural (BIC) y patrimonio histórico insular.
* `silver_oficinas_turismo`: Red insular de oficinas de información turística.
* `silver_satelite_stats`: Estadísticas zonales de Sentinel-2 (NDVI, NDBI) y radiancia nocturna VIIRS.

### `clima/`
* `silver_clima_agrocabildo`: Lecturas horarias depuradas de 57 estaciones maduras del Cabildo (filtradas por fecha de instalación <= 01/01/2022 para evitar discontinuidades y nulos en el histórico), filtrando códigos de error (-999, -9999).
* `silver_estaciones_agrocabildo`: Metadatos, coordenadas y geometría PostGIS de las 57 estaciones meteorológicas maduras (instaladas <= 2022-01-01).

### `istac/`
* `silver_istac_anual`: Cifras de población, tramos de edad y demografía municipal.
* `silver_istac_mensual`: Estadísticas mensuales de ocupación, empleo hostelero, paro y empresas dadas de alta.
* `silver_istac_trimestral`: Afiliaciones trimestrales a la Seguridad Social por sector de actividad.

### `movilidad/`
* `silver_aena_pasajeros`: Serie histórica limpia de pasajeros y vuelos por aeropuerto.
* `silver_gtfs_paradas`: 3.893 paradas geolocalizadas de la red de transporte insular (TITSA y Tranvía).
* `silver_gtfs_rutas`: Trazados, cabeceras y frecuencias de líneas de guagua y tranvía.

### `losviajeros/` — Foros de viajes (NLP)
* `silver_losviajeros_mensajes`: Corpus textual de viajeros depurado sin etiquetas HTML.

### `youtube/` — Redes sociales (NLP)
* `silver_youtube`: Vídeos con métricas de engagement normalizadas.
* `silver_youtube_comentarios`: Comentarios depurados en español e inglés.

---

## 6. Fuentes Bronze declaradas (`sources.yml`)

Las tablas fuente se almacenan en el esquema `bronze.*` de Azure PostgreSQL, pobladas desde Azure Blob Storage mediante los scripts de ingesta (`ingestion/postgres/01` a `07`). Se encuentran declaradas formalmente en `models/silver/sources.yml`:

```
bronze.bronze_estaciones_agrocabildo
bronze.bronze_clima_horario_agrocabildo
bronze.bronze_sensores_meteorologicos
bronze.bronze_h3_grid
bronze.bronze_espacios_naturales
bronze.bronze_mdt_stats
bronze.bronze_satelite_stats
bronze.bronze_limites_municipales
bronze.bronze_zonas_turisticas
bronze.bronze_osm_pois
bronze.bronze_bienes_interes_cultural
bronze.bronze_oficinas_turismo
bronze.bronze_gtfs_paradas
bronze.bronze_gtfs_rutas
bronze.bronze_gtfs_viajes
bronze.bronze_gtfs_horarios
bronze.bronze_aena_pasajeros
bronze.bronze_booking_establishments
bronze.bronze_booking_reviews
bronze.bronze_registro_hoteles
bronze.bronze_registro_viviendas_vacacionales
bronze.bronze_registro_extrahoteleros
bronze.bronze_tripadvisor_resenas
bronze.bronze_tripadvisor_ubicaciones
bronze.bronze_youtube_videos
bronze.bronze_youtube_comments
bronze.bronze_losviajeros_temas
bronze.bronze_losviajeros_mensajes
bronze.bronze_istac_mun_*
```

---

## 7. Pruebas y validación de calidad de datos (Data Governance)

Siguiendo las directrices del **Bloque 2 del TFM (Gobernanza y Calidad de Datos)** y los estándares de *Analytics Engineering*, cada una de las subcarpetas del proyecto (`silver/` y `gold/`) cuenta con su correspondiente archivo de gobernanza **`schema.yml`**, configurando un total de **229 pruebas automatizadas** de integración y validación:

| Capa / Dominio | Método de Ingesta (Bronze / Origen) | Archivo de Especificación | Modelos Cubiertos | Pruebas de Calidad |
|---|---|---|---|---|
| **Gold** | Transformación y materialización analítica dbt SQL (`dbt run --select gold.*`) a partir de capas Silver + enriquecimiento ML | `models/gold/schema.yml` | 11 modelos analíticos | 73 pruebas (`unique`, `not_null`, `relationships`, `accepted_values`) |
| **Silver Espacial** | API CKAN (`datos.tenerife.es`), WFS IDECanarias/GRAFCAN, Overpass API (OSM) y exportación raster GEE → Azure Blob → PostGIS | `models/silver/espacial/schema.yml` | 9 modelos espaciales | 52 pruebas (integridad geométrica, `unique`, `not_null`, `relationships`) |
| **Silver Clima** | API REST v2.0.0 Agrocabildo con control de flujo (10 req/min) y partición Hive (`año=YYYY/mes=MM/`) → Azure Blob → PostgreSQL | `models/silver/clima/schema.yml` | 2 modelos climáticos | 15 pruebas (validación de sensores, integridad referencial de 1.8M filas) |
| **Silver Movilidad** | Descarga directa de feeds ZIP GTFS (TITSA/Tranvía) y descarga automatizada de CSVs mensuales de AENA → Azure Blob → PostgreSQL | `models/silver/movilidad/schema.yml` | 3 modelos GTFS / AENA | 19 pruebas (`stop_id`, `shape_id`, aeropuertos canónicos) |
| **Silver ISTAC** | API REST / SDMX estadística del ISTAC (sistemas `C00067A` y `C00065A_000061`) con paginación JSON → Azure Blob → PostgreSQL | `models/silver/istac/schema.yml` | 3 modelos demográficos/laborales | 19 pruebas (códigos INE municipales, temporalidad) |
| **Silver Alojamiento** | Extracción web / API abierta del Registro General Turístico (Gobierno de Canarias) + Geocodificación por lotes con caché PostGIS | `models/silver/alojamiento/schema.yml` | 1 modelo oficial | 7 pruebas (categorías oficiales, tipologías regladas) |
| **Silver Booking** | Web scraping ético distribuido con rotación de User-Agent, retrasos probabilísticos (2,5–5 s) y sitemaps XML → Azure Blob → PostgreSQL | `models/silver/booking/schema.yml` | 2 modelos OTA Booking | 13 pruebas (integridad referencial review-hotel, ratings) |
| **Silver TripAdvisor** | Scraping / Terra API con validación geoespacial perimetral en PostGIS para evitar homónimos → Azure Blob → PostgreSQL | `models/silver/tripadvisor/schema.yml` | 2 modelos OTA TripAdvisor | 14 pruebas (location_id, reviews limpias > 15 chars) |
| **Silver YouTube** | Extracción automatizada vía YouTube Data API v3 (Google Cloud Platform) con endpoints REST paginados → Azure Blob → PostgreSQL | `models/silver/youtube/schema.yml` | 2 modelos social video | 12 pruebas (`video_id`, comentarios válidos) |
| **Silver LosViajeros** | Web scraping ético en Python (BeautifulSoup) sobre paginación HTML de foros (248 hilos, cortesía 1,5 s) → Azure Blob → PostgreSQL | `models/silver/losviajeros/schema.yml` | 1 modelo foros de viajes | 5 pruebas (`unique`, `not_null` en mensaje, tema, texto y fecha) |
| **Singular Tests** | Scripts Python y queries SQL de validación cruzada y privacidad | `tests/` | Pruebas transversales | `assert_no_personal_data_columns`, `assert_rating_in_range`, etc. |

### Ejecución de la suite completa de calidad:
```bash
# Desde la raíz del repositorio
python run_dbt.py test

# O desde dentro de dbt_project/
dbt test
```

### Tipología de pruebas implementadas:
- **Unicidad (`unique`):** Claves primarias únicas estrictas (`h3_index` en `gold_h3_master` y `silver_h3_grid`, `cod_municipio` en `gold_municipio_master`, `stop_id`, `shape_id`, `location_id`, `video_id`, `id_estacion`).
- **Completitud y No Nulos (`not_null`):** Campos críticos de negocio 100% libres de nulos (geometrías PostGIS, elevaciones MDT > 0 m, centroides canónicos, población empadronada, afiliación laboral, series temporales).
- **Integridad Referencial (`relationships`):** Garantía relacional estricta entre dimensiones (cada celda de `gold_h3_master` se relaciona biunívocamente con `silver_h3_grid` y `gold_municipio_master`; cada reseña se enlaza obligatoriamente con un establecimiento existente).
- **Dominios Aceptados (`accepted_values`):** Validación estricta de diccionarios de variables (ej. trimestres `['Q1', 'Q2', 'Q3', 'Q4']`, aeropuertos IATA `['TFN', 'TFS']`, polos turísticos `['Polo Sur', 'Polo Norte', 'Polo Metropolitano']`, fuentes de POIs `['OSM', 'IDE_Canarias']`).
- **Gestión de Advertencias (`severity: warn`):** Tratamiento analítico de peculiaridades inherentes a datos crudos de terceros (ej. licencias turísticas multi-modalidad en el registro oficial canario o reingestas puntuales de comentarios en YouTube/TripAdvisor).
