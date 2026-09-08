{{ config(
    materialized='table',
    tags=['silver', 'espacial', 'cultura'],
    indexes=[
      {'columns': ['geometry'], 'type': 'gist'}
    ]
) }}

WITH raw_data AS (
    SELECT
        geometry,
        -- Quitar dobles espacios y convertir a Title Case
        INITCAP(REGEXP_REPLACE(TRIM(bic_nombre), E'\\s+', ' ', 'g')) AS raw_nombre,
        
        -- Arreglar los paréntesis de los municipios (ej: "OROTAVA (LA)" -> "LA OROTAVA")
        -- Patrón: captura el nombre base ($1) y el artículo del paréntesis ($2), invierte el orden
        INITCAP(
            CASE
                WHEN municipio_nombre ~ E'^.+\\s+\\((LA|EL|LOS|LAS)\\)$'
                THEN REGEXP_REPLACE(TRIM(municipio_nombre), E'^(.+)\\s+\\((LA|EL|LOS|LAS)\\)$', '\2 \1', 'i')
                ELSE TRIM(municipio_nombre)
            END
        ) AS raw_municipio
    FROM {{ source('bronze', 'bronze_bienes_interes_cultural') }}
    WHERE geometry IS NOT NULL
),
cleaned_data AS (
    SELECT
        geometry,
        -- Arreglar preposiciones para que queden en minúscula en medio del texto
        REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(raw_nombre, 
            ' De ', ' de '), ' Del ', ' del '), ' La ', ' la '), ' El ', ' el '), ' Los ', ' los '), ' Y ', ' y ') AS nombre,
            
        REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(raw_municipio, 
            ' De ', ' de '), ' Del ', ' del '), ' La ', ' la '), ' El ', ' el '), ' Los ', ' los '), ' Y ', ' y ') AS municipio
    FROM raw_data
)

SELECT
    MD5(COALESCE(nombre, '') || '_' || COALESCE(municipio, '')) AS id,
    nombre,
    'bien_cultural' AS tipo,
    municipio,
    geometry
FROM cleaned_data
