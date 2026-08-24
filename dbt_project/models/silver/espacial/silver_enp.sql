{{ config(materialized='table', tags=['silver', 'espacial', 'enp']) }}

/*
  Modelo Silver: silver_enp (Espacios Naturales Protegidos)
  Polígonos de ENP de Tenerife con categoría y área.
*/

SELECT
    id AS id_enp,
    nombre AS nombre_enp,
    categoria,   -- Parque Nacional, Parque Rural, Reserva, Monumento Natural, etc.
    NULL AS municipio,
    NULL AS cod_municipio,
    ROUND(CAST(ST_Area(geometry::geography) / 1000000.0 AS NUMERIC), 2) AS area_km2,
    geometry
FROM {{ source('bronze', 'espacios_naturales') }}
WHERE geometry IS NOT NULL
