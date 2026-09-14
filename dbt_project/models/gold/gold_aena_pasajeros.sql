{{ config(
    materialized='table',
    tags=['gold', 'movilidad', 'aena'],
    indexes=[
      {'columns': ['periodo']},
      {'columns': ['aeropuerto_codigo']}
    ]
) }}

/*
  Modelo Gold: gold_aena_pasajeros
  Series temporales mensuales de tráfico de pasajeros y operaciones en los dos aeropuertos
  de Tenerife (TFS y TFN). 
  Estandarizado para consultas analíticas de estacionalidad, demanda turística y Text-to-SQL para LLMs.
*/

WITH aena_clean AS (
    SELECT
        periodo,
        anio,
        mes,
        CASE 
            WHEN mes IN (1, 2, 3) THEN 'Q1'
            WHEN mes IN (4, 5, 6) THEN 'Q2'
            WHEN mes IN (7, 8, 9) THEN 'Q3'
            ELSE 'Q4'
        END AS trimestre,
        CASE 
            WHEN mes IN (11, 12, 1, 2, 3, 4) THEN 'Invierno (Temporada Alta)'
            ELSE 'Verano (Temporada Media/Baja)'
        END AS temporada,
        CASE 
            WHEN aeropuerto ILIKE '%SUR%' THEN 'TFS'
            ELSE 'TFN'
        END AS aeropuerto_codigo,
        CASE 
            WHEN aeropuerto ILIKE '%SUR%' THEN 'Tenerife Sur - Reina Sofía'
            ELSE 'Tenerife Norte - Ciudad de La Laguna'
        END AS aeropuerto_nombre,
        CASE 
            WHEN aeropuerto ILIKE '%SUR%' THEN 'Internacional predominante'
            ELSE 'Nacional e Interinsular'
        END AS tipo_trafico_principal,
        pasajeros,
        operaciones,
        ROUND((pasajeros / NULLIF(operaciones, 0))::numeric, 1) AS pasajeros_por_operacion
    FROM {{ ref('silver_aena_pasajeros') }}
)

SELECT
    periodo,
    anio,
    mes,
    trimestre,
    temporada,
    aeropuerto_codigo,
    aeropuerto_nombre,
    tipo_trafico_principal,
    pasajeros,
    operaciones,
    pasajeros_por_operacion
FROM aena_clean
ORDER BY anio DESC, mes DESC, aeropuerto_codigo ASC
