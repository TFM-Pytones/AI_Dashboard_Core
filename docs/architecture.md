# Arquitectura del proyecto

Flujo de datos de extremo a extremo:

```
Fuentes externas (AEMET, Copernicus, GTFS, Cabildo/ISTAC, scraping)
        │
        ▼
   ingestion/  (scripts Python por fuente)
        │
        ▼
   Data Warehouse (Neon / PostgreSQL + PostGIS)  ── sql/
        │  orquestado por dags/ (Airflow) + dbt_project/ (dbt)
        ▼
   analytics/  (NLP, NDVI/NDBI, clustering, isocronas, MGWR)
        │
        ▼
   llm/  (agente Text-to-SQL / generación de insights)
        │
        ▼
   app/  (dashboard Streamlit — visualización y simulador)
```

Cada bloque corresponde a una sección del índice del TFM (ver `docs/00_indice_tfm.md`) y a un grupo de issues en GitHub.
