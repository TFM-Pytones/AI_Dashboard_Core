# Decisiones Técnicas — Ingesta de Datos Satelitales
## `ingestion/copernicus/` — Issue #10

> **Fecha de implementación**: 30 de julio de 2026  
> **Autores**: TFM — AI Dashboard Core  
> **Relacionado con**: Issues #10, #21, #22, #23, #24

---

## 1. Contexto: ¿Por qué cambiar el enfoque original?

El Issue #10 original planteaba descargar **una escena Sentinel-2 por mes** con filtro de nubosidad `< 20%` usando la API STAC de Copernicus o `sentinelhub`. Este enfoque es el estándar en proyectos de teledetección continentales o de baja nubosidad.

**Tenerife no es un contexto estándar.**

Dos fenómenos climáticos muy específicos de la isla hacen inviable ese enfoque:

---

## 2. Problema 1: La "Panza de Burro"

### Qué es

La **"panza de burro"** es un banco de estratocúmulos (nubes bajas) que cubre de forma casi permanente la **vertiente norte de Tenerife** entre aproximadamente 600 y 1500 m de altitud. Es producida por los **vientos alisios del NE** que, al chocar con el macizo central del Teide, se enfrían y forman condensación en esa cota altitudinal.

Este fenómeno es especialmente intenso en **verano (junio-septiembre)**, que curiosamente coincide con la **temporada turística alta** — el trimestre más importante del modelo.

### Municipios más afectados

| Municipio | Zona | Impacto estimado |
|-----------|------|-----------------|
| Anaga (noreste) | Macizo forestal | ~8 meses/año con > 50% nubosidad |
| La Orotava | Vertiente norte | ~6 meses/año con > 50% nubosidad |
| Acentejo (La Victoria, La Matanza) | Vertiente norte baja | ~5 meses/año |
| Puerto de la Cruz | Costa norte | 3-4 meses/año |

### Impacto en el enfoque original

Con un filtro `< 20%` de nubosidad por escena, la búsqueda de imágenes válidas para el norte de Tenerife retornaría **0-2 escenas útiles por año** en Q3. Resultado: toda la franja norte del modelo NDVI quedaría sin datos.

---

## 3. Problema 2: La Calima Sahariana

### Qué es

La **calima** es polvo mineral del desierto del Sáhara (aerosoles silíceos) transportado a Canarias por los **vientos del sur y del este** a distintas altitudes. Tenerife recibe episodios de calima a lo largo de todo el año, pero son más frecuentes e intensos en **verano (Q3)** y en episodios esporádicos invernales.

### Por qué es crítica para NDVI/NDBI

A diferencia de las nubes, **la calima NO es detectada como nube por el algoritmo SCL de Sentinel-2**. La capa SCL (Scene Classification Layer) solo clasifica nubes de agua líquida y cirrus, pero el polvo mineral pasa todos los filtros de nubosidad con valores bajos (escenas "despejadas").

El efecto de la calima sobre los índices es:
- **NDVI**: se **subestima** sistemáticamente. El polvo absorbe y dispersa la radiación en el rojo y el NIR, reduciendo la diferencia `(NIR - RED)`. La vegetación parece menos verde de lo que realmente es.
- **NDBI**: puede **sobreestimarse**. El polvo eleva la reflectancia en SWIR.
- **Impacto en el modelo**: si el NDVI de Q3 está sesgado hacia abajo en todos los años, el modelo MGWR interpretaría incorrectamente la cobertura vegetal de verano.

### Episodios documentados relevantes para el TFM

| Episodio | Intensidad | Meses afectados |
|----------|-----------|----------------|
| Calima de marzo 2020 | Extrema (AOT > 3.0) | Marzo 2020 |
| Verano 2021 | Alta-moderada | Jul-Sep 2021 |
| Verano 2022-2024 | Moderada-recurrente | Jul-Sep |

---

## 4. Solución Adoptada: Composite de Mediana Trimestral en GEE

### Concepto de compositing

En lugar de seleccionar **una** imagen por mes (que puede tener nubes o calima), el compositing consiste en **combinar todos los píxeles válidos de un periodo** (en este caso, un trimestre) y calcular un estadístico por píxel.

La técnica es estándar en teledetección para regiones tropicales y subtropicales con alta nubosidad. Se usa en programas globales como **Global Forest Watch** (Hansen) y los productos MODIS de NASA.

### Por qué la mediana (y no el máximo o el mínimo)

| Estadístico | Descripción | Problema |
|------------|-------------|---------|
| **Máximo** de NDVI | Coge el valor más verde de la serie | Sesgado por errores atmosféricos residuales (píxeles brillantes anómalos) |
| **Mínimo** de NDVI | Coge el valor más seco | Sesgado hacia píxeles con nubes residuales o calima severa |
| **Media** | Promedio de todos los píxeles válidos | Sensible a valores extremos |
| **Mediana** | Valor central de la distribución | Robusta frente a outliers; representa bien la condición típica del trimestre |

### Por qué GEE y no Copernicus Data Space

| Criterio | GEE | Copernicus Data Space (OpenEO) |
|----------|-----|-------------------------------|
| Procesamiento | En la nube (gratis) | En la nube (cuota limitada) |
| Almacenamiento a descargar | Solo el composite resultante (~200-400 MB/trimestre) | Ídem |
| Velocidad de proceso | Alta (infraestructura Google) | Variable |
| Volumen de escenas fuente a procesar | ~500-1000 escenas Sentinel-2 para Tenerife 2019-2026 | Ídem |
| Cuota gratuita | Generosa para investigación | Más restrictiva |
| Colección disponible | `COPERNICUS/S2_SR_HARMONIZED` (armonizada entre procesadores) | `SENTINEL2_L2A` |
| CLI/Python API | Madura (`earthengine-api`) | (`openeo`) |
| **Decisión** | **Elegida** | Alternativa documentada en `download_sentinel2_gee.py` (Opción B) |

### Por qué trimestral (y no mensual o anual)

- **Mensual**: con la panza de burro, muchos meses del norte de Tenerife no tendrían píxeles válidos suficientes. Además, la granularidad mensual no aporta ventaja al modelo MGWR que tiene pernoctaciones ISTAC **anuales o como máximo mensuales** por municipio.
- **Anual**: pierde la **estacionalidad** — un objetivo clave del TFM es detectar la diferencia entre Q3 (verano, máxima presión turística) y Q1 (invierno, menor afluencia).
- **Trimestral **: capta los 4 patrones estacionales canarios, tiene suficientes píxeles válidos incluso en el norte, y se alinea con los análisis de pernoctaciones trimestrales.

---

## 5. Triple Filtrado de Calidad por Píxel

La pipeline aplica tres filtros en cascada **a nivel de píxel** (no de imagen completa):

```
[Colección S2] → [Pre-filtro imagen < 90% nubes] → [Máscara SCL] → [Máscara AOT] → [Máscara B02] → [Mediana trimestral]
```

### Filtro 1 — SCL (Scene Classification Layer)

La banda SCL de Sentinel-2 L2A clasifica cada píxel en 12 categorías. Se **excluyen**:

| Valor SCL | Clase | Razón |
|-----------|-------|-------|
| 1 | Saturado o defectuoso | Dato corrupto |
| 3 | Sombra de nube | Geometría oscura no vegetación |
| 8 | Nubes (media probabilidad) | Artefacto |
| 9 | Nubes (alta probabilidad) | Artefacto |
| 10 | Cirrus | Nubes altas semitransparentes |

Los valores **conservados** incluyen vegetación (4), suelo desnudo (5), agua (6), niebla/stratus de baja certeza (7) — esta última es la categoría que a veces incluye calima ligera, por eso se añaden los filtros 2 y 3.

### Filtro 2 — AOT (Aerosol Optical Thickness)

- **Qué es**: medida de la cantidad de aerosol en la columna atmosférica. Un AOT de 0.0 es atmósfera perfectamente limpia; 0.5 es moderadamente turbio; 1.0+ es calima severa.
- **Fuente**: banda auxiliar incluida en el producto Sentinel-2 L2A por el procesador ESA (Sen2Cor).
- **Umbral adoptado**: `AOT < 0.3` (DN < 300 en la codificación GEE). Este valor es el umbral estándar para considerar atmósfera limpia en zonas subtropicales (Kaufman et al., 1997).
- **Limitación**: el AOT de Sen2Cor puede tener errores en zonas costeras y sobre agua. El filtro B02 actúa como refuerzo.

### Filtro 3 — B02 Banda Azul (490 nm)

- **Qué es**: la banda azul de Sentinel-2 es la más sensible al scattering de Rayleigh y al aerosol fino (polvo sahariano). Con calima, la reflectancia azul de superficies oscuras (vegetación, agua) aumenta anómalamente.
- **Umbral adoptado**: `B02 < 0.18` (DN < 1800). Empírico para Canarias, basado en que la reflectancia azul de vegetación sana es ~0.03-0.06 y de suelo seco es ~0.10-0.15. Valores > 0.18 indican aerosol significativo.
- **Carácter**: filtro de refuerzo — actúa principalmente sobre píxeles que pasaron el filtro AOT pero aún tienen aerosol.

---

## 6. Granularidad y Periodo

### Sentinel-2

| Parámetro | Valor | Justificación |
|-----------|-------|---------------|
| Granularidad | Trimestral (Q1-Q4) | Ver sección 4 |
| Periodo inicio | 2019 Q1 (2019-01-01) | Línea base pre-COVID del TFM |
| Periodo fin | Último Q completo auto-calculado | Script usa `datetime.today()` para no requerir edición manual |
| Total composites | 30 (hasta 2026 Q2 a julio 2026) | Aumentará automáticamente según avance el tiempo |
| Resolución export | 20m | Tenerife (~2045 km²): 10m = ~2 GB/composite, 20m = ~500 MB/composite |
| CRS | EPSG:32628 | Sistema oficial Canarias (WGS 84 / UTM Zone 28N) |

### VIIRS Luces Nocturnas

| Parámetro | Valor | Justificación |
|-----------|-------|---------------|
| Granularidad | Mensual | Composites ya procesados mensualmente por NASA/NOAA |
| Periodo inicio | 2019-01 | Línea base pre-COVID |
| Periodo fin | Último mes disponible (~2 meses de latencia NASA) | Auto-calculado en script |
| Total composites | 90 meses (hasta 2026-06) | |
| Fuente preferida | GEE (`NOAA/VIIRS/DNB/MONTHLY_V1/VCMSLCFG`) | No requiere cuenta NASA, más rápido |
| Fuente alternativa | NASA LAADS DAAC VNP46A2 | Para validación cruzada o si GEE no tiene el dato |
| Resolución | ~500m (~GEE scale 500) | Resolución nativa del producto VIIRS |
| Metadato COVID | `periodo_covid=1` para 2020-2021 | Caída artificial de ~60-70% por COVID; excluir de regresión MGWR (#31) |

---

## 7. Decisión sobre el Cálculo de NDVI/NDBI

**Opción A** (implementada): calcular NDVI y NDBI **dentro de GEE** antes de exportar.  
**Opción B** (alternativa): exportar bandas crudas (B04, B08, B11) y calcular localmente con `rasterio`.

### Por qué se eligió Opción A (cálculo en GEE)

| Criterio | Opción A (GEE) | Opción B (local) |
|----------|---------------|-----------------|
| Tamaño de descarga | ~200-400 MB/composite (NDVI+NDBI+B02) | ~600 MB-1.2 GB/composite (3 bandas crudas) |
| Procesamiento local | Mínimo | `rasterio` + álgebra de bandas |
| Flexibilidad | Fija el índice en GEE | Permite recalcular índices sin re-descargar |
| Para el TFM | Suficiente — índices ya validados | Sobredimensionado |

**Banda B02 azul** se incluye igualmente en el export para:
1. Control de calidad visual (identificar si el composite tiene calima residual)
2. Referencia para documentar el filtrado

---

## 8. Estrategia de Relleno de NaN

Después del compositing, algunas zonas pueden tener píxeles `NaN` (sin ningún píxel válido en todo el trimestre). Esto es esperable principalmente en:
- Norte de Tenerife en Q3 (panza de burro + calima simultáneos)
- Zonas de alta cota (cumbres del Teide) con nieve/hielo

### Estrategia adoptada para el TFM

1. **Primero**: Gap-filling con el trimestre adyacente del mismo año (Q2 o Q4 para huecos de Q3).
2. **Si persiste**: Interpolación temporal lineal entre el mismo trimestre de año anterior y posterior.
3. **Documentar**: Generar mapa de cobertura de píxeles válidos por composite (% válidos vs NaN) → incluir en el TFM como análisis de calidad del dato.
4. **Justificación académica**: *"La zona norte de Tenerife presenta limitaciones inherentes en la disponibilidad de imágenes satelitales ópticas de calidad debidas a la 'panza de burro', fenómeno de estratocúmulos persistentes. Esta limitación se ha mitigado mediante compositing trimestral de mediana y gap-filling con periodos adyacentes, documentando la incertidumbre asociada en los municipios con mayor cobertura nubosa."*

---

## 9. Estructura de Archivos Generados

```
ingestion/copernicus/
├── download_sentinel2_gee.py    # Pipeline principal Sentinel-2 GEE
├── download_viirs.py            # Pipeline VIIRS (GEE + NASA LAADS)
├── DECISIONES_TECNICAS.md       # Este documento
└── README.md                    # Guía de uso rápido

data/bronce/spatial/satelite/
├── sentinel2/
│   ├── tenerife_ndvi_ndbi_2019_Q1.tif   # NDVI, NDBI, B02_blue
│   ├── tenerife_ndvi_ndbi_2019_Q2.tif
│   ├── ...
│   └── tenerife_ndvi_ndbi_2026_Q2.tif   # 30 composites total
└── viirs/
    ├── tenerife_viirs_2019_01.tif        # avg_rad (nW/cm²/sr)
    ├── ...
    └── tenerife_viirs_2026_06.tif        # 90 meses total

Azure Blob (bronce-raw):
├── satelite/sentinel2/year=XXXX/quarter=QN/tenerife_ndvi_ndbi_XXXX_QN.tif
└── satelite/viirs/year=XXXX/month=MM/tenerife_viirs_XXXX_MM.tif
```

---

## 10. Flujo hacia la Capa Plata y Oro

Los composites de la capa Bronce alimentan directamente los Issues de Fase 3:

```
Bronce (GeoTIFF)
    ↓ Issue #21 — preprocess_sentinel.py
Plata (GeoTIFF recortado a municipios + estadísticas)
    ↓ Issue #22 — calculate_ndvi.py
Oro → oro.ndvi_h3 (NDVI medio por hexágono H3 y por ENP, por trimestre)
    ↓ Issue #23 — calculate_ndbi.py
Oro → oro.ndbi_h3 (NDBI medio por hexágono H3, por trimestre)
    ↓ Issue #24 — process_viirs.py
Oro → oro.viirs_h3 (radianza nocturna por hexágono H3, por mes)
    ↓ Issue #25 — build_features.py
Oro → features para HDBSCAN clustering + MGWR regression
```

---

## 11. Referencias Técnicas

- **Sentinel-2 SCL**: ESA (2021). *Sentinel-2 Level-2A Algorithm Overview*. https://sentinels.copernicus.eu/
- **AOT Sen2Cor**: Müller-Wilm, U. et al. (2018). *Sentinel-2 Level 2A Prototype Processor*. ESA.
- **Calima en Canarias**: Prospero, J.M. et al. (2020). *Characterizing the temporal and spatial variability of African dust*. JGR Atmospheres.
- **Compositing mediana**: Hansen, M.C. et al. (2013). *High-Resolution Global Maps of 21st-Century Forest Cover Change*. Science.
- **GEE Sentinel-2**: https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S2_SR_HARMONIZED
- **GEE VIIRS**: https://developers.google.com/earth-engine/datasets/catalog/NOAA_VIIRS_DNB_MONTHLY_V1_VCMSLCFG
- **NASA VNP46A2**: https://ladsweb.modaps.eosdis.nasa.gov/missions-and-measurements/products/VNP46A2/
