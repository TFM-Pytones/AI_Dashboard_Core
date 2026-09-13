# Ingesta Espacial (Spatial Ingestion)

Esta carpeta contiene los scripts encargados de generar y procesar las capas geoespaciales base del proyecto. El componente más crítico es la generación de la **Malla H3**, que actúa como el "tablero" sobre el cual se cruzan todas las demás fuentes de datos (satélite, meteorología, movilidad, turismo, relieve, etc.).

## Scripts

### 1. `h3_grid_upload_blob.py`
Crea la cuadrícula espacial hexagonal base de Uber H3 para la isla de Tenerife y la almacena en Azure Blob Storage (`bronce-raw/espacial/h3/h3_grid_tenerife_res8.parquet`).

**Flujo de ejecución:**
1. **Extracción**: Descarga el polígono/límite oficial de la isla de Tenerife desde OpenStreetMap mediante `osmnx.geocode_to_gdf('Tenerife, Spain')`.
2. **Buffer de amortiguación costera**: Aplica un buffer perimetral de **0.01 grados (~1,1 km)** al polígono insular. Este margen de seguridad garantiza que el centroide de las celdas costeras caiga siempre dentro del área de análisis, asegurando el 100% de playas, acantilados, puertos, paseos marítimos y hoteles de primera línea sin dejar huecos.
3. **Generación Matemática**: Utiliza `h3-py` (`h3.polygon_to_cells`) en **Resolución 8** (~0,85 km² por hexágono), generando exactamente **2.746 celdas** en la capa Bronze.
4. **Conversión a Geometría y Almacenamiento**: Transforma los índices H3 en polígonos `shapely` en EPSG:4326 y los guarda en Parquet localmente (`data/bronce/espacial/h3/h3_grid_tenerife_res8.parquet`).
5. **Subida al Datalake**: Sube el archivo a Azure Blob Storage en `espacial/h3/h3_grid_tenerife_res8.parquet`.

#### Transición de Bronze a Silver: de 2.746 a 2.579 celdas
- **Capa Bronze (`bronze.bronze_h3_grid`):** Contiene las **2.746 celdas** generadas con el buffer perimetral de 1,1 km.
- **Capa Silver (`silver.silver_h3_grid`):** Aplica dos filtros de depuración espacial y biofísica:
  1. *Filtro de límites municipales:* Descarta **163 celdas 100% marítimas** del buffer en alta mar mediante `ST_Intersects` con `silver_limites_municipales`.
  2. *Filtro de integridad física (MDT y NDVI):* Descarta **4 celdas residuales de acantilados/roques marinos** (1 en Tacoronte sin cota de elevación y 3 en los Roques de Anaga sin cobertura satelital de Sentinel-2).
- **Resultado:** Quedan consolidadas exactamente **2.579 celdas hexagonales limpias** 100% libres de nulos en topografía y teledetección, con centroides geométricos canónicos puros, que vertebran toda la capa Gold (`gold_h3_master`).

---

### 2. `enp_zonas_upload_blob.py`
Descarga las capas geográficas institucionales de IDECanarias (GRAFCAN):
- **Espacios Naturales Protegidos (ENP):** 48 figuras de protección ambiental (Parque Nacional del Teide, Anaga, Corona Forestal, Teno, etc.).
- **Zonas Turísticas Oficiales:** Delimitaciones normativas de los polos turísticos de la isla.
- **Destino Blob:** `espacial/enp/` y `espacial/zonas_turisticas/`.

### 3. `cabildo_opendata_upload_blob.py`
Descarga desde el portal de Open Data del Cabildo de Tenerife:
- **Bienes de Interés Cultural (BIC):** Monumentos, conjuntos históricos y sitios arqueológicos.
- **Oficinas de Información Turística:** Puntos de atención y asistencia al viajero.
- **Destino Blob:** `espacial/bienes_interes_cultural/` y `espacial/oficina_turismo/`.

### 4. `osm_tourism_upload_blob.py`
Lanza consultas OverpassQL a la API de OpenStreetMap para extraer puntos de interés turísticos y de servicios (restaurantes, bares, cafeterías, miradores, museos, playas, etc.).
- **Destino Blob:** `espacial/osm/osm_pois_tenerife.parquet`.

## Dependencias
Las librerías requeridas se gestionan en el entorno virtual (`.venv`):
`h3`, `osmnx`, `geopandas`, `shapely`, `azure-storage-blob`, `python-dotenv`.

