# Ingesta y Catálogo de Datos ISTAC (Capa Bronze y Silver)

Documentación técnica y catálogo de indicadores socioeconómicos, demográficos, laborales y turísticos extraídos programáticamente desde la API del **Instituto Canario de Estadística (ISTAC)** para el proyecto *Tenerife AI Dashboard*.

El módulo ingiere **24 indicadores independientes** para los **31 municipios de Tenerife** (códigos INE 38001 a 38052) mediante dos sistemas REST complementarios, organizados en 24 tablas en la capa `bronze` y consolidados en 3 modelos dimensionales en la capa `silver` mediante dbt.

---

## 1. Arquitectura y Flujo de Datos

```
                 API REST DEL ISTAC (datos.canarias.es)
                                   │
         ┌─────────────────────────┴─────────────────────────┐
         ▼                                                   ▼
Sistema C00067A (Municipios en Cifras)             Sistema C00065A_000061 (Vivienda Vacacional)
istac_municipios_cifras_upload_blob.py             istac_vivienda_vacacional_upload_blob.py
- 19 indicadores demográficos, laborales,          - 5 indicadores mensuales de VV
  empleo SS y hoteleros EOH                        - Cobertura integral para los 31 municipios
- Formato largo TSV por instancia UUID             - Series continuas 2022–2026
         │                                                   │
         └─────────────────────────┬─────────────────────────┘
                                   ▼
          Azure Blob Storage: contenedor bronce-raw/tabular/istac/
          (24 archivos Parquet Snappy con tipado estandarizado)
                                   │
                                   ▼ Carga masiva COPY nativo (05_ingest_tabular_to_postgres.py)
          Azure PostgreSQL: 24 tablas bronze.bronze_istac_mun_*
                                   │
                                   ▼ Transformación analítica y pivoteo con dbt Core 1.8
          Azure PostgreSQL (Capa Silver):
          ├── silver.silver_istac_anual      (124 filas: Demografía censal y PTE)
          ├── silver.silver_istac_trimestral (682 filas: Suite de Empleo y Seguridad Social)
          └── silver.silver_istac_mensual    (1.736 filas: EOH, Vivienda Vacacional y Paro)
```

---

## 2. Los Dos Sistemas Oficiales del ISTAC

1. **`C00067A` (*Municipios en Cifras*)**:
   * **Endpoint**: `https://datos.canarias.es/api/estadisticas/indicators/v1.0/indicatorsSystems/C00067A/indicatorsInstances/{uuid}/data.tsv`
   * **Propósito**: Proporciona los indicadores demográficos municipales, el desempleo registrado (SEPE/OBECAN), la matriz completa de empleo y afiliaciones a la Seguridad Social, y la Encuesta de Ocupación Hotelera (EOH).
2. **`C00065A_000061` (*Estadística de la Vivienda Vacacional de Canarias*)**:
   * **Endpoint**: `https://datos.canarias.es/api/estadisticas/statistical-resources/v1.0/datasets/ISTAC/C00065A_000061/~latest.csv`
   * **Justificación técnica**: La EOH hotelera tradicional solo publica datos para los 6 municipios con masa crítica hotelera (Adeje, Arona, Puerto de la Cruz, Santa Cruz, Santiago del Teide y Granadilla), arrojando nulos para el resto de la isla. La ingesta de la serie de Vivienda Vacacional (VV) cubre los **31 municipios**, permitiendo cuantificar la oferta alojativa y la presión turística en las medianías y zonas de interior.

---

## 3. Catálogo Detallado de los 24 Indicadores

### A. Demografía y Presión Turística Estructural (Anual $\to$ `silver_istac_anual`)
Cobertura para los 31 municipios de Tenerife. Fuente: Sistema `C00067A`.

| Indicador | Columna Silver | Granularidad | Rango | UUID ISTAC C00067A | Tabla Bronze PostgreSQL |
|---|---|---|---|---|---|
| **Población total municipal** | `poblacion_total` | Anual | 2019 → 2025 | `6daf4220-c08f-431c-8383-a0a7daa87da7` | `bronze_istac_mun_poblacion_total` |
| **Población activa (15–64)** | `poblacion_15_64` | Anual | 2019 → 2025 | `05ac75fe-6ddf-45be-8ad6-ae8101b775dc` | `bronze_istac_mun_poblacion_15_64` |
| **Población mayor ($\ge 65$)** | `poblacion_65_mas` | Anual | 2019 → 2025 | `c19aa858-484a-4d4d-a6af-9cc4b268424a` | `bronze_istac_mun_poblacion_65_mas` |
| **Edad media municipal** | `edad_media` | Anual | 2019 → 2025 | `87f99b2c-608f-44be-8d7e-2e26681d1b45` | `bronze_istac_mun_edad_media` |
| **Población Turística Equivalente** | `pob_turistica_equiv` | Anual | 2021 → 2025 | `224a27c7-5682-4ae9-bf56-58ce4f5aebe6` | `bronze_istac_mun_pob_turistica_equiv` |

### B. Suite de Empleo y Afiliaciones a la Seguridad Social (Trimestral $\to$ `silver_istac_trimestral`)
Cobertura para los 31 municipios. Mide la dependencia económica del turismo y la diversificación sectorial. Fuente: Sistema `C00067A`.

| Indicador | Columna Silver | Régimen / Sector | UUID ISTAC C00067A | Tabla Bronze PostgreSQL |
|---|---|---|---|---|
| **Afiliaciones totales** | `empleo_total` | Total regímenes | `579c2c01-3219-46ba-8741-a32c6566581a` | `bronze_istac_mun_empleo_total` |
| **Régimen general** | `empleo_asalariados` | Asalariados | `25c18e4f-45f1-4a1c-b7df-397c5004d1b1` | `bronze_istac_mun_empleo_asalariados` |
| **Trabajadores autónomos** | `empleo_autonomos` | RETA | `a243a472-95af-48b5-b773-47031e3ac4a3` | `bronze_istac_mun_empleo_autonomos` |
| **Empleo en hostelería** | `empleo_hosteleria` | Hostelería (CNAE-09) | `edb35ff9-70d5-4f38-b4fd-25eaf02ff3c8` | `bronze_istac_mun_empleo_hosteleria` |
| **Sector servicios** | `empleo_servicios` | Servicios global | `486e46ff-788c-4dcd-845b-c16fbd5b4d82` | `bronze_istac_mun_empleo_servicios` |
| **Comercio y automoción** | `empleo_comercio` | Comercio | `12aa2d29-6f23-4726-8748-e0f54b36828b` | `bronze_istac_mun_empleo_comercio` |
| **Construcción** | `empleo_construccion` | Construcción | `b81f92b4-4d9a-48ad-9fde-7fcde28174a2` | `bronze_istac_mun_empleo_construccion` |
| **Industria** | `empleo_industria` | Industria | `eb3d7390-4902-4cc0-9fa4-8c5a15933810` | `bronze_istac_mun_empleo_industria` |
| **Agricultura** | `empleo_agricultura` | Primario | `3f29230c-8680-4fd4-a06f-22a46972f078` | `bronze_istac_mun_empleo_agricultura` |

### C. Mercado Laboral, EOH Hotelera y Vivienda Vacacional (Mensual $\to$ `silver_istac_mensual`)

#### 1. Paro Registrado (31 Municipios)
* **`paro_registrado`** (UUID `9de5166a-c9d0-4e56-bf73-42a6e07f5a97`): Demandantes de empleo en SEPE/OBECAN $\to$ `bronze_istac_mun_paro_registrado`.

#### 2. Encuesta de Ocupación Hotelera EOH (6 Polos Turísticos)
Fuente: Sistema `C00067A`. Cobertura histórica desde 2009.

| Indicador | Columna Silver | Descripción | UUID ISTAC C00067A | Tabla Bronze PostgreSQL |
|---|---|---|---|---|
| **Pernoctaciones hoteleras** | `pernoctaciones` | Noches en hoteles y apartamentos | `503ab41f-6906-4eb1-9c7d-e49ee137ea53` | `bronze_istac_mun_pernoctaciones` |
| **Plazas hoteleras ofertadas** | `plazas_ofertadas` | Capacidad hotelera en el mercado | `f7ef630f-7d4a-401c-9db8-d6c3c805a0a2` | `bronze_istac_mun_plazas_ofertadas` |
| **Tasa de ocupación plazas** | `tasa_ocupacion_plazas` | Ratio pernoctaciones / plazas (\%) | `ac286c1a-f70a-4888-9679-bd973250c824` | `bronze_istac_mun_tasa_ocupacion_plazas` |
| **Viajeros entrados** | `viajeros_entrados` | Llegadas registradas en recepción | `011c4c75-c288-4274-83b4-fe5eb68ba861` | `bronze_istac_mun_viajeros_entrados` |

#### 3. Estadística de Vivienda Vacacional VV (31 Municipios)
Fuente: Sistema `C00065A_000061`. Cobertura mensual continua (2022–2026).

| Indicador | Columna Silver | Descripción | Métrica ISTAC | Tabla Bronze PostgreSQL |
|---|---|---|---|---|
| **Plazas en VV** | `plazas_vv` | Plazas ofertadas en vivienda vacacional | Plazas disponibles | `bronze_istac_mun_plazas_vv` |
| **Viviendas activas** | `alojamientos_abiertos_vv` | Número de viviendas comercializadas | VV disponibles | `bronze_istac_mun_alojamientos_abiertos_vv` |
| **Tasa de ocupación VV** | `tasa_ocupacion_vv` | Porcentaje de días reservados | Tasa de vivienda reservada | `bronze_istac_mun_tasa_ocupacion_vv` |
| **Estancia media VV** | `estancia_media_vv` | Duración media de la estancia (días) | Estancia media en VV | `bronze_istac_mun_estancia_media_vv` |
| **Ingresos brutos VV** | `ingresos_vv` | Facturación total estimada (€) | Ingresos totales | `bronze_istac_mun_ingresos_vv` |

---

## 4. Resumen de Tablas y Volúmenes Verificados

| Capa | Objeto en PostgreSQL | Granularidad | Registros Verificados | Descripción |
|---|---|---|:---:|---|
| **Bronze** | `bronze.bronze_istac_mun_*` (24 tablas) | Mensual / Trim / Anual | **82.721** filas (suma total) | Series temporales crudas sin pivotar |
| **Silver** | `silver.silver_istac_anual` | Anual (31 municipios) | **124** filas | Demografía y PTE por municipio y año (2022–2026) |
| **Silver** | `silver.silver_istac_trimestral` | Trimestral (31 municipios) | **682** filas | Matriz de 9 sectores/regímenes de empleo |
| **Silver** | `silver.silver_istac_mensual` | Mensual (31 municipios) | **1.736** filas | EOH hotelera, Vivienda Vacacional (VV) y Paro |

---

## 5. Instrucciones de Ejecución

### Requisitos previos en `.env`:
```bash
AZURE_STORAGE_CONNECTION_STRING="DefaultEndpointsProtocol=https;AccountName=...;AccountKey=..."
AZURE_DB_HOST="servidor-postgres.postgres.database.azure.com"
AZURE_DB_USER="usuario"
AZURE_DB_PASSWORD="password"
AZURE_DB_NAME="database"
```

### 1. Descargar indicadores de Municipios en Cifras (C00067A):
```bash
python ingestion/istac/istac_municipios_cifras_upload_blob.py
```

### 2. Descargar serie de Vivienda Vacacional (C00065A_000061):
```bash
python ingestion/istac/istac_vivienda_vacacional_upload_blob.py
```

### 3. Cargar a tablas Bronze en Azure PostgreSQL:
```bash
python ingestion/postgres/05_ingest_tabular_to_postgres.py
```

### 4. Transformar en dbt (Capa Silver):
```bash
dbt run --models silver.istac
```
