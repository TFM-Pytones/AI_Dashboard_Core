{{ config(
    materialized='table',
    tags=['silver', 'espacial', 'puntos_interes'],
    indexes=[
      {'columns': ['geometry'], 'type': 'gist'},
      {'columns': ['fuente']},
      {'columns': ['tipo']}
    ]
) }}

WITH osm AS (
    SELECT 
        CAST(osm_id AS VARCHAR) AS id,
        poi_name AS nombre,
        poi_type AS tipo,
        poi_group AS categoria,
        NULL AS municipio,
        'OSM' AS fuente,
        NULL AS horario,
        NULL AS descripcion,
        NULL AS telefono,
        NULL AS estado,
        geometry
    FROM {{ ref('silver_osm_pois') }}
    WHERE geometry IS NOT NULL
),

cultura AS (
    SELECT 
        CAST(id AS VARCHAR) AS id,
        nombre,
        tipo,
        'Cultura' AS categoria,
        municipio,
        'IDE_Canarias' AS fuente,
        NULL AS horario,
        NULL AS descripcion,
        NULL AS telefono,
        NULL AS estado,
        geometry
    FROM {{ ref('silver_bienes_culturales') }}
    WHERE geometry IS NOT NULL
),

turismo AS (
    SELECT 
        CAST(id AS VARCHAR) AS id,
        nombre,
        tipo,
        'Turismo' AS categoria,
        municipio,
        'IDE_Canarias' AS fuente,
        horario,
        descripcion,
        telefono,
        estado,
        geometry
    FROM {{ ref('silver_oficinas_turismo') }}
    WHERE geometry IS NOT NULL
)

SELECT * FROM osm
UNION ALL
SELECT * FROM cultura
UNION ALL
SELECT * FROM turismo
