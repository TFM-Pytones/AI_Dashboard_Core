{{ config(
    materialized='table',
    schema='silver',
    tags=['turismo', 'foros']
) }}

WITH raw_data AS (
    SELECT * FROM {{ source('raw_data', 'losviajeros_temas') }}
),

cleaned_temas AS (
    SELECT
        CAST(tema_id AS BIGINT) AS id_tema,
        TRIM(titulo) AS titulo_tema,
        TRIM(url) AS url_tema
    FROM raw_data
    WHERE tema_id IS NOT NULL
)

SELECT * FROM cleaned_temas