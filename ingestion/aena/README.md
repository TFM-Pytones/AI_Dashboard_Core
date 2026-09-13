# Ingesta de Tráfico Aéreo: AENA (Capa Bronze)

Documentación técnica del pipeline de extracción, estructuración y carga de las estadísticas oficiales de tráfico aéreo de los aeropuertos de la isla de Tenerife (**Tenerife Norte - Ciudad de La Laguna [TFN]** y **Tenerife Sur - Reina Sofía [TFS]**), publicadas mensualmente por **AENA**.

---

## 1. Arquitectura y Flujo de Datos

El proceso automatizado se encuentra implementado en [`aena_pasajeros_upload_blob.py`](file:///c:/Users/ROBERTO/Proyectos_Python/TFM_TUI_Tenerife/AI_Dashboard_Core/ingestion/aena/aena_pasajeros_upload_blob.py):

```
Archivos Excel AENA (data/aena/*.xls, *.xlsx)
       │
       ▼  Parseo inteligente (búsqueda de "TENERIFE" y detección de categoría)
aena_pasajeros_upload_blob.py
       │
       ├─► Guardado local Parquet: data/aena/aena_pasajeros_tenerife.parquet
       │
       ▼  Subida a Data Lake (Azure Blob Storage)
Contenedor: bronce-raw/aena/aena_pasajeros_tenerife.parquet
       │
       ▼  Carga por lotes (ingestion/postgres/05_ingest_tabular_to_postgres.py)
PostgreSQL: bronze.bronze_aena_pasajeros
       │
       ▼  Transformación analítica con dbt
PostgreSQL: silver.silver_aena_pasajeros
```

---

## 2. Complejidad del Formato Fuente y Solución Técnica

AENA publica sus informes mensuales de tráfico en libros Excel multi-hoja con estructuras tabulares no normalizadas (tablas paralelas de pasajeros, operaciones y carga dentro de la misma cuadrícula, carátulas institucionales y acumulados anuales).

### Estrategia de Extracción en [`extract_aena_data`](file:///c:/Users/ROBERTO/Proyectos_Python/TFM_TUI_Tenerife/AI_Dashboard_Core/ingestion/aena/aena_pasajeros_upload_blob.py#L32-L118):
1. **Selección Dinámica de Hoja**:
   - Prioridad 1: Hojas con denominación explícita `"Ranking mensual"` o `"Ranking anual"`.
   - Prioridad 2: Descarte sistemático de carátulas técnicas del sistema generador (`"Mozart Reports"`) y hojas de acumulados que duplicarían las métricas mensuales.
2. **Inferencia Temporal**:
   - Extracción de año mediante expresiones regulares sobre el nombre del fichero (`\d{4}`).
   - Mapeo de meses en español (`enero` a `diciembre`) para estandarizar el campo temporal `TIME_CODE` en formato ISO `YYYY-MM`.
3. **Escaneo Celular y Segmentación**:
   - Escaneo de filas buscando menciones a `"TENERIFE"` (`Tenerife Norte` y `Tenerife Sur`).
   - Búsqueda en una ventana deslizante de 3 columnas a la derecha para localizar el valor numérico correspondiente.
   - Clasificación por posición relativa en la hoja: primer tercio (Pasajeros), tercio medio (Operaciones/Vuelos) y tercio final (Mercancías/Carga en kg).
4. **Pivoteo y Normalización**:
   - Se transforman los registros capturados a formato tabular plano (*tidy data*): cada fila representa unívocamente la tupla `(TIME_CODE, AEROPUERTO)` con sus tres métricas cuantitativas desglosadas en columnas.

---

## 3. Esquema de Datos Resultante

El fichero consolidado `aena_pasajeros_tenerife.parquet` contiene el siguiente esquema:

| Columna | Tipo | Descripción | Ejemplo |
|---|---|---|---|
| `TIME_CODE` | `VARCHAR(7)` | Año y mes de las operaciones en formato estándar | `2024-05` |
| `AEROPUERTO` | `VARCHAR` | Nombre del aeropuerto en la nomenclatura AENA | `TENERIFE SUR`, `TENERIFE NORTE-C. LA LAGUNA` |
| `Pasajeros` | `FLOAT / INT` | Total de pasajeros comerciales transportados en el mes | `1124530` |
| `Operaciones` | `FLOAT / INT` | Número total de vuelos (despegues y aterrizajes) | `7412` |
| `Mercancías` | `FLOAT` | Volumen de carga y correo transportado (kg) | `452310.5` |

---

## 4. Instrucciones de Ejecución

### Requisitos previos:
Asegúrate de contar con los archivos mensuales descargados en el directorio local `data/aena/` y de tener configurada la cadena de conexión en el `.env`:
```bash
AZURE_STORAGE_CONNECTION_STRING="DefaultEndpointsProtocol=https;AccountName=...;AccountKey=..."
```

### Ejecutar ingesta y subida al Data Lake:
```bash
python ingestion/aena/aena_pasajeros_upload_blob.py
```

### Cargar a la base de datos PostgreSQL:
Para cargar el Parquet generado en la tabla `bronze.bronze_aena_pasajeros`:
```bash
python ingestion/postgres/05_ingest_tabular_to_postgres.py
```
