{{ config(materialized='table', tags=['silver', 'nlp', 'foro']) }}

/*
  Modelo Silver: silver_losviajeros
  Limpieza del foro LosViajeros.com.
  Agrega temas con sus mensajes filtrando textos vacíos.
  Calcula métricas de actividad del tema.
*/

WITH temas AS (
    SELECT
        id_tema,
        titulo_tema,
        subforo,
        fecha_inicio::date  AS fecha_inicio,
        num_respuestas,
        num_visitas,
        autor_tema
    FROM {{ source('bronze', 'losviajeros_temas') }}
    WHERE id_tema IS NOT NULL
),

mensajes AS (
    SELECT
        id_mensaje,
        id_tema,
        fecha_mensaje::date  AS fecha_mensaje,
        autor,
        texto,
        LENGTH(texto)        AS longitud_texto
    FROM {{ source('bronze', 'losviajeros_mensajes') }}
    WHERE id_mensaje IS NOT NULL
      AND texto IS NOT NULL
      AND TRIM(texto) != ''
)

SELECT
    t.id_tema,
    t.titulo_tema,
    t.subforo,
    t.fecha_inicio,
    t.num_respuestas,
    t.num_visitas,
    COUNT(m.id_mensaje)                          AS mensajes_validos,
    ROUND(AVG(m.longitud_texto)::numeric, 1)     AS longitud_media_mensaje,
    MIN(m.fecha_mensaje)                          AS primera_respuesta,
    MAX(m.fecha_mensaje)                          AS ultima_respuesta
FROM temas t
LEFT JOIN mensajes m ON t.id_tema = m.id_tema
GROUP BY
    t.id_tema, t.titulo_tema, t.subforo, t.fecha_inicio,
    t.num_respuestas, t.num_visitas
