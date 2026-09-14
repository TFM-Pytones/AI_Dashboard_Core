# Catálogo de Fuentes de Datos — TFM TUI Tenerife

Este documento sirve como registro vivo de todas las fuentes de datos (archivos, APIs y descargas manuales) utilizadas en el proyecto. 
El objetivo es tener un mapa claro de **dónde sale cada archivo** que alimenta el Azure Blob Storage (Capa Bronce).

---

## Clima y Meteorología (Agrocabildo)
*Datos meteorológicos, agrícolas y climáticos de la isla.*
- **Origen / Proveedor:** Cabildo de Tenerife (Agrocabildo).
- **Método de Extracción:** API Pública SOAP (`http://www.agrocabildo.org/WsAgrocabildo.asmx`).
- **Archivos Resultantes en Azure:**
  - `clima_horario_agrocabildo/mediciones/estacion_X.parquet`: Lecturas horarias (temperatura, humedad, viento) ingestadas automáticamente por Python.
  - `clima_horario_agrocabildo/estaciones/estaciones_agrocabildo.parquet`: Ubicaciones y metadatos de las estaciones.
  - `clima_horario_agrocabildo/sensores/sensores_meteorologicos.parquet`: Catálogo de los tipos de sensores. Se genera a partir de un archivo estático local (`sensores-meteorologicos.csv`).

## Puntos de Interés (OpenStreetMap - OSM)
*Ubicación de restaurantes, hospitales, playas, atractivos naturales, etc.*
- **Origen / Proveedor:** OpenStreetMap.
- **Método de Extracción:** Overpass API (`https://overpass-api.de/api/interpreter`).
- **Archivos Resultantes en Azure (`bronce-raw`):**
  - `espacial/osm/osm_pois_tenerife.parquet`: Generado por `osm_tourism_upload_blob.py` buscando `tourism`, `amenity`, `natural`, `leisure`, `historic`, etc.

## Malla Geoespacial Discreta (Uber H3 Res 8)
*Estructura de indexación territorial hexagonal base para la integración microespacial de toda la isla.*
- **Origen / Proveedor:** OpenStreetMap (geocodificación oficial de Tenerife) + Uber H3 Spatial Indexing System (`h3-py`).
- **Método de Generación:** Script automatizado [`ingestion/espacial/h3_grid_upload_blob.py`](file:///c:/Users/ROBERTO/Proyectos_Python/TFM_TUI_Tenerife/AI_Dashboard_Core/ingestion/espacial/h3_grid_upload_blob.py).
- **Buffer de amortiguación costera:** Se aplica intencionadamente un buffer perimetral de 0.01° (~1,1 km) sobre el polígono insular para garantizar la cobertura total de acantilados, playas, puertos y hoteles en primera línea de costa.
- **Archivos Resultantes en Azure Blob (`bronce-raw`):**
  - `espacial/h3/h3_grid_tenerife_res8.parquet`: Malla vectorial con **2.746 celdas hexagonales brutas** (Capa Bronze).
- **Transición a Silver y Gold:** En la tabla `silver.silver_h3_grid`, se aplica un filtro espacial (`ST_Intersects` con los 31 límites municipales) y de integridad física (MDT > 0 y NDVI válido), descartando 163 celdas marítimas de buffer y 4 celdas de roques marinos sin datos, consolidando **2.579 celdas hexagonales limpias y 100% completas** que vertebran `gold.gold_h3_master`.

## Datos Espaciales Institucionales (Estáticos)
*Polígonos y ubicaciones oficiales (Límites, zonas naturales, patrimonio, relieve).*
- **Origen / Proveedor:** IDE Canarias (Infraestructura de Datos Espaciales) / Grafcan / Open Data Cabildo.
- **Método de Extracción:** Descargas manuales y WFS institucionales.
- **Archivos Resultantes en Azure (`bronce-raw`):**
  - `espacial/bienes_interes_cultural/bienes_interes_cultural_tenerife.parquet`: Polígonos BIC.
  - `espacial/oficina_turismo/oficinas_turismo_tenerife.parquet`: Puntos de información turística.
  - `espacial/enp/tenerife_espacios_naturales_protegidos.parquet`: 48 figuras de protección ambiental ENP.
  - `espacial/zonas_turisticas/tenerife_zonas_turisticas.parquet`: Polígonos de zonas turísticas oficiales.
  - `espacial/limites_municipales/limites_municipales_tenerife.parquet`: Límites de los 31 municipios.
  - `data/mdt/136_MDT25_TF.tif`: Modelo Digital del Terreno (resolución 25 m) de GRAFCAN. Genera `bronze.bronze_mdt_stats` mediante estadísticas zonales.

## Economía y Turismo Oficial (ISTAC)
*Estadísticas macroeconómicas, empleo, y ocupación hotelera/viviendas vacacionales.*
- **Origen / Proveedor:** Instituto Canario de Estadística (ISTAC).
- **Método de Extracción:** API Base del ISTAC.
- **Archivos Resultantes en Azure:**
  - Diferentes datasets tabulares sobre plazas de VV, indicadores económicos por municipio, etc. (Gestionados por los scripts de `ingestion/istac/`).

## Movilidad e Infraestructuras
*Tráfico de pasajeros y transporte público.*
- **AENA (Aeropuertos):** Datos de tráfico de pasajeros de TFS (Sur) y TFN (Norte), extraídos desde los informes Excel públicos de AENA y cargados en el blob de Azure como dato complementario de contexto (`blob: aena/`). No integrado directamente en `gold_h3_master`.
- **TITSA y Metropolitano (Guaguas):**
  - **Origen:** Datos Abiertos de Tenerife, formato GTFS.
  - **Resultado en blob:** 7 archivos Parquet por operador (paradas, rutas, viajes, horarios, calendario, excepciones, atributos).
  - **Uso:** Base para el cálculo de isócronas de accesibilidad y la capa `silver_gtfs_paradas` (3.893 paradas geolocalizadas).

## Reputación y NLP (Booking, TripAdvisor, YouTube, LosViajeros)
*Opiniones, precios y sentimiento de los turistas.*
- **Booking.com:** Extracción de hoteles, viviendas vacacionales y reseñas mediante scraping automatizado con Python (Selenium/Playwright). Datos almacenados en el blob y procesados en la tabla `silver_booking_establishments` y `silver_booking_reviews`.
- **TripAdvisor:** Ubicaciones y reseñas convertidas desde JSON a Parquet y cargadas en el blob. Procesadas en `silver_tripadvisor_ubicaciones` y `silver_tripadvisor_resenas`. Ambas fuentes se integran en `gold_h3_master`.
- **YouTube API v3:** 41 vídeos y ~3.100 comentarios extraídos con la API gratuita (sin tarjeta de crédito). Almacenados en `bronze.youtube_videos` y `bronze.youtube_comments`. Procesados por el modelo de sentimiento (Hugging Face) y BERTopic.
- **LosViajeros.com:** ~248 hilos y 167.000 mensajes extraídos mediante scraping con BeautifulSoup. Almacenados en `bronze.losviajeros_temas` y `bronze.losviajeros_mensajes`. Usados en el modelo de tópicos BERTopic.

---
*(Nota: Este documento es dinámico. Si añadimos una API nueva o subimos un CSV manual de otra consejería, debemos documentarlo aquí para no perder la trazabilidad).*
