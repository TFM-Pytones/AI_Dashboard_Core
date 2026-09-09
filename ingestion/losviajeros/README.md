# Ingesta — LosViajeros.com

Pipeline de extracción, conversión, carga a Azure y a PostgreSQL de los datos del foro LosViajeros.com (sección Tenerife).

## Scripts (orden de ejecución)

| # | Script | Descripción |
|---|---|---|
| 1 | `losviajeros_scraper.py` | Scraping de hilos y mensajes del foro (BeautifulSoup, rate limiting, respeta robots.txt) |
| 2 | `csv_to_parquet.py` | Convierte los CSV generados a formato Parquet |
| 3 | `upload_losviajeros_azure.py` | Sube los Parquet al contenedor bronce de Azure Blob Storage |
| 4 | `load_losviajeros_postgres.py` | Carga los datos en el esquema bronze de PostgreSQL |

## Volúmenes

- **248 hilos** scrapeados
- **~167.000 mensajes** extraídos
- 2 tablas: `bronze_losviajeros_temas`, `bronze_losviajeros_mensajes`

## Notas

- Los datos **no contienen geolocalización**: se usan para análisis de sentimiento general, no geoespacial.
- El scraper incluye User-Agent académico y rate limiting (1,5-3 s entre peticiones).
