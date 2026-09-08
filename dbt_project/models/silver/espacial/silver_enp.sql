{{ config(materialized='table', tags=['silver', 'espacial', 'enp']) }}

/*
  Modelo Silver: silver_enp (Espacios Naturales Protegidos)
  Polígonos de ENP de Tenerife con categoría y área.
  Columnas reales en bronze: categoria, nombre, codigo, geometry
*/

SELECT
    codigo AS id_enp,
    nombre AS nombre_enp,
    categoria,
    ROUND(CAST(ST_Area(geometry::geography) / 1000000.0 AS NUMERIC), 2) AS area_km2,
    ST_Transform(ST_SetSRID(geometry, COALESCE(NULLIF(ST_SRID(geometry), 0), 4326)), 4326) AS geometry
FROM {{ source('bronze', 'bronze_espacios_naturales') }}
WHERE geometry IS NOT NULL
