# ingestion/open_meteo/

Módulo de Ingesta para la **Capa Bronce (Raw Ingestion)** de datos meteorológicos satelitales (ERA5-Land) y previsiones operacionales (GFS) desde la API de Open-Meteo hacia **Azure Blob Storage**.

## 📌 Arquitectura Medallón — Capa Bronce (Azure Data Lakehouse)

Los scripts en este módulo descargan e ingieren datos inmutables y los almacenan en el contenedor `bronce-raw` con metadatos de auditoría (`ingested_at_utc`, `source_api`, `model_name`):

- `satelite_era5land/`: Reanálisis histórico ERA5-Land (Nivel 1 de validación).
- `forecast_gfs/`: Pronóstico histórico operacional GFS `gfs_seamless` (Nivel 2 de validación).
- `leadtime_gfs/`: Series temporales por horizonte de pronóstico (D+1, D+3, D+7).

## 🚀 Uso

```bash
# Ejecutar ingesta completa hacia Azure Blob Storage (Capa Bronce)
python ingestion/open_meteo/open_meteo_ingestion.py
```

## 🔐 Configuración

Requiere la variable de entorno `AZURE_STORAGE_CONNECTION_STRING` en el archivo `.env` raíz. Si no está configurada, los datos se guardarán de forma transparente en la carpeta local `data/bronce/`.
