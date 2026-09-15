# Metodología — Bloque 5: Índice PTNA (Potencial Turístico No Aprovechado)

*Resumen de metodología para lectura del repositorio y evaluación del TFM. El detalle completo del
proceso de investigación, depuración y las decisiones intermedias vive en la bitácora de trabajo
interna: `analytics/mgwr/docs/contexto_maestro_proyecto_ptna.md`.*

## 1. Qué es el PTNA y el modelo MGWR

El PTNA (Potencial Turístico No Aprovechado) es un índice a nivel de hexágono H3 que mide la
diferencia entre la oferta de alojamiento turístico que un territorio *debería* tener dadas sus
condiciones geográficas, climáticas y de accesibilidad, y la oferta que efectivamente tiene hoy. Un
PTNA positivo señala una zona con condiciones favorables pero infraexplotada — una oportunidad de
inversión. Un PTNA negativo señala una zona ya sobre-explotada en relación a lo que su territorio
"justifica", con el riesgo de saturación que eso implica.

Para estimar ese valor "esperado" se usa MGWR (Multiscale Geographically Weighted Regression), una
regresión que, a diferencia de una regresión lineal clásica, permite que la relación entre cada
variable explicativa y la variable a explicar cambie de un punto del territorio a otro, y que cada
variable lo haga a su propia escala geográfica (algunas influyen de forma muy local, otras casi de
forma global en toda la isla). Esto es clave en un territorio tan heterogéneo como Tenerife, donde el
efecto de por ejemplo la altitud o la distancia a la costa sobre la densidad turística no es el mismo
en el sur árido que en el norte húmedo.

La variable a explicar (Y) es `densidad_plazas_km2` (plazas de alojamiento regladas por km² de cada
hexágono, Registro Oficial de Turismo). El PTNA se calcula como
`Valor_esperado_por_MGWR − Valor_observado_real`: el residuo del modelo, con signo, interpretado como
oportunidad (positivo) o saturación (negativo).

## 2. Dataset final: 14 variables X

El dataset final usa 14 variables explicativas, agrupadas en 4 dimensiones. Todas provienen de tablas
Gold ya consolidadas — no se calculó nada ad-hoc para el modelo.

| Dimensión | Variable | Fuente (tabla Gold) |
|---|---|---|
| Satelital / terreno | `ndvi_medio` | `gold.gold_h3_master` |
| Satelital / terreno | `altitud_media_m` | `gold.gold_h3_master` |
| Satelital / terreno | `slope_mean` | `gold.gold_h3_master` |
| Satelital / terreno | `pct_area_enp` | `gold.gold_h3_master` |
| Satelital / terreno | `temp_media_anual` | `gold.gold_h3_master` |
| Satelital / terreno | `lluvia_mm_anual` | `gold.gold_h3_master` |
| POIs | `n_restaurantes` | `gold.gold_h3_master` |
| POIs | `n_naturaleza` | `gold.gold_h3_master` |
| POIs | `n_cultura` | `gold.gold_h3_master` |
| Accesibilidad | `dist_hospital_km` | `gold.gold_h3_accesibilidad` |
| Accesibilidad | `dist_parada_cercana_m` | `gold.gold_h3_accesibilidad` |
| Accesibilidad | `tiempo_aeropuerto_min` | `gold.gold_h3_accesibilidad` |
| Accesibilidad | `dist_costa_km` | `gold.gold_h3_accesibilidad` |
| Sentimiento | `sentimiento_medio` | `gold.gold_h3_sentimiento` |

## 3. Decisiones metodológicas relevantes

**Exclusión de `viirs_medio` y `ndbi_medio`.** Ambas están disponibles en `gold_h3_master`, pero se
excluyeron del modelo por ser proxies casi directos de la variable Y: luz nocturna y sellado del suelo
son, en la práctica, otra forma de medir densidad de edificación turística/urbana. Incluirlas habría
inflado artificialmente el ajuste del modelo sin aportar poder explicativo real e independiente.

**Exclusión de `tiempo_teide_min` y `tiempo_polo_turistico_min`.** El plan original proponía 3
variables de tiempo de viaje (`tiempo_aeropuerto_min`, `tiempo_teide_min`,
`tiempo_polo_turistico_min`). Se descartaron 2 de las 3 por multicolinealidad severa: VIF entre
185 y 345 (muy por encima del umbral aceptado de 10) y correlación superior a 0.98 entre las tres. En
una isla del tamaño de Tenerife, las tres miden esencialmente la misma dimensión — "qué tan lejos del
interior/costa está el hexágono" — así que se conservó solo `tiempo_aeropuerto_min`, la más
interpretable para el caso de negocio.

**Tratamiento de `sentimiento_medio`.** Esta variable solo tiene cobertura real en el 15.9% de los
hexágonos (410 de 2579) — el resto no tiene ninguna reseña geolocalizada cerca (zonas sin alojamiento
turístico). Por eso se excluyó explícitamente del filtro de calidad de >50% NaN que sí aplica al resto
de variables (incluirla habría descartado incorrectamente la mayoría del dataset por un problema de
cobertura, no de calidad). Para el ajuste del modelo, los valores faltantes se imputan con la mediana,
igual que el resto de variables.

**Casos de `confianza_ptna = 'baja'` (107/2579, 4.1%).** Se marcan por dos criterios independientes,
no excluyentes entre sí:
1. **Periferia geográfica + bandwidth chico**: hexágonos en el borde del rango geográfico de la isla
   cuyo coeficiente de `dist_costa_km` o `dist_parada_cercana_m` cae en el percentil 1 o 99 — zonas
   donde el modelo local tiene pocos vecinos para estimar con solidez.
2. **Colinealidad moderada de `altitud_media_m` en 2 clústeres geográficos**: `altitud_media_m` quedó
   en el modelo con un VIF moderado (13.4, por debajo del umbral de severidad) pero actúa como proxy
   compuesto de varias dimensiones geográficas relacionadas (litoralidad, clima, protección ambiental,
   accesibilidad). Esto genera coeficientes inestables en 2 zonas geográficas compactas y bien
   pobladas (no periféricas), que se marcan aparte del criterio anterior.

## 4. Resultado

Distribución de `ptna_score` sobre los 2579 hexágonos (índice sin acotar, puede ser negativo):

| Percentil | Valor |
|---|---|
| Mínimo | −3.983 |
| P10 | −52 |
| P25 | −15 |
| Mediana (P50) | +1.6 |
| P75 | +24 |
| P90 | +95 |
| P95 | +203 |
| P99 | +610 |
| Máximo | +7.370 |

La distribución es muy asimétrica hacia la derecha: la mediana está cerca de 0 (como se espera de un
residuo), pero una cola larga de hexágonos con oportunidad alta concentra la mayor parte de la señal
útil para inversión.

**Top de oportunidades con `confianza_ptna = 'normal'`** (hallazgo presentable sin salvedades):

| # | Hexágono | Municipio | PTNA score |
|---|---|---|---|
| 1 | `88344cdb1dfffff` | Puerto de la Cruz | 3.285,2 |
| 2 | `88344125d1fffff` | Adeje | 1.315,5 |
| 3 | `88344cdb57fffff` | Puerto de la Cruz | 1.304,2 |
| 4 | `883441254dfffff` | Guía de Isora | 1.265,6 |
| 5 | `88344125cbfffff` | Adeje | 1.077,4 |
| 6 | `88344c5015fffff` | Granadilla de Abona | 1.077,0 |
| 7 | `88344cd84bfffff` | La Orotava | 1.033,0 |
| 8 | `88344124e9fffff` | Adeje | 935,4 |
| 9 | `883441249bfffff` | Arona | 775,6 |
| 10 | `88344cda0bfffff` | Santa Úrsula | 755,0 |

**Nota sobre los casos de confianza baja:** si se mira el top 10 sin filtrar por confianza, 4 de los
10 hexágonos son `confianza_ptna = 'baja'` — incluido el valor más alto de todo el dataset
(`88344c5a51fffff`, Arona, PTNA = 7.370). Estos casos no deben presentarse como oportunidades de
inversión sin la salvedad correspondiente: su coeficiente es estadísticamente menos estable que el del
resto del dataset, por los motivos descritos en la sección 3, y requieren una lectura más cualitativa
antes de usarse para una decisión.

## 5. Limitaciones conocidas

- **4 variables mesomunicipales sin ingesta real**: `renta_bruta_irpf`, `poblacion_extranjera`,
  `empresas_ss` y `parque_vehiculos_1000hab` no tienen ninguna tabla silver/gold que las contenga
  todavía en el repositorio.
- **Posible tercer clúster de inestabilidad sin investigar a fondo**: al margen de los 2 clústeres de
  `altitud_media_m`, un corredor geográfico compacto de 26 hexágonos (Santa Úrsula – La Victoria de
  Acentejo – La Matanza de Acentejo – El Sauzal) muestra coeficientes de `dist_parada_cercana_m` casi
  congelados entre sí, sin ser periféricos según el criterio actual. No se investigó el origen
  (VIF/vecindad local) en profundidad — queda pendiente para una futura revisión.
- **Sin diagnósticos `ENP_j`/`CCT`**: los diagnósticos de significancia estadística local de MGWR
  (`ENP_j`, criterio de comparación de modelos `CCT`) no se calcularon. Su costo computacional es alto
  (más que duplica el tiempo de ejecución del ajuste) frente al beneficio esperado para los objetivos
  actuales del TFM, así que se dejaron fuera por decisión de costo/beneficio, no por imposibilidad
  técnica.
