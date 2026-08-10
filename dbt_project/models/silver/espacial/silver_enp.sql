{{ config(materialized='table', tags=['silver', 'espacial', 'enp']) }}

/*
  Modelo Silver: silver_enp (Espacios Naturales Protegidos)
  Polígonos de ENP de Tenerife con categoría y área.
*/

SELECT
    id_enp,
    nombre_enp,
    categoria,   -- Parque Nacional, Parque Rural, Reserva, Monumento Natural, etc.
    municipio,
    cod_municipio,
    ROUND(CAST(ST_Area(geometry::geography) / 1000000.0 AS NUMERIC), 2) AS area_km2,
    geometry
FROM {{ source('bronze', 'tenerife_espacios_naturales_protegidos') }}
WHERE geometry IS NOT NULL
