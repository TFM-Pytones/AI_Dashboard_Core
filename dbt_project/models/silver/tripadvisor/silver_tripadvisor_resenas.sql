{{ config(
    materialized='table',
    tags=['silver', 'nlp', 'tripadvisor'],
    indexes=[
      {'columns': ['location_id']},
      {'columns': ['fecha_publicacion']}
    ]
) }}

/*
  Modelo Silver: silver_tripadvisor_resenas
  Reseñas de TripAdvisor limpias y con flag de periodo COVID.
  Tabla de referencia para NLP (Squad A): sentimiento y aspectos.
  Se une con silver_tripadvisor_ubicaciones por location_id para
  obtener coordenadas y hacer el cruce con la malla H3.
*/

WITH source_data AS (
    SELECT
        resena_raw::jsonb AS resena_raw,
        location_id
    FROM {{ source('bronze', 'bronze_tripadvisor_resenas') }}
),
raw_data AS (
    SELECT
        resena_raw->>'id' AS review_id,
        location_id,
        (resena_raw->>'rating')::numeric AS rating,
        COALESCE(
            jsonb_path_query_first(resena_raw->'title', '$[*] ? (@.language == "es").value') #>> '{}',
            jsonb_path_query_first(resena_raw->'title', '$[*] ? (@.primary == true).value') #>> '{}',
            resena_raw->'title'->0->>'value'
        ) AS titulo,
        COALESCE(
            jsonb_path_query_first(resena_raw->'text', '$[*] ? (@.language == "es").value') #>> '{}',
            jsonb_path_query_first(resena_raw->'text', '$[*] ? (@.primary == true).value') #>> '{}',
            resena_raw->'text'->0->>'value'
        ) AS texto,
        (resena_raw->>'publish_ts')::date AS fecha_publicacion,
        CASE 
            WHEN length(resena_raw->>'travel_date') = 7 THEN (resena_raw->>'travel_date' || '-01')::date
            ELSE (resena_raw->>'travel_date')::date 
        END AS fecha_viaje,
        resena_raw->>'trip_type' AS tipo_viaje,
        resena_raw->'user'->>'username' AS usuario
    FROM source_data
)

SELECT
    review_id,
    location_id,
    rating,
    titulo,
    texto,
    fecha_publicacion,
    fecha_viaje,
    tipo_viaje,
    usuario,
    LENGTH(TRIM(COALESCE(texto, ''))) AS longitud_texto,
    CASE
        WHEN EXTRACT(YEAR FROM fecha_publicacion) BETWEEN 2020 AND 2021 THEN TRUE
        ELSE FALSE
    END AS periodo_covid
FROM raw_data
WHERE review_id IS NOT NULL  AND texto IS NOT NULL
  AND LENGTH(TRIM(texto)) > 15
  AND EXTRACT(YEAR FROM fecha_publicacion) >= 2022
