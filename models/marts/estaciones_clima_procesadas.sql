{{ config(materialized='table') }}

SELECT 
    id_estacion as id,
    nombre,
    ST_Transform(ubicacion, 32628) as geometry,
    altitud
FROM {{ source('raw_data', 'estaciones_clima') }}