# Contexto maestro — TFM AI Dashboard Tenerife: Bloque 5 (MGWR + Índice PTNA)

**Fecha de creación:** 2 de septiembre de 2026
**Última actualización:** 16 de septiembre de 2026 — Fase B del v2 completó OK (`ptna_mgwr_model_v2.pkl`, con el fix de Hallazgo 9 ya aplicado), pero el diagnóstico de coeficientes reveló multicolinealidad severa entre 3 variables de tiempo (VIF 185.9-345.8, ver Hallazgo 10) — se excluyen 2 de las 3 (`tiempo_teide_min`, `tiempo_polo_turistico_min`), quedando 14 variables X. El v2 queda invalidado como versión definitiva ("v2, primer intento"); falta correr un v3 con el set corregido. Ver Hallazgo 9 (checkpoint) y Hallazgo 10 (multicolinealidad) para el detalle completo.
**Propósito de este documento:** contexto técnico completo y autosuficiente del Bloque 5 (`gold_h3_ptna`), para retomar el trabajo en conversaciones nuevas sin necesidad de re-explicar nada desde cero. Sigue el mismo patrón que `contexto_maestro_proyecto.md` (Booking, issue #12).

Para el panorama general del repo (equipo, otras fuentes, infraestructura Azure) usar `contexto_maestro_repo.md` — este documento se enfoca solo en el Bloque 5.

---

## 1. Qué es el Bloque 5 y por qué importa

Del plan vigente (`plan_final_mejorado.md`, Squad B, Prioridad Alta, Semana 2):

**MGWR (Multiscale Geographically Weighted Regression)** es el modelo estadístico estrella del TFM. Permite que un mismo factor (ej. NDVI/verde) tenga distinto peso según la zona geográfica — en el norte de Tenerife el NDVI puede importar menos que en el sur árido. Con sus resultados se construye el **PTNA (Potencial Turístico No Aprovechado)**, el indicador más valioso del proyecto de cara a TUI (partner/caso de uso del TFM).

Fórmula conceptual:
```
PTNA = Valor_esperado_por_MGWR - Valor_observado_real
```

- `ptna_score > 0` → el hexágono **debería** tener más plazas hoteleras según sus condiciones → oportunidad de inversión.
- `ptna_score < 0` → zona sobre-explotada → riesgo de overtourism.

Además, la Subtarea 5.3 pide un **Índice ESG Territorial** (0-100) para que TUI pueda filtrar oportunidades de inversión (PTNA alto) que también cumplan criterios de sostenibilidad.

Asignado a mí (jcabrera1605-netizen) el 02-sep-2026, en conjunto con quien más comparta el Squad B (a confirmar quién es la otra persona asignada al bloque — el plan dice "Personas 3 y 4").

## 2. Librerías necesarias

```bash
pip install mgwr libpysal scikit-learn numpy pandas matplotlib
```

Instalar puntual, no vía `requirements.txt` completo — mismo criterio que ya se aplica en la VM del proyecto para evitar arrastrar dependencias pesadas innecesarias (ver incidente de disco lleno documentado para Booking, sección 6 del `SKILL.md` de scraping).

## 3. Subtarea 5.1 — Construir el dataset de regresión

### Actualización 12-sep-2026: `gold.gold_h3_master` SÍ existe

A diferencia de lo documentado en la versión anterior de este archivo, `gold.gold_h3_master` **existe como tabla real y consolidada** (confirmado vía `information_schema.columns`). No hace falta unir manualmente `features_h3` + otras tablas sueltas para las variables satelitales/topográficas/POIs — ya vienen juntas ahí. Sí sigue haciendo falta un join aparte con `gold.gold_h3_accesibilidad` (esa tabla no está fusionada en el master) y, en el futuro, con la tabla de sentimiento cuando exista.

Tablas Gold confirmadas hoy (`information_schema.tables`, schema `gold`): `gold_h3_master`, `gold_h3_accesibilidad`, `gold_isocronas_visuales`, `gold_municipio_master`. La tabla vieja `h3_accesibilidad` (sin prefijo `gold_`) **ya no existe** — la ambigüedad documentada en la versión anterior de este archivo queda resuelta de hecho.

### Estado real de las variables (verificado 12-sep-2026)

| Variable X | ¿Disponible? | Detalle |
|---|---|---|
| `ndvi_medio` | ✅ | `gold_h3_master.ndvi_medio` (también hay desagregado anual 2022-2026 y trimestral) |
| `ndbi_medio` | ✅ | `gold_h3_master.ndbi_medio` (mismo desagregado) |
| `viirs_medio` | ✅ | `gold_h3_master.viirs_medio` (mismo desagregado). **Brecha bloqueante original, ya resuelta.** |
| `altitud_media` | ✅ | `gold_h3_master.altitud_media_m` |
| `pendiente_media` | ✅ | `gold_h3_master.slope_mean` |
| `sentimiento_medio` | ❌ **Bloqueante activo** | Ver sección 6 — la tabla fuente no existe en ningún esquema, en construcción por el equipo de NLP |
| `tiempo_a_tfs_min` | ✅ | `gold_h3_accesibilidad.tiempo_tfs_min` |
| `n_paradas_15min` | ⚠️ Proxy aceptado | No existe como métrica de tiempo. Usar `n_paradas_bus_500m` (o 200m/1000m) de `gold_h3_accesibilidad` — decisión provisional aceptada, no bloqueante |
| `n_pois` (turístico) | ✅ Con matiz — ver hallazgo #1 | No usar `n_pois_total` tal cual (ver sección 6). Usar `n_pois_turisticos` = `n_restaurantes + n_cultura + n_naturaleza + n_pois_institucionales`, todas columnas de `gold_h3_master` |

**Variable Y — resuelta.** `gold_h3_master.n_plazas_registro` existe tal cual el plan lo pedía (densidad = `n_plazas_registro / area_km2`). Ya no hace falta el proxy `n_alojamientos` (que contaba establecimientos, no plazas).

**Distancia a costa — resuelta, ver hallazgo #2 en sección 6.** Usar `gold_h3_accesibilidad.dist_costa_km`, no `gold_h3_master.distancia_costa_metros`.

### Columnas completas de `gold_h3_master` (referencia)

```
h3_index, cod_municipio, municipio, area_km2, centroide_lon, centroide_lat,
n_establecimientos_registro, n_plazas_registro, n_hoteles, n_vv, n_extrahoteleros,
n_establecimientos_booking, rating_booking_medio, n_reviews_booking,
n_establecimientos_tripadvisor, rating_tripadvisor_medio,
n_pois_total, n_restaurantes, n_cultura, n_naturaleza, n_pois_institucionales,
n_paradas_bus, altitud_media_m, elevation_min, elevation_max,
slope_mean, aspect_mean, hillshade_mean,
ndvi_medio, ndvi_2022..ndvi_2026, ndvi_q1..ndvi_q4,
viirs_medio, viirs_2022..viirs_2026, viirs_q1..viirs_q4,
ndbi_medio, ndbi_2022..ndbi_2026,
dias_ola_calor_anual, amplitud_termica_media, radiacion_mediodia_q1/q3,
temp_media_anual, temp_media_q1..q4, lluvia_mm_anual, lluvia_mm_q1..q4,
vel_viento_media_anual, vel_viento_media_q1..q4,
humedad_media_anual, humedad_media_q1..q4,
insolacion_media_anual, insolacion_media_q1..q4,
distancia_costa_metros, es_enp, pct_area_enp, es_zona_turistica_oficial, geometry
```

### Columnas completas de `gold_h3_accesibilidad` (referencia, corregido 15-sep-2026)

**Corrección 15-sep-2026**: la version anterior de esta lista tenia `tiempo_polo_sur_min` /
`tiempo_polo_norte_min` -- esos nombres NO existen en el schema real. Los nombres correctos,
verificados contra `information_schema.columns`, son `tiempo_extremo_sur_min` /
`tiempo_extremo_norte_min`.

```
h3_index, tiempo_tfs_min, tiempo_tfn_min, tiempo_capital_min, tiempo_extremo_sur_min,
tiempo_extremo_norte_min, tiempo_teide_min, tiempo_la_laguna_min, tiempo_candelaria_min,
tiempo_los_gigantes_min, tiempo_el_medano_min, tiempo_garachico_min, tiempo_anaga_min,
tiempo_masca_min, tiempo_vilaflor_min, tiempo_la_orotava_min, tiempo_guimar_min,
tiempo_buenavista_min, tiempo_arico_min, tiempo_aeropuerto_min, aeropuerto_mas_cercano,
n_paradas_bus_200m, n_paradas_bus_500m, n_paradas_bus_1000m, dist_parada_cercana_m,
dist_hospital_km, dist_costa_km
```

### Filtro de calidad (>50% NaN) — resuelto, implementado en `02_filter_nan.py`

No existe `excluded_high_nan` ni `n_features_missing` en `gold_h3_master` (la versión vieja de este documento asumía que sí, era incorrecto). El cálculo ya no se hace a mano en SQL (el query de ejemplo que había aquí quedó obsoleto) -- lo hace `02_filter_nan.py` en pandas, sobre `PTNA_NAN_FILTER_COLUMNS` (`_db.py`, ver Hallazgo 5 sobre por qué `sentimiento_medio` queda afuera de este cálculo).

### Query de construcción del dataset -- v1 (12-sep-2026, referencia histórica, YA NO VIGENTE)

```sql
SELECT
    m.h3_index,
    m.centroide_lon,
    m.centroide_lat,
    m.n_plazas_registro / NULLIF(m.area_km2, 0) AS densidad_plazas_km2,  -- variable Y
    m.ndvi_medio,
    m.ndbi_medio,
    m.viirs_medio,
    m.altitud_media_m,
    m.slope_mean,
    (m.n_restaurantes + m.n_cultura + m.n_naturaleza + m.n_pois_institucionales) AS n_pois_turisticos,
    a.tiempo_tfs_min,
    a.n_paradas_bus_500m,
    a.dist_costa_km
    -- sentimiento_medio: pendiente, sumar via join cuando la tabla exista (ver sección 6)
FROM gold.gold_h3_master m
LEFT JOIN gold.gold_h3_accesibilidad a ON a.h3_index = m.h3_index;
```

Resultado guardado como referencia/borrador exploratorio en `analytics/mgwr/data/interim/ptna_mgwr_model.pkl` y `analytics/mgwr/data/processed/gold_h3_ptna_v1.parquet` -- **no se borran ni sobreescriben**. `06_load_to_gold.py` nunca se corrió contra esta versión; `gold.gold_h3_ptna_v1_sin_sentimiento` no existe en Postgres.

### Query de construcción del dataset -- v2 (15-sep-2026, VIGENTE)

Corrige el set de variables contra `plan_final_mejorado.md` (Bloque 5, Subtarea 5.1) en vez del resumen de la sesión del 12-sep -- ver Hallazgos 4-7 abajo para el detalle completo de cada cambio.

```sql
SELECT
    m.h3_index,
    m.municipio,                                                                   -- NUEVO, solo reporting (no es X)
    m.centroide_lon,
    m.centroide_lat,
    m.n_plazas_registro / NULLIF(m.area_km2, 0) AS densidad_plazas_km2,            -- variable Y, sin cambios
    m.ndvi_medio,
    -- ndbi_medio y viirs_medio: ELIMINADAS (colinealidad/proxy directo de Y, plan Subtarea 5.1)
    m.altitud_media_m,
    m.slope_mean,
    m.n_restaurantes,                                                              -- separada, ver Hallazgo 1
    m.n_naturaleza,                                                                -- separada, ver Hallazgo 1
    m.n_cultura,                                                                   -- separada, ver Hallazgo 1
    a.dist_hospital_km,                                                            -- NUEVA
    m.pct_area_enp,                                                                -- NUEVA
    m.temp_media_anual,                                                            -- NUEVA
    m.lluvia_mm_anual,                                                             -- NUEVA
    a.tiempo_teide_min,                                                            -- NUEVA
    a.dist_parada_cercana_m,                                                       -- reemplaza n_paradas_bus_500m
    a.tiempo_aeropuerto_min,                                                       -- reemplaza tiempo_tfs_min (ya precalculada)
    LEAST(a.tiempo_extremo_sur_min, a.tiempo_extremo_norte_min) AS tiempo_polo_turistico_min,  -- NUEVA, calculada aca
    a.dist_costa_km,
    sent.sentimiento_medio,                                                        -- NUEVA, ver Hallazgo 5
    sent.n_resenas_sentimiento                                                     -- NUEVA, informativa, no es X
FROM gold.gold_h3_master m
LEFT JOIN gold.gold_h3_accesibilidad a ON a.h3_index = m.h3_index
LEFT JOIN gold.gold_h3_sentimiento sent ON sent.h3_index = m.h3_index;
```

16 variables X (antes 9 en v1): `ndvi_medio, altitud_media_m, slope_mean, n_restaurantes, n_naturaleza, n_cultura, dist_hospital_km, pct_area_enp, temp_media_anual, lluvia_mm_anual, tiempo_teide_min, dist_parada_cercana_m, tiempo_aeropuerto_min, tiempo_polo_turistico_min, dist_costa_km, sentimiento_medio` (lista real en `_db.py::PTNA_QUALITY_COLUMNS`).

Verificado contra Postgres real (15-sep-2026, 2579 filas): `sentimiento_medio` con 2169 NULL (84.1%, ver Hallazgo 5), `lluvia_mm_anual` con 322 NULL (12.5%, dentro del umbral de 50% del filtro de 02).

Diseño modular preservado: `gold.gold_h3_sentimiento` se suma con un `LEFT JOIN` adicional aislado, mismo patrón que `gold_h3_accesibilidad`, sin tocar el resto de la query.

## 4. Subtarea 5.2 — Ejecutar el modelo MGWR e Índice PTNA

### Estado real (15-sep-2026, tarde): Fase B en curso contra el dataset v2, resultado final todavía no confirmado

`04_run_model.py` se corrió en terminal (jcabrera1605-netizen) contra el dataset v2 filtrado (2579 filas, 16 variables), con el fix de `init_multi=n_sub` de Hallazgo 8 ya aplicado. Dos de las tres fases completaron sin error; la tercera seguía en curso al momento de este apunte:

**1. Búsqueda de bandwidth sobre la submuestra (860 filas) — completada sin error.** 50 iteraciones de backfitting, SOC de 0.0109 a 4.07e-05, ~16:26 min. Bandwidths finales sobre la submuestra:

```
ndvi_medio: 537   altitud_media_m: 53   slope_mean: 858 (techo)   n_restaurantes: 669
n_naturaleza: 65   n_cultura: 44   dist_hospital_km: 113   pct_area_enp: 79
temp_media_anual: 858 (techo)   lluvia_mm_anual: 858 (techo)   tiempo_teide_min: 858 (techo)
dist_parada_cercana_m: 858 (techo)   tiempo_aeropuerto_min: 858 (techo)
tiempo_polo_turistico_min: 858 (techo)   dist_costa_km: 858 (techo)   sentimiento_medio: 682
```

8 de las 16 variables convergieron al bandwidth techo de la submuestra (858 = n_sub) — ver el matiz completo en Hallazgo 8, no es un error.

**2. Backfitting sobre el dataset completo (2579 filas), con los bandwidths ya reescalados por densidad (Hallazgo 4) — completado sin error.** 50 iteraciones, SOC de 0.0065 a 3.36e-05, ~4:15 min (más rápido que la búsqueda sobre la submuestra, esperable porque acá los bandwidths ya vienen fijos del reescalado, no se buscan desde cero). Bandwidths finales sobre el dataset completo:

```
ndvi_medio: 1610   altitud_media_m: 159   slope_mean: 2573 (techo)   n_restaurantes: 2006
n_naturaleza: 195   n_cultura: 132   dist_hospital_km: 339   pct_area_enp: 237
temp_media_anual: 2573 (techo)   lluvia_mm_anual: 2573 (techo)   tiempo_teide_min: 2573 (techo)
dist_parada_cercana_m: 2573 (techo)   tiempo_aeropuerto_min: 2573 (techo)
tiempo_polo_turistico_min: 2573 (techo)   dist_costa_km: 2045   sentimiento_medio: 2573 (techo)
```

Confirma lo anticipado en Hallazgo 8: las mismas variables que llegaron al techo en la submuestra vuelven a llegar al techo en el dataset completo tras el reescalado — patrón consistente, no una sorpresa nueva. Nota: `dist_costa_km` bajó de techo (858 en la submuestra) a 2045 (no techo) en el dataset completo — con más densidad de puntos, encontró un óptimo local por debajo del máximo; no es contradictorio con el hallazgo anterior.

**3. Cálculo de diagnósticos post-fit (`MGWR.fit()`, ENP_j/CCT) — falló con `TimeoutError` a los 40.1 min, backfitting perdido.** Esta fase no tiene barra de progreso propia (solo heartbeat cada minuto). Se confirmó que era la parte más cara y hoy no aprovechada del proceso (ver Hallazgo 9) — al no haber checkpoint intermedio, el timeout se llevó también los ~31 min de búsqueda + backfitting ya completados, no solo el cálculo de `ENP_j`/`CCT`. Decisión tomada: implementar checkpoint temprano + `.fit()` opcional (Hallazgo 9, opción híbrida) antes de volver a correr `04_run_model.py`.

### Referencia técnica del plan (para cuando el resultado esté confirmado)

- Todas las X se normalizan con `StandardScaler` antes de pasarlas al modelo (aplicado en `04_run_model.py`).
- Coordenadas de entrada: centroides de cada hexágono H3 (`gold_h3_master.centroide_lon/lat`), EPSG:4326.
- **Output esperado:** DataFrame con coeficientes locales (`params`) y `ptna_score` = predicho − observado. **Nombre real usado en el pipeline** (no el esqueleto genérico del plan): `analytics/mgwr/data/processed/gold_h3_ptna_v2.parquet` para el resultado local; subir a Postgres queda pendiente de decisión explícita vía `06_load_to_gold.py` (ver sección 9) — no automatizado.

## 5. Subtarea 5.3 — Índice ESG Territorial

Todavía no iniciada. Referencia del plan:

Score de 0 a 100 evaluando sostenibilidad ambiental/social/gobernanza por hexágono, usando solo datos públicos. Ponderación de ejemplo dada por el plan:

- **[E] Medio Ambiente (40%)**: `ndvi_medio` alto (+), `viirs_medio` bajo (+, menos contaminación lumínica), `dist_enp_km` o `pct_area_enp` (ya disponible en `gold_h3_master`) con lectura no lineal.
- **[S] Social (40%)**: `densidad_plazas_km2` bajo (+, menor saturación), `n_paradas_bus_500m` alto (+, accesibilidad pública), `sentimiento_medio` de quejas de ruido en NLP bajo (+) — depende de que sentimiento esté resuelto.
- **[G] Gobernanza (20%)**: ratio `n_hoteles` vs `n_vv` (viviendas vacacionales) — ambas columnas ya disponibles en `gold_h3_master`. Mayor ratio de hoteles regulados = mejor score.

Cálculo: normalizar todas las variables con `MinMaxScaler` (0 a 1), aplicar pesos, sumar → `esg_territorial_score` (0-100).

**Nota actualizada 12-sep-2026**: a diferencia de lo que decía la versión anterior de este documento, `n_hoteles` y `n_vv` **sí están disponibles** en `gold_h3_master` (columnas confirmadas). Falta todavía `dist_enp_km` explícito (hay `pct_area_enp` y `es_enp`, que pueden servir de proxy o insumo directo — evaluar cuando se llegue a esta subtarea).

**Interpretación combinada para TUI:** un hexágono con `ptna_score > 0` y `esg_territorial_score > 80` es la oportunidad ideal — inversión justificada + criterios de sostenibilidad.

## 6. Hallazgos de la sesión de investigación de variables (12-sep-2026)

### Hallazgo 1 — `n_pois_total` no es una suma exhaustiva de sus subcategorías

Al comparar `n_pois_total` contra la suma de `n_restaurantes + n_cultura + n_naturaleza + n_pois_institucionales`, la diferencia es sistemática y positiva en todos los hexágonos revisados. Se confirmó contra el código dbt real (no la versión desactualizada del plan) que el filtro de cada subcategoría es:

```sql
n_pois_total            → COUNT(p.id) sin filtro (cuenta TODO)
n_restaurantes          → tipo IN ('restaurant','bar','cafe','fast_food','pub')
n_cultura               → categoria IN ('Atracciones_Turisticas','Cultura')
n_naturaleza            → categoria IN ('Naturaleza_Deporte')
n_pois_institucionales  → fuente = 'IDE_Canarias'
```

Todo lo que cae en `categoria = 'Transporte'` (paradas de bus, parking, taxis — miles de registros en `silver.puntos_interes_unificados`) o `categoria = 'Servicios_Basicos'` (supermercados, bancos, farmacias — también miles) se cuenta en el total pero en ninguna subcategoría. Se descartó contaminación por alojamiento (`hotel`/`guest_house` = 5 registros sobre miles, despreciable).

**No es un bug de código** — es una decisión de diseño (subcategorías como recortes temáticos parciales, no partición exhaustiva) que no está documentada como tal en ningún lado.

**Decisión tomada para PTNA (12-sep-2026, REVERTIDA 15-sep-2026)**: ~~no usar `n_pois_total`. Usar `n_pois_turisticos` = suma de las 4 subcategorías~~.

**Reversión (15-sep-2026, dataset v2)**: `plan_final_mejorado.md` (Bloque 5, Subtarea 5.1) lista `n_restaurantes`, `n_naturaleza` y `n_cultura` como **3 variables X independientes**, cada una con su propia justificación de negocio (densidad de POIs y servicios de ocio caminables) — no aparece `n_pois_turisticos` ni `n_pois_institucionales` en ningún lado de esa tabla. La suma del 12-sep fue una decisión de esa sesión, no algo que pidiera el plan real (el plan no estaba siendo consultado directamente en ese momento, solo el resumen de variables). Se revierte: el dataset v2 usa las 3 columnas por separado, sin sumar. `n_pois_institucionales` queda fuera del todo (tampoco aparece en el plan). Con esto, las 3 variables quedan más obviamente candidatas a colinealidad entre sí (todas cuentan densidad de POIs del mismo hexágono) — se agregó un chequeo de VIF específico para ellas en `04_run_model.py` (ver Hallazgo 4).

**Sigue pendiente**: preguntar al responsable de Bloque 1 (Espacial/OSM) si el diseño de `n_pois_total` no exhaustivo es intencional — no bloqueante, no afecta la decisión de arriba (ya no se usa `n_pois_total` de ninguna forma).

### Hallazgo 2 — Distancia a costa: dos métricas válidas con distinto punto de referencia

- `gold_h3_master.distancia_costa_metros` (Subtarea 1.10, Bloque 1): mide desde el **hexágono completo** (polígono) hasta `ST_Boundary(ST_Union(limites_municipales))`. Al no partir de un punto, PostGIS calcula la distancia mínima desde el borde más cercano del polígono.
- `gold_h3_accesibilidad.dist_costa_km` (Subtarea 4.5, Bloque 4): mide explícitamente desde el **centroide** del hexágono (`h.centroide_lon/lat`), con cast a `::geography`.

Offset observado entre ambas: sistemático, entre 0.49-0.58 km, mayor cuanto más cerca de la costa en términos relativos (30%+ de error relativo en hexágonos costeros). Se verificó con una query de distancia centroide-a-borde del mismo hexágono (~491m, mismo orden de magnitud que el offset — confirma la dirección de la hipótesis, aunque no coincide al milímetro, posiblemente por diferencias de geometría exacta borde/vértice o precisión geodésica).

**No es un error** — son dos definiciones legítimas con propósitos distintos (1.10 pensada para valor inmobiliario general, 4.5 específicamente para atractivo turístico con respaldo de literatura de precios hedónicos, β ≈ -0.42).

**Decisión tomada para PTNA**: usar `dist_costa_km` (Bloque 4), por dos motivos — (a) consistencia con que el modelo ya usa centroides como coordenadas de entrada en MGWR, (b) respaldo empírico específico para el fenómeno que PTNA modela (atractivo turístico, no valor inmobiliario general).

**No incluir ambas variables en el modelo**: al estar casi perfectamente correlacionadas (offset ~constante), meter ambas como X en MGWR infla la varianza de los coeficientes y puede producir estimaciones inestables por zona sin aportar información real adicional.

**Pendiente**: avisar a Bloque 1 y Bloque 4 el hallazgo, por transparencia y documentación — no bloqueante, decisión ya tomada.

### Hallazgo 3 — Sentimiento agregado por hexágono: tabla fuente no existe, en construcción (12-sep-2026, RESUELTO 15-sep-2026)

`gold.nlp_sentimiento_resenas` (que la versión anterior de este documento daba por existente, sin agregar) **ya no existe en ningún esquema** — se confirmó con búsqueda amplia en `gold` y `silver` (`information_schema.tables`, filtro por `%sentimiento%`/`%sentiment%`/`%nlp%`). Consultado con el equipo: la tabla está en construcción por el área de NLP, no se perdió.

**Decisión tomada en su momento**: dataset v1 de PTNA sin esta variable. Diseño modular (query con `LEFT JOIN` adicional aislado) para incorporarla el día que exista, sin rehacer el resto del dataset.

**Resuelto (15-sep-2026)**: `gold.nlp_sentimiento_resenas` ya existe y está poblada (74.695 filas). Ver Hallazgo 5 para el detalle completo de la integración real (cobertura, agregación, tabla `gold.gold_h3_sentimiento`).

### Hallazgo 4 — Fix de estabilidad de bandwidth en MGWR (retroactivo, turnos previos a esta sesión, documentado recién ahora)

Durante las primeras corridas reales de `04_run_model.py` contra el dataset v1 (9 variables) se encontraron y resolvieron, en sesiones previas a esta, dos incidentes reales de `LinAlgError: A singular matrix detected` que nunca se documentaron en este archivo (quedaron solo en el docstring extenso de `04_run_model.py`). Se documentan aca retroactivamente porque son limitaciones reales de la librería `mgwr` 2.2.1 que siguen aplicando igual al dataset v2 (no dependen de cuántas ni cuáles sean las variables X):

1. **Kernel fijo + coordenadas en grados**: con `fixed=True` (bandwidth = radio en grados), la búsqueda por sección áurea probaba candidatos de bandwidth cada vez más chicos hasta quedar por debajo de la distancia mínima entre vecinos (~0.009°), dejando ventanas locales sin vecinos suficientes. Fix: usar kernel **adaptativo** (`fixed=False`, bandwidth = cantidad de vecinos) para la búsqueda sobre la submuestra — garantiza un mínimo de puntos por ventana sin importar la densidad/escala de las coordenadas.
2. **Bandwidth adaptativo no transferible entre datasets de distinta densidad**: un bandwidth adaptativo es una CANTIDAD DE VECINOS, no una distancia física — no es transferible tal cual entre la submuestra (menor densidad) y el dataset completo (mayor densidad) sobre la misma área geográfica. Fix: reescalar cada bandwidth por la razón de tamaños (`n_total / n_submuestra`), con un piso de seguridad (`max(30, 3 × n_variables)`, hoy 48 con 16 variables) y techo `n_total`. Además, el paso "semilla" de `multi_bw()` (que ajusta todas las variables juntas para inicializar el backfitting) NO respeta `multi_bw_min`/`multi_bw_max` — se fija explícitamente con `init_multi = n_total` para evitar que ese paso dispare su propia búsqueda no controlada.

Esta lógica **no cambia entre v1 y v2** — sigue igual en `04_run_model.py`, solo con `bw_floor` recalculado dinámicamente según `len(PTNA_QUALITY_COLUMNS)` (30→48 al pasar de 9 a 16 variables). Ver el docstring de `04_run_model.py` para el detalle línea por línea (incluye también los ajustes posteriores de visibilidad del fit final y timeout de la búsqueda sobre la submuestra, tampoco documentados aquí hasta ahora).

### Hallazgo 5 — `sentimiento_medio`: cobertura real del 15.9% de los hexágonos (15-sep-2026)

Con `gold.nlp_sentimiento_resenas` ya poblada (ver Hallazgo 3), se construyó `gold.gold_h3_sentimiento` (ver `00_create_sentimiento_table.py`) agregando por `h3_index`: `sentimiento_medio` (AVG del score), `n_resenas_sentimiento`, `n_resenas_booking`, `n_resenas_tripadvisor`, `queja_principal` (ver Hallazgo 6).

**Chequeo de cobertura (pedido explícitamente antes de integrar la variable)**: de los 2579 hexágonos de `gold_h3_master`, solo **410 (15.9%)** tienen al menos una reseña geolocalizada — los **2169 restantes (84.1%) quedan con `sentimiento_medio = NULL`** tras el `LEFT JOIN`. No es un problema de calidad de dato — son zonas de Tenerife sin alojamiento turístico cercano (interior/rural), reflejo real del fenómeno, no un bug. Entre los 410 hexágonos con match, la cobertura es buena (mediana 36.5 reseñas/hexágono, rango 1-5423).

**Decisión tomada**: `sentimiento_medio` se agrega como variable X del modelo (imputada con la mediana en `04_run_model.py`, igual que las demás), pero **queda excluida del filtro de >50% NaN de `02_filter_nan.py`** (`PTNA_NAN_FILTER_COLUMNS` en `_db.py` = `PTNA_QUALITY_COLUMNS` sin `sentimiento_medio`) — contarla ahí excluiría de forma incorrecta el 84.1% del dataset por una variable sin cobertura geográfica completa, no por mala calidad del resto de sus datos. `n_resenas_sentimiento` queda como columna informativa (no es variable X), similar en espíritu a `confianza_ptna` (ver `05_ptna_score.py`).

### Hallazgo 6 — `queja_principal`: ambigüedad de polaridad en el SQL del plan (15-sep-2026)

El SQL de `plan_final_mejorado.md` (Subtarea 2.3) calcula `queja_principal` como `MODE() WITHIN GROUP (ORDER BY a.aspecto)` sobre **todos** los aspectos detectados, sin filtrar por polaridad — pero el nombre de la columna ("queja") sugiere que debería considerar solo aspectos con sentimiento negativo.

Ejemplo real (5 hexágonos donde el resultado cambia): sin filtrar, el resultado en la práctica es el aspecto más **mencionado en general** (79% de los aspectos detectados en `gold.nlp_aspectos_resenas` son `Positive`, solo 17% `Negative`) — ej. "apartamento", "hotel", "habitación", que no son quejas. Filtrando por `sentimiento = 'Negative'`, el resultado sí son quejas reales (ej. "cupboard"/armario, "ascensor", "cage"/jaulón — ruido de vecinos, "beds"/camas).

**Decisión tomada**: filtrar por `sentimiento = 'Negative'`. De los 410 hexágonos con datos de sentimiento, 351 tienen al menos un aspecto negativo detectado y por tanto `queja_principal` no nulo; los 59 restantes quedan con `queja_principal = NULL` a propósito (no se rellenan con ningún valor por defecto). Implementado en `00_create_sentimiento_table.py`.

### Hallazgo 7 — Inconsistencia del plan sobre dónde vive `gold_h3_sentimiento` (15-sep-2026)

`plan_final_mejorado.md` es inconsistente consigo mismo: la Subtarea 2.3 (Bloque 2) da el SQL de cruce NLP→H3 pero dice que el resultado va directo a `gold.h3_master` (línea 538: *"incorporadas a gold.h3_master"*), mientras que el Bloque 5 (Subtarea 5.1, línea 959) y el Bloque 5.3 (ESG) asumen una tabla **separada** `gold.gold_h3_sentimiento`. Ningún bloque tiene asignado explícitamente el trabajo de construir esa tabla.

**Decisión tomada**: se construyó `gold.gold_h3_sentimiento` como tabla real independiente (no subquery inline, no fusionada en `gold_h3_master`) — mismo patrón modular que `gold_h3_accesibilidad`, y deja la tabla lista para cuando se llegue a la Subtarea 5.3 (ESG), que necesita el aspecto "ruido" de la misma fuente. El SQL real usado (`00_create_sentimiento_table.py`) NO es una copia literal del SQL de la Subtarea 2.3 del plan — ese SQL asume columnas (`review_id`, `plataforma` en sentimiento; `resena_id`, `aspecto`, `sentimiento` con `ST_Contains` para geolocalizar) que no coinciden con las tablas reales ya pobladas por el equipo de NLP (`gold.nlp_sentimiento_resenas` con `h3_index` ya precalculado, `gold.nlp_aspectos_resenas` sin `h3_index` propio, unido por `(resena_id, fuente)`). Se avisa aquí para que quede constancia de que la tabla se construyó adaptando el *propósito* de 2.1/2.2/2.3 al schema real, no por haber ignorado el plan.

**Único bloqueante activo del Bloque 5 a la fecha: ninguno** (Hallazgo 3 quedó resuelto).

### Hallazgo 8 — LinAlgError en la búsqueda sobre la submuestra (dataset v2, mismo tipo de fix que Hallazgo 4 pero aplicado al paso que faltaba)

Al correr `04_run_model.py` contra el dataset v2 (16 variables) en la Fase B, `Sel_BW().search()` falló con `LinAlgError: A singular matrix detected: slice(s) [0] are singular` **dentro de `_bw_search_worker`, sobre la submuestra (860 filas)** — un fallo distinto al de Hallazgo 4 (aquel ocurría después, al transferir el bandwidth al dataset completo por diferencia de densidad).

**Diagnóstico (sesión de solo lectura, sin recalcular nada hasta confirmar la causa)**:
- El traceback mostró que el fallo ocurre en `self._mbw()` → `multi_bw(self.init_multi, ...)` — el mismo paso "semilla" (todas las variables juntas, para inicializar el backfitting) que ya causó el incidente del Hallazgo 4. La diferencia: `_full_fit_worker` ya fija `init_multi=n_total` para ese paso, pero **`_bw_search_worker` (la búsqueda sobre la submuestra) nunca lo hacía** — en el v1 (9 variables) ese paso nunca había fallado ahí, así que nadie le aplicó el mismo fix.
- Se descartó la hipótesis inicial de que `sentimiento_medio` (imputada con mediana en 84.1% de las filas) fuera la causa: al aislar variables por eliminación controlada, quitarla del design matrix local casi no cambia el número de condición (de 2e15 a 2e15 en el punto que falló). En cambio, quitar `lluvia_mm_anual` sola mejora el condicionamiento en ~10 órdenes de magnitud (de 5.4e18 a 2.0e8) — es, por lejos, la variable más responsable.
- Causa real: `lluvia_mm_anual`, `tiempo_teide_min`, `tiempo_aeropuerto_min` y `tiempo_polo_turistico_min` son variables derivadas de rásters/red vial interpolados a resolución más gruesa que el hexágono H3 — hexágonos vecinos cercanos heredan valores casi idénticos (ej. `lluvia_mm_anual` con varianza 0.000000 entre los 29 vecinos más cercanos de un punto en zona densa, no periférica). En bandwidths chicos (los que golden-section prueba al principio de la búsqueda sin `init_multi` fijo), esto produce columnas localmente casi-constantes → matriz de diseño local singular o pésimamente condicionada. Es un problema **sistémico**, no aislado a una geografía particular: a bw=17, el 100% de los 860 puntos de la submuestra tenían `cond(X'WX) > 1e10`; a bw=40, todavía el 35%.

**Fix aplicado (15-sep-2026)**: mismo patrón que Hallazgo 4 — fijar `init_multi = n_sub` (tamaño de la submuestra, no `n_total`) en `_bw_search_worker`, para que el paso semilla no dispare su propia búsqueda de bandwidth no controlada. Verificado con un experimento aislado (Sel_BW real sobre las 860 filas y 16 variables, con `init_multi=860`): la búsqueda completa (semilla + backfitting de las 16 variables) terminó sin ningún error en 27.3 min, con SOC convergiendo de 0.0109 a 4.07e-05 en 50 iteraciones. No hizo falta excluir ninguna variable.

**Matiz importante, no es una alarma**: de las 16 variables, **8 convergieron al bandwidth techo de la submuestra (858 = n_sub)** — no solo las 4 sospechadas (`lluvia_mm_anual`, `tiempo_teide_min`, `tiempo_aeropuerto_min`, `tiempo_polo_turistico_min`), sino también `slope_mean`, `temp_media_anual`, `dist_parada_cercana_m` y `dist_costa_km`. Esto **no es un error** — la búsqueda entera convergió limpio, sin ninguna excepción. Es información real sobre qué variables son casi-globales (su relación con la Y no varía mucho geográficamente en esta submuestra) vs. genuinamente locales (`altitud_media_m` bw=53, `n_cultura` bw=44, `pct_area_enp` bw=79, etc.). **Es esperable que el paso de reescalado por densidad lleve a estas mismas variables al techo del dataset completo (2579) en el fit final** — si eso aparece al correr la Fase B, no es motivo de alarma, es consistente con este hallazgo.

**Ajuste relacionado**: `--bw-search-timeout-min` subido de 30 a 45 min. La corrida real de las 50 iteraciones completas (con el fix ya aplicado) tardó 27.3 min, muy cerca del límite viejo de 30 — ese timeout nunca había sido calibrado para una búsqueda real completa (estaba pensado para el caso que fallaba en segundos). `--max-iter-multi` se mantiene en 50 sin cambios, a pedido explícito, aunque el SOC ya se había estabilizado antes en la corrida de referencia.

### Hallazgo 9 — `--full-fit-timeout-min` (40 min) nunca calibrado, y `MGWR.fit()` recalcula diagnósticos que hoy no se usan (15-sep-2026, CONFIRMADO — TimeoutError real, decisión tomada)

Mientras corría la Fase B real (ver sección 4), la fase de diagnósticos post-fit (`MGWR.fit()`, llamada después de que `selector_full.search()` ya completó el backfitting en 4:15 min) no mostraba ninguna señal de progreso más allá del heartbeat cada 60s, generando dudas sobre si el timeout de 40 min alcanzaba.

**Punto 1 — origen del timeout de 40 min**: a diferencia de `--bw-search-timeout-min` (calibrado dos veces contra corridas reales: 15→30 por una corrida de 13:48 min, 30→45 por la de 27.3 min de Hallazgo 8), `--full-fit-timeout-min` **nunca fue calibrado** — es un valor redondo elegido como "red de seguridad generosa" en un momento en que ninguna corrida real había llegado siquiera a completar el fit final (todas fallaban antes, por los incidentes de Hallazgos 4 y 8). No hay ningún dato real detrás del número 40.

**Punto 2 — hallazgo más importante, leyendo el código fuente de `mgwr` (no solo el propio)**: `MGWR.fit()` obtiene `params` (los coeficientes) directo de `self.selector.params` — ya calculados dentro del backfitting que ya terminó — y `predy` es una multiplicación trivial. Lo caro de `.fit()` es `_chunk_compute_R()`, que calcula `ENP_j`/`CCT` (número efectivo de parámetros y varianzas de coeficientes) **volviendo a recorrer toda la historia de iteraciones del backfitting**, sin importar el flag `hat_matrix` (que solo controla si además se devuelve la matriz hat completa, no si se hace este cálculo). En la práctica, `.fit()` rehace casi todo el trabajo del backfitting una segunda vez, solo para producir dos valores — `ENP_j` y `CCT` — que **`05_ptna_score.py` no usa hoy en absoluto** (solo usa `params`, `predy`, `h3_index`).

**Riesgo real, no solo de tiempo**: `_full_fit_worker` solo pone algo en `result_queue` al final de todo — si el proceso timeoutea o muere durante `.fit()`, se pierde también el backfitting ya completado (bandwidths + coeficientes), obligando a repetir toda la corrida cara (~31 min de búsqueda + backfitting) para volver a llegar al mismo punto.

**Propuestas sobre la mesa (ninguna implementada todavía — decisión pendiente)**:
1. Guardar un checkpoint en disco con `params`/`predy`/bandwidths apenas termina `selector_full.search()` (antes de llamar a `.fit()`), de forma que un timeout/falla posterior en `.fit()` no obligue a repetir el backfitting.
2. Alternativa más agresiva: no llamar a `.fit()` en absoluto y construir el resultado directo desde `selector_full` — elimina la parte más cara y hoy no aprovechada, pero renuncia a `ENP_j`/`CCT` para siempre a menos que se recalculen aparte más adelante.
3. Híbrida (evaluándose): checkpoint temprano (opción 1) + `.fit()` como paso opcional detrás de un flag (ej. `--con-diagnosticos-enp`), para no pagar el costo en cada corrida pero conservar la posibilidad de recalcular `ENP_j`/`CCT` el día que se necesiten (ej. para justificar significancia estadística de los coeficientes en la redacción del TFM — todavía no se confirmó si el plan o la metodología van a requerir esto).

**Confirmado (15-sep-2026, noche)**: la corrida real terminó en `TimeoutError` a los 40.1 min — la hipótesis de riesgo dejó de ser teórica. Como sospechado, se perdió también el backfitting ya completado (bandwidths + coeficientes de las 16 variables sobre las 2579 filas), no solo `ENP_j`/`CCT` — obligando a repetir la corrida completa desde cero.

**Decisión tomada**: opción 3 (híbrida). Se implementa un checkpoint en disco con `params`/`predy`/`bandwidths_full` apenas termina `selector_full.search()`, y `.fit()` pasa a ser opcional detrás de un flag (`--con-diagnosticos-enp`, default `False`), corrible aparte sobre el checkpoint ya guardado sin repetir el backfitting. Esto desbloquea la corrida (vuelve a tardar ~31 min en vez de 71+) sin cerrar la puerta a `ENP_j`/`CCT` si el TFM los termina necesitando.

**Advertencia para quien vuelva a tocar este cálculo — bug real encontrado al implementar el checkpoint**: `selector_full.params` trae `k+1` columnas (intercepto + las 16 variables X), aunque el `X` que se le pasa al modelo solo tenga 16 — `GLM.__init__(..., constant=True)` agrega esa columna del intercepto internamente, dentro de la librería, no en este script. Calcular `predy` a mano (`np.sum(X * params, axis=1)`) con el `X` de 16 columnas revienta por `ValueError: shapes (n,16) (n,17)`. Hay que armar `X_with_intercept = np.column_stack([np.ones(len(X)), X])` antes de multiplicar. Confirmado leyendo `mgwr/gwr.py` real, no supuesto.

**Validación barata antes de la corrida real (15-sep-2026, noche)**: dry-run con una submuestra de 150 filas del dataset v2 filtrado y `--max-iter-multi 4` (segundos en vez de 31+ min) para probar la mecánica del checkpoint sin arriesgar la corrida completa. Confirmado: (a) el checkpoint se escribe a disco antes de que `.fit()` se llegue siquiera a invocar (con `--con-diagnosticos-enp` en su default `False`); (b) el archivo tiene las 7 claves esperadas (`h3_index`, `y`, `predy`, `params`, `feature_names`, `bandwidths_full`, `quality_columns`) con las formas correctas; (c) `05_ptna_score.py` lee ese checkpoint sin ningún error de formato — llega hasta `calcular_h3_confianza_baja` y se frena ahí solo por el guard ya conocido de `CONFIANZA_BAJA_VARIABLES` (`n_paradas_bus_500m` no existe en el v2, pendiente a propósito, ver Próximos pasos), no por ningún problema del checkpoint. El bug del intercepto de arriba se encontró y corrigió durante este mismo dry-run, antes de gastar los 31+ min reales.

### Hallazgo 10 — Multicolinealidad severa entre las 3 variables de tiempo del v2 (16-sep-2026, CONFIRMADO, decisión tomada)

La corrida real del v2 (16 variables, ver Hallazgo 9) terminó OK y produjo `ptna_mgwr_model_v2.pkl`, pero los coeficientes de 3 variables llamaron la atención: `tiempo_teide_min` (media 338.8), `tiempo_aeropuerto_min` (media 781.1) y `tiempo_polo_turistico_min` (media -1129.0) — todas con rango min/max casi nulo (bandwidth casi-global, esperable) pero de magnitud varios órdenes por encima del resto de las variables (mayoría entre -30 y +30) y del intercepto (~70).

**Diagnóstico de solo lectura sobre el checkpoint ya guardado** (sin recalcular el modelo):

1. **Matriz de correlación** entre las 3 variables de tiempo, sobre el dataset completo (2579 filas):
   ```
   tiempo_teide_min <-> tiempo_aeropuerto_min:         r = 0.9877
   tiempo_teide_min <-> tiempo_polo_turistico_min:     r = 0.9910
   tiempo_aeropuerto_min <-> tiempo_polo_turistico_min: r = 0.9970
   ```
   Ninguna otra variable del grupo de "bandwidth techo" (`slope_mean`, `temp_media_anual`, `lluvia_mm_anual`, `dist_parada_cercana_m`, `sentimiento_medio`) supera |r|=0.35 con nada — el problema es específico de estas 3, no del grupo entero.

2. **VIF completo sobre las 16 variables** (no solo las 3 de POIs, umbral 10):
   ```
   tiempo_polo_turistico_min    VIF=345.8   <-- 35x el umbral
   tiempo_teide_min             VIF=199.4   <-- 20x el umbral
   tiempo_aeropuerto_min        VIF=185.9   <-- 19x el umbral
   altitud_media_m              VIF=15.9    <-- levemente sobre el umbral (probable arrastre por su
                                                 correlación con las 3 de tiempo, no un problema propio
                                                 -- a reverificar con el VIF completo después del fix)
   dist_costa_km                VIF=7.1
   pct_area_enp                 VIF=3.7
   dist_hospital_km             VIF=2.7
   dist_parada_cercana_m        VIF=2.5
   temp_media_anual             VIF=2.1
   slope_mean                   VIF=1.6
   n_restaurantes                VIF=1.5
   ndvi_medio                   VIF=1.4
   lluvia_mm_anual               VIF=1.3
   n_naturaleza                  VIF=1.3
   n_cultura                     VIF=1.3
   sentimiento_medio             VIF=1.0
   ```
   Las 3 de tiempo están 19x-35x por encima del umbral — multicolinealidad severa de manual, no un caso límite. Todo el resto (salvo `altitud_media_m`, levemente) está muy por debajo de 10, incluidas las 3 de POIs (Hallazgo 1) que ya se habían chequeado antes.

3. **Contribución individual al `predy` en los hexágonos más extremos** (5 con `predy` más alto, 5 con `predy` más bajo) — la firma clásica de colinealidad, coeficientes que se cancelan entre sí:
   | Grupo | contrib. `tiempo_teide_min` | contrib. `tiempo_aeropuerto_min` | contrib. `tiempo_polo_turistico_min` | **suma de las 3** |
   |---|---|---|---|---|
   | TOP 5 predy | -55 a -95 | -150 a -220 | +280 a +430 | **+95 a +155** |
   | BOTTOM 5 predy | -44 a -95 | -150 a -220 | +280 a +390 | **+33 a +115** |

   La suma neta de las 3 es un orden de magnitud menor que cualquiera de las contribuciones individuales — exactamente el patrón de coeficientes inflados que se cancelan al combinarse, no de tres efectos genuinos que se suman. Extra (no pedido, cierra la interpretación): en los hexágonos con `predy` más alto, `n_restaurantes` domina el resultado (contribuye >85% del `predy` total) — la inestabilidad de las 3 variables de tiempo no está distorsionando las predicciones extremas de `ptna_score`, pero sí hace que sus coeficientes individuales no sean interpretables por separado.

**Decisión tomada**: excluir `tiempo_teide_min` y `tiempo_polo_turistico_min` de `PTNA_QUALITY_COLUMNS`, conservando solo `tiempo_aeropuerto_min`. Razón de negocio: continuidad con el v1 (que ya usaba el equivalente `tiempo_tfs_min`), es una columna precalculada en `gold_h3_accesibilidad` (no requiere `LEAST()`), y es la más directamente interpretable para TUI ("tiempo al aeropuerto") frente a las otras dos, que en una isla del tamaño de Tenerife miden esencialmente la misma dimensión subyacente ("qué tan lejos del interior/costa está el hexágono"). 16 → 14 variables X. `bw_floor` pasa de 48 a 42 (`max(30, 3×14)`).

**Esto invalida `ptna_mgwr_model_v2.pkl` como versión definitiva del modelo** — pasa a ser "v2, primer intento" (útil como referencia y como el dataset que permitió diagnosticar esta multicolinealidad, no se borra). Hace falta una corrida v3 con las 14 variables. Outputs de `01`/`02`/`04` renombrados con sufijo `_v3` explícito (mismo criterio que v1→v2) para no pisar `ptna_dataset_raw_v2.parquet`, `ptna_dataset_filtered_v2.parquet`, `ptna_mgwr_model_v2.pkl` ni su checkpoint. `05_ptna_score.py` todavía apunta a los nombres `_v2` por default — pendiente de actualizar a `_v3` cuando se llegue a rediagnosticar `CONFIANZA_BAJA_VARIABLES` (ver Próximos pasos), no se tocó en esta pasada.

## 7. Brechas de datos — estado actualizado (15-sep-2026)

1. ~~`viirs_medio`~~ — ✅ Resuelto (12-sep-2026), existe en `gold_h3_master`. **Nota v2**: excluida igual del modelo por colinealidad/proxy de Y (plan Subtarea 5.1), no por brecha de dato.
2. ~~`n_pois`~~ — ✅ Resuelto, pero decisión revertida en el v2: ver Hallazgo 1. Ya no se usa `n_pois_turisticos` sumada, se usan `n_restaurantes`/`n_naturaleza`/`n_cultura` por separado.
3. ~~Columna de plazas hoteleras~~ — ✅ Resuelto, `n_plazas_registro` existe tal cual.
4. `n_paradas_15min` — ⚠️ Sigue sin existir como métrica de tiempo real. **Nota v2**: ya no aplica de todos modos — la variable del modelo pasó a `dist_parada_cercana_m` (distancia continua), no un conteo por radio.
5. ~~Sentimiento agregado~~ — ✅ Resuelto (15-sep-2026). Ver Hallazgo 3 (tabla fuente) y Hallazgo 5 (cobertura real, 15.9%, y cómo se integró). Ya no es bloqueante.
6. ~~Ambigüedad `gold_h3_accesibilidad` vs `h3_accesibilidad`~~ — ✅ Resuelto de hecho, la tabla vieja ya no existe en el esquema.
7. Distancia a costa, dos métricas con distinto punto de referencia. Ver Hallazgo 2. No bloqueante, decisión tomada (12-sep-2026).
8. **Nuevo (15-sep-2026)** — Nombres de columna incorrectos en la sección 3 de este documento (`tiempo_polo_sur_min`/`tiempo_polo_norte_min` → `tiempo_extremo_sur_min`/`tiempo_extremo_norte_min`). Corregido.
9. **Nuevo (15-sep-2026)** — Inconsistencia de `plan_final_mejorado.md` sobre dónde vive `gold_h3_sentimiento`. Ver Hallazgo 7. No bloqueante, decisión tomada (tabla propia).
10. **Nuevo (15-sep-2026)** — `LinAlgError` en la búsqueda de bandwidth sobre la submuestra (`_bw_search_worker`), causado por `lluvia_mm_anual`/`tiempo_teide_min`/`tiempo_aeropuerto_min`/`tiempo_polo_turistico_min` con varianza local ~0 en bandwidths chicos. Ver Hallazgo 8. Resuelto (`init_multi=n_sub`).
11. **Nuevo (16-sep-2026)** — Multicolinealidad severa entre `tiempo_teide_min`/`tiempo_aeropuerto_min`/`tiempo_polo_turistico_min` (VIF 185.9-345.8). Ver Hallazgo 10. Resuelto (excluir 2 de las 3, conservar `tiempo_aeropuerto_min`) — falta correr el v3 con las 14 variables.

**Ningún bloqueante activo a la fecha (16-sep-2026) — pendiente de ejecución, no de decisión: falta correr `04_run_model.py` v3.**

## 8. Decisiones tomadas

- Usar `dist_costa_km` (Bloque 4/centroide) en vez de `distancia_costa_metros` (Bloque 1/borde) (12-sep-2026).
- Diseño modular de la query del dataset (joins separados por fuente) para poder sumar tablas nuevas después sin reescribir todo (12-sep-2026) — aplicado de nuevo para sumar `gold_h3_sentimiento` en el v2 (15-sep-2026).
- **[v2, 15-sep-2026]** Revertida la decisión del 12-sep de sumar `n_pois_turisticos` — usar `n_restaurantes`/`n_naturaleza`/`n_cultura` como 3 variables X independientes (Hallazgo 1), fieles a `plan_final_mejorado.md` en vez del resumen de esa sesión.
- **[v2, 15-sep-2026]** Excluir `ndbi_medio` y `viirs_medio` del set de variables X (colinealidad/proxy directo de la variable Y, según el plan).
- **[v2, 15-sep-2026]** Sumar `sentimiento_medio` como variable X (imputada con mediana), pero excluirla del filtro de >50% NaN de `02_filter_nan.py` dada su cobertura del 15.9% (Hallazgo 5).
- **[v2, 15-sep-2026]** `queja_principal` en `gold_h3_sentimiento` se calcula filtrando por `sentimiento = 'Negative'` (Hallazgo 6).
- **[v2, 15-sep-2026]** `gold.gold_h3_sentimiento` construida como tabla real independiente, no subquery inline ni fusionada en `gold_h3_master` (Hallazgo 7).
- **[v2, 15-sep-2026]** Chequeo de VIF (umbral 10, el que menciona el propio plan) agregado en `04_run_model.py`, específicamente entre `n_restaurantes`/`n_naturaleza`/`n_cultura` por ser las más obviamente correlacionadas tras separarlas (Hallazgo 1). Resultado del dry-run contra datos reales (sin correr el modelo completo): VIF de 1.14 a 1.34 para las 3 — muy por debajo del umbral, sin problema de multicolinealidad detectado.
- **[v2, 15-sep-2026]** `init_multi=n_sub` agregado a `_bw_search_worker` en `04_run_model.py` (Hallazgo 8) — mismo patrón que `_full_fit_worker` ya usaba con `init_multi=n_total`, aplicado ahora también al paso que le faltaba. `--bw-search-timeout-min` subido de 30 a 45 min; `--max-iter-multi` se mantiene en 50 sin cambios.
- **[v3, 16-sep-2026]** Excluir `tiempo_teide_min` y `tiempo_polo_turistico_min` de `PTNA_QUALITY_COLUMNS`, conservando solo `tiempo_aeropuerto_min` (Hallazgo 10) — VIF 185.9-345.8 entre las 3, muy por encima del umbral 10. 16 → 14 variables, `bw_floor` 48 → 42.

## 9. Próximos pasos

- [x] Aplicar el filtro de >50% NaN sobre el dataset real v2 — hecho, 0 hexágonos excluidos (`02_filter_nan.py`, 15-sep-2026).
- [x] Sumar sentimiento vía el join modular — hecho (`gold.gold_h3_sentimiento`, Hallazgo 5/6/7).
- [x] Defaults de entrada/salida de `01`/`02`/`04` con sufijo `_v3` explícito (Hallazgo 10) — para no sobreescribir los artefactos del v2 (que sirvieron para diagnosticar la multicolinealidad) ni del v1.
- [x] `LinAlgError` en la búsqueda sobre la submuestra — resuelto con `init_multi=n_sub`, ver Hallazgo 8. `--bw-search-timeout-min` subido de 30 a 45 min.
- [x] Aplicar el fix de Hallazgo 8 (`init_multi=n_sub`) de forma permanente en `_bw_search_worker` — hecho, verificado con `ast.parse` y con que los artefactos del v1 no se tocaron.
- [x] **Fase B, primer intento (15-sep-2026, tarde) — FALLÓ por TimeoutError, backfitting perdido.** `04_run_model.py` corrido en terminal contra el dataset v2 filtrado. Búsqueda de bandwidth sobre la submuestra: completada sin error (16:26 min). Backfitting sobre el dataset completo: completado sin error (4:15 min). Cálculo de diagnósticos post-fit (`MGWR.fit()`): timeout a los 40.1 min, sin checkpoint intermedio — se perdió también el backfitting ya completado. Ver Hallazgo 9.
- [x] Implementar el fix de Hallazgo 9 (checkpoint + `.fit()` opcional detrás de `--con-diagnosticos-enp`) — hecho, validado con dry-run de 150 filas antes de relanzar (bug del intercepto encontrado y corregido en ese mismo dry-run, ver Hallazgo 9).
- [x] **Fase B, segundo intento (15/16-sep-2026, noche) — OK, produjo `ptna_mgwr_model_v2.pkl`.** Búsqueda sobre la submuestra: 998.2s (~16.6 min). Checkpoint (backfitting completo): 12.1 min. Total: 2038.8s (~34 min). Sin diagnósticos ENP/CCT (default). Este resultado es el que permitió detectar la multicolinealidad del Hallazgo 10 — **queda invalidado como versión definitiva**, pasa a ser "v2, primer intento" (no se borra, sirve de referencia).
- [ ] **Fase B, tercer intento (v3, 14 variables) — pendiente de ejecución.** Con el fix de Hallazgo 10 ya aplicado en `_db.py`, correr `04_run_model.py` contra un dataset v3 recién generado (`01` → `02` → `04`, defaults ya apuntan a `_v3`). Esperable: ~mismo tiempo que el segundo intento del v2 (la lógica no cambió, solo bajó de 16 a 14 variables) y que `tiempo_teide_min`/`tiempo_polo_turistico_min` ya no aparezcan como coeficientes — revisar igual el VIF completo de las 14 variables tras esta corrida para confirmar que `altitud_media_m` (15.9 en el v2) baja de 10 sin las 2 variables eliminadas.
- [ ] Adaptar `05_ptna_score.py` para v3: sus defaults de `--model`/`--dataset`/`--output` todavía apuntan a los nombres `_v2` (no se tocaron en el Hallazgo 10, fuera de alcance de esa pasada) — actualizar a `_v3` junto con rediagnosticar `CONFIANZA_BAJA_VARIABLES` (`n_paradas_bus_500m` no existe desde el v2, sigue pendiente, guard ya existente evita que falle en silencio).
- [ ] Decidir dónde vive el resultado final de PTNA en Postgres: `06_load_to_gold.py` existe pero nunca se corrió — la tabla v1 (`gold_h3_ptna_v1_sin_sentimiento`) no existe todavía en Postgres, solo como parquet local. Subir v2 queda pendiente de decisión explícita, no se automatiza.
- [ ] Avanzar a Subtarea 5.3 (ESG) una vez cerrada 5.1 y 5.2 del v2 — ya se confirmó que `n_hoteles`/`n_vv` están disponibles y que `gold_h3_sentimiento` (con `queja_principal`, incluye "ruido" si aparece como aspecto) está lista; falta evaluar `dist_enp_km` vs. `pct_area_enp`/`es_enp` como insumo. No tocar todavía (fuera del alcance de esta sesión) — condicionado además a verificar si `gold_municipio_master`/`gold_municipio_empleo` existen en Postgres real para las Subtareas 5.3/5.4 de escala municipal.

## Cómo usar este documento en una conversación nueva

Al empezar, decir algo como: *"Retomo el Bloque 5 (MGWR/PTNA) del TFM — ya tenés el contexto técnico completo en el archivo de Proyecto."* No hace falta re-explicar el plan ni las brechas — solo referenciar la sección relevante si hace falta precisión (ej. "sección 6, hallazgo de distancia a costa"). Para contexto del repo en general, usar `contexto_maestro_repo.md`.
