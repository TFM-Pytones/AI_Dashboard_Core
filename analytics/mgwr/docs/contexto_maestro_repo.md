# Contexto maestro — TFM AI Dashboard Tenerife: repo completo

**Última actualización:** 12 de septiembre de 2026 — actualización de la sección 3 (Gold) tras investigación real de variables del Bloque 5, ver nota al final de esa sección.
**Actualización anterior:** 2 de septiembre de 2026
**Propósito:** contexto general y autosuficiente de TODO el repo `TFM-Pytones/AI_Dashboard_Core`, para arrancar conversaciones nuevas sobre cualquier issue, no solo Booking. Para el detalle técnico de scraping de Booking (selectores, bugs de Selenium, heurísticas de descubrimiento) seguí usando `contexto_maestro_proyecto.md` — ese documento NO se tocó y sigue siendo la referencia de la issue #12 cerrada. Este documento apunta ahí en vez de duplicar ese contenido.

**Mapa visual complementario:** `mapa_repo_ai_dashboard_core.canvas` (Obsidian, en `OneDrive/Documentos/FACULTAD/TFM/`) — pipeline completo, estado por fuente, esquema Silver/Gold, infraestructura y backlog, todo con coordenadas espaciales. Generado el 30-ago-2026 leyendo el código y git log reales, no solo docs. **Nota:** la sección 3 de este documento (estado real de Gold) se actualizó por última vez el 12-sep-2026 con datos más recientes que el canvas — priorizar este documento en caso de discrepancia hasta que el canvas se regenere.

---

## 1. Panorama general del proyecto

TFM sobre inteligencia territorial turística en Tenerife. Arquitectura Data Lakehouse en Azure:

```
Fuentes (Booking, TripAdvisor, YouTube, LosViajeros, GTFS, AENA,
         Alojamientos oficiales, Clima/Agrocabildo, Espacial, ISTAC, Satélite)
        ↓
Bronce: Azure Blob Storage (storage account `datalaketfmtenerife`,
        contenedor `bronce-raw`, Parquet) — GTFS es la única excepción,
        escribe directo a Silver
        ↓
Postgres esquema `bronze`: Azure Postgres Flexible `db-tfm-tenerife`
        ↓
Silver: dbt, esquema `silver` — ~25 modelos, la mayoría ✅ completos
        ↓
Gold: esquema `gold` — ver sección 3 (estado actualizado 12-sep-2026):
      `gold.gold_h3_master` existe como tabla consolidada real, con la
      mayoría de variables satelitales/topográficas/POIs/alojamiento en
      un solo lugar. Coexiste con tablas separadas por bloque
      (`gold_h3_accesibilidad`, `nlp_topics`, etc.). Plan completo de
      10 Bloques definido en `plan_final_mejorado.md`, con varios
      bloques ya con datos reales subidos.
        ↓
Dashboard: Streamlit — NO iniciado. Frontend existente usa datos mockeados.
```

Repo: `TFM-Pytones/AI_Dashboard_Core`. Rama de trabajo histórica: `feature/scraping-reviews` (issue #12, ya cerrada/mergeada). Para trabajo nuevo, arrancar rama propia desde `main` actualizado.

**Nomenclatura de esquemas — cuidado con docs viejos**: el estándar actual y real es `bronze`/`silver`/`gold` (inglés). Documentos más viejos (`github_issues_plan.md`, `docs/00_indice_tfm.md`, `sql/README.md`) usan `bronce`/`plata`/`oro` (español) o incluso `raw_data`/`processed_data` — quedaron obsoletos. `plan_final_mejorado.md` (25-ago-2026) es el plan vigente y reemplaza explícitamente a `github_issues_plan.md` en todo lo de arquitectura de datos.

## 2. Equipo — quién trabaja en qué (inferido de git log, sin confirmación directa salvo donde se indica)

| Persona (usuario git) | Área principal |
|---|---|
| jcabrera1605-netizen (vos) | Booking (issue #12, cerrada) + **Bloque 5 Gold (`gold_h3_ptna` — MGWR/PTNA)**, asignado 02-sep-2026 |
| roberhernando / Roberto Hernando Ascaso | Infra Azure, migración Neon→Azure, reestructuración de carpetas, capa espacial, `gold_h3_master`, clima/Agrocabildo (ruta hardcodeada `C:\Users\ROBERTO\...` confirma autoría) |
| jtmn03-2002 | YouTube, NLP (sentimiento #16/#17, aspectos #18), setup Hugging Face |
| guillermoortigosa28 ("Guille") | Probable autor de microdatos/ISTAC/AENA/Alojamientos oficiales (issue #5, cerrada) — sin confirmación directa en código, solo por patrón de commits "Add files via upload" y renames de esa época |
| jaimedevera32-alt | LosViajeros (scraper + modelos Silver), configuración inicial de dbt |
| Mario Rosete (mariorosete) | GTFS (notebooks 7 y 8) — ruta hardcodeada `C:\Users\mario\...` confirma autoría |

VM compartida (`mv-orquestador-tfm`) — cuidado con archivos de otros: logs y progress-trackers de otras fuentes (`clima_vm.log`, `agrocabildo/backfill_progress.json`, etc.) no son tuyos, no tocar.

## 3. Estado por fuente (resumen — detalle completo en el canvas, Zona 2 y 3)

| Fuente | Bronce | Silver (dbt) | Gold | Nota |
|---|---|---|---|---|
| Booking | ✅ | ✅ tag:booking, único con tests | usado en Gold (features_h3, nlp_sentimiento_resenas) | issue #12 cerrada |
| TripAdvisor | ✅ | ✅ tag:tripadvisor | usado en Gold | CATALOGO_FUENTES_DATOS.md dice "pendiente", está desactualizado |
| YouTube | ✅ | ✅ tag:youtube | NLP en silver, parcialmente en gold (nlp_topics, nlp_informe_global) | pipeline de sentimiento activo |
| LosViajeros (foro) | ⚠️ solo en rama sin mergear `origin/losviajeros_scraping` | ✅ tag:foro en main (posiblemente vacía) | no | **modelos Silver en main sin su ingesta mergeada** |
| GTFS | ⚠️ bypassa Bronce | ✅ (vía notebooks, no dbt) | usado en gold_h3_accesibilidad | única fuente sin `ingestion/gtfs/*.py` real — todo en `notebooks/7_...` y `notebooks/8_...` |
| AENA | ✅ | ✅ tag:aena | no | — |
| Alojamientos oficiales | ✅ | ✅ tag:alojamiento | usado en features_h3 (n_alojamientos) | — |
| Clima/Agrocabildo | ✅ | ✅ (sin tags dbt) | no confirmado en tablas Gold vistas al 02-sep | AEMET no se usa, es 100% Agrocabildo pese a que `ingestion/README.md` diga "aemet/" |
| Espacial (OSM/ENP/H3/zonas/cabildo) | ✅ | ✅ tag:espacial | parcial — ver brecha `n_pois` abajo | ENP y oficinas turismo con columnas placeholder (`id`/`municipio` NULL) |
| ISTAC | ✅ | ✅ tag:istac | no | gaps documentados en `docs/catalogo_datos_istac.md` |
| Satélite (Sentinel2/VIIRS) | ✅ | ⚠️ `silver_indices_satelite` sin tag dbt | NDVI/NDBI sí están en `features_h3`; **VIIRS no aparece en ninguna tabla Gold** | ex-"Copernicus" en docs viejos |
| MDT (elevación) | ✅ | ❌ no hay modelo silver | sí en Gold: `features_h3.elevation_mean`, `slope_mean`, `aspect_mean`, `hillshade_mean` | — |
| NLP Sentimiento/Aspectos | — | ✅ `silver.sentiment_results` / `silver.aspect_results` | ✅ sí migrado a Gold: `gold.nlp_sentimiento_resenas`, `gold.nlp_aspectos_resenas` (sin agregar por hexágono todavía) | corrige nota anterior de este documento, que decía "no migrado" — sí llegó a Gold, falta la agregación por `h3_index` |

### Actualización 02-sep-2026 — Estado real de Gold (tablas confirmadas por consulta directa a `information_schema`)

No existe una tabla `gold.h3_master` unificada de ~60 columnas como se documentó en versiones anteriores de este archivo. Lo que existe hoy son tablas temáticas repartidas por bloque del plan (`plan_final_mejorado.md`):

| Tabla Gold | Contenido | Bloque del plan |
|---|---|---|
| `gold.features_h3` | NDVI, NDBI, elevación, pendiente, aspect, hillshade, `is_protected_area`, `n_alojamientos`, `n_paradas_transporte` (+ versiones `_scaled` normalizadas), flags de calidad (`n_features_missing`, `excluded_high_nan`) | Bloque 1 |
| `gold.gold_h3_accesibilidad` | Tiempos a ~19 puntos de interés (TFS, TFN, capital, Teide, municipios, etc.), aeropuerto más cercano, paradas de bus en buffers 200/500/1000m, distancias a hospital/costa | Bloque 4 |
| `gold.h3_accesibilidad` | ⚠️ Versión más chica de la anterior — mismas columnas de tiempos, pero solo buffer de 500m y sin el de 200m/1000m. **Pendiente confirmar con autor del Bloque 4 cuál de las dos es la vigente** — no usar ninguna en un modelo definitivo sin esa confirmación |
| `gold.nlp_sentimiento_resenas` | Sentimiento sin agregar (1 fila = 1 reseña), con `resena_id`, `hotel_id`, `score`, `h3_index`, `fuente` | Bloque 2 |
| `gold.nlp_aspectos_resenas` | Aspectos NLP sin agregar (1 fila = 1 reseña × aspecto), con `aspecto`, `sentimiento`, `confianza` | Bloque 2 |
| `gold.nlp_topics` | Resultados de topic modeling (BERTopic), con `topic_id`, `topic_label`, `probability` | Bloque 3 |
| `gold.nlp_informe_global` | Informes narrativos generados por LLM | Bloque 9 |
| `gold.geo_mentions` | Menciones geográficas extraídas de texto (lugar mencionado, método de extracción) | Bloque 2/3 |
| `gold.isocronas_visuales` | Geometrías de isócronas por destino y rango de minutos | Bloque 4 |

**Brechas de datos identificadas (bloqueantes para Bloque 5 — MGWR/PTNA — y potencialmente para otros bloques que las usen):**
- **`viirs_medio`** — no existe en ninguna tabla Gold. Necesario para PTNA (Subtarea 5.1) y para el Índice ESG Territorial (Subtarea 5.3, componente ambiental).
- **`n_pois`** — no existe. No confundir con `features_h3.n_alojamientos`, que cuenta establecimientos de alojamiento, no POIs de OSM en general.
- **Columna de plazas hoteleras** (`n_plazas_registro` o similar) — la variable Y del modelo PTNA es densidad de *plazas*, no de *establecimientos*. Solo se encontró `features_h3.n_alojamientos` (conteo de alojamientos). Falta confirmar si existe una columna de plazas/camas en alguna tabla no revisada aún, o si hay que calcularla desde Silver.
- **`sentimiento_medio` agregado por hexágono** — el dato base sí existe (`gold.nlp_sentimiento_resenas`), pero está a nivel de reseña individual, no agregado. Requiere un `AVG(score) GROUP BY h3_index` antes de poder usarse como variable X.

### Actualización 12-sep-2026 — Corrección importante sobre el estado real de Gold

La tabla anterior y las brechas de arriba quedaron desactualizadas tras una sesión de investigación directa contra Postgres para el Bloque 5. Cambios confirmados:

- **`gold.gold_h3_master` SÍ existe** como tabla consolidada real (no es una tabla soñada del plan, y tampoco son solo tablas temáticas sueltas como se documentó el 02-sep). Contiene la gran mayoría de variables satelitales, topográficas, de POIs y de alojamiento/plazas en un solo lugar. Sigue existiendo `gold.gold_h3_accesibilidad` como tabla separada (no fusionada en el master).
- **`viirs_medio`** — ✅ ya no es una brecha, está en `gold_h3_master` con desagregado anual (2022-2026) y trimestral.
- **`n_plazas_registro`** — ✅ ya no es una brecha, existe tal cual en `gold_h3_master`. La variable Y de PTNA ya no necesita el proxy `n_alojamientos`.
- **Sentimiento (`gold.nlp_sentimiento_resenas`)** — ❌ empeoró respecto a lo documentado: la tabla **ya no existe en ningún esquema** (ni gold ni silver), confirmado con búsqueda amplia. No es un problema de falta de agregación — la fuente completa no está. El equipo de NLP la está construyendo.
- **`n_pois`** — existe como `n_pois_total` en `gold_h3_master`, pero se descubrió que no es una suma exhaustiva de sus subcategorías (mezcla con `n_pois_total` incluye Transporte y Servicios_Básicos, categorías no contempladas en ninguna subcategoría). No es un bug de código, es diseño no documentado. Ver detalle completo en `contexto_maestro_proyecto_ptna.md`, sección 6.
- **Nuevo hallazgo — distancia a costa**: `gold_h3_master.distancia_costa_metros` (Bloque 1) y `gold_h3_accesibilidad.dist_costa_km` (Bloque 4) miden la misma cosa con distinto punto de referencia (borde del hexágono vs. centroide) — offset sistemático de ~0.5 km, no es un error. Ver detalle en `contexto_maestro_proyecto_ptna.md`, sección 6.
- **Ambigüedad `gold_h3_accesibilidad` vs `h3_accesibilidad`** — resuelta de hecho: la tabla vieja `h3_accesibilidad` ya no aparece en el listado de tablas de `gold` (confirmado vía `information_schema.tables`, 12-sep-2026).

Detalle técnico completo de estos hallazgos (queries de verificación, código dbt real revisado, decisiones tomadas) en `contexto_maestro_proyecto_ptna.md`, secciones 3, 6 y 7 — priorizar ese documento sobre esta sección para cualquier trabajo nuevo del Bloque 5.

## 4. Esquema Silver/Gold

Para el detalle completo de columnas de Silver, seguir usando el canvas (Zona 3). Para Gold, la tabla de la sección 3 de este documento (actualizada 02-sep-2026) es más reciente que el canvas — usarla como referencia hasta la próxima regeneración del canvas. Puntos clave a recordar:

- Solo `booking/` tiene `schema.yml` + tests dbt en Silver. Los otros 11 dominios no tienen tests ni descripción de columnas.
- 3 modelos silver **sin tags** (`silver_clima_horario_agrocabildo`, `silver_h3_grid`, `silver_indices_satelite`) — se caen de cualquier `dbt run --select tag:...`.
- En Gold, ninguna tabla vista hasta ahora tiene ~60 columnas ni es un maestro único — ver tabla de la sección 3.
- `dbt_project.yml` solo define el nodo `silver` a nivel proyecto — falta el nodo `gold` (no rompe nada, pero es asimétrico).

## 5. Infraestructura Azure compartida

- **Resource Group**: `rg-tfm-tenerife` (Spain Central)
- **Storage**: `datalaketfmtenerife` (StorageV2, LRS), contenedor `bronce-raw`
- **Postgres**: `db-tfm-tenerife.postgres.database.azure.com` — Burstable B1ms (1 vCore/2GB/32GB), PostgreSQL 16.14 + PostGIS, admin `patron_tfm`. Esquemas `bronze`/`silver` llenos, `gold` con varias tablas pobladas (ver sección 3).
- **VM**: `mv-orquestador-tfm`, B2ats_v2 (2 vCPU), Ubuntu 24.04, admin `patron_tfm_mv`, IP `68.221.135.144`. ⚠️ RAM inconsistente entre docs (2GB / 1GB / ~842MiB según el documento) — verificar con `free -h` antes de asumir.

**Convivencia**:
- Contributor a nivel Resource Group (no Owner) — en el portal, la pestaña default de roles esconde Contributor/Owner, buscar en "Roles de administrador de privilegios".
- Cada quien agrega su propia IP pública al firewall de Postgres para conectar local (DBeaver/Python).
- SIEMPRE `tmux` en la VM. Instalar solo lo que tu script necesita (`pip install` puntual, no `requirements.txt` completo — puede arrastrar torch/CUDA y llenar el disco de 29GB).
- Vigilar RAM (`free -h`) y disco (`df -h /`) — el disco es más fácil de subestimar.
- Parar la VM (Deallocate) y pausar Postgres si no se usan >1-2 días — control de costos del equipo.

## 6. Discrepancias/deuda técnica conocidas (última revisión 12-sep-2026)

- ✅ **`SKILL.md` de Booking** — resuelto (02-sep-2026): `.gitignore` corregido (ruta `ingestion/scraping` → `ingestion/booking`) y archivo agregado a git en rama `feature/scraping-reviews`, PR abierto contra `main`.
- 🔒 **PENDIENTE — coordinado con Roberto (02-sep-2026)**: `plan_final_mejorado.md` tiene una credencial de Postgres en texto plano embebida en dos bloques de código (Bloque 4 y Bloque 7) — rotarla en Azure y sacarla del archivo. La rotación y decisión quedan del lado de Roberto (admin de infra); no accionar sin coordinar, ya que afecta la conexión de todo el equipo.
- 🔒 `docs/manual_conexion_mv.md`/`.txt` tienen la IP pública real de la VM commiteada — dato sensible en texto plano. Mencionado a Roberto junto con el punto anterior.
- 🟡 LosViajeros: modelos Silver en `main` sin su ingesta correspondiente mergeada (ver sección 3).
- 🟡 Varios README desactualizados con nombres de carpeta/archivo viejos: `ingestion/README.md` (raíz), `ingestion/booking/README.md`, `dbt_project/README.md`, `ingestion/clima/README.md`, `ingestion/espacial/README.md`, `ingestion/satelite/README.md`, `infra/README.md` (todavía dice DigitalOcean), `sql/README.md` (todavía dice `raw_data`/`processed_data`).
- ✅ **Resuelto (12-sep-2026)**: la ambigüedad entre `gold_h3_accesibilidad` y `h3_accesibilidad` — la tabla vieja ya no existe en el esquema, solo queda `gold_h3_accesibilidad`. Ver sección 3.
- 🟡 **Nuevo (12-sep-2026)**: `distancia_costa_metros` (Bloque 1) y `dist_costa_km` (Bloque 4) no coinciden por medir desde puntos de referencia distintos (borde vs. centroide del hexágono) — no es error, pero conviene que ambos bloques lo sepan y se documente cuál usar según el caso. Ver `contexto_maestro_proyecto_ptna.md`, sección 6.
- 🟡 **Nuevo (12-sep-2026)**: `n_pois_total` en `gold_h3_master` no es una suma exhaustiva de sus subcategorías (`n_restaurantes`, `n_cultura`, `n_naturaleza`, `n_pois_institucionales`) — faltan `Transporte` y `Servicios_Basicos` sin categoría propia. Decisión de diseño a confirmar con Bloque 1. Ver `contexto_maestro_proyecto_ptna.md`, sección 6.

## 7. Backlog general (detalle completo en el canvas, Zona 5)

- **Gold — Bloque 5 (MGWR/PTNA, `gold_h3_ptna`)**: asignado a jcabrera1605-netizen (02-sep-2026). En etapa de construcción del dataset de regresión (Subtarea 5.1). Las 3 brechas de datos originales (`viirs_medio`, `n_pois`, columna de plazas hoteleras) y la ambigüedad de accesibilidad ya se resolvieron (12-sep-2026, ver sección 3). Único bloqueante activo hoy: `sentimiento_medio` (tabla fuente en construcción por el equipo de NLP). Documentación técnica detallada de este bloque en `contexto_maestro_proyecto_ptna.md`, siguiendo el mismo patrón que `contexto_maestro_proyecto.md` para Booking.
- **Gold**: de los 10 Bloques del plan (`plan_final_mejorado.md`), varios ya tienen datos reales subidos (1, 2 parcial, 3 parcial, 4) — actualizar este backlog a medida que se confirme el estado de cada uno. Sin empezar o sin confirmar: Bloque 6 (clustering HDBSCAN), Bloque 7 (Text-to-SQL), Bloque 8 (Dashboard Streamlit), Bloque 9 (informes LLM), Bloque 10 (QA final).
- **Analytics/NLP**: `topics/` (BERTopic, issue #19) parece tener avance (`gold.nlp_topics` poblada) — confirmar estado real. Georreferenciación para el módulo de Mapa (#20), `ambiental/` (#21-24), `clustering/` (#25-27), `isocronas/` (#28-30, aunque `gold.isocronas_visuales` ya existe — confirmar si está completo), `mgwr/` (#31-33, en curso vía Bloque 5).
- **ISTAC**: histórico de `empleo_hosteleria` incompleto, 25 municipios rurales sin pernoctaciones, Registro de Establecimientos Turísticos Canarias e Inside Airbnb sin ingestar.
- **GTFS**: resolver NULLs en `arrival_seconds`/`departure_seconds` interpolados — bloquea el trabajo de isócronas.

## 8. Documentos de referencia (dónde está cada cosa)

- `contexto_maestro_proyecto.md` (este mismo directorio) — detalle técnico completo de Booking (issue #12): selectores, bugs de Selenium, heurísticas de descubrimiento/geocodificación.
- `contexto_maestro_proyecto_ptna.md` — detalle técnico del Bloque 5 (MGWR/PTNA): construcción del dataset, decisiones sobre qué tablas usar, resultados del modelo.
- `mapa_repo_ai_dashboard_core.canvas` (Obsidian, `OneDrive/Documentos/FACULTAD/TFM/`) — mapa visual completo del repo. Su sección de Gold quedó desactualizada respecto a este documento al 02-sep-2026 — priorizar este documento hasta la próxima regeneración del canvas.
- `plan_final_mejorado.md` (raíz del repo) — plan técnico vigente para completar Gold, con SQL/Python de referencia por Bloque. Reemplaza a `github_issues_plan.md`. ⚠️ Contiene credencial de Postgres en texto plano (Bloques 4 y 7) — ver sección 6, pendiente de rotación por Roberto.
- `docs/arquitectura_azure.md` — referencia autoritativa de recursos Azure.
- `analytics/README.md` — estado issue-por-issue de la capa de analytics/NLP.
- `docs/catalogo_datos_istac.md` — gaps detallados de ISTAC.

## Cómo usar este documento en una conversación nueva

Al empezar, decir algo como: *"Retomo el TFM de inteligencia territorial en Tenerife — ya tenés el contexto completo del repo en el archivo de Proyecto. Quiero [tarea específica sobre X fuente/módulo]."* Si la tarea es específicamente sobre Booking, mejor referenciar `contexto_maestro_proyecto.md` en su lugar (tiene mucho más detalle técnico de esa fuente). Si la tarea es sobre el Bloque 5 (MGWR/PTNA), referenciar `contexto_maestro_proyecto_ptna.md` una vez creado. Si hace falta el detalle exacto de columnas/estado de otra fuente que no está acá, referenciar el canvas (con la salvedad de la sección 3, más actualizada en este documento).