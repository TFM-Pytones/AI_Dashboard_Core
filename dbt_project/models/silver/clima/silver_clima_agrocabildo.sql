{{ config(materialized='table') }}

/* 
  Modelo Silver: silver_clima_horario_agrocabildo
  -------------------------------------------------------------
  Limpieza de datos meteorológicos de Agrocabildo:
  1. Filtra únicamente lecturas diezminutales de HORAS EN PUNTO (:00:00).
  2. Elimina códigos de error (-999, -9999, NULL).
  3. Prioriza valor_validado sobre valor_observado.
  4. Trata valores extremos mediante capado (Winsorización/CASE WHEN).
*/

WITH lecturas_en_punto AS (
    SELECT 
        id_estacion,
        id_sensor,
        "timestamp",
        valor_observado,
        valor_validado,
        COALESCE(valor_validado, valor_observado) AS valor_raw,
        es_validado
    FROM {{ source('bronze', 'bronze_clima_horario_agrocabildo') }}
    WHERE 
        -- 1. Filtrar solo horas en punto (00 min 00 seg)
        date_trunc('hour', "timestamp") = "timestamp"
        -- 2. Eliminar nulos y codigos de error tipicos de sensores
        AND COALESCE(valor_validado, valor_observado) IS NOT NULL
        AND COALESCE(valor_validado, valor_observado) NOT IN (-999, -9999, -99, 999, 9999)
        -- 3. Filtrar datos desde 2022 hasta la actualidad
        AND "timestamp" >= '2022-01-01'
        -- 4. Filtrar solo estaciones maduras (instaladas <= 2022-01-01) presentes en silver_estaciones_agrocabildo
        AND id_estacion IN (SELECT id_estacion FROM {{ ref('silver_estaciones_agrocabildo') }})
),

lecturas_con_umbrales AS (
    SELECT
        id_estacion,
        id_sensor,
        "timestamp",
        valor_raw,
        es_validado,
        
        -- 3. Manejo de Valores Extremos: Capado / Winsorizacion por limites de seguridad fisica
        CASE 
            -- Si el valor es negativo invalido para magnitudes absolutas
            WHEN valor_raw < -50 THEN NULL
            WHEN valor_raw > 1500 THEN NULL
            ELSE valor_raw
        END AS valor_limpio,
        
        -- Flag para identificar si la medicion sufrio ajuste o es valida
        CASE 
            WHEN valor_raw < -50 OR valor_raw > 1500 THEN TRUE 
            ELSE FALSE 
        END AS es_extremo
    FROM lecturas_en_punto
),

sensor_base AS (
    -- Calculamos el sensor mínimo de cada estación, que es el sensor base (Velocidad del viento)
    -- El resto de variables se derivan por offset relativo desde el sensor de viento:
    -- +0=Vel.Viento, +1=Dir.Viento, +2=Temperatura, +3=Humedad, +5=Precipitación, +8=Radiación
    SELECT id_estacion, MIN(id_sensor) AS base_sensor
    FROM {{ source('bronze', 'bronze_clima_horario_agrocabildo') }}
    WHERE id_estacion IN (SELECT id_estacion FROM {{ ref('silver_estaciones_agrocabildo') }})
    GROUP BY id_estacion
)

SELECT 
    l.id_estacion,
    l.id_sensor,
    s.name AS variable_nombre,
    s.unit AS variable_unidad,
    l."timestamp",
    l.valor_limpio,
    l.es_validado,
    l.es_extremo
FROM lecturas_con_umbrales l
JOIN sensor_base sb ON l.id_estacion = sb.id_estacion
LEFT JOIN {{ source('bronze', 'bronze_sensores_meteorologicos') }} s
    ON CASE (l.id_sensor - sb.base_sensor)
        WHEN 0 THEN 13 -- Velocidad del viento
        WHEN 1 THEN 14 -- Dirección del viento
        WHEN 2 THEN 10 -- Temperatura
        WHEN 3 THEN 11 -- Humedad relativa
        WHEN 5 THEN 12 -- Precipitación
        WHEN 8 THEN 15 -- Radiación solar
        ELSE NULL
    END = s.id_weatherdatatype
WHERE l.valor_limpio IS NOT NULL
