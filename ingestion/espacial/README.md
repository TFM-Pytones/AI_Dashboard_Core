# Ingesta Espacial (Spatial Ingestion)

Esta carpeta contiene los scripts encargados de generar y procesar las capas geoespaciales base del proyecto. El componente más crítico es la generación de la **Malla H3**, que actúa como el "tablero" sobre el cual se cruzan todas las demás fuentes de datos (satélite, meteorología, movilidad, turismo, etc.).

## Scripts

### `generate_h3_to_blob.py`
Este script es el responsable de crear la cuadrícula espacial base para la isla de Tenerife y almacenarla en el Datalake (Azure Blob Storage).

**Flujo de ejecución:**
1. **Extracción**: Conecta con los servidores de OpenStreetMap (a través de `osmnx`) para descargar el polígono/límite oficial exacto de la isla de Tenerife.
2. **Generación Matemática**: Utiliza la librería de Uber (`h3-py`) para calcular todos los hexágonos matemáticos que intersectan o caben dentro de ese polígono.
3. **Conversión a Geometría**: Transforma los índices alfanuméricos de H3 en polígonos geográficos reales (coordenadas Lat/Lon en formato EPSG:4326) usando `shapely` y `geopandas`.
4. **Almacenamiento Local**: Guarda el resultado como un archivo GeoJSON temporal en `data/bronce/spatial/h3/h3_grid_tenerife_res8.geojson`.
5. **Subida al Datalake (Blob Storage)**: Se autentica con Azure utilizando la cadena de conexión definida en el archivo `.env` (`AZURE_STORAGE_CONNECTION_STRING`) y sube el archivo a la capa de datos crudos (`bronce-raw/spatial/h3/`).

#### Por qué Resolución 8
Se ha elegido la **resolución 8** del sistema H3 porque genera celdas con un área media de **0.74 km²** (aproximadamente 2.396 celdas para cubrir toda la isla de Tenerife). 
Es la granularidad perfecta para este caso de uso:
- Es lo suficientemente pequeña para captar micro-variaciones (como el NDVI en un bosque específico o la densidad de paradas de guagua en una calle turística).
- Es lo suficientemente grande para que los modelos de Machine Learning y los agrupamientos espaciales se procesen de forma rápida y eficiente en la base de datos PostgreSQL/PostGIS.

## Dependencias
Para ejecutar los scripts de esta carpeta, es necesario asegurar que las siguientes librerías están instaladas en el entorno virtual (`.venv`):
- `h3`
- `osmnx`
- `geopandas`
- `shapely`
- `azure-storage-blob`
- `python-dotenv`
