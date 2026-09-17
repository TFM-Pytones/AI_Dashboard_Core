# Ingesta de Establecimientos y Reseñas: Booking.com (Capa Bronze)

Módulo encargado del descubrimiento, extracción automatizada y almacenamiento de establecimientos hoteleros y reseñas de viajeros en la isla de Tenerife mediante scraping ético sobre **Booking.com**.

---

## 1. Arquitectura y Flujo de Datos

```
Sitemaps XML de Booking.com (sitembk-hotel-es.*.xml.gz)
       │
       ▼  Cruce con topónimos de OpenStreetMap (Overpass API)
build_tenerife_keywords.py / build_priority_keywords.py
       │
       ▼  Descubrimiento de URLs en Tenerife
booking_scraper.py / run_continuous.py (Selenium Headless)
       │
       ├─► Extracción de establecimientos, puntuaciones, servicios y reseñas
       │
       ▼  Almacenamiento directo en Data Lake (Azure Blob Storage)
Contenedor: bronce-raw/booking/*.parquet
       │
       ▼  Puente de carga (ingestion/postgres/04_ingest_booking_to_postgres.py)
PostgreSQL: bronze.bronze_booking_establishments (4.099 filas) / bronze_booking_reviews (105.104 filas)
       │
       ▼  Geocodificación PostGIS (ingestion/postgres/06_geocode_booking_pg.py)
PostgreSQL: Enriquecimiento espacial con Nominatim y tabla centralizada `bronze.bronze_booking_geocoding_lookup`
       │
       ▼  Transformación analítica y deduplicación con dbt
PostgreSQL: silver.silver_booking_establishments (3.740 hoteles) / silver_booking_reviews (73.888 reseñas)
```

---

## 2. Componentes del Módulo

### Scripts Principales
* [`booking_scraper.py`](file:///c:/Users/ROBERTO/Proyectos_Python/TFM_TUI_Tenerife/AI_Dashboard_Core/ingestion/booking/booking_scraper.py): Scraper modular con Selenium en modo headless. Implementa control de banners de cookies, ventanas emergentes (Google One Tap), reintentos con esperas inteligentes y extracción robusta de metadatos.
* [`booking_scraper_deep.py`](file:///c:/Users/ROBERTO/Proyectos_Python/TFM_TUI_Tenerife/AI_Dashboard_Core/ingestion/booking/booking_scraper_deep.py): Extracción en profundidad de opiniones históricas y desglose de valoraciones por categoría (limpieza, confort, ubicación, relación calidad/precio).
* [`run_continuous.py`](file:///c:/Users/ROBERTO/Proyectos_Python/TFM_TUI_Tenerife/AI_Dashboard_Core/ingestion/booking/run_continuous.py): Orquestador por lotes con persistencia de estado (`scraping_progress.json`), diseñado para ejecuciones largas y estables tanto en local como en máquinas virtuales Azure (`mv-orquestador-tfm`).
* [`validate_booking_data.py`](file:///c:/Users/ROBERTO/Proyectos_Python/TFM_TUI_Tenerife/AI_Dashboard_Core/ingestion/booking/validate_booking_data.py): Script de auditoría y calidad post-extracción. Verifica la integridad de columnas obligatorias, nulos anormales y consistencia temporal.
* [`build_tenerife_keywords.py`](file:///c:/Users/ROBERTO/Proyectos_Python/TFM_TUI_Tenerife/AI_Dashboard_Core/ingestion/booking/build_tenerife_keywords.py) y [`build_priority_keywords.py`](file:///c:/Users/ROBERTO/Proyectos_Python/TFM_TUI_Tenerife/AI_Dashboard_Core/ingestion/booking/build_priority_keywords.py): Generadores del diccionario de topónimos de Tenerife desde OpenStreetMap (municipios, núcleos costeros, barrios, playas) para filtrar el sitemap global.
* [`config.py`](file:///c:/Users/ROBERTO/Proyectos_Python/TFM_TUI_Tenerife/AI_Dashboard_Core/ingestion/booking/config.py): Archivo de configuración centralizado (límites de scraping, tiempos de espera, user-agents y credenciales).

### Módulos de Soporte (`utils/`)
* `azure_storage.py`: Conexión y subida de archivos Parquet directamente a Azure Blob Storage (`bronce-raw`).
* `rate_limiter.py`: Pausas estocásticas entre peticiones para emular navegación humana y mitigar bloqueos.
* `user_agents.py`: Rotación controlada de cabeceras User-Agent identificables.
* `progress_tracker.py`: Manejo del progreso incremental para evitar duplicar peticiones.
* `logger.py`: Registro detallado de trazas en `booking_scraper.log`.

---

## 3. Consideraciones Éticas y Cumplimiento Normativo

El diseño del scraper sigue un estricto protocolo ético:
1. **Sin buscador interno**: El descubrimiento de URLs se realiza exclusivamente a través de los sitemaps XML públicos de Booking (`sitembk-hotel-es.*.xml.gz`).
2. **Protección de Privacidad (Zero PII)**: No se recolecta ningún dato personal de los autores de reseñas (nombres de usuario o avatares se descartan; únicamente se conserva el país de procedencia extraído de la bandera del avatar).
3. **Uso exclusivamente analítico**: La información agregada alimenta modelos de analítica de texto (BERTopic, PyABSA) y visualización territorial para el TFM, sin fines comerciales ni de republicación íntegra.
4. **Respeto a la infraestructura**: Rate limiting con pausas aleatorias entre visitas para no sobrecargar el servidor web.

### Documentación Legal y Operativa (`docs/`)
* [`resumen_robots_booking.md`](file:///c:/Users/ROBERTO/Proyectos_Python/TFM_TUI_Tenerife/AI_Dashboard_Core/ingestion/booking/docs/resumen_robots_booking.md): Análisis de directivas `robots.txt` de Booking.com.
* [`resumen_terminos_servicio.md`](file:///c:/Users/ROBERTO/Proyectos_Python/TFM_TUI_Tenerife/AI_Dashboard_Core/ingestion/booking/docs/resumen_terminos_servicio.md): Evaluación de Términos de Servicio y marco ético académico.
* [`consultas_cruce_municipios_booking.md`](file:///c:/Users/ROBERTO/Proyectos_Python/TFM_TUI_Tenerife/AI_Dashboard_Core/ingestion/booking/docs/consultas_cruce_municipios_booking.md): Cruces espaciales y validaciones municipales.
* [`hallazgo_establecimientos_sin_resenas.md`](file:///c:/Users/ROBERTO/Proyectos_Python/TFM_TUI_Tenerife/AI_Dashboard_Core/ingestion/booking/docs/hallazgo_establecimientos_sin_resenas.md): Análisis de cobertura de opiniones.
* [`incidente_disco_lleno_vm.md`](file:///c:/Users/ROBERTO/Proyectos_Python/TFM_TUI_Tenerife/AI_Dashboard_Core/ingestion/booking/docs/incidente_disco_lleno_vm.md): Post-mortem y resolución de incidentes en VM de Azure.
* [`limitacion_orden_relevancia_deep_scrape.md`](file:///c:/Users/ROBERTO/Proyectos_Python/TFM_TUI_Tenerife/AI_Dashboard_Core/ingestion/booking/docs/limitacion_orden_relevancia_deep_scrape.md): Paginación y criterios de ordenación en scraping profundo.

---

## 4. Flujo hacia la Base de Datos y Capa Silver

1. **Carga en PostgreSQL**:
   Los Parquets generados en el Data Lake se vuelcan a la base de datos relacional mediante:
   ```bash
   python ingestion/postgres/04_ingest_booking_to_postgres.py
   ```
   *(Modo `append` en PostgreSQL para registrar todas las extracciones).*

2. **Georreferenciación**:
   ```bash
   python ingestion/postgres/06_geocode_booking_pg.py
   ```
   *(Asigna coordenadas geográficas a partir de la dirección, usando Nominatim y la tabla centralizada en Azure PostgreSQL `bronze.bronze_booking_geocoding_lookup`).*

3. **Deduplicación y Transformación en dbt**:
   En la capa Silver (`silver_booking_establishments` y `silver_booking_reviews`), dbt se encarga de deduplicar por identificador de hotel y reseña (`keep last`), descartar opiniones anteriores a 2022 o con menos de 15 caracteres, aplicar tests de calidad y estandarizar tipos numéricos.

| Capa | Tabla PostgreSQL | Volumen Verificado | Descripción |
|---|---|:---:|---|
| **Bronze** | `bronze.bronze_booking_establishments` | **4.099** filas | Establecimientos brutos extraídos de sitemaps y OpenStreetMap |
| **Bronze** | `bronze.bronze_booking_reviews` | **105.104** filas | Reseñas completas brutas con texto y metadatos |
| **Bronze** | `bronze.bronze_booking_geocoding_lookup` | **32** filas | Caché de resoluciones directas de coordenadas |
| **Silver** | `silver.silver_booking_establishments` | **3.740** filas | Alojamientos deduplicados con lat/lon validadas |
| **Silver** | `silver.silver_booking_reviews` | **73.888** filas | Reseñas filtradas ($\ge 2022$, longitud $> 15$, con hotel válido) |

---

## 5. Instrucciones de Ejecución

```bash
# Corrida única de prueba
python ingestion/booking/booking_scraper.py

# Corrida continua por lotes (producción)
python ingestion/booking/run_continuous.py

# Validación de calidad post-scraping
python ingestion/booking/validate_booking_data.py --all --gap-minutes 600
```
