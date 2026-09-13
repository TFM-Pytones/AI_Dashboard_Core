# Ingesta y Catálogo de Datos ISTAC (Capa Bronce)

Documentación técnica y catálogo de indicadores extraídos del **Instituto Canario de Estadística (ISTAC)** para el proyecto *Tenerife AI Dashboard*, abarcando demografía municipal, mercado laboral y actividad turística (Encuesta de Ocupación Hotelera y Vivienda Vacacional).

---

## 1. Arquitectura de Extracción y Flujo de Datos

### A. Exploración y Descubrimiento de la API
En lugar de descargar ficheros Excel manuales y pivotados que mezclaban todas las islas, se implementó una integración directa contra la **API REST del ISTAC**:
* **Sistema Base**: `C00067A` (Municipios en Cifras) y `C00065A_000061` (Vivienda Vacacional).
* **Endpoint Base**: `https://datos.canarias.es/api/estadisticas/indicators/v1.0/indicatorsSystems/{system_id}/indicatorsInstances/{uuid}/data.tsv`

### B. Scripts de Ingesta Disponibles
1. [`istac_municipios_cifras_upload_blob.py`](istac_municipios_cifras_upload_blob.py):
   * Descarga los indicadores demográficos, económicos y de ocupación hotelera reglada.
   * Aplica paginación dinámica para recuperar las series temporales completas.
   * Filtra estrictamente por los **31 municipios de Tenerife** y sus variantes toponímicas.
   * Formato de descarga en formato largo (`long format`: Periodo, Municipio, Medida, Valor).
2. [`istac_vivienda_vacacional_upload_blob.py`](istac_vivienda_vacacional_upload_blob.py):
   * Descarga la serie mensual de Vivienda Vacacional (VV) cubriendo los 31 municipios insulares (plazas ofertadas, tasa de ocupación, estancia media, ingresos y alojamientos abiertos).

### C. Almacenamiento en Azure Blob Storage (Raw) y Carga a PostgreSQL
* **Compresión**: Los ficheros son convertidos a formato **Apache Parquet (Snappy)**, reduciendo el volumen en más de un 95% respecto al CSV original.
* **Destino Cloud**: Contenedor `bronce-raw/tabular/istac/`.
* **Carga en Base de Datos**: Ingesta masiva por lotes a tablas `bronze.bronze_istac_mun_*`.
* **Capa Silver (dbt)**: Modelado en `silver_istac_anual`, `silver_istac_mensual` y `silver_istac_trimestral` con pivoteo de métricas, tratamiento del secreto estadístico (`.`) y tipado numérico.

---

## 2. Catálogo Detallado de Indicadores

### A. Indicadores con Cobertura Turística EOH (6 Polos Turísticos)
La Encuesta de Ocupación Hotelera (EOH) del INE/ISTAC solo publica datos para municipios con masa crítica de alojamiento reglado suficiente:
* **Municipios cubiertos**: Adeje, Arona, Granadilla de Abona, Puerto de la Cruz, Santa Cruz de Tenerife y Santiago del Teide.

| Indicador | Columna Silver | Granularidad | Rango Temporal | UUID ISTAC C00067A |
|---|---|---|---|---|
| **Alojamientos turísticos abiertos** | `alojamientos_abiertos_eoh` | Mensual | 2009-01 → Actual | `5ac41241-1008-4495-bc24-04d478deac2a` |
| **Pernoctaciones hoteleras** | `pernoctaciones` | Mensual | 2009-01 → Actual | `503ab41f-6906-4eb1-9c7d-e49ee137ea53` |
| **Plazas ofertadas** | `plazas_ofertadas` | Mensual | 2009-01 → Actual | `f7ef630f-7d4a-401c-9db8-d6c3c805a0a2` |
| **Tasa de ocupación por plazas** | `tasa_ocupacion_plazas` | Mensual | 2009-01 → Actual | `ac286c1a-f70a-4888-9679-bd973250c824` |
| **Viajeros entrados** | `viajeros_entrados` | Mensual | 2009-01 → Actual | `011c4c75-c288-4274-83b4-fe5eb68ba861` |
| **Población turística equivalente** | `pob_turistica_equiv` | Anual | 2021 → 2025 | Sistema de indicadores ISTAC |

### B. Indicadores de Vivienda Vacacional (31 Municipios)
Complementa la ausencia de EOH en los 25 municipios no tradicionales, ofreciendo cobertura total insular:
* **Métricas**: Plazas VV, Tasa de ocupación VV, Estancia media VV, Ingresos brutos VV y Alojamientos abiertos.
* **Granularidad**: Mensual continua (2022-2026).

### C. Indicadores Demográficos y Mercado Laboral (31 Municipios)
* **Población total y grupos de edad**: `poblacion_total`, `poblacion_15_64`, `poblacion_65_mas`, `edad_media` (Anual, 2019-2025).
* **Paro registrado**: Total de desempleados inscritos en el SEPE/OBECAN (Mensual, 2019-2026).
* **Afiliación y Empleo Sectorial**: `empleo_total`, `empleo_asalariados`, `empleo_autonomos`, `empleo_hosteleria`, `empleo_servicios`, `empleo_comercio`, `empleo_construccion`, `empleo_industria`, `empleo_agricultura` (Trimestral, 2021-2026).
