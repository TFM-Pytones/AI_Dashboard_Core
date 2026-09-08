# ingestion/copernicus/

Issue #10 — Extracción Satelital (Copernicus / Sentinel).

## Scripts disponibles

### `download_sentinel2_gee.py` — Sentinel-2 NDVI/NDBI
Genera composites trimestrales libres de nubes y calima de Sentinel-2 L2A
usando Google Earth Engine. Calcula NDVI y NDBI directamente en GEE.

**Filtrado aplicado:**
- **SCL** (Scene Classification Layer): elimina nubes, sombras y cirrus.
- **AOT** (Aerosol Optical Thickness): elimina calima sahariana (AOT < 0.3).
- **B02 Azul** (refuerzo): umbral de reflectancia azul < 0.18 para aerosol residual.
- **Composite de mediana trimestral**: combina todos los píxeles válidos del trimestre → soluciona la "panza de burro" del norte de Tenerife.

**Outputs:**
- GeoTIFFs en `data/bronce/spatial/satelite/sentinel2/` (descargados de Google Drive)
- Azure Blob: `bronce-raw/satelite/sentinel2/year=XXXX/quarter=QN/`
- Bandas exportadas: `NDVI`, `NDBI`, `B02_blue` (QC visual)
- 30 composites totales: 2019–2026 Q2 (4 trimestres/año)

```bash
# 1. Autenticar GEE (solo la primera vez)
earthengine authenticate

# 2. Exportar todos los composites a Google Drive
python ingestion/copernicus/download_sentinel2_gee.py --export

# 3. Ver estado de tasks en GEE
python ingestion/copernicus/download_sentinel2_gee.py --status

# 4. Tras descargar de Drive → subir a Azure
python ingestion/copernicus/download_sentinel2_gee.py --upload-azure

# Ver inventario local
python ingestion/copernicus/download_sentinel2_gee.py --list
```

---

### `download_viirs.py` — VIIRS Luces Nocturnas
Descarga composites mensuales VIIRS VNP46A2 de luces nocturnas.

**Dos fuentes:**
- **GEE (recomendada)**: colección `NOAA/VIIRS/DNB/MONTHLY_V1/VCMSLCFG`, más sencillo.
- **NASA LAADS DAAC**: producto VNP46A2, tile `h17v05`, requiere `EARTHDATA_TOKEN`.

**Metadata COVID:** los años 2020-2021 se etiquetan con `periodo_covid=1` e
`incluir_en_modelo=0` para excluirlos del modelo MGWR de regresión (#31).

**Outputs:**
- GeoTIFFs mensuales en `data/bronce/spatial/satelite/viirs/`
- Azure Blob: `bronce-raw/satelite/viirs/year=XXXX/month=MM/`
- 90 meses totales: 2019/01 → 2026/06

```bash
# Opción A: via GEE (recomendada)
python ingestion/copernicus/download_viirs.py --source gee --export

# Opción B: via NASA LAADS (requiere EARTHDATA_TOKEN en .env)
python ingestion/copernicus/download_viirs.py --source nasa --download

# Subir a Azure
python ingestion/copernicus/download_viirs.py --upload-azure
```

---

## Variables de entorno requeridas (`.env`)

```
GEE_PROJECT_ID=           # ID del proyecto Google Earth Engine
EARTHDATA_TOKEN=          # Token NASA Earthdata (solo si usas NASA LAADS)
AZURE_STORAGE_CONNECTION_STRING=   # Ya configurado en el proyecto
```

## Referencias
- [GEE Sentinel-2 SR Harmonized](https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S2_SR_HARMONIZED)
- [GEE VIIRS Monthly](https://developers.google.com/earth-engine/datasets/catalog/NOAA_VIIRS_DNB_MONTHLY_V1_VCMSLCFG)
- [NASA LAADS VNP46A2](https://ladsweb.modaps.eosdis.nasa.gov/missions-and-measurements/products/VNP46A2/)
- [Sentinel-2 SCL classification](https://sentinels.copernicus.eu/web/sentinel/technical-guides/sentinel-2-msi/level-2a/algorithm-overview)
