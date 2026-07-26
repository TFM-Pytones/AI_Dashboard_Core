# ingestion/microdatos/

Pipeline de ingesta de microdatos espaciales y tabulares para el TFM (punto 4.6).

## Scripts disponibles

| Script | Fuente | Capas / Tablas | Blob destino |
|--------|--------|----------------|--------------|
| `mdt_ingestion.py` | CNIG/IGN | Elevacion, Slope, Aspect, Hillshade | `bronce-raw/mdt/` |
| `spatial_layers_ingestion.py` | IDECanarias / GRAFCAN | ENP, Zonas Turisticas | `bronce-raw/spatial/` |
| `tabular_ingestion.py` | INE, ISTAC | Padron Municipal, Indicadores, EAT Hoteles | `bronce-raw/tabular/` |

## Fuentes de datos

### Microdatos Espaciales

| Capa | Fuente | URL | Formato |
|------|--------|-----|---------|
| Limites municipales | IGN / INE | Ya disponible en BBDD | GeoJSON |
| Espacios Naturales Protegidos (ENP) | GRAFCAN / SITCAN | https://opendata.sitcan.es/ | Shapefile / GeoPackage |
| Zonas / Nucleos Turisticos | IDECanarias | https://datos.canarias.es/ | GeoJSON via WFS |
| MDT25 (Modelo Digital del Terreno) | CNIG / IGN | https://centrodedescargas.cnig.es/ | GeoTIFF (REGCAN95 UTM28N) |

### Microdatos Tabulares

| Tabla | Fuente | URL | Codigo |
|-------|--------|-----|--------|
| Padron Municipal - Poblacion por municipio | INE | https://www.ine.es/jaxiT3/Tabla.htm?t=2852 | t=2852 |
| Indicadores demograficos municipales | INE | https://www.ine.es/jaxiT3/Tabla.htm?t=31195 | t=31195 |
| EAT Hoteles - Plazas/Ocupacion por municipio | ISTAC | https://www.gobiernodecanarias.org/istac/ | E16028A_000008 |

## Descarga del MDT (importante)

El portal del CNIG puede requerir sesion web. Si la descarga automatica falla:

1. Ve a https://centrodedescargas.cnig.es/CentroDescargas/
2. Selecciona: Modelos Digitales de Elevaciones -> MDT25 -> REGCAN95 UTM28N
3. Descarga las hojas: **1083, 1084, 1085, 1086, 1087, 1088** (cubren Tenerife)
4. Coloca los ZIP en: `data/bronce/mdt/raw/`
5. Ejecuta: `python ingestion/microdatos/mdt_ingestion.py`

## Capas derivadas del MDT (punto 4.6 TFM)

A partir del MDT se calculan automaticamente:

- **Elevacion**: correccion termica por gradiente (-0.0065 C/m, ~3.2 C cada 500 m)
- **Slope** (pendiente): deteccion de valles encajonados
- **Aspect** (orientacion): Norte vs Sur -> impacto alisios / mar de nubes
- **Hillshade** (sombras): estimacion de radiacion solar recibida

Algoritmo: Horn (1981), equivalente a `gdaldem slope/aspect/hillshade`.

## Dependencias adicionales

```bash
pip install rasterio    # MDT: lectura/escritura GeoTIFF
pip install geopandas   # ENP y Zonas Turisticas: capas vectoriales
# En Windows puede requerir instalar GDAL primero:
# pip install GDAL
```
