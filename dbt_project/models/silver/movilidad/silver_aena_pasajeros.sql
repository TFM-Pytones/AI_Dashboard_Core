{{ config(
    materialized='table',
    tags=['silver', 'movilidad', 'aena']
) }}

WITH source_data AS (
    SELECT *
    FROM {{ source('bronze', 'bronze_aena_pasajeros') }}
),

cleaned AS (
    SELECT
        "TIME_CODE" AS periodo,
        CAST(SUBSTRING("TIME_CODE" FROM 1 FOR 4) AS INTEGER) AS anio,
        CAST(SUBSTRING("TIME_CODE" FROM 6 FOR 2) AS INTEGER) AS mes,
        "AEROPUERTO" AS aeropuerto,
        COALESCE(CAST("Pasajeros" AS NUMERIC), 0)   AS pasajeros,
        COALESCE(CAST("Operaciones" AS NUMERIC), 0) AS operaciones
    FROM source_data
    WHERE "TIME_CODE" IS NOT NULL
      AND CAST(SUBSTRING("TIME_CODE" FROM 1 FOR 4) AS INTEGER) >= 2022
)

SELECT
    periodo,
    anio,
    mes,
    aeropuerto,
    pasajeros,
    operaciones
FROM cleaned
ORDER BY anio DESC, mes DESC, aeropuerto ASC
