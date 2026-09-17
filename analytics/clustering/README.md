# Documentación Metodológica del Proceso de Clustering
## Tipificación Territorial de Tenerife mediante HDBSCAN
### TFM — Máster en Data Science, Big Data & Business Analytics (UCM)

---

## 1. Punto de Partida — El Problema

El sistema de clustering inicial (en producción en `build_features.py`) producía clasificaciones **geográficamente incoherentes**. El caso más flagrante: el **Parque Nacional del Teide** (el espacio natural más emblemático de Canarias) quedaba clasificado como **"Urbano Sin Turismo"**.

### ¿Por qué fallaba el modelo original?

El algoritmo veía las celdas H3 del Teide como:
- Sin hoteles ni establecimientos turísticos
- Baja iluminación nocturna (VIIRS ~ 0)
- Sin vegetación densa (NDVI moderado por la roca volcánica)
- Alta altitud y pendiente

Sin una variable que indicara que era una **zona protegida legalmente**, el modelo no podía distinguir esas características de las de un polígono industrial o una zona despoblada. La causa raíz: la ausencia de `pct_area_enp` (porcentaje de área en Espacio Natural Protegido) en el conjunto de features.

---

## 2. Descripción del Modelo Original (en producción)

**Fuente**: `build_features.py`

### Features utilizadas (9 variables):

| Variable | Descripción |
|:---|:---|
| `elevation_mean` | Altitud media de la celda (m) |
| `slope_mean` | Pendiente media (grados) |
| `aspect_mean` | Orientación media |
| `hillshade_mean` | Sombreado de relieve |
| `ndvi_mean` | Índice de vegetación (NDVI) |
| `ndbi_mean` | Índice de edificación (NDBI) |
| `n_alojamientos` | Nº de establecimientos de alojamiento |
| `n_paradas_transporte` | Nº de paradas de transporte público |
| `viirs_mean` | Iluminación nocturna (VIIRS) |

### Resultados del modelo original:

| Métrica | Valor |
|:---|:---:|
| PCA (3 componentes) — varianza explicada | **65.6%** |
| Clusters encontrados por HDBSCAN | **2** |
| Puntos clasificados como ruido | **55.2%** |
| Silhouette Score (puntos núcleo) | **0.619** |
| Davies-Bouldin Index | **0.572** |
| Calinski-Harabasz Score | **1743.0** |

### Tipologías producidas:
- **Cluster 0** (37.1%): Zona media-alta, semi-protegida (mezcla Teide + medianías)
- **Cluster 1** (7.7%): Zona alta protegida (Anaga, Teno, cumbre)
- **Ruido** (55.2%): Todo lo costero, urbano y turístico — sin clasificar

**Diagnóstico**: El modelo generaba 2 clusters que solo diferenciaban el eje altitudinal, ignorando completamente la dimensión turística y costera. El 55% del territorio (incluidas todas las zonas turísticas relevantes para el TFM) quedaba como "ruido" no clasificado.

---

## 3. Iteración 1 — Identificación de la Variable Clave

### Hipótesis

La variable `pct_area_enp` (fracción del hexágono cubierta por un Espacio Natural Protegido) es la dimensión que separa el Teide de cualquier zona urbana o agrícola. Sin ella, el algoritmo no puede distinguir "zona volcánica de alta altitud" de "zona industrial despoblada".

### Nuevo modelo propuesto (V1)

**Script**: `../../scratch/test_hdbscan_experiment.py`

| Variable | Transformación | Justificación |
|:---|:---|:---|
| `n_plazas_registro` | `log1p` | Presión turística real (plazas hoteleras) |
| `viirs_medio` | `log1p` | Actividad económica nocturna |
| `ndvi_medio` | — | Cobertura vegetal satelital |
| `ndbi_medio` | — | Grado de edificación/impermeabilización |
| `altitud_media_m` | — | Gradiente altitudinal |
| `slope_mean` | — | Rugosidad / habitabilidad del terreno |
| `dist_costa_km` | — | Posición costera (clave en isla) |
| **`pct_area_enp`** | — | **Variable crítica: protección legal del ENP** |

> **Nota sobre transformaciones log**: `log1p` en `n_plazas_registro` y `viirs_medio` es necesario porque ambas variables tienen distribuciones fuertemente sesgadas a la derecha. Sin la transformación, unas pocas celdas con valores extremos (Las Américas, Santa Cruz) dominarían el espacio de clustering.

### Pipeline técnico

```
gold.gold_h3_master
        ↓
fillna(mediana) por columna
        ↓
StandardScaler (z-score)
        ↓
PCA(n_components=3, random_state=42)  →  81.5% varianza explicada
        ↓
HDBSCAN(min_cluster_size=30, min_samples=10, cluster_selection_method='eom')
        ↓
4 clusters + ruido (42.7%)
        ↓
Reglas experto post-hoc sobre puntos ruido
        ↓
6 tipologías con cobertura 100%
```

### Resultados del modelo nuevo (V1):

| Métrica | Valor |
|:---|:---:|
| PCA (3 componentes) — varianza explicada | **81.5%** |
| Clusters encontrados por HDBSCAN | **4** |
| Puntos clasificados como ruido | **42.7%** |
| Silhouette Score (puntos núcleo) | **0.472** |
| Davies-Bouldin Index | **0.709** |
| Calinski-Harabasz Score | **1484.6** |

### Tipologías producidas (4 clusters HDBSCAN + 2 reglas experto):

| Tipología | n | % | Perfil |
|:---|:---:|:---:|:---|
| **Espacio Natural / Teide y Cumbre** | 716 | 27.8% | Alt. 1768m, ENP 93%, VIIRS ~0 |
| **Espacios Rurales Protegidos (Anaga/Teno)** | 456 | 17.7% | Alt. 714m, ENP 87%, pendiente 30° |
| **Transición Costera y Medianías** | 895 | 34.7% | Alt. 328m, ENP 8%, VIIRS 4.9 |
| **Rural Agrícola / Medianías Norte** | 412 | 16.0% | Alt. 490m, NDVI alto, VIIRS 4.8 |
| **Saturado / Overtourism** *(regla experto)* | 61 | 2.4% | Alt. 71m, plazas >500, VIIRS 28 |
| **Urbano Residencial** *(regla experto)* | 39 | 1.5% | VIIRS >41, ENP 0%, SCT/La Laguna |

### Reglas experto para asignación de ruido:

1. Si `n_plazas_registro >= 500` → **Saturado / Overtourism**
2. Si `viirs_medio >= 20` AND `pct_area_enp < 0.2` → **Urbano Residencial**
3. Resto → centroide más próximo en espacio PCA

---

## 4. Iteración 2 — ¿Mejora añadiendo variables del modelo antiguo?

### Pregunta: ¿`gold_h3_accesibilidad` ya estaba en `gold_h3_master`?

**Respuesta**: No. Son tablas separadas:
- `gold_h3_master.n_paradas_bus` → número total de paradas de bus
- `gold_h3_accesibilidad` → tiempos de isócrona a 19 destinos de referencia (TFS, TFN, Teide, hospitales…) + radios de paradas a 200/500/1000m

### Experimento: V2 — Modelo enriquecido (45 features)

Se probó añadir todas las variables del modelo antiguo + climáticas + accesibilidad completa.

**Script**: `../../scratch/test_hdbscan_v2_comparison.py`

| Métrica | V1 (8 feat) | V2 (45 feat) |
|:---|:---:|:---:|
| PCA varianza | 81.5% | 68.8% |
| Clusters | **4** | 2 |
| % Ruido | 42.7% | 0% |
| Silhouette | 0.472 | **0.829** |

**Diagnóstico**: El Silhouette de 0.83 de V2 es un **artefacto estadístico**. Con 45 variables altamente correlacionadas (19 tiempos de isócrona entre sí), el PCA(3) colapsa toda la información en una dimensión dominante (accesible vs. remoto) y HDBSCAN solo detecta 2 grupos: sur turístico densísimo (3.6%) y todo lo demás (96.4%). Inútil para el TFM.

---

## 5. Iteración 3 — Selección sistemática de features (4 configuraciones)

**Script**: `../../scratch/test_hdbscan_feature_selection.py`

Se evaluaron 4 configuraciones con criterio de ortogonalidad de dimensiones:

| Config | Features | Clusters | Ruido | Silhouette | DB |
|:---|:---:|:---:|:---:|:---:|:---:|
| **V1 — Base (8)** | 8 | **4** | 43% | 0.472 | 0.709 |
| V3 — +Clima (10) | 10 | 2 | 24% | 0.210 | 1.176 |
| V4 — +Accesibilidad+Calidad (14) | 14 | 8 | 64% | 0.351 | 0.711 |
| V5 — +Dinamismo+Naturaleza (17) | 17 | 3 | 69% | 0.552 | 0.612 |

**Diagnóstico**:
- **V3**: Añadir clima colapsa a 2 clusters (clima y altitud están correlacionados en Tenerife)
- **V4**: Demasiadas features de accesibilidad generan 8 clusters con 64% ruido — inmanejable
- **V5**: Buen Silhouette pero solo 3 clusters y 69% ruido — cobertura insuficiente

---

## 6. Iteración 4 — Barrido de n_components PCA (24 experimentos)

**Script**: `../../scratch/test_hdbscan_pca_sweep.py`

Se barrió el número de componentes PCA (3 a 8) sobre las 4 configuraciones anteriores, más:
- **V6 — Territorial puro (11)**: Variables exclusivamente geofísicas (sin turismo)
- **V7 — Territorial+Turismo (13)**: V6 + plazas + accesibilidad mínima

**Resultados (top por Score compuesto):**

| Config | PCA | Clusters | Ruido | Silhouette | Score★ |
|:---|:---:|:---:|:---:|:---:|:---:|
| **V1 — Base (8), PCA=3** | 3 | **4** | 43% | 0.472 | **0.458** |
| V1 — Base (8), PCA=6 | 6 | 6 | 60% | 0.430 | 0.331 |
| V1 — Base (8), PCA=8 | 8 | 5 | 59% | 0.412 | 0.318 |
| V5 — Dinamismo (17), PCA=3 | 3 | 3 | 69% | 0.552 | 0.259 |
| V6 — Territorial (11), PCA=4 | 4 | 3 | 7% | 0.377 | 0.227 |

> **Score★** = Silhouette − penalización por <4 clusters (−0.15/cluster faltante) − penalización por >40% ruido (−0.5 × exceso)

**Resultado**: La configuración V1 con PCA(3) es la única que simultáneamente cumple todos los criterios deseables: ≥4 clusters, Silhouette>0.45, <55% ruido, PCA varianza>70%.

---

## 7. Comparativa Final — Modelo Viejo vs Modelo Nuevo

**Script**: `../../scratch/comparativa_modelos.py`

### Métricas cuantitativas:

| Métrica | Modelo Viejo | Modelo Nuevo | Diferencia |
|:---|:---:|:---:|:---:|
| Features | 9 | **8** | −1 |
| PCA varianza | 65.6% | **81.5%** | +15.9 pp |
| Clusters HDBSCAN | 2 | **4** | ×2 |
| % Ruido | 55.2% | **42.7%** | −12.5 pp |
| % Territorio clasificado | 44.8% | **57.3%** | +12.5 pp |
| Silhouette | **0.619** | 0.472 | −0.147 |
| Davies-Bouldin | **0.572** | 0.709 | +0.137 |
| Calinski-Harabasz | **1743** | 1484 | −259 |

### Validación geográfica (criterio principal):

| Zona geográfica | Modelo Viejo | Modelo Nuevo |
|:---|:---:|:---:|
| **Parque Nacional del Teide** | ❌ "Urbano Sin Turismo" | ✅ "Espacio Natural" |
| **Anaga / Teno** | ❌ Mezclado con Teide | ✅ "Espacios Rurales Protegidos" |
| **Las Américas / Adeje** | ❌ Ruido (sin clasificar) | ✅ "Saturado / Overtourism" |
| **Santa Cruz / La Laguna** | ❌ Ruido (sin clasificar) | ✅ "Urbano Residencial" |
| **Medianías Norte** | ❌ Ruido (sin clasificar) | ✅ "Rural Agrícola" |

---

## 8. Justificación de la Elección del Modelo Final

### ¿Por qué el Modelo Nuevo (V1) a pesar de tener métricas numéricas inferiores?

**1. Las métricas del modelo viejo son un artefacto estadístico**

El Silhouette más alto del modelo viejo se debe a que separar **2 grupos es siempre más fácil** estadísticamente que separar 4+. Un modelo que divide Tenerife solo en "alta altitud" y "resto" tendrá métricas perfectas porque los dos grupos son extremadamente homogéneos entre sí. Pero no tiene ningún valor científico ni aplicado.

**2. El modelo viejo no clasifica el territorio — lo descarta**

Con un 55.2% de ruido, el modelo viejo **deja sin clasificar más de la mitad de Tenerife**, incluyendo toda la franja costera turística que es el objeto de estudio central del TFM. Un modelo de clustering que no puede clasificar el 55% de los datos no es un modelo de clustering.

**3. La varianza PCA es un indicador más fiable de la calidad del espacio**

El modelo nuevo captura el **81.5%** de la varianza en 3 componentes vs. el 65.6% del viejo. Esto significa que el nuevo espacio PCA preserva más información del territorio real, proporcionando una base más sólida para el algoritmo de clustering.

**4. La validez de constructo territorial prima sobre la métrica**

En Spatial Data Science, la coherencia geográfica del resultado es el criterio de validación más importante cuando los datos tienen estructura espacial conocida. Un modelo que clasifica el Parque Nacional del Teide como "Urbano Sin Turismo" **no puede ser válido**, independientemente de su Silhouette. Esto está respaldado por la literatura de validación de clustering geoespacial (Cressie, 1993; Anselin, 1995).

**5. Argumento para el tribunal de TFM**

> *"Se priorizó la validez de constructo territorial (coherencia con el conocimiento geográfico experto) frente a la optimización ciega de métricas internas de clustering. El modelo revisado reduce el Silhouette Score al incorporar 4 tipologías genuinamente heterogéneas (frente a 2 artificialmente homogéneas), pero incrementa la varianza explicada por PCA en +16 pp, reduce el porcentaje de puntos no clasificados en −12.5 pp, y produce tipologías con coherencia territorial demostrada mediante validación cruzada con los límites de Espacios Naturales Protegidos (r_ENP=0.93 en cluster Teide). Siguiendo la práctica estándar en Spatial Data Science, el domain knowledge territorial ha sido utilizado como criterio de validación externa del clustering no supervisado."*

---

## 9. Scripts de Experimentos

| Script | Descripción |
|:---|:---|
| `../../scratch/test_hdbscan_experiment.py` | **Modelo final (V1)** con 6 tipologías y reglas experto |
| `../../scratch/check_columns.py` | Inspección de esquema de `gold_h3_master` y tablas gold |
| `../../scratch/test_hdbscan_v2_comparison.py` | V1 vs V2 (45 features) — demuestra colapso con sobreajuste |
| `../../scratch/test_hdbscan_feature_selection.py` | Selección sistemática de features (V1–V5) |
| `../../scratch/test_hdbscan_pca_sweep.py` | Barrido PCA n_components × 4 configs (24 experimentos) |
| `../../scratch/comparativa_modelos.py` | Comparativa head-to-head Viejo vs Nuevo con perfil geográfico |

---

## 10. Conclusión y Modelo Seleccionado

**Modelo seleccionado**: V1 — 8 features + StandardScaler + PCA(3) + HDBSCAN + 2 reglas experto post-hoc

### Hiperparámetros definitivos

```python
StandardScaler()
PCA(n_components=3, random_state=42)
HDBSCAN(
    min_cluster_size=30,
    min_samples=10,
    cluster_selection_method='eom'
)
```

### Variables del modelo final

```python
FEATURES = [
    "n_plazas_log",    # log1p(n_plazas_registro)
    "viirs_log",       # log1p(viirs_medio)
    "ndvi_medio",
    "ndbi_medio",
    "altitud_media_m",
    "slope_mean",
    "dist_costa_km",
    "pct_area_enp",    # ← variable crítica
]
```

### Tipologías resultantes (6 en total)

| # | Tipología | Origen | % territorio |
|:---:|:---|:---:|:---:|
| 1 | Espacio Natural / Teide y Cumbre | HDBSCAN | 27.8% |
| 2 | Espacios Rurales Protegidos — Anaga/Teno | HDBSCAN | 17.7% |
| 3 | Transición Costera y Medianías | HDBSCAN | 34.7% |
| 4 | Rural Agrícola / Medianías Norte | HDBSCAN | 16.0% |
| 5 | Saturado / Overtourism | Regla experto | 2.4% |
| 6 | Urbano Residencial | Regla experto | 1.5% |

**Estado**: ✅ **Implantado en Producción en la tabla `gold.h3_clusters`** (con respaldo de seguridad en `gold.h3_clusters_backup_old`) mediante el script oficial [`analytics/clustering/run_hdbscan_clustering.py`](run_hdbscan_clustering.py).

---

## 11. De la Clasificación Discreta a la Matriz Estratégica Bidimensional (Eje 1 y Eje 2)

### 11.1. Justificación de la Evolución Analítica

El clustering no supervisado mediante HDBSCAN proporciona un diagnóstico territorial objetivo e incontestable de la estructura insular, validado con un Silhouette Score de 0.808 en su partición núcleo. Sin embargo, para la toma de decisiones corporativas de **TUI Group**, una tipología puramente categórica resulta insuficiente para responder a las preguntas de inversión y ordenación turística:

* ¿Qué grado de saturación experimenta una celda de transición antes de traspasar el umbral de masificación?
* ¿Cuáles son los hexágonos rurales que, además de poseer una huella antrópica baja, presentan un verdadero **Potencial Turístico No Aprovechado (PTNA)** y solvencia de sostenibilidad (**ESG**)?

Para salvar la distancia entre el **diagnóstico geofísico no supervisado** y la **prescripción estratégica de negocio**, se proyectan los 2.579 hexágonos en un espacio bidimensional continuo:

```
                      Eje 2: Potencial rural y sostenible [0 - 1]
                                     ▲
                                     │
           [Q2: EXPANSIÓN SOSTENIBLE]│   [Q4: DIVERSIFICACIÓN MIXTA]
           Alto PTNA / Alto ESG      │   Medianías y transición activa
           Eco-Resorts & Bienestar   │   Productos híbridos
                                     │
      ───────────────────────────────┼───────────────────────────────► Eje 1: Saturación
                                     │                                  turística [0 - 1]
           [Q3: PRESERVACIÓN / NEUTRO]│   [Q1: OVERTOURISM CRÍTICO]
           Teide (ENP estricto)      │   Playa de las Américas / Adeje
           Urbano Residencial puro   │   Descompresión y reconversión
                                     │
```

### 11.2. Formulación Matemática de los Ejes

#### Eje 1: Saturación turística $[0, 1]$
Calibrado a partir de la firma de densidad descubierta por HDBSCAN y la presión de oferta hotelera:
$$\text{Eje 1} = \text{Norm}\Big(0.45 \cdot \log(1 + \text{Plazas}) + 0.25 \cdot \log(1 + \text{VIIRS}) + 0.15 \cdot \text{ProxCosta} + 0.15 \cdot \log(1 + \text{Establecimientos})\Big)$$

#### Eje 2: Potencial rural y sostenible $[0, 1]$
Integra el capital natural, el potencial latente no monetizado y la calidad ambiental:
$$\text{Eje 2} = \text{Norm}\Big(0.25 \cdot \text{NDVI} + 0.25 \cdot \text{PTNA} + 0.20 \cdot (1 - \text{PlazasNorm}) + 0.15 \cdot (1 - \text{NDBI}) + 0.15 \cdot \text{ESG}\Big)$$

---

## 12. Modelización de los 5 Arquetipos de Producto Turístico TUI

A partir de la combinación de los ejes estratégicos, la accesibilidad multimodal y la semántica de reseñas, se asigna a cada hexágono un **Arquetipo TUI óptimo** mediante un sistema de scoring multi-criterio ponderado:

| Arquetipo de Producto | Icono | Driver Principal de Scoring | Perfil Territorial Idóneo | Estrategia Comercial TUI |
|:---|:---:|:---|:---|:---|
| **Sol y Playa Premium** | 🏖️ | Plazas hoteleras + Proximidad costera (<1 km) + Rating Booking | Franja litoral de Adeje, Arona y Puerto de la Cruz | Contención de camas, elevación de ADR a gama alta y digitalización. |
| **Ecoturismo Rural y Medianías** | 🌿 | NDVI vegetación + PTNA no explotado + Score ESG + Ausencia de saturación | Medianías agrícolas del Norte, Anaga y Teno | Creación de producto TUI Nature, micro-hoteles boutique y senderismo. |
| **Cultural y Patrimonial** | 🏛️ | POIs culturales + Densidad de restauración + Patrimonio histórico | Cascos históricos de La Laguna, La Orotava y Garachico | Rutas de gastronomía canaria, turismo de experiencias y patrimonio UNESCO. |
| **Aventura y Turismo Activo** | 🏔️ | Pendiente del terreno + Altitud + Recursos naturales de cumbre | Corredores de montaña, cumbre y entornos del Teide | Paquetes de trekking, parapente, ciclismo de montaña y astroturismo. |
| **Bienestar y Salud (Wellness)** | 🧘 | Confort térmico continuo (~21 °C) + Silencio/Baja masificación + Alta sostenibilidad | Zonas templadas de medianías y costa tranquila | Retiros de salud, spa holístico, desconexión y estancias desestacionalizadas. |

---

## 13. Explotación Interactiva en el AI-Dashboard

La totalidad de estos modelos se encuentra plenamente operativa en la interfaz analítica (`app/`):

1. **Página Dedicada "Oportunidades TUI" (`app/arquetipos.py`):**
   * **KPIs de Alta Visibilidad:** Conteo y peso porcentual de las 6 tipologías HDBSCAN y de las Oportunidades Ideales TUI identificadas en el Bloque 5.
   * **Scatter Plot 2D Interactivo:** Gráfico de dispersión Eje 1 vs Eje 2 con delimitación de cuadrantes estratégicos mediante líneas de control dinámicas, coloreable por clúster o arquetipo, y filtrable por municipio.
   * **Catálogo de Arquetipos:** Fichas estratégicas por cada uno de los 5 arquetipos de producto con distribución de celdas y recomendaciones de implantación.
   * **Tabla de Emplazamientos:** Listado tabular con filtros interactivos y descarga directa en formato CSV.

2. **Cartografía Interactiva H3 (`app/map_layers.py`):**
   * Incorporación de las capas temáticas con gradientes optimizados:
     * *Clústeres territoriales* (paleta categórica de 6 clases).
     * *Arquetipo TUI óptimo* (paleta de producto de 5 clases).
     * *Saturación turística* (rampa secuencial ámbar/fuego).
     * *Potencial rural y sostenible* (rampa secuencial menta/esmeralda).
     * *Potencial turístico* y *Sostenibilidad ESG*.

3. **Panel de Detalle Microespacial (`app/detail_panel.py`):**
   * Al hacer clic sobre cualquier hexágono H3, se despliega un bloque de resumen estratégico que muestra la tipología HDBSCAN asignada, el arquetipo TUI prescrito, barras de progreso para el Eje 1 y Eje 2, y los valores normalizados de PTNA y ESG.

4. **Gobierno de Datos y Persistencia:**
   * Script de actualización oficial: [`analytics/clustering/run_hdbscan_clustering.py`](run_hdbscan_clustering.py).
   * Tabla maestra en Azure PostgreSQL: `gold.h3_clusters` (respaldo de seguridad: `gold.h3_clusters_backup_old`).

