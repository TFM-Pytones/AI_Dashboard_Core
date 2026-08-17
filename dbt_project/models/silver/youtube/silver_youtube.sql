{{ config(materialized='table', tags=['silver', 'nlp', 'youtube']) }}

/*
  Modelo Silver: silver_youtube
  Agrega videos + comentarios limpiando textos vacíos.
  Calcula ratio de engagement y longitud media de comentarios.
*/

WITH videos AS (
    SELECT
        video_id,
        titulo,
        canal,
        fecha_publicacion::date   AS fecha_publicacion,
        duracion_segundos,
        visualizaciones,
        likes,
        num_comentarios,
        CASE 
            WHEN visualizaciones > 0 
            THEN ROUND(CAST((likes + num_comentarios)::numeric / visualizaciones * 100, 4))
            ELSE NULL
        END AS engagement_pct,
        descripcion,
        tags
    FROM {{ source('bronze', 'youtube_videos') }}
    WHERE video_id IS NOT NULL
      AND fecha_publicacion IS NOT NULL
),

comentarios AS (
    SELECT
        comment_id,
        video_id,
        fecha_comentario::date  AS fecha_comentario,
        autor,
        texto,
        likes                   AS likes_comentario,
        LENGTH(texto)           AS longitud_texto
    FROM {{ source('bronze', 'youtube_comments') }}
    WHERE comment_id IS NOT NULL
      AND texto IS NOT NULL
      AND TRIM(texto) != ''
)

SELECT
    v.video_id,
    v.titulo,
    v.canal,
    v.fecha_publicacion,
    v.visualizaciones,
    v.likes,
    v.num_comentarios,
    v.engagement_pct,
    COUNT(c.comment_id)                     AS comentarios_validos,
    ROUND(AVG(c.longitud_texto)::numeric, 1) AS longitud_media_comentario
FROM videos v
LEFT JOIN comentarios c ON v.video_id = c.video_id
GROUP BY
    v.video_id, v.titulo, v.canal, v.fecha_publicacion,
    v.visualizaciones, v.likes, v.num_comentarios, v.engagement_pct
