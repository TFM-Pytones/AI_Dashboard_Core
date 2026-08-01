# Documentación: Ingesta de Datos del ISTAC (Capa Bronce)

Este documento detalla el proceso técnico seguido para la extracción, tratamiento y carga de los datos del Instituto Canario de Estadística (ISTAC) correspondientes a los "Municipios en Cifras" (Sistema de Indicadores C00067A).

## 1. Exploración y Descubrimiento de la API
El punto de partida fue el portal web del ISTAC. En lugar de descargar excels manuales pivotados (que mezclaban todas las islas y tenían una estructura compleja), investigamos la API REST del ISTAC.

Descubrimos que la API de indicadores se estructura de la siguiente manera:
- **Sistema Base:** `C00067A` (Municipios en cifras)
- **Endpoint:** `https://datos.canarias.es/api/estadisticas/indicators/v1.0/indicatorsSystems/{system_id}/indicatorsInstances/{uuid}/data.tsv`

Utilizamos un enfoque programático para listar todos los indicadores disponibles del sistema, identificar sus UUIDs específicos y mapear exactamente los 16 indicadores demográficos, económicos y turísticos requeridos para el TFM.

## 2. Extracción de Datos (Raw)
Se desarrolló el script `ingestion/istac/istac_municipios_api.py` para realizar las siguientes tareas:
1. **Paginación:** La API del ISTAC estaba paginada. El script recorre dinámicamente las páginas para recuperar la lista completa de indicadores (75 en total) y filtra los 16 objetivos.
2. **Descarga en formato TSV:** Se utilizó el endpoint TSV de la API ya que proporciona un formato largo (long format: Periodo, Municipio, Medida, Valor) ideal para procesamiento de datos, frente al formato Excel pivotado de la web.
3. **Filtrado Geográfico:** Se implementó un filtro estricto por nombre de municipio. Se definió una lista exacta con los 31 municipios de la isla de Tenerife (junto con sus variantes abreviadas reportadas por el ISTAC, ej. "San Cristóbal de L"). Esto descartó automáticamente los datos de otras islas (como Gran Canaria o La Gomera) que venían mezclados en los resultados de la API.
4. **Filtrado Temporal:** Se restringieron los datos al periodo de interés para el modelo (2019 - 2026).
5. **Consolidación:** El script concatena los 16 indicadores en un único archivo maestro: `data/bronce/tabular/raw/istac_municipios_cifras_tenerife.csv`.

**Resultado de Extracción:** Un dataset unificado de 40.975 filas limpias, exclusivamente de la isla de Tenerife.

## 3. Optimización y Subida a Azure (Capa Bronce-Raw)
Para cumplir con la arquitectura *Medallion* del proyecto, los datos debían almacenarse en la nube antes de pasar a la base de datos.
- **Script:** `ingestion/istac/upload_istac_to_blob.py`
- **Conversión a Parquet:** El CSV generado de 4.17 MB fue convertido a formato Apache Parquet utilizando compresión Snappy. Esto redujo drásticamente el tamaño a solo **0.14 MB** (un 96% de compresión), optimizando los costes de almacenamiento y mejorando los tiempos de lectura.
- **Carga en la Nube:** Mediante `azure-storage-blob`, el archivo Parquet fue subido automáticamente al contenedor `bronce-raw` del Datalake bajo la ruta `tabular/istac/istac_municipios_cifras_tenerife.parquet`.

## 4. Ingesta en PostgreSQL (Capa Bronze)
El último paso de la fase Bronce fue cargar los datos desde Azure Blob Storage hacia el sistema de bases de datos relacional (Azure PostgreSQL) donde dbt realizará las transformaciones.
- **Script:** Se modificó `ingestion/postgres/ingest_bronze_to_postgres.py` para incluir la nueva ruta del archivo Parquet en la lista de archivos a ingestar.
- **Ejecución:** El script conectó con el Azure Blob Storage, descargó el Parquet en memoria y utilizando la función `to_sql` de Pandas (con `method="multi"` y `chunksize=1000`), insertó las 40.975 filas en la tabla `bronze.istac_municipios`.

---
> **Siguiente Fase:** A partir de aquí (y ya completado), dbt toma el relevo. Lee la tabla `bronze.istac_municipios` para ejecutar la transformación a la capa **Silver**, donde pivota las variables en columnas independientes, maneja el secreto estadístico (`.`), extrae el mes numéricamente y ajusta los tipos de datos a numéricos.
