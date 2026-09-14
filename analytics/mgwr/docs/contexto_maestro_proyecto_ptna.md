# Contexto maestro — TFM AI Dashboard Tenerife: Bloque 5 (MGWR + Índice PTNA)

**Fecha de creación:** 2 de septiembre de 2026
**Última actualización:** 12 de septiembre de 2026 — sesión de investigación de variables reales contra `gold.gold_h3_master` (ya existe como tabla, corrige la versión anterior de este documento que la daba por inexistente).
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

### Columnas completas de `gold_h3_accesibilidad` (referencia)

```
h3_index, tiempo_tfs_min, tiempo_tfn_min, tiempo_capital_min, tiempo_polo_sur_min,
tiempo_polo_norte_min, tiempo_teide_min, tiempo_la_laguna_min, tiempo_candelaria_min,
tiempo_los_gigantes_min, tiempo_el_medano_min, tiempo_garachico_min, tiempo_anaga_min,
tiempo_masca_min, tiempo_vilaflor_min, tiempo_la_orotava_min, tiempo_guimar_min,
tiempo_buenavista_min, tiempo_arico_min, tiempo_aeropuerto_min, aeropuerto_mas_cercano,
n_paradas_bus_200m, n_paradas_bus_500m, n_paradas_bus_1000m, dist_parada_cercana_m,
dist_hospital_km, dist_costa_km
```

### Filtro de calidad (>50% NaN) — sigue pendiente de calcular a mano

No existe `excluded_high_nan` ni `n_features_missing` en `gold_h3_master` (la versión vieja de este documento asumía que sí, era incorrecto). Hay que calcular el conteo de NULLs sobre las variables X finales elegidas antes de correr el modelo, con una query tipo:
```sql
SELECT h3_index,
    ((ndvi_medio IS NULL)::int + (ndbi_medio IS NULL)::int + (viirs_medio IS NULL)::int +
     (altitud_media_m IS NULL)::int + (slope_mean IS NULL)::int +
     (n_restaurantes IS NULL)::int + (n_paradas_bus_500m IS NULL)::int) AS n_nulos
FROM gold.gold_h3_master m
LEFT JOIN gold.gold_h3_accesibilidad a ON a.h3_index = m.h3_index;
```

### Query de construcción del dataset (versión actualizada 12-sep-2026)

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
-- Falta aplicar el filtro de >50% NaN antes de usar este dataset en el modelo
```

Diseño modular: cuando exista la tabla de sentimiento, sumar como CTE separada + `LEFT JOIN` adicional, sin reescribir el resto.

## 4. Subtarea 5.2 — Ejecutar el modelo MGWR e Índice PTNA

Todavía no iniciada (depende de cerrar 5.1 primero — ya con el dataset real armado, ver sección 3). Referencia del plan para cuando se llegue a esta etapa:

- Normalizar todas las variables X con `StandardScaler` de sklearn antes de pasarlas al modelo.
- Las coordenadas de entrada son los **centroides** de cada hexágono H3, en EPSG:4326 (`gold_h3_master.centroide_lon/lat`).
- Código esqueleto del plan:

```python
from mgwr.gwr import MGWR
from mgwr.sel_bw import Sel_BW
from sklearn.preprocessing import StandardScaler
import numpy as np

coords = list(zip(df['centroide_lon'], df['centroide_lat']))
X = StandardScaler().fit_transform(df[variables_x].fillna(df[variables_x].median()))
y = df[['densidad_plazas_km2']].values

bw = Sel_BW(coords, y, X).search()
modelo = MGWR(coords, y, X, bw).fit()

df['coef_ndvi']  = modelo.params[:, 0]
df['ptna_score'] = modelo.predy.flatten() - y.flatten()  # Esperado - Observado
```

**Nota sobre pipeline técnico**: si se quiere validar que MGWR corre correctamente antes de tener el dataset 100% cerrado (ej. mientras se espera sentimiento), usar un dataset sintético separado (`numpy.random`), en un script de prueba aparte que nunca toque las tablas reales de Gold — evita el riesgo de mezclar accidentalmente datos ficticios con el dataset real de producción.

- **Output esperado:** DataFrame con coeficientes locales y `ptna_score`. Pendiente decidir dónde vive el resultado final: ¿se crea un `gold.h3_master` unificado recién en este punto (nombre distinto de `gold.gold_h3_master`, que ya cumple ese rol para varias variables), o el output vive directo en `gold.h3_ptna` (tabla nueva, mencionada en el plan, todavía no creada)?

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

**Decisión tomada para PTNA**: no usar `n_pois_total`. Usar `n_pois_turisticos` = suma de las 4 subcategorías, variable con significado territorial-turístico más limpio (sin transporte/servicios genéricos diluyendo la señal).

**Pendiente**: preguntar al responsable de Bloque 1 (Espacial/OSM) si el diseño es intencional o si conviene ampliar las subcategorías para que `n_pois_total` sea exhaustivo — no bloqueante, decisión ya tomada mientras tanto.

### Hallazgo 2 — Distancia a costa: dos métricas válidas con distinto punto de referencia

- `gold_h3_master.distancia_costa_metros` (Subtarea 1.10, Bloque 1): mide desde el **hexágono completo** (polígono) hasta `ST_Boundary(ST_Union(limites_municipales))`. Al no partir de un punto, PostGIS calcula la distancia mínima desde el borde más cercano del polígono.
- `gold_h3_accesibilidad.dist_costa_km` (Subtarea 4.5, Bloque 4): mide explícitamente desde el **centroide** del hexágono (`h.centroide_lon/lat`), con cast a `::geography`.

Offset observado entre ambas: sistemático, entre 0.49-0.58 km, mayor cuanto más cerca de la costa en términos relativos (30%+ de error relativo en hexágonos costeros). Se verificó con una query de distancia centroide-a-borde del mismo hexágono (~491m, mismo orden de magnitud que el offset — confirma la dirección de la hipótesis, aunque no coincide al milímetro, posiblemente por diferencias de geometría exacta borde/vértice o precisión geodésica).

**No es un error** — son dos definiciones legítimas con propósitos distintos (1.10 pensada para valor inmobiliario general, 4.5 específicamente para atractivo turístico con respaldo de literatura de precios hedónicos, β ≈ -0.42).

**Decisión tomada para PTNA**: usar `dist_costa_km` (Bloque 4), por dos motivos — (a) consistencia con que el modelo ya usa centroides como coordenadas de entrada en MGWR, (b) respaldo empírico específico para el fenómeno que PTNA modela (atractivo turístico, no valor inmobiliario general).

**No incluir ambas variables en el modelo**: al estar casi perfectamente correlacionadas (offset ~constante), meter ambas como X en MGWR infla la varianza de los coeficientes y puede producir estimaciones inestables por zona sin aportar información real adicional.

**Pendiente**: avisar a Bloque 1 y Bloque 4 el hallazgo, por transparencia y documentación — no bloqueante, decisión ya tomada.

### Hallazgo 3 — Sentimiento agregado por hexágono: tabla fuente no existe, en construcción

`gold.nlp_sentimiento_resenas` (que la versión anterior de este documento daba por existente, sin agregar) **ya no existe en ningún esquema** — se confirmó con búsqueda amplia en `gold` y `silver` (`information_schema.tables`, filtro por `%sentimiento%`/`%sentiment%`/`%nlp%`). Consultado con el equipo: la tabla está en construcción por el área de NLP, no se perdió.

**Decisión tomada**: dataset v1 de PTNA sin esta variable. Diseño modular (query con `LEFT JOIN` adicional aislado) para incorporarla el día que exista, sin rehacer el resto del dataset. Se descartó usar datos ficticios/sintéticos mezclados en el dataset real (riesgo de que se corra el modelo con datos inventados sin darse cuenta); si se necesita validar que el pipeline de MGWR corre técnicamente antes de tener el dato real, usar un dataset sintético separado en un script de prueba aparte, nunca contra las tablas reales de Gold.

**Único bloqueante activo del Bloque 5 a la fecha.**

## 7. Brechas de datos — estado actualizado (12-sep-2026)

1. ~~`viirs_medio`~~ — ✅ Resuelto, existe en `gold_h3_master`.
2. ~~`n_pois`~~ — ✅ Resuelto, ver Hallazgo 1 (usar `n_pois_turisticos`, no `n_pois_total`).
3. ~~Columna de plazas hoteleras~~ — ✅ Resuelto, `n_plazas_registro` existe tal cual.
4. `n_paradas_15min` — ⚠️ Sigue sin existir como métrica de tiempo real. Proxy de distancia (`n_paradas_bus_500m`) aceptado, no bloqueante.
5. ~~Sentimiento agregado~~ — ❌ Reclasificado: no es que falte el `GROUP BY`, la tabla fuente completa no existe todavía. Ver Hallazgo 3. **Único bloqueante activo.**
6. ~~Ambigüedad `gold_h3_accesibilidad` vs `h3_accesibilidad`~~ — ✅ Resuelto de hecho, la tabla vieja ya no existe en el esquema.
7. **Nuevo (12-sep-2026)** — Distancia a costa, dos métricas con distinto punto de referencia. Ver Hallazgo 2. No bloqueante, decisión tomada.

## 8. Decisiones tomadas

- Usar `n_pois_turisticos` (suma de 4 subcategorías) en vez de `n_pois_total` (12-sep-2026).
- Usar `dist_costa_km` (Bloque 4/centroide) en vez de `distancia_costa_metros` (Bloque 1/borde) (12-sep-2026).
- No usar datos sintéticos mezclados en el dataset real para cubrir la ausencia de sentimiento; solo en script de prueba de mecánica aparte si hace falta (12-sep-2026).
- Diseño modular de la query del dataset (joins separados por fuente) para poder sumar sentimiento después sin reescribir todo (12-sep-2026).

## 9. Próximos pasos

- [ ] Comentar los 3 hallazgos en la reunión de seguimiento (12-sep-2026 o siguiente).
- [ ] Avisar a Bloque 1 el hallazgo de `n_pois_total` (no bloqueante, FYI + pregunta de diseño).
- [ ] Avisar a Bloque 1 y Bloque 4 el hallazgo de distancia a costa (no bloqueante, FYI).
- [ ] Aplicar el filtro de >50% NaN sobre el dataset real (query en sección 3) antes de correr el modelo.
- [ ] Correr el esqueleto de MGWR (Subtarea 5.2) sobre el dataset real sin sentimiento, para validar que el pipeline técnico funciona mientras se espera esa variable.
- [ ] Sumar sentimiento vía el join modular apenas la tabla NLP esté lista.
- [ ] Decidir dónde vive el resultado final de PTNA: ¿tabla `gold.h3_ptna` nueva, o se integra a `gold.gold_h3_master`?
- [ ] Avanzar a Subtarea 5.3 (ESG) una vez cerrada 5.1 y 5.2 — ya se confirmó que `n_hoteles`/`n_vv` están disponibles; falta evaluar `dist_enp_km` vs. `pct_area_enp`/`es_enp` como insumo.

## Cómo usar este documento en una conversación nueva

Al empezar, decir algo como: *"Retomo el Bloque 5 (MGWR/PTNA) del TFM — ya tenés el contexto técnico completo en el archivo de Proyecto."* No hace falta re-explicar el plan ni las brechas — solo referenciar la sección relevante si hace falta precisión (ej. "sección 6, hallazgo de distancia a costa"). Para contexto del repo en general, usar `contexto_maestro_repo.md`.
