# Ingesta de Redes Sociales: YouTube Data API v3 (Capa Bronze)

Documentación técnica del pipeline de captura de contenido audiovisual y análisis de percepción del destino mediante la **YouTube Data API v3**, enfocándose en vídeos turísticos sobre Tenerife y los comentarios de viajeros internacionales e hispanohablantes.

---

## 1. Arquitectura y Flujo de Datos

```
YouTube Data API v3 (https://www.googleapis.com/youtube/v3)
       │
       ▼  youtube_upload_blob.py
       ├─► search.list (100 unidades/llamada): Búsqueda por 4 términos turísticos
       ├─► videos.list (1 unidad/llamada): Estadísticas y visualizaciones
       └─► commentThreads.list (1 unidad/llamada): Hilos de comentarios de usuarios
       │
       ▼  Serialización en memoria a Parquet Snappy (io.BytesIO)
Azure Blob Storage: bronce-raw/youtube/
       ├── youtube_videos.parquet    (Vídeos turísticos y métricas de visualización)
       └── youtube_comments.parquet  (Comentarios y reacciones de viajeros)
       │
       ▼  Carga en Base de Datos (ingestion/postgres/05_ingest_tabular_to_postgres.py)
PostgreSQL:
       ├── bronze.bronze_youtube_videos
       └── bronze.bronze_youtube_comments
       │
       ▼  Transformación analítica con dbt
PostgreSQL: silver.silver_youtube_videos / silver_youtube_comentarios
       │
       ▼  Modelos de IA y Procesamiento del Lenguaje Natural (Analytics)
       ├── BERTopic Modelo A (Tópicos cualitativos y sentimiento global)
       └── Sistema RAG Turístico e Informes de Percepción del Destino
```

---

## 2. Gestión Eficiente de Cuotas de la API

La cuota gratuita de Google Cloud para YouTube Data API v3 es de **10.000 unidades/día**. El script [`youtube_upload_blob.py`](file:///c:/Users/ROBERTO/Proyectos_Python/TFM_TUI_Tenerife/AI_Dashboard_Core/ingestion/youtube/youtube_upload_blob.py) está específicamente diseñado para minimizar el consumo de cuota:

1. **Búsqueda Focalizada (`search.list`)**:
   - Coste: **100 unidades por llamada**.
   - Se limita estrictamente a 4 términos clave de alta relevancia:
     * `"Tenerife turismo"`
     * `"Tenerife travel"`
     * `"visitar Tenerife"`
     * `"Tenerife vacaciones"`
   - Máximo 15 vídeos por término (`MAX_VIDEOS_PER_TERM = 15`), consumiendo solo 400 unidades de cuota.
2. **Batching de Estadísticas (`videos.list`)**:
   - Coste: **1 unidad por llamada** para lotes de hasta 50 IDs.
   - Recupera el recuento real de reproducciones (`viewCount`) para todos los vídeos en una única petición agrupada.
3. **Paginación Controlada de Comentarios (`commentThreads.list`)**:
   - Coste: **1 unidad por página** (hasta 100 comentarios por página).
   - Se fija un límite de 3 páginas por vídeo (`MAX_COMMENT_PAGES_PER_VIDEO = 3`), extrayendo hasta ~300 comentarios por vídeo con un consumo de apenas 3 unidades por vídeo.

---

## 3. Estructura de Datos en Capa Bronze

### A. `youtube_videos.parquet` (`bronze.bronze_youtube_videos`)
| Columna | Tipo | Descripción | Ejemplo |
|---|---|---|---|
| `video_id` | `VARCHAR` | Identificador único del vídeo en YouTube | `dQw4w9WgXcQ` |
| `search_term` | `VARCHAR` | Término de búsqueda que descubrió el vídeo | `Tenerife turismo` |
| `title` | `TEXT` | Título del vídeo | `Qué ver en Tenerife: Guía de 7 días` |
| `channel_title` | `VARCHAR` | Nombre del canal creador | `Viajeros Callejeros` |
| `published_at` | `TIMESTAMP` | Fecha de publicación del vídeo | `2023-04-12T10:00:00Z` |
| `view_count` | `BIGINT` | Número total de reproducciones acumuladas | `145230` |

### B. `youtube_comments.parquet` (`bronze.bronze_youtube_comments`)
| Columna | Tipo | Descripción |
|---|---|---|
| `comment_id` | `VARCHAR` | Identificador del comentario |
| `video_id` | `VARCHAR` | Identificador del vídeo padre |
| `text` | `TEXT` | Texto completo del comentario |
| `like_count` | `INT` | Número de "Me gusta" recibidos por el comentario |
| `published_at` | `TIMESTAMP` | Fecha de publicación del comentario |
| `author_name` | `VARCHAR` | Nombre del usuario autor |

---

## 4. Instrucciones de Ejecución

### Requisitos previos en `.env`:
```bash
YOUTUBE_API_KEY="AIzaSy..."
AZURE_STORAGE_CONNECTION_STRING="DefaultEndpointsProtocol=https;AccountName=...;AccountKey=..."
```

### 1. Ejecutar extracción y subida a Azure Blob Storage:
```bash
python ingestion/youtube/youtube_upload_blob.py
```

### 2. Cargar en Azure PostgreSQL:
```bash
python ingestion/postgres/05_ingest_tabular_to_postgres.py
```
