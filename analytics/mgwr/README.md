# Regresión Espacial Multiescalar (MGWR), Índice PTNA y Scoring ESG (`analytics/mgwr/`)

Este módulo implementa el núcleo econométrico y geoespacial del **Bloque 5 del TFM**: la estimación del **Potencial Turístico No Aprovechado (PTNA)** mediante **MGWR** (*Multiscale Geographically Weighted Regression*) y el cálculo de índices de sostenibilidad territorial (**ESG**) a escala microespacial (H3) y mesomunicipal (31 municipios).

---

## 1. Fundamento Teórico y Necesidad del Enfoque Multiescalar

### 1.1. El Fracaso del Modelo Global OLS
Un modelo de regresión lineal tradicional por Mínimos Cuadrados Ordinarios (OLS) asume **estacionariedad espacial global**: presupone que el impacto de covariables como la distancia a la costa, la altitud o la vegetación sobre la densidad de alojamiento es constante en toda la isla.

En un territorio con orografía abrupta y microclimas contrastados como Tenerife, este supuesto es falso:
* En el sur árido (Adeje, Arona), la proximidad a la costa es el principal impulsor de densidad hotelera.
* En medianías y zonas altas (Vilaflor, El Sauzal), el turista busca tranquilidad, senderismo y naturaleza.

Al imponer un coeficiente uniforme, OLS genera estimaciones sesgadas y residuos fuertemente autocorrelacionados (**I de Moran = 0,3065**, $p = 0,0010$, permutación con 999 iteraciones).

### 1.2. Ventajas del Modelo MGWR
**MGWR** permite que los coeficientes de regresión varíen espacialmente de un punto a otro y, fundamentalmente, **asigna a cada variable explicativa su propio ancho de banda (*bandwidth*) óptimo**. De este modo, ciertas variables operan a escala casi global insular, mientras que otras responden estrictamente a microdinámicas de valle o costa.

---

## 2. Formulación Matemática del Índice PTNA

La variable dependiente a modelar ($Y$) es la **densidad de plazas de alojamiento regladas por $\text{km}^2$** en cada uno de los 2.579 hexágonos H3 de Tenerife, procedente del Registro General Turístico:

$$Y_i = \beta_0(u_i, v_i) + \sum_{k=1}^{14} \beta_k(u_i, v_i) X_{ik} + \varepsilon_i$$

Donde $(u_i, v_i)$ son las coordenadas del centroide de la celda $i$.

A partir de la predicción del modelo ($\hat{Y}_i$, valor esperado dadas las condiciones territoriales, ambientales y de movilidad), se calcula el **Índice PTNA**:

$$\text{PTNA}_i = \hat{Y}_i - Y_{i, \text{observado}}$$

* **$\text{PTNA} > 0$ (Oportunidad / Infraexplotado)**: El territorio posee atributos biofísicos y de conectividad que justifican mayor actividad turística que la oferta actualmente consolidada.
* **$\text{PTNA} < 0$ (Saturación / Overtourism)**: La presión hotelera y de vivienda vacacional excede la capacidad territorial explicable por los forzadores naturales, señalando riesgo de masificación.

---

## 3. Dataset y Variables Explicativas (14 Variables X)

Las 14 variables de entrada provienen de tablas maestras Gold ya consolidadas en el Data Warehouse:

| Dimensión | Variable | Descripción | Fuente Gold |
|---|---|---|---|
| **Satelital / Terreno** | `ndvi_medio` | Vigor vegetal satelital Sentinel-2 | `gold.gold_h3_master` |
| **Satelital / Terreno** | `altitud_media_m` | Elevación media del terreno (MDT) | `gold.gold_h3_master` |
| **Satelital / Terreno** | `slope_mean` | Pendiente media en grados | `gold.gold_h3_master` |
| **Satelital / Terreno** | `pct_area_enp` | Proporción de Espacio Natural Protegido | `gold.gold_h3_master` |
| **Satelital / Terreno** | `temp_media_anual` | Temperatura media anual estimada | `gold.gold_h3_master` |
| **Satelital / Terreno** | `lluvia_mm_anual` | Precipitación acumulada anual estimada | `gold.gold_h3_master` |
| **Equipamientos / POIs** | `n_restaurantes` | Densidad de establecimientos de restauración | `gold.gold_h3_master` |
| **Equipamientos / POIs** | `n_naturaleza` | Miradores, senderos y atractivos naturales | `gold.gold_h3_master` |
| **Equipamientos / POIs** | `n_cultura` | Monumentos, museos y patrimonio histórico | `gold.gold_h3_master` |
| **Accesibilidad** | `dist_hospital_km` | Distancia euclidiana al hospital más próximo | `gold.gold_h3_accesibilidad` |
| **Accesibilidad** | `dist_parada_cercana_m` | Proximidad a la parada de guaguas más cercana | `gold.gold_h3_accesibilidad` |
| **Accesibilidad** | `tiempo_aeropuerto_min` | Tiempo en coche al aeropuerto más próximo (ORS) | `gold.gold_h3_accesibilidad` |
| **Accesibilidad** | `dist_costa_km` | Distancia a la línea litoral | `gold.gold_h3_accesibilidad` |
| **Sentimiento** | `sentimiento_medio` | Puntuación media de reseñas turísticas | `gold.gold_h3_sentimiento` |

### Decisiones Metodológicas de Depuración:
1. **Exclusión de `viirs_medio` y `ndbi_medio`**: Luz nocturna y suelo edificado son colineales con la propia existencia de hoteles ($Y$). Incluirlas sobreajustaría el modelo con tautologías.
2. **Exclusión de tiempos redundantes**: `tiempo_teide_min` y `tiempo_polo_turistico_min` presentaban VIF entre 185 y 345 y correlación $> 0,98$ frente a `tiempo_aeropuerto_min`. Se mantuvo solo esta última por interpretabilidad.
3. **Imputación de `sentimiento_medio`**: Al estar restringido a las 410 celdas con alojamientos (15,9% de la isla), los valores ausentes se imputan mediante la mediana insular sin penalizar la cobertura global de las 2.579 celdas.

---

## 4. Resultados Empíricos y Diagnósticos Estadísticos (Checkpoint v3)

| Métrica de Validación | Modelo OLS Global (14 vars) | Modelo MGWR Definitivo | Diagnóstico Metodológico |
|---|:---:|:---:|---|
| **$R^2$ Global (no ajustado)** | 0,5444 | **0,8272** | +28,28 puntos porcentuales de varianza explicada |
| **I de Moran (Residuos)** | 0,3065 ($p = 0,0010$) | **0,0355** ($p = 0,0110$) | **Mitigación sustancial de dependencia espacial** (ambas significativas, 999 permutaciones) |

> 📌 **Interpretación académica rigurosa**: El MGWR mitiga sustancialmente la dependencia espacial residual (reduciendo la I de Moran de 0,3065 a 0,0355), si bien no la elimina por completo ($p = 0,0110$).

### Estructura de Anchos de Banda (*Bandwidths*):
* **Escalas Locales Empíricas**: El modelo ajustó anchos de banda genuinamente locales para variables con fuerte variabilidad física:
  * `altitud_media_m`: **bw = 138** celdas
  * `n_naturaleza`: **bw = 132** celdas
  * `n_restaurantes`: **bw = 177** celdas
  * `ndvi_medio`: **bw = 198** celdas
  * `n_cultura`: **bw = 960** celdas
* **Saturación Cuasi-Global (Hallazgo 12)**: 9 de las 14 variables (entre ellas `dist_costa_km` y `tiempo_aeropuerto_min`) saturaron en **bw ≈ 2.573** (99,8% de las 2.579 celdas). El propio modelo señala esto como pérdida de variación local genuina, no como hallazgo positivo de escala. Por ello, los hexágonos con valores extremos en estas covariables se penalizan en su nivel de confianza.

---

## 5. Control de Calidad y Clasificación de Confianza (`confianza_ptna`)

Para evitar falsos positivos en decisiones de inversión corporativa, el sistema asigna a cada hexágono una etiqueta de fiabilidad:
* **`confianza_ptna = 'normal'`**: 2.320 hexágonos (**90,0%** del territorio). Estimaciones plenamente robustas.
* **`confianza_ptna = 'baja'`**: 259 hexágonos (**10,0%** del territorio). Marcados por 3 criterios objetivos:
  1. Periferia geográfica insular con ventanas locales pequeñas.
  2. Inestabilidad por correlación compuesta de altitud en 2 clústeres geográficos.
  3. Saturación en anchos de banda cuasi-globales (percentiles 1/99 de las 9 variables saturadas).

---

## 6. Filtro Combinado PTNA × ESG (Interpretabilidad para TUI)

El cruce simultáneo entre oportunidad de expansión e idoneidad de sostenibilidad territorial define el filtro de **Oportunidades Ideales**:
$$\text{ptna\_score} > 0 \quad \text{AND} \quad \text{esg\_h3\_score} > 60$$

* **Identificación**: Identifica exactamente **247 hexágonos** (**9,6% del total insular**).
* **Control de Calidad**: 22 de ellos (8,9%) mantienen `confianza_ptna = 'baja'`, quedando documentados con salvedad.
* **Concentración Municipal**: Los 247 emplazamientos prioritarios se concentran en:
  * **Santa Cruz de Tenerife**: 34 hexágonos
  * **San Cristóbal de La Laguna**: 29 hexágonos
  * **La Orotava**: 22 hexágonos
  * **Buenavista del Norte**: 20 hexágonos
  * **El Tanque**: 19 hexágonos
  * **Los Realejos**: 18 hexágonos


---

## 6. Estructura de Scripts y Pipeline de Ejecución

```
analytics/mgwr/
├── docs/                                 # Bitácoras de investigación y metodología detallada
│   ├── contexto_maestro_proyecto_ptna.md
│   ├── contexto_maestro_repo.md
│   └── metodologia_bloque5_ptna.md
├── scripts/                              # Pipeline secuencial de cálculo
│   ├── _db.py                            # Conexión centralizada a PostgreSQL
│   ├── 00_create_sentimiento_table.py    # Generación de tabla satélite de sentimiento H3
│   ├── 01_build_dataset.py               # Extracción y ensamblado de las 14 variables X + Y
│   ├── 02_filter_nan.py                  # Control de nulos y verificación de esquema
│   ├── 03_validate_mgwr_synthetic.py     # Test sintético de calibración de kernel
│   ├── 04_run_model.py                   # Ajuste del modelo MGWR y serialización (.pkl)
│   ├── 05_ptna_score.py                  # Cálculo de residuos PTNA y flags de confianza
│   ├── 06_load_to_gold.py                # Carga de gold.h3_oportunidad en PostgreSQL
│   ├── 07_gold_h3_esg.py                 # Construcción del Score ESG H3 microespacial
│   ├── 08_gold_municipio_esg.py          # Agregación del Score ESG mesomunicipal (31 mun)
│   └── 09_gold_h3_oportunidad.py         # Consolidación final de la capa de oportunidades
└── README.md                             # Esta documentación técnica
```

### Ejecución del Pipeline:
```bash
python analytics/mgwr/scripts/01_build_dataset.py
python analytics/mgwr/scripts/04_run_model.py
python analytics/mgwr/scripts/05_ptna_score.py
python analytics/mgwr/scripts/06_load_to_gold.py
python analytics/mgwr/scripts/07_gold_h3_esg.py
python analytics/mgwr/scripts/08_gold_municipio_esg.py
python analytics/mgwr/scripts/09_gold_h3_oportunidad.py
```

---

## 7. Tablas Generadas en Azure PostgreSQL

1. **`gold.h3_oportunidad`**: 2.579 celdas H3 con `ptna_score`, densidad esperada vs observada y flag `confianza_ptna`.
2. **`gold.gold_h3_esg_v1`**: Índice ESG microespacial normalizado (0 a 100) combinando cobertura vegetal, confort bioclimático, presión turística y protección ambiental.
3. **`gold.gold_bloque5_municipio_esg_v1`**: Índice ESG mesomunicipal para los 31 municipios de Tenerife.
