# 📋 Catálogo de Datos ISTAC — TFM AI Dashboard Tenerife

> **Última actualización**: 2026-08-09  
> **Script de ingesta**: `ingestion/istac/istac_reingest_all_uuid.py`  
> **Sistema ISTAC**: `C00067A` — Municipios en Cifras  
> **API Base**: `https://datos.canarias.es/api/estadisticas/indicators/v1.0`

---

## Estado actual de los datos ISTAC (verificado en disco)

### Indicadores con cobertura TURÍSTICA (6 municipios)

> Los siguientes indicadores solo tienen datos para los municipios con masa estadística suficiente según el INE/ISTAC.  
> Municipios cubiertos: **Adeje, Arona, Granadilla de Abona, Puerto de la Cruz, Santa Cruz de Tenerife, Santiago del Teide**  
> *Puerto de la Cruz estaba ausente en la ingesta original por bug de búsqueda por título → corregido en v2 con UUID directo.*

| Indicador | Columna | Municipios | Granularidad | Rango temporal | UUID C00067A |
|-----------|---------|-----------|--------------|----------------|--------------|
| Alojamientos turísticos abiertos | `alojamientos_abiertos` | **6** | Mensual | 2009-01 → 2026-06 | `5ac41241-...` |
| Pernoctaciones en alojamientos turísticos | `pernoctaciones` | **6** | Mensual | 2009-01 → 2026-06 | `503ab41f-...` ✅ verificado |
| Plazas ofertadas por alojamientos turísticos | `plazas_ofertadas` | **6** | Mensual | 2009-01 → 2026-06 | `f7ef630f-...` |
| Tasa de ocupación por plazas | `tasa_ocupacion_plazas` | **6** | Mensual | 2009-01 → 2026-06 | `ac286c1a-...` |
| Viajeros entrados en alojamientos turísticos | `viajeros_entrados` | **6** | Mensual | 2009-01 → 2026-06 | `011c4c75-...` |
| Población turística equivalente | `pob_turistica_equiv` | **5** | Anual | 2021 → 2025 | pendiente resolver |

> [!IMPORTANT]
> **Por qué solo 6 municipios**: El INE solo publica la EOH (Encuesta de Ocupación Hotelera) para municipios con alojamiento reglado estadísticamente significativo. Los 25 municipios rurales de Tenerife no tienen masa estadística suficiente para ser publicados. Esto es una limitación del origen, no de la ingesta.

---

### Indicadores con cobertura DEMOGRÁFICA/ECONÓMICA (31 municipios)

> Cubren los **31 municipios de Tenerife**.  
> *La ingesta original devolvía 30/31 (faltaba Puerto de la Cruz por el mismo bug) → corregido en v2.*

| Indicador | Columna | Municipios | Granularidad | Rango temporal | Notas |
|-----------|---------|-----------|--------------|----------------|-------|
| Paro registrado | `paro_registrado` | **31** | Mensual | 2019-01 → 2026-06 | — |
| Empresas inscritas SS | `empresas_ss` | **31** | Mensual | 2019-03 → 2026-06 | — |
| Empleo registrado. Hostelería | `empleo_hosteleria` | **31** | Trimestral | 2026-Q1 → 2026-Q2 | ⚠️ Solo 2 trimestres |
| Empleo registrado. Servicios | `empleo_servicios` | **31** | Trimestral | 2026-Q1 → 2026-Q2 | ⚠️ Solo 2 trimestres |
| Saldo migratorio | `saldo_migratorio` | **31** | Anual | 2019 → 2021 | ⚠️ Solo hasta 2021 |
| Población total | `poblacion_total` | **31** | Anual | 2019 → 2025 | — |
| Población 15-64 años | `poblacion_15_64` | **31** | Anual | 2019 → 2025 | — |
| Población 65+ años | `poblacion_65_mas` | **31** | Anual | 2019 → 2025 | — |
| Edad media | `edad_media` | **31** | Anual | 2019 → 2025 | — |
| Superficie km² | `superficie_km2` | **31** | Estático | 2024 | Dato fijo |

---

## Gaps conocidos y estado de resolución

| Gap | Causa | Solución | Estado |
|-----|-------|----------|--------|
| Puerto de la Cruz ausente en indicadores turísticos | Bug búsqueda por título en script v1 | UUID directo en `istac_reingest_all_uuid.py` | ✅ Resuelto |
| Puerto de la Cruz ausente en indicadores demográficos | Mismo bug | UUID directo en `istac_reingest_all_uuid.py` | ✅ Resuelto |
| `empleo_hosteleria` solo tiene 2026 | Datos trimestrales recientes en el sistema | Buscar UUID de serie histórica o INE INES | 🔴 Pendiente |
| `saldo_migratorio` solo hasta 2021 | ISTAC no ha publicado años posteriores | Dato completo hasta 2021, aceptable para modelo | ⚠️ Limitación fuente |
| 25 municipios sin pernoctaciones | INE no publica EOH municipal rural | ISTAC Vivienda Vacacional (C00065A_000061) | 🔴 Pendiente |
| `pob_turistica_equiv` UUID no resuelto | UUID no identificado aún | Revisar sistema manualmente | 🟡 En progreso |

---

## Ficheros en disco (post ingesta v2)

```
data/bronce/tabular/raw/
├── istac_v2_alojamientos_abiertos.csv    ← v2, 6 municipios incluyendo Pto. Cruz
├── istac_v2_pernoctaciones.csv           ← v2, 6 municipios incluyendo Pto. Cruz
├── istac_v2_plazas_ofertadas.csv         ← v2, 6 municipios incluyendo Pto. Cruz
├── istac_v2_tasa_ocupacion_plazas.csv    ← v2, 6 municipios incluyendo Pto. Cruz
├── istac_v2_viajeros_entrados.csv        ← v2, 6 municipios incluyendo Pto. Cruz
├── istac_v2_paro_registrado.csv          ← v2, 31 municipios
├── istac_v2_empresas_ss.csv              ← v2, 31 municipios
├── istac_v2_empleo_hosteleria.csv        ← v2, 31 municipios (solo 2026)
├── istac_v2_saldo_migratorio.csv         ← v2, 31 municipios (2019-2021)
├── istac_v2_poblacion_total.csv          ← v2, 31 municipios
├── istac_v2_poblacion_15_64.csv          ← v2, 31 municipios
├── istac_v2_poblacion_65_mas.csv         ← v2, 31 municipios
├── istac_v2_edad_media.csv               ← v2, 31 municipios
├── istac_v2_superficie_km2.csv           ← v2, 31 municipios
├── istac_v2_consolidado.parquet          ← Todos los anteriores consolidados
│
├── [LEGACY - v1, con bug Puerto de la Cruz]
├── istac_mun_pernoctaciones.csv          ← v1, 5 municipios (deprecated)
├── istac_municipios_cifras_tenerife.csv  ← v1, consolidado (deprecated)
└── istac_municipios_cifras_tenerife.parquet ← v1 (deprecated)
```

---

## UUIDs verificados (sistema C00067A)

```python
UUID_MAP = {
    # Turisticos (6 municipios)
    "alojamientos_abiertos":  "5ac41241-1008-4495-bc24-04d478deac2a",
    "pernoctaciones":         "503ab41f-6906-4eb1-9c7d-e49ee137ea53",
    "plazas_ofertadas":       "f7ef630f-7d4a-401c-9db8-d6c3c805a0a2",
    "tasa_ocupacion_plazas":  "ac286c1a-f70a-4888-9679-bd973250c824",
    "viajeros_entrados":      "011c4c75-c288-4274-83b4-fe5eb68ba861",
    # Demograficos/economicos (31 municipios)
    "paro_registrado":        "9de5166a-c9d0-4e56-bf73-42a6e07f5a97",
    "empresas_ss":            "9990ffac-b016-49f8-8d23-eea5538da814",
    "saldo_migratorio":       "c8747bfa-2967-499b-81fb-9b58557f1322",
    "superficie_km2":         "b2699bcd-25da-4322-82f2-83d33ed92f5c",
    "empleo_hosteleria":      "579c2c01-3219-46ba-8741-a32c6566581a",
    "poblacion_*":            "6daf4220-c08f-431c-8383-a0a7daa87da7",  # compartido
}
```

---

## Fuentes pendientes de ingesta

| Fuente | Datos | URL / Acceso | Prioridad |
|--------|-------|--------------|-----------|
| ISTAC Vivienda Vacacional | Plazas VV, ocupación, ingresos por municipio (2019-2026) | [Visualizador ISTAC C00065A_000061](https://www3.gobiernodecanarias.org/istac/statistical-visualizer/visualizer/data.html?resourceType=dataset&agencyId=ISTAC&resourceId=C00065A_000061&version=~latest) | 🔴 Alta |
| Registro Establecimientos Turísticos Canarias | Alojamientos con coords para 31 municipios | [datos.canarias.es](https://datos.canarias.es/catalogos/general/) | 🔴 Alta |
| Inside Airbnb España | Listings Airbnb Tenerife con coords | [insideairbnb.com/get-the-data](http://insideairbnb.com/get-the-data/) | 🟡 Media |
| OSM Overpass API | POIs turísticos por municipio | Script `osm_tourism_tenerife.py` | 🟡 Media |
| AENA pasajeros TFN+TFS | Pasajeros mensuales 2019-2025 | [aena.es/estadisticas](https://www.aena.es/es/estadisticas/informes-mensuales.html) | 🟢 Baja |
