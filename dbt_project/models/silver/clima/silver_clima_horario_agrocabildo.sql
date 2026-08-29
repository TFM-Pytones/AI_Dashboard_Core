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
    FROM {{ source('bronze', 'clima_horario_agrocabildo') }}
    WHERE 
        -- 1. Filtrar solo horas en punto (00 min 00 seg)
        date_trunc('hour', "timestamp") = "timestamp"
        -- 2. Eliminar nulos y codigos de error tipicos de sensores
        AND COALESCE(valor_validado, valor_observado) IS NOT NULL
        AND COALESCE(valor_validado, valor_observado) NOT IN (-999, -9999, -99, 999, 9999)
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
)

SELECT 
    l.id_estacion,
    l.id_sensor,
    s.sensor_nombre AS variable_nombre,
    s.sensor_unidad AS variable_unidad,
    l."timestamp",
    l.valor_limpio,
    l.es_validado,
    l.es_extremo
FROM lecturas_con_umbrales l
LEFT JOIN {{ source('bronze', 'sensores_meteorologicos') }} s 
    ON l.id_sensor = s.sensor_id
WHERE l.valor_limpio IS NOT NULL
