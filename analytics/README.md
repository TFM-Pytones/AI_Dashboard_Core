# Analítica Avanzada e Inteligencia Espacial (Bloque 4 del TFM)

Este directorio centraliza los módulos de **Machine Learning, Procesamiento de Lenguaje Natural (NLP) y Modelado Geoespacial** del proyecto *Tenerife AI Dashboard*, transformando las capas Silver y Gold en conocimiento predictivo y descriptivo.

---

## Mapa de Componentes Analíticos

```
analytics/
├── sentiment/          # 4.1 Inferencia de sentimiento multilingüe (XLM-RoBERTa)
├── topics/             # 4.2 Modelado de tópicos de conversación turística (BERTopic)
├── aspects/ & tarea2/  # 4.2 Extracción y normalización de aspectos/quejas (PyABSA)
├── clustering/         # 4.4 Detección de brechas y hotspots de saturación (HDBSCAN)
├── accesibilidad/      # 4.5 Modelado de tiempos de acceso e isócronas (GTFS / OSRM)
├── geo/                # Utilidades de enriquecimiento espacial y zonal
└── llm/                # Bloque 5: Agente analítico y generación de resúmenes ejecutivos
```

---

## 1. Módulos y Metodologías Aplicadas

### 1.1. Análisis de Sentimiento Multilingüe ([`sentiment/`](sentiment/))
* **Modelo**: `cardiffnlp/twitter-xlm-roberta-base-sentiment` (Hugging Face Transformers).
* **Entrada**: Comentarios de YouTube y reseñas depuradas de Booking y TripAdvisor.
* **Características**: Clasificación nativa multilingüe (español, inglés, alemán, francés e italiano) y mapeo determinístico a escala 1 a 5 estrellas para agregación territorial.
* **Documentación completa**: Ver [`analytics/sentiment/README.md`](sentiment/README.md).

### 1.2. Modelado de Tópicos de Conversación ([`topics/`](topics/))
* **Modelo**: **BERTopic** con embeddings semánticos multilingües (`sentence-transformers`).
* **Subflujos**:
  * *Corpus General*: Detección de grandes temáticas insulares (clima, precios, masificación, experiencias naturales).
  * *Corpus Georreferenciado*: Extracción de tópicos vinculados a establecimientos y municipios específicos para su cruce con la malla H3.

### 1.3. Extracción de Aspectos y Quejas Específicas ([`aspects/`](aspects/) y [`tarea2/`](tarea2/))
* **Tecnología**: **PyABSA** (*Aspect-Based Sentiment Analysis*).
* **Objetivo**: Aislar el aspecto concreto evaluado por el turista (ej. *limpieza*, *ruido*, *atención del personal*, *comida*, *playas*) junto con la polaridad asociada.
* **Normalización**: Traducción y agrupación canónica de aspectos (`gold.aspecto_traducciones`) para determinar la queja principal modal por hexágono H3 en `gold_sentimiento_h3`.

### 1.4. Detección de Hotspots y Brechas de Mercado ([`clustering/`](clustering/))
* **Algoritmo**: **HDBSCAN** (*Hierarchical Density-Based Spatial Clustering of Applications with Noise*).
* **Variables**: Densidad de oferta reglada (hoteles, VV), presión de plazas, precios medios y concentración de POIs.
* **Resultado**: Segmentación del territorio en clústeres de saturación crítica (polos maduros) y clústeres de oportunidad/brechas de mercado (zonas rurales y de medianías con atractivo ambiental pero baja oferta).

### 1.5. Modelado de Accesibilidad y Transporte ([`accesibilidad/`](accesibilidad/))
* **Script**: [`gold_h3_accesibilidad.py`](accesibilidad/gold_h3_accesibilidad.py).
* **Entrada**: Red de paradas GTFS (`silver_gtfs_paradas`), rutas de transporte regular y centroides canónicos H3.
* **Métricas**: Frecuencia diaria de expediciones accesibles, líneas disponibles por hexágono y distancias a nodos de movilidad primaria.
