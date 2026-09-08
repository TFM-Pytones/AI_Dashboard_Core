# 📚 Catálogo de Fuentes de Datos — TFM TUI Tenerife

Este documento sirve como registro vivo de todas las fuentes de datos (archivos, APIs y descargas manuales) utilizadas en el proyecto. 
El objetivo es tener un mapa claro de **dónde sale cada archivo** que alimenta el Azure Blob Storage (Capa Bronce).

---

## 🌤️ Clima y Meteorología (Agrocabildo)
*Datos meteorológicos, agrícolas y climáticos de la isla.*
- **Origen / Proveedor:** Cabildo de Tenerife (Agrocabildo).
- **Método de Extracción:** API Pública SOAP (`http://www.agrocabildo.org/WsAgrocabildo.asmx`).
- **Archivos Resultantes en Azure:**
  - `clima_horario_agrocabildo/mediciones/estacion_X.parquet`: Lecturas horarias (temperatura, humedad, viento) ingestadas automáticamente por Python.
  - `clima_horario_agrocabildo/estaciones/estaciones_agrocabildo.parquet`: Ubicaciones y metadatos de las estaciones.
  - `clima_horario_agrocabildo/sensores/sensores_meteorologicos.parquet`: Catálogo de los tipos de sensores. Se genera a partir de un archivo estático local (`sensores-meteorologicos.csv`).

## 🗺️ Puntos de Interés (OpenStreetMap - OSM)
*Ubicación de restaurantes, hospitales, playas, atractivos naturales, etc.*
- **Origen / Proveedor:** OpenStreetMap.
- **Método de Extracción:** Overpass API (`https://overpass-api.de/api/interpreter`).
- **Archivos Resultantes en Azure:**
  - `espacial/osm/osm_pois_tenerife.geojson`: Generado por el script de Python que lanza queries OverpassQL (buscando `tourism`, `amenity`, `natural`, etc.).

## 🏛️ Datos Espaciales Institucionales (Estáticos)
*Polígonos y ubicaciones oficiales (Límites, zonas naturales, patrimonio).*
- **Origen / Proveedor:** IDE Canarias (Infraestructura de Datos Espaciales) / Grafcan / Open Data Cabildo.
- **Método de Extracción:** Descargas manuales de portales institucionales.
- **Archivos Resultantes en Azure (Espacial):**
  - `espacial/raw/bienes_interes_cultural_tenerife.geojson`: Polígonos BIC.
  - `espacial/raw/oficinas_turismo_tenerife.geojson`: Puntos de información turística.
  - `espacial/raw/tenerife_espacios_naturales_protegidos.geojson`: Polígonos ENP.
  - `espacial/raw/mdt...`: Modelo Digital del Terreno (Altitud / Relieve) descargado manualmente.

## 📊 Economía y Turismo Oficial (ISTAC)
*Estadísticas macroeconómicas, empleo, y ocupación hotelera/viviendas vacacionales.*
- **Origen / Proveedor:** Instituto Canario de Estadística (ISTAC).
- **Método de Extracción:** API Base del ISTAC.
- **Archivos Resultantes en Azure:**
  - Diferentes datasets tabulares sobre plazas de VV, indicadores económicos por municipio, etc. (Gestionados por los scripts de `ingestion/istac/`).

## ✈️ Movilidad e Infraestructuras
*Tráfico de pasajeros y transporte público.*
- **AENA (Aeropuertos):** Datos de tráfico de pasajeros (TFS y TFN). Extraídos vía API pública de AENA o portales estadísticos.
- **TITSA (Guaguas):** 
  - **Origen:** Datos Abiertos de Tenerife (GTFS o Google Transit).
  - **Uso:** Paradas y rutas de transporte público para medir la accesibilidad.

## 💬 Reputación y NLP (Booking, TripAdvisor, Foros)
*Opiniones, precios y sentimiento de los turistas.*
- **Booking.com:** Extracción de hoteles, VVs y reseñas mediante scripts de scraping (Selenium/Playwright) o APIs no oficiales.
- **TripAdvisor:** Ubicaciones y reseñas (Actualmente pendiente de integración en el código; se aportarán como cargas de archivos externos temporales).
- **LosViajeros.com & YouTube:** Scraping de foros y extracción mediante YouTube Data API v3 para medir la "Marca Tenerife" a nivel global.

---
*(Nota: Este documento es dinámico. Si añadimos una API nueva o subimos un CSV manual de otra consejería, debemos documentarlo aquí para no perder la trazabilidad).*
