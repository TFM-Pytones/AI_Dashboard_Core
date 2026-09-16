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

**Casos de `confianza_ptna = 'baja'` (259/2579, 10.0%).** Se marcan por tres criterios independientes,
no excluyentes entre sí:
1. **Periferia geográfica + bandwidth chico**: hexágonos en el borde del rango geográfico de la isla
   cuyo coeficiente de `dist_costa_km` o `dist_parada_cercana_m` cae en el percentil 1 o 99 — zonas
   donde el modelo local tiene pocos vecinos para estimar con solidez.
2. **Colinealidad moderada de `altitud_media_m` en 2 clústeres geográficos**: `altitud_media_m` quedó
   en el modelo con un VIF moderado (13.4, por debajo del umbral de severidad) pero actúa como proxy
   compuesto de varias dimensiones geográficas relacionadas (litoralidad, clima, protección ambiental,
   accesibilidad). Esto genera coeficientes inestables en 2 zonas geográficas compactas y bien
   pobladas (no periféricas), que se marcan aparte del criterio anterior.
3. **Bandwidth casi-global (Hallazgo 12)**: al inspeccionar `bandwidths_full` del checkpoint MGWR v3
   ajustado, 9 de las 14 variables X (`slope_mean`, `dist_hospital_km`, `pct_area_enp`,
   `temp_media_anual`, `lluvia_mm_anual`, `dist_parada_cercana_m`, `tiempo_aeropuerto_min`,
   `dist_costa_km`, `sentimiento_medio`) quedaron con un bandwidth óptimo de 2573 vecinos sobre un
   techo de N=2579 (99.8% del dataset) — muy por encima del umbral de saturación fijado en el 90% de
   N (2321.1 vecinos). Las otras 5 variables (`ndvi_medio`=198, `altitud_media_m`=138,
   `n_restaurantes`=177, `n_naturaleza`=132, `n_cultura`=960) quedaron con ventanas mucho más chicas
   y genuinamente locales. Este criterio es **conceptualmente distinto** a los dos anteriores: no es
   "coeficiente ruidoso por pocos vecinos" (criterio 1, Hallazgo 4 — bandwidth chico) ni "coeficiente
   inestable por colinealidad con ventana local real" (criterio 2, Hallazgo 11). Con un bandwidth casi
   global, el kernel adaptativo del MGWR promedia casi toda la isla para estimar el coeficiente local
   de esa variable en ese hexágono — la varianza del estimador debería ser *baja* (todo lo contrario de
   un problema de inestabilidad), pero el coeficiente deja de representar una relación local genuina:
   el modelo lo trató, en la práctica, como un efecto casi global constante, y el valor extremo en
   percentil 1/99 solo refleja el 0.2% de vecinos que sí cambia según dónde esté el hexágono. Por el
   mismo motivo **no se aplica el filtro de periferia** a este criterio (criterios 1 y 2 solo excluyen
   o incluyen según cercanía al borde del mapa): el vecindario de estas 9 variables es casi toda la
   isla, exactamente lo opuesto de "pocos vecinos reales concentrados de un lado" — exigir periferia
   aquí descartaría el hallazgo por el motivo equivocado. Cifras: 217/2579 hexágonos (8.4%) caen en
   percentil 1/99 de al menos una de estas 9 variables; de esos, 152 no estaban ya cubiertos por los
   criterios 1 y 2, y son los que este tercer criterio suma de nuevo a `confianza_ptna='baja'` (de 107
   a 259 en total). Implementado en `calcular_h3_confianza_baja_bandwidth`,
   `analytics/mgwr/scripts/05_ptna_score.py`.

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

**Top de oportunidades con `confianza_ptna = 'normal'`** (hallazgo presentable sin salvedades; tabla
actualizada tras sumar el criterio de bandwidth casi-global — Hallazgo 12, sección 3 — que reclasificó
varios de los hexágonos que antes encabezaban esta lista, entre ellos los 3 primeros de la versión
previa):

| # | Hexágono | Municipio | PTNA score |
|---|---|---|---|
| 1 | `88344125d1fffff` | Adeje | 1.315,5 |
| 2 | `883441254dfffff` | Guía de Isora | 1.265,6 |
| 3 | `88344125cbfffff` | Adeje | 1.077,4 |
| 4 | `88344124e9fffff` | Adeje | 935,4 |
| 5 | `883441249bfffff` | Arona | 775,6 |
| 6 | `88344124e1fffff` | Adeje | 737,6 |
| 7 | `88344122c7fffff` | Santiago del Teide | 679,2 |
| 8 | `88344124e7fffff` | Adeje | 668,2 |
| 9 | `88344125ddfffff` | Adeje | 650,2 |
| 10 | `88344cdb17fffff` | Puerto de la Cruz | 639,0 |

**Nota sobre los casos de confianza baja:** si se mira el top 10 sin filtrar por confianza, 7 de los
10 hexágonos son `confianza_ptna = 'baja'` (antes del Hallazgo 12 eran 4/10) — incluido el valor más
alto de todo el dataset (`88344c5a51fffff`, Arona, PTNA = 7.370, ya marcado `baja` desde antes de este
hallazgo). Estos casos no deben presentarse como oportunidades de inversión sin la salvedad
correspondiente: su coeficiente es estadísticamente menos estable — o, en el caso del criterio de
bandwidth casi-global, no representativo de una relación local genuina — que el del resto del dataset,
por los motivos descritos en la sección 3, y requieren una lectura más cualitativa antes de usarse para
una decisión.

## 5. Limitaciones conocidas

- **4 variables mesomunicipales sin ingesta real**: `renta_bruta_irpf`, `poblacion_extranjera`,
  `empresas_ss` y `parque_vehiculos_1000hab` no tienen ninguna tabla silver/gold que las contenga
  todavía en el repositorio. Ver sección 6 para el reemplazo definitivo aplicado.
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

## 6. Índice ESG Territorial — dimensión mesomunicipal (Subtarea 5.3)

Complementa al ESG H3 microespacial (`gold.gold_h3_esg_v1`, construido sobre hexágonos individuales
para filtrar oportunidades de inversión puntual). La dimensión mesomunicipal opera a escala de
municipio (31 municipios de Tenerife) y está pensada para diagnóstico de políticas públicas, capacidad
de carga y resiliencia territorial — no para decisiones de inversión hexágono a hexágono.

Tabla final: `gold.gold_bloque5_municipio_esg_v1` (31 filas, una por municipio; script
`analytics/mgwr/scripts/08_gold_municipio_esg.py`), tabla satélite propia del Bloque 5, sin modificar
`gold_municipio_master` ni ningún modelo dbt de otro bloque — mismo criterio ya usado para
`gold.gold_bloque5_municipio_anual_extra`/`_mensual_extra`.

### 6.1 Por qué se reemplazaron 4 de las 6 variables originales del plan

El plan original (`plan_final_mejorado.md`, Subtarea 5.3) pedía `renta_bruta_irpf`,
`poblacion_extranjera` (pilar Social) y `empresas_ss`, `parque_vehiculos_1000hab` (pilar Gobernanza).
Verificación exhaustiva contra `information_schema` de Postgres (bronze/silver/gold completos, no solo
los modelos gold ya construidos) confirmó que ninguna de las 4 tiene ingesta real en el repositorio, y
el responsable de ISTAC del equipo confirmó que no van a estar disponibles. Es una decisión
metodológica propia del equipo, no una corrección de un error de otra persona: se reemplazan por
variables que sí existen y que pasaron el mismo proceso de verificación (cobertura sobre los 31
municipios, distribución/outliers, VIF contra las variables ya en uso con el mismo umbral 10 del resto
del proyecto) antes de incorporarse al score.

Adicionalmente, el pilar **[E] Environmental mesomunicipal** dependía en el plan original en solitario
de `pob_turistica_equiv / poblacion_total`, con cobertura real de solo **6 de 31 municipios (19.4%)** —
insuficiente para integrar al score compuesto sin dejar `esg_municipal_score` en `NULL` para 25
municipios. Se decidió completar el pilar con variables adicionales de mejor cobertura en vez de
excluirlo o reponderar ignorándolo (ver 6.2).

### 6.2 Variables finales por pilar y justificación conceptual

**[E] Environmental (40%)** — agregadas desde `gold.gold_h3_master` (hexágono) a nivel `cod_municipio`:

| Variable | Agregación | Polaridad | Nota |
|---|---|---|---|
| `ndvi_medio` | `AVG` | + | Sin capeo (ratio max/mediana 1.64x) |
| `viirs_medio` | `AVG` | − (invertida) | Sin capeo (5.06x); se descartó `cambio_luz_nocturna_pct` (mide lo mismo, cruza cero) |
| `pct_area_enp` | `SUM(pct_area_enp·area_km2)/SUM(area_km2)` | + | Ponderado por área del hexágono — verificado que da prácticamente igual que un `AVG` simple (hexágonos H3 res. 8 con área casi uniforme, 0.8471–0.8509 km², CV~0.09%), pero es lo metodológicamente correcto |
| `dias_ola_calor_anual` | `AVG`, **capeado en p95** | − (invertida) | Ratio max/mediana 10.33x con un outlier fuerte (Candelaria); capeado antes de normalizar, mismo criterio que `densidad_plazas_km2` en el ESG H3 |
| `amplitud_termica_media` | `AVG` | − (invertida) | Sin capeo (1.46x) |

`pob_turistica_equiv` **no entra al cálculo del score** por su cobertura de 6/31 — queda como columna
informativa en `gold.gold_bloque5_municipio_anual_extra`, fuera de `gold_bloque5_municipio_esg_v1`.

Nota de escala: `ndvi_medio`, `viirs_medio`, `pct_area_enp` (y `ndbi_medio`/`cambio_luz_nocturna_pct`,
descartadas aquí) ya se usan en el pilar E del ESG H3 microespacial. Reutilizarlas a nivel municipio no
es redundante en sentido estricto — la escala geográfica y el propósito de cada índice son distintos
(hexágono para inversión puntual, municipio para política pública) — pero es un punto a tener presente
al interpretar ambos scores en conjunto.

**[S] Social (40%)** — de `gold.gold_municipio_master` y `silver.silver_istac_anual` (`anio=2025`):

| Variable | Polaridad | Nota |
|---|---|---|
| `pct_dependencia_hosteleria` | − | Ya en uso, sin cambios |
| `paro_actual` | − | Ya en uso, sin cambios |
| `var_paro_pct` | − | Ya en uso, sin cambios |
| `plazas_por_1000_hab` | − | Ya en uso, sin cambios |
| `edad_media` | − | **Nueva.** Reemplaza a `renta_bruta_irpf`/`poblacion_extranjera` |
| `ratio_dependencia` | − | **Nueva.** Reemplaza a `renta_bruta_irpf`/`poblacion_extranjera` |

**Por qué `edad_media`/`ratio_dependencia` encajan conceptualmente como reemplazo**: el plan original
agrupaba renta y extranjería bajo "Nivel de Renta", como proxy de vulnerabilidad económica del
municipio. Se optó por un proxy alternativo de vulnerabilidad social — estructura etaria y presión de
población dependiente sobre población en edad activa — porque es un indicador social reconocido de
capacidad de sostén de un territorio (más población fuera del rango activo, mayor presión sobre
servicios y menor colchón económico ante shocks), con ingesta real y completa en el proyecto.

Se probó primero incluir `poblacion_15_64` y `poblacion_65_mas` (recuentos absolutos) directamente:
quedaron descartadas por colinealidad severa con `paro_actual` (VIF 66.8–508, r=0.982–0.997) — al ser
recuentos absolutos, ambas escalan con el tamaño del municipio casi igual que `paro_actual` (también un
recuento absoluto). `ratio_dependencia`, al ser un cociente, no tiene ese problema (VIF=1.569,
r=−0.19 con `paro_actual`) — confirmado con el dato real, no asumido de antemano.

**Limitación explícita sobre `ratio_dependencia`**: `silver.silver_istac_anual` no tiene ninguna
columna de población 0-14 años (ni en bronze existe una tabla ISTAC equivalente). La variable se
calculó como `(poblacion_total − poblacion_15_64) / poblacion_15_64`, que es algebraicamente
equivalente a usar `poblacion_0_14_proxy = poblacion_total − poblacion_15_64 − poblacion_65_mas` como
residuo de la partición estándar INE/ISTAC de grandes grupos de edad (0-14 + 15-64 + 65+ = total). Es
una **derivación aritmética, no un dato de población 0-14 medido directamente** — el residuo da valores
plausibles (8.8%–14.0% de la población total, sin negativos en ningún municipio) pero su precisión
depende de que esa partición estándar sea la que ISTAC usó realmente para construir `poblacion_15_64` y
`poblacion_65_mas`, algo no verificado columna por columna contra la fuente original. Aceptado como
decisión metodológica del equipo tras confirmar que no existe alternativa con dato real.

**Colinealidad preexistente sin resolver**: `plazas_por_1000_hab` y `pct_dependencia_hosteleria`
(ambas ya en uso antes de esta ronda, no son variables nuevas) tienen VIF 11.6–16.3 entre sí —
por encima del umbral 10 del proyecto. Se decidió no tocarlas: quedan fuera del alcance de esta tarea
(reemplazar las 4 variables ISTAC sin ingesta), documentado aquí como limitación conocida, no resuelta.

**[G] Gobernanza (20%)** — de `gold.gold_municipio_empleo` (período trimestral más reciente) y
`gold.gold_h3_master` agregado por municipio:

| Variable | Polaridad | Nota |
|---|---|---|
| `pct_autonomos` | + | **Reasignada desde el pilar Social.** Reemplaza a `empresas_ss` |
| `ratio_hoteles` = `SUM(n_hoteles)/SUM(n_hoteles+n_vv)` por municipio | + | **Nueva a nivel mesomunicipal** (el ratio por hexágono ya existía en el pilar G del ESG H3). Reemplaza a `parque_vehiculos_1000hab` |

**Por qué `pct_autonomos` se reasignó de Social a Gobernanza**: el plan original lo interpretaba como
"Tejido Emprendedor Endógeno" (distribución de riqueza/microemprendimiento, pilar Social). Se
reinterpreta como proxy de **formalización productiva** — proporción de actividad económica que opera
bajo régimen formal de alta en la Seguridad Social como autónomo, en vez de trabajo asalariado — que
encaja mejor en el propósito del pilar Gobernanza (regulación/formalidad del tejido económico) y ocupa
el hueco dejado por `empresas_ss` (empresas con asalariados dadas de alta en SS), que mide un concepto
muy cercano pero no tiene ingesta real. Se usó el **ratio** `pct_autonomos`, no los recuentos absolutos
`empleo_autonomos`/`empleo_total`: estos últimos tendrían el mismo problema de colinealidad con
variables de tamaño municipal (`paro_actual`, etc.) que se descartó explícitamente para
`poblacion_15_64`/`poblacion_65_mas` en el pilar Social.

**Por qué el ratio de hoteles se agrega sumando y no promediando**: promediar el ratio ya calculado por
hexágono le da el mismo peso a un hexágono con 1 hotel/0 VV que a uno con 0 hoteles/24 VV, ignorando el
volumen real de alojamiento. Verificado con un caso real: El Tanque (11 hexágonos con alojamiento, 1
hotel y 70 VV en total) da `SUM/SUM = 1/71 = 0.0141` (1.4%) correctamente, frente a
`AVG(ratio por hexágono) = 0.0909` (9.1%) si se promediara mal — una diferencia de 6.5x que habría
distorsionado el pilar G de ese municipio.

### 6.3 Fórmula y resultado

Normalización MinMax por variable sobre los 31 municipios (mín/máx calculados dinámicamente en la
misma query, no hardcodeados), inversión de polaridad donde corresponde (`1 − normalizado`),
ponderación equal-weight dentro de cada pilar (asunción explícita, no especificada por el plan — mismo
criterio ya usado en el ESG H3), y `esg_municipal_score = 0.40·E + 0.40·S + 0.20·G` (0 a 100).

Resultado real (`gold.gold_bloque5_municipio_esg_v1`, 31 municipios, sin `NULL`): min=36.73 (Puerto de
la Cruz), mediana=60.91, max=73.56 (Los Realejos). Top-3: Los Realejos (73.56), La Victoria de
Acentejo (70.13), Vilaflor (70.10). Bottom-3: Puerto de la Cruz (36.73), Arona (38.39), San Miguel de
Abona (38.81) — ambos casos del sur con `e_score` muy bajo (7.84 y 17.17 respectivamente), coherente
con mayor presión turística/ambiental.

Caso notable: Arafo tiene `g_score = 0.00` — no es un error de cálculo, es el mínimo real y simultáneo
en ambas variables del pilar G (`pct_autonomos` = 8.79%, el más bajo de los 31 municipios; `ratio_hoteles`
= 0, con 96 viviendas vacacionales y 0 hoteles en sus 44 hexágonos con alojamiento).

No fue necesario re-correr el modelo MGWR/PTNA (`04_run_model.py`, ~30 min de cómputo): ninguna de las
fuentes usadas para el ESG mesomunicipal (`gold_h3_master`, `gold_municipio_master`,
`gold_municipio_empleo`, `silver_istac_anual`) depende de los outputs del pipeline MGWR
(`gold_h3_ptna_v3`) — misma independencia ya confirmada para el ESG H3.

## 7. Filtro combinado PTNA × ESG H3 (interpretabilidad para TUI)

El plan (`plan_final_mejorado.md`, Subtarea 5.3) describe como objetivo final de interpretabilidad un
filtro que cruce `ptna_score` (oportunidad de inversión) con el score ESG H3 (sostenibilidad) para
señalar hexágonos que son simultáneamente ambas cosas. Nunca se había construido ni validado — quedó
como pendiente suelto hasta esta ronda de trabajo.

### 7.1 Dos problemas reales encontrados al construirlo

**Nombre de columna incorrecto en el plan.** El plan se refiere a la columna del score ESG como
`esg_territorial_score`. Esa columna no existe con ese nombre en ningún lado — el nombre real,
verificado contra `information_schema.columns` de Postgres, es **`esg_h3_score`**
(`gold.gold_h3_esg_v1`). El plan también usa `esg_territorial_score` en otras secciones no relacionadas
con este bloque (Bloque 9, visualización del dashboard) — no se tocaron esas secciones, pero comparten
el mismo error de nombre.

**Umbrales matemáticamente inalcanzables.** El plan define el filtro en dos lugares con dos criterios
distintos:
- Subtarea 5.3 (este bloque): `ptna_score > 0` AND `esg_score > 75`.
- Subtarea 9.2 (Bloque 9 — Dashboard/Alertas, fuera de este bloque): `ptna_score > 80` AND
  `esg_score > 80`.

Ambos son inaplicables: el máximo real de `esg_h3_score` sobre los 2579 hexágonos es **68.55**
(min=36.28, P50=55.08, P95=62.75 — mismos datos ya reportados en la sección "Índice ESG H3" más
arriba). Ningún hexágono de Tenerife llega siquiera a 69, muy por debajo de 75 u 80 en cualquiera de
los dos criterios del plan. No es un umbral "estricto" — es un desajuste entre el valor absoluto que el
plan asumía y la escala real que produce la normalización MinMax equal-weight del ESG H3 (que nunca se
acerca a 100 en la práctica, por el mismo motivo que el pilar G del ESG H3 queda dominado por E+S — ver
sección "Índice ESG H3" más arriba).

### 7.2 Decisión aplicada

Se mantuvo un **umbral absoluto** (no un percentil dinámico de la distribución) pero ajustado a la
escala real: `esg_h3_score > 60`, combinado sin cambios con `ptna_score > 0` (esta parte del criterio
original sí es alcanzable: 1373/2579 hexágonos tienen `ptna_score > 0`). Con este criterio ajustado:
**247/2579 hexágonos (9.6%)** cumplen ambas condiciones.

Los hexágonos con `confianza_ptna = 'baja'` **no se excluyeron** del resultado — de los 247, 22 tienen
`confianza_ptna='baja'` (1 preexistente + 21 sumados al aplicar el criterio de bandwidth casi-global,
Hallazgo 12, sección 3), y quedan presentes en la tabla con esa columna visible, para que cada consumo
de la tabla decida si filtrarlos según el nivel de rigor que necesite (ver sección 3 de este documento
para qué significa `confianza_ptna='baja'`).

Verificación previa a la construcción: join 1:1 exacto entre `gold.gold_h3_ptna_v3` y
`gold.gold_h3_esg_v1` por `h3_index` (2579 filas en cada tabla, sin huérfanos ni duplicados de ningún
lado).

### 7.3 Resultado

Tabla final: `gold.gold_bloque5_h3_oportunidad_v1` (script
`analytics/mgwr/scripts/09_gold_h3_oportunidad.py`), tabla satélite propia del Bloque 5 — no se
modificó `gold_h3_ptna_v3` ni `gold_h3_esg_v1`. 2579 filas totales (todo el universo de hexágonos, no
solo los que cumplen el criterio), columnas `h3_index`, `municipio`, `ptna_score`, `esg_h3_score`,
`confianza_ptna` y la columna booleana `es_oportunidad_ideal`.

Top de oportunidades ideales (por `ptna_score` descendente): dominado por La Orotava (3 de los 10
primeros) y Los Realejos (2), con Adeje (2), Guía de Isora y Güímar también presentes — concentradas en
el norte/valle de La Orotava y el sureste de Adeje, coherente con el patrón geográfico ya observado en
el top de oportunidades PTNA general (sección 4).

**La Subtarea 9.2 (Bloque 9) no se tocó** — queda fuera del alcance de este trabajo, pero hereda el
mismo problema de nombre de columna y de umbral (`> 80`/`> 80`, también inalcanzable) sin resolver.
Documentado aquí para quien retome ese bloque.
