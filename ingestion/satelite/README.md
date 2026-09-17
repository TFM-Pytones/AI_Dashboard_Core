# Ingesta Satelital y Teledetección: Sentinel-2 y VIIRS (Capa Bronze)

Módulo de teledetección espacial para la captura, corrección atmosférica y procesamiento de imágenes satelitales de la constelación **Copernicus Sentinel-2** (vegetación y urbanización) y el sensor **NOAA/NASA VIIRS** (luces nocturnas y radianza económica).

> [!NOTE]
> Para conocer los fundamentos biofísicos, comparativa de índices espectrales, máscaras de nubes y justificación del filtrado de calima sahariana, consulta el documento técnico detallado: [`DECISIONES_TECNICAS.md`](file:///c:/Users/ROBERTO/Proyectos_Python/TFM_TUI_Tenerife/AI_Dashboard_Core/ingestion/satelite/DECISIONES_TECNICAS.md).

---

## 1. Arquitectura y Flujo de Procesamiento

```
                     Google Earth Engine (GEE) / NASA LAADS
                                      │
              ┌───────────────────────┴───────────────────────┐
              ▼                                               ▼
 sentinel2_upload_blob.py                            viirs_upload_blob.py
 - Sentinel-2 L2A (20m, EPSG:32628)                 - VIIRS DNB / VNP46A2 (~500m)
 - Filtrado SCL (nubes y sombras)                    - Radianza nocturna mensual
 - Filtrado AOT sahariana (< 0.3)                    - Etiquetado COVID 2020-2021
 - Filtro B02 reflectancia azul                      - Exportación GeoTIFFs
 - Composite trimestral de mediana (NDVI+NDBI)
              │                                               │
              └───────────────────────┬───────────────────────┘
                                      ▼
             Almacenamiento en Data Lake (Azure Blob Storage)
             ├── bronce-raw/satelite/sentinel2/year=XXXX/quarter=QN/
             └── bronce-raw/satelite/viirs/year=XXXX/month=MM/
                                      │
                                      ▼
             Carga y Estadísticas Zonales en Malla H3 (PostgreSQL)
             (ingestion/postgres/03_ingest_satelite_to_postgres.py)
             ├── bronze.bronze_satelite_stats (NDVI y NDBI por celda H3)
             └── bronze.bronze_viirs_stats (Radianza mensual por celda H3)
```

---

## 2. Scripts Disponibles

### 1. [`sentinel2_upload_blob.py`](file:///c:/Users/ROBERTO/Proyectos_Python/TFM_TUI_Tenerife/AI_Dashboard_Core/ingestion/satelite/sentinel2_upload_blob.py) — Sentinel-2 L2A (NDVI y NDBI)
Genera composites trimestrales de reflectancia en superficie libres de nubes y calima mediante Google Earth Engine (GEE):

* **Estrategia para el Fenómeno de "Panza de Burro"**: En la vertiente norte de Tenerife, la nubosidad estratocumular constante oculta el suelo en imágenes individuales. Se aplica un **composite de mediana trimestral** que selecciona el valor central de todos los píxeles despejados de cada trimestre, reconstruyendo la cobertura vegetal continua de la isla.
* **Triple Filtrado Atmosférico**:
  1. **SCL (Scene Classification Layer)**: Excluye píxeles clasificados como nubes de media/alta probabilidad, sombras de nubes y cirros.
  2. **AOT (Aerosol Optical Thickness)**: Filtra episodios de calima sahariana descartando observaciones con `AOT > 0.3`.
  3. **Banda Azul (B02)**: Umbral de reflectancia azul residual `< 0.18` para suprimir aerosoles finos no detectados por SCL.
* **Cálculo Espectral en GEE**:
  * **NDVI (Normalized Difference Vegetation Index)**: $(B8 - B4) / (B8 + B4)$ a 20m de resolución.
  * **NDBI (Normalized Difference Built-up Index)**: $(B11 - B8) / (B11 + B8)$ para cuantificar suelo sellado y presión urbanística.
* **Sistema de Coordenadas**: Proyección métrica oficial de Canarias **EPSG:32628** (UTM Zona 28N).

#### Comandos de ejecución:
```bash
# 1. Autenticación en GEE (solo la primera vez)
earthengine authenticate

# 2. Iniciar tareas de exportación en GEE hacia Google Drive
python ingestion/satelite/sentinel2_upload_blob.py --export

# 3. Supervisar estado de tareas en GEE
python ingestion/satelite/sentinel2_upload_blob.py --status

# 4. Subir GeoTIFFs descargados a Azure Blob Storage
python ingestion/satelite/sentinel2_upload_blob.py --upload-azure

# Listar inventario local
python ingestion/satelite/sentinel2_upload_blob.py --list
```

---

### 2. [`viirs_upload_blob.py`](file:///c:/Users/ROBERTO/Proyectos_Python/TFM_TUI_Tenerife/AI_Dashboard_Core/ingestion/satelite/viirs_upload_blob.py) — VIIRS Luces Nocturnas
Adquiere y calibra imágenes de radianza nocturna para evaluar la intensidad económica, presión turística y contaminación lumínica insular:

* **Fuentes Compatibles**:
  * **Google Earth Engine (Recomendada)**: Colección `NOAA/VIIRS/DNB/MONTHLY_V1/VCMSLCFG`.
  * **NASA LAADS DAAC**: Producto `VNP46A2` (Black Marble), tile `h17v05`.
* **Tratamiento del Período Temporal**:
  Se ingesta la serie histórica completa desde 2019 en la capa Bronze para mantener la trazabilidad inmutable. Posteriormente, en la capa Silver (`silver_satelite_stats`) se estandariza y filtra a partir de 2022 (`WHERE year >= 2022`), asegurando que los modelos de Machine Learning espacial (MGWR, HDBSCAN) se calibren sobre la serie post-pandemia sin distorsiones.

#### Comandos de ejecución:
```bash
# Vía GEE (método estándar)
python ingestion/satelite/viirs_upload_blob.py --source gee --export

# Vía NASA LAADS (requiere EARTHDATA_TOKEN)
python ingestion/satelite/viirs_upload_blob.py --source nasa --download

# Subir GeoTIFFs a Azure Blob Storage
python ingestion/satelite/viirs_upload_blob.py --upload-azure

# Listar inventario local
python ingestion/satelite/viirs_upload_blob.py --list
```

---

## 3. Variables de Entorno Requeridas (`.env`)

```ini
GEE_PROJECT_ID="nombre-del-proyecto-gee"
EARTHDATA_TOKEN="token-nasa-laads"            # Solo si se utiliza la descarga de NASA DAAC
AZURE_STORAGE_CONNECTION_STRING="DefaultEndpointsProtocol=https;AccountName=...;AccountKey=..."
```

---

## 4. Cruce Espacial hacia PostgreSQL

Una vez depositados los ficheros GeoTIFF en Azure Blob Storage o en el almacenamiento local, el script [`ingestion/postgres/03_ingest_satelite_to_postgres.py`](file:///c:/Users/ROBERTO/Proyectos_Python/TFM_TUI_Tenerife/AI_Dashboard_Core/ingestion/postgres/03_ingest_satelite_to_postgres.py) realiza las estadísticas zonales sobre cada celda hexagonal de la malla H3, poblando:
* `bronze.bronze_satelite_stats` (panel trimestral 2019-2026 de NDVI y NDBI)
* `bronze.bronze_viirs_stats` (panel mensual de radianza nocturna)
