# ingestion/

Scripts de extracción de datos de cada fuente externa. Una subcarpeta por fuente, correspondiente a su issue en GitHub:

- `aemet/` — issue #9 (Conexión API AEMET)
- `copernicus/` — issue #10 (Extracción Satelital Copernicus)
- `gtfs/` — issue #8 (Parseo de GTFS a Tablas)
- `microdatos/` — issue #5 (Extracción Microdatos Oficiales Cabildo/ISTAC, ya cerrada — código de referencia)
- `scraping/` — issues #12, #13, #14 (TripAdvisor/Booking, Google/YouTube, Reddit)

Cada script debe leer credenciales desde `.env` (nunca hardcodeadas) y dejar los datos ya listos para cargarse en el Data Warehouse (`sql/`).
