# Arquitectura del proyecto

Flujo de datos de extremo a extremo:

```
Fuentes externas (AEMET, Copernicus, GTFS, Cabildo/ISTAC, TripAdvisor/Scraping)
        │
        ▼  [Orquestado por GitHub Actions (Cron Jobs)]
   ingestion/ (scripts Python por fuente)
        │
        ▼
[Capa Bronce] Data Lake (Azure Storage Account Gen2) ── raw/ (JSON, CSV, SHP, TIF)
        │
        ▼  [Limpieza y Transformación vía scripts Python/SQL en GitHub Actions]
[Capa Plata]  Data Warehouse (Azure PostgreSQL + PostGIS) ── Esquema 'silver' (Datos limpios y espaciales)
        │
        ▼  analytics/ (NLP, NDVI/NDBI, clustering, isocronas, MGWR)
[Capa Oro]    Data Mart (Azure PostgreSQL) ── Esquema 'gold' (KPIs y agregaciones)
        │
        ▼
   llm/ (Agente Text-to-SQL consultando el Esquema 'gold')
        │
        ▼
   app/ (AI-Dashboard Streamlit — visualización y simulador)
```

Cada bloque corresponde a una sección del índice del TFM (ver `docs/00_indice_tfm.md`) y a un grupo de issues en GitHub.
