{{ config(
    materialized='table',
    tags=['gold', 'municipio'],
    indexes=[
      {'columns': ['municipio_cod'], 'unique': True}
    ]
) }}

/*
  Modelo Gold: gold_municipio_master
  Rollup a nivel municipio (31 filas) de gold_h3_master. Igual que
  gold_h3_master, no tiene dimension temporal -- es un snapshot del estado
  actual de la oferta turistica.

  Poblacion/paro/ocupacion (que si tienen serie temporal en ISTAC, con
  varios anios y meses disponibles) NO se colapsan aqui a "el ultimo dato" --
  se consultan completas desde silver_istac_anual/silver_istac_mensual
  directamente en el dashboard (app/municipios.py), donde el usuario elige
  el anio. Colapsar a un unico anio en este modelo habria obligado a
  recompilar el modelo dbt cada vez que llega un periodo ISTAC nuevo, y
  habria bloqueado ver anios anteriores.
*/

SELECT
    cod_municipio AS municipio_cod,
    municipio,
    COUNT(*) AS n_hexagonos,
    SUM(n_establecimientos_registro) AS n_establecimientos_registro,
    SUM(n_plazas_registro) AS n_plazas_registro,
    SUM(n_hoteles) AS n_hoteles,
    SUM(n_vv) AS n_vv,
    SUM(n_extrahoteleros) AS n_extrahoteleros,
    SUM(n_establecimientos_booking) AS n_establecimientos_booking,
    ROUND(AVG(rating_booking_medio)::numeric, 2) AS rating_booking_medio,
    SUM(n_establecimientos_tripadvisor) AS n_establecimientos_tripadvisor,
    ROUND(AVG(rating_tripadvisor_medio)::numeric, 2) AS rating_tripadvisor_medio,
    ROUND(AVG(ndvi_medio)::numeric, 3) AS ndvi_medio
FROM {{ ref('gold_h3_master') }}
WHERE cod_municipio IS NOT NULL
GROUP BY cod_municipio, municipio
ORDER BY municipio
