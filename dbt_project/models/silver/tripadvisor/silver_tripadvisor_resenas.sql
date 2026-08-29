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

SELECT
    review_id,
    location_id,
    rating,
    titulo,
    texto,
    fecha_publicacion::date AS fecha_publicacion,
    fecha_viaje,
    tipo_viaje,
    usuario,
    LENGTH(TRIM(COALESCE(texto, ''))) AS longitud_texto,
    CASE
        WHEN EXTRACT(YEAR FROM fecha_publicacion) BETWEEN 2020 AND 2021 THEN TRUE
        ELSE FALSE
    END AS periodo_covid
FROM {{ source('bronze', 'tripadvisor_resenas') }}
WHERE review_id IS NOT NULL
  AND texto IS NOT NULL
  AND LENGTH(TRIM(texto)) > 15
