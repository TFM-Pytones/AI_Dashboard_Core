{{ config(materialized='table', tags=['silver', 'nlp', 'youtube']) }}

/*
  Modelo Silver: silver_youtube_comentarios
  Contiene 1 fila por comentario. 
  Generado específicamente para alimentar el pipeline de NLP (BERTopic / PyABSA).
*/

WITH comentarios AS (
    SELECT
        comment_id,
        video_id,
        fecha_comentario::date  AS fecha_comentario,
        autor,
        texto,
        likes                   AS likes_comentario,
        LENGTH(texto)           AS longitud_texto,
        CASE 
            WHEN fecha_comentario::date BETWEEN '2020-03-14' AND '2021-12-31' THEN TRUE 
            ELSE FALSE 
        END AS periodo_covid
    FROM {{ source('bronze', 'youtube_comments') }}
    WHERE comment_id IS NOT NULL
      AND texto IS NOT NULL
      AND TRIM(texto) != ''
)

SELECT * FROM comentarios
