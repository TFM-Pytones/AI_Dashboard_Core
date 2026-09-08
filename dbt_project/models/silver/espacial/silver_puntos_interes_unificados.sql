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
        CAST(osm_id AS VARCHAR)  AS id,
        CAST(poi_name AS TEXT)   AS nombre,
        CAST(poi_type AS TEXT)   AS tipo,
        CAST(poi_group AS TEXT)  AS categoria,
        NULL::text               AS municipio,
        'OSM'                    AS fuente,
        geometry
    FROM {{ ref('silver_osm_pois') }}
    WHERE geometry IS NOT NULL
),

cultura AS (
    SELECT 
        CAST(id AS VARCHAR)      AS id,
        CAST(nombre AS TEXT)     AS nombre,
        CAST(tipo AS TEXT)       AS tipo,
        'Cultura'::text          AS categoria,
        CAST(municipio AS TEXT)  AS municipio,
        'IDE_Canarias'           AS fuente,
        geometry
    FROM {{ ref('silver_bienes_interes_culturales') }}
    WHERE geometry IS NOT NULL
),

turismo AS (
    SELECT 
        NULL::varchar            AS id,
        CAST(nombre AS TEXT)     AS nombre,
        CAST(tipo AS TEXT)       AS tipo,
        'Turismo'::text          AS categoria,
        CAST(municipio AS TEXT)  AS municipio,
        'IDE_Canarias'           AS fuente,
        geometry
    FROM {{ ref('silver_oficinas_turismo') }}
    WHERE geometry IS NOT NULL
)

SELECT * FROM osm
UNION ALL
SELECT * FROM cultura
UNION ALL
SELECT * FROM turismo
