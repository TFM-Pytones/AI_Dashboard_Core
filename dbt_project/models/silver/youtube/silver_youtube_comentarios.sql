{{ config(materialized='table', tags=['silver', 'nlp', 'youtube']) }}

/*
  Modelo Silver: silver_youtube_comentarios
  Contiene 1 fila por comentario.
  Columnas reales en bronze: comment_id, video_id, author, text, like_count, published_at, fetched_at
*/

WITH comentarios AS (
    SELECT
        comment_id,
        video_id,
        published_at::date  AS fecha_comentario,
        author              AS autor,
        "text"              AS texto,
        like_count          AS likes_comentario,
        LENGTH("text")      AS longitud_texto,
        CASE
            WHEN published_at::date BETWEEN '2020-03-14' AND '2021-12-31' THEN TRUE
            ELSE FALSE
        END AS periodo_covid
    FROM {{ source('bronze', 'bronze_youtube_comments') }}
    WHERE comment_id IS NOT NULL
      AND "text" IS NOT NULL
      AND TRIM("text") != ''
      AND EXTRACT(YEAR FROM published_at) >= 2022
)

SELECT * FROM comentarios
