# ingestion/

Scripts de extracción de datos de cada fuente externa. Una subcarpeta por fuente, correspondiente a su issue en GitHub:

- `aemet/` — issue #9 (Conexión API AEMET)
- `booking/` — issue #12 (Scraping de Booking.com)
- `copernicus/` — issue #10 (Extracción Satelital Copernicus)
- `gtfs/` — issue #8 (Parseo de GTFS a Tablas)
- `microdatos/` — issue #5 (Extracción Microdatos Oficiales Cabildo/ISTAC, ya cerrada — código de referencia)
- `youtube/` — issue #13 (Integración API de YouTube)

Cada script debe leer credenciales desde `.env` (nunca hardcodeadas) y dejar los datos ya listos para cargarse en el Data Warehouse (`sql/`).
