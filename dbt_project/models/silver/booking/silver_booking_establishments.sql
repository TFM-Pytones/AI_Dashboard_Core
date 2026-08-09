{{ config(
    materialized='table',
    tags=['silver', 'booking']
) }}

-- Deduplica establecimientos: como el scraper puede re-procesar el mismo
-- establecimiento en distintas corridas (ej. tras un timeout que obligó a
-- reintentar), la capa Bronce puede tener el mismo establishment_id repetido
-- varias veces con datos prácticamente idénticos. No existe una columna de
-- timestamp de scraping en los datos crudos (limitación conocida — el
-- timestamp solo vive en el nombre del archivo Parquet, no se llevó a la
-- tabla), así que DISTINCT ON toma una fila arbitraria por establishment_id
-- (no necesariamente la más reciente) — aceptable porque los atributos del
-- establecimiento no cambian entre corridas.

WITH source_data AS (
    SELECT *
    FROM {{ source('bronze', 'booking_establishments') }}
),

deduplicated AS (
    SELECT DISTINCT ON (establishment_id) *
    FROM source_data
    ORDER BY establishment_id
)

SELECT
    establishment_id,
    name,
    url,
    address,
    latitude,
    longitude,
    establishment_type
FROM deduplicated
