{{ config(
    materialized='table',
    tags=['silver', 'espacial', 'cultura'],
    indexes=[
      {'columns': ['geometry'], 'type': 'gist'}
    ]
) }}

SELECT
    NULL AS id,
    bic_nombre AS nombre,
    'bien_cultural' AS tipo,
    municipio_nombre AS municipio,
    geometry
FROM {{ source('bronze', 'bienes_interes_cultural') }}
WHERE geometry IS NOT NULL
