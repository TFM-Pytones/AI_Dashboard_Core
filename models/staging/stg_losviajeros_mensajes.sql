{{ config(
    materialized='table',
    schema='silver',
    tags=['turismo', 'foros', 'nlp']
) }}

WITH raw_data AS (
    SELECT * FROM {{ source('raw_data', 'losviajeros_mensajes') }}
),

cleaned_mensajes AS (
    SELECT
        CAST(mensaje_id AS BIGINT) AS id_mensaje,
        CAST(tema_id AS BIGINT) AS id_tema,
        TRIM(tema_titulo) AS titulo_tema,
        
        -- Limpieza de texto: Reemplaza saltos de línea y retornos de carro por espacios simples
        REGEXP_REPLACE(
            REGEXP_REPLACE(contexto_pagina_raw, '\r', ' ', 'g'), 
            '\n+', ' ', 'g'
        ) AS texto_mensaje_limpio,
        
        TRIM(url) AS url_mensaje,
        CAST(fetched_at AS TIMESTAMP) AS fecha_extraccion
    FROM raw_data
    WHERE mensaje_id IS NOT NULL
)

SELECT * FROM cleaned_mensajes