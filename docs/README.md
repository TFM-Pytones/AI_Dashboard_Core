# Centro de Documentación Técnica — AI Dashboard Core

Bienvenido al centro de documentación técnica y gobernanza del proyecto **Tenerife Tourism AI Dashboard**. Este directorio centraliza la arquitectura de sistemas, las guías de infraestructura cloud en Microsoft Azure y los marcos metodológicos que sustentan el Trabajo de Fin de Máster (TFM).

---

## Mapa y Guía de Navegación de Documentos

```
docs/
├── README.md                           # Índice principal de documentación (este archivo)
├── 00_indice_tfm.md                    # Estructura académica y bloques del TFM
│
├── Arquitectura y Datos
│   ├── architecture.md                 # Flujo lógico global de datos (Medallion: Bronze -> Silver -> Gold)
│   └── arquitectura_azure.md           # Arquitectura física cloud en Microsoft Azure (Spain Central)
│
├── Infraestructura Cloud y Conectividad
│   ├── azure_access_management_guide.md# Gestión de permisos IAM, cortafuegos de red y plan de migración
│   ├── azure_vm_setup_guide.md         # Guía completa de configuración y resolución de problemas en la VM
│   ├── manual_conexion_mv.md           # Manual de operación diaria (SSH, recursos, nohup y background)
│   ├── vm_orquestador_setup.md         # Instalación y configuración de Apache Airflow y dbt en Linux
│   └── conexion_dbeaver_azure.md       # Guía de conexión DBeaver / clientes SQL a PostgreSQL con SSL
│
└── Metodología y Modelización Avanzada
    └── 10_modelizacion_microclimatica.md# Formulación matemática y espacial del modelo microclimático H3
```

---

## 1. Arquitectura y Gobernanza del Proyecto

| Documento | Alcance y Contenido | Bloque TFM |
|---|---|---|
| [`00_indice_tfm.md`](00_indice_tfm.md) | Desglose pormenorizado de los 7 bloques del TFM (Negocio, Ingesta, DW Espacial, Analítica, IA Generativa, Dashboard y Validación). | Bloques 1 a 7 |
| [`architecture.md`](architecture.md) | Diagrama conceptual del pipeline de datos de extremo a extremo: fuentes externas → Data Lake → Data Warehouse → Analítica/NLP → LLM → Frontend. | Bloques 2 y 3 |
| [`arquitectura_azure.md`](arquitectura_azure.md) | Ficha técnica de los recursos aprovisionados en Azure (`datalaketfmtenerife`, `db-tfm-tenerife`, `mv-orquestador-tfm`) en la región *Spain Central*. | Bloque 2 |

---

## 2. Infraestructura Cloud y Operaciones (Azure & Linux)

| Documento | Alcance y Contenido |
|---|---|
| [`azure_access_management_guide.md`](azure_access_management_guide.md) | Configuración de roles IAM (*Contributor*, *Storage Blob Data Contributor*), reglas de firewall para IPs del equipo y protocolo de contingencia/migración entre cuentas Azure. |
| [`azure_vm_setup_guide.md`](azure_vm_setup_guide.md) | Guía paso a paso para desplegar la máquina virtual Ubuntu 24.04 LTS, conexión SSH (Windows y macOS/Linux), configuración de memoria Swap, Git PAT y entornos virtuales Python. |
| [`manual_conexion_mv.md`](manual_conexion_mv.md) | Manual de administración operativa: monitorización de consumo (`htop`, `free -m`, `df -h`), gestión de procesos (`kill`, `pkill`) y ejecución desatendida en segundo plano con `nohup`. |
| [`vm_orquestador_setup.md`](vm_orquestador_setup.md) | Despliegue de Apache Airflow y dbt en la VM para orquestación automatizada de pipelines y tareas programadas (DAGs). |
| [`conexion_dbeaver_azure.md`](conexion_dbeaver_azure.md) | Instrucciones para conectar clientes de base de datos relacional (DBeaver, pgAdmin) a Azure Database for PostgreSQL Flexible Server exigiendo encriptación SSL (`require`). |

---

## 3. Metodología Científica y Modelización Espacial

| Documento | Alcance y Contenido | Bloque TFM |
|---|---|---|
| [`10_modelizacion_microclimatica.md`](10_modelizacion_microclimatica.md) | Formulación matemática que corrige la interpolación meteorológica tradicional (IDW) en la orografía de Tenerife: gradiente térmico altitudinal (-0,0065 °C/m), termorregulación marina, efecto mar de nubes (inversión térmica 800-1500m), sombra de lluvia pluviométrica y canalización eólica Venturi. Implementado en dbt PostGIS dentro de `gold_h3_master`. | Bloque 4 |

---

## 4. Documentación Específica por Módulos del Repositorio

Para consultar la documentación técnica de cada componente específico, navega directamente a su respectivo directorio:

* **Catálogo Maestro de Fuentes**: [`../CATALOGO_FUENTES_DATOS.md`](../CATALOGO_FUENTES_DATOS.md)
* **Ingesta General (Pipelines Bronze)**: [`../ingestion/README.md`](../ingestion/README.md)
  * **Transporte y Movilidad (GTFS TITSA / Tranvía)**: [`../ingestion/gtfs/README.md`](../ingestion/gtfs/README.md)
  * **Estadística Municipal y Turismo (ISTAC)**: [`../ingestion/istac/README.md`](../ingestion/istac/README.md)
  * **Malla H3 y Capas Vectoriales (IDECanarias, OSM)**: [`../ingestion/espacial/README.md`](../ingestion/espacial/README.md)
  * **Scraping de Alojamientos y Reseñas (Booking)**: [`../ingestion/booking/README.md`](../ingestion/booking/README.md)
  * **Opiniones y Valoraciones Turísticas (TripAdvisor)**: [`../ingestion/tripadvisor/README.md`](../ingestion/tripadvisor/README.md)
  * **Foro de Viajeros (LosViajeros)**: [`../ingestion/losviajeros/README.md`](../ingestion/losviajeros/README.md)
  * **Redes Sociales (YouTube Data API)**: [`../ingestion/youtube/README.md`](../ingestion/youtube/README.md)
  * **Observación de la Tierra (Sentinel-2 / VIIRS)**: [`../ingestion/satelite/README.md`](../ingestion/satelite/README.md)
* **Transformación y Data Warehouse (dbt Silver & Gold)**: [`../dbt_project/README.md`](../dbt_project/README.md)
* **Analítica Avanzada, Machine Learning y Modelado Espacial (Bloques 4 y 5)**: [`../analytics/README.md`](../analytics/README.md)
  * **Inferencia de Sentimiento Multilingüe**: [`../analytics/sentiment/README.md`](../analytics/sentiment/README.md)
  * **Modelado de Tópicos con BERTopic**: [`../analytics/topics/README.md`](../analytics/topics/README.md)
  * **Extracción de Aspectos con PyABSA**: [`../analytics/aspects/README.md`](../analytics/aspects/README.md)
  * **Clustering Territorial y Arquetipos TUI (HDBSCAN)**: [`../analytics/clustering/README.md`](../analytics/clustering/README.md)
  * **Regresión Espacial Multiescalar y Potencial PTNA (MGWR)**: [`../analytics/mgwr/README.md`](../analytics/mgwr/README.md)
* **Orquestación de Pipelines (Apache Airflow)**: [`../dags/README.md`](../dags/README.md)
* **Catálogo DDL de Machine Learning y NLP**: [`../sql/README.md`](../sql/README.md)
* **Plataforma Analítica y Dashboard Territorial (Streamlit / Pydeck)**: [`../app/README.md`](../app/README.md)

