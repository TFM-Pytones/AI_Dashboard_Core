

SELECT 
    id_estacion as id,
    nombre,
    ST_Transform(ubicacion, 32628) as geometry,
    altitud
FROM "neondb"."raw_data"."estaciones_clima"