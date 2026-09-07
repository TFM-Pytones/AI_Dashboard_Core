{{ config(materialized='table', tags=['silver', 'nlp', 'youtube']) }}

/*
  Modelo Silver: silver_youtube
  Agrega videos + comentarios limpiando textos vacíos.
  Columnas reales en bronze_youtube_videos: video_id, search_term, title, channel_title, published_at, view_count, fetched_at
  Columnas reales en bronze_youtube_comments: comment_id, video_id, author, text, like_count, published_at, fetched_at
*/

WITH videos AS (
    SELECT
        video_id,
        title           AS titulo,
        channel_title   AS canal,
        search_term,
        published_at::date      AS fecha_publicacion,
        view_count              AS visualizaciones
    FROM {{ source('bronze', 'bronze_youtube_videos') }}
    WHERE video_id IS NOT NULL
      AND published_at IS NOT NULL
      AND EXTRACT(YEAR FROM published_at) >= 2022
),

comentarios AS (
    SELECT
        comment_id,
        video_id,
        published_at::date  AS fecha_comentario,
        author              AS autor,
        "text"              AS texto,
        like_count          AS likes_comentario,
        LENGTH("text")      AS longitud_texto
    FROM {{ source('bronze', 'bronze_youtube_comments') }}
    WHERE comment_id IS NOT NULL
      AND "text" IS NOT NULL
      AND TRIM("text") != ''
      AND EXTRACT(YEAR FROM published_at) >= 2022
)

SELECT
    v.video_id,
    v.titulo,
    v.canal,
    v.search_term,
    v.fecha_publicacion,
    v.visualizaciones,
    COUNT(c.comment_id)                      AS comentarios_validos,
    ROUND(AVG(c.longitud_texto)::numeric, 1) AS longitud_media_comentario
FROM videos v
LEFT JOIN comentarios c ON v.video_id = c.video_id
GROUP BY
    v.video_id, v.titulo, v.canal, v.search_term,
    v.fecha_publicacion, v.visualizaciones
