{{ config(materialized='table', tags=['silver', 'nlp', 'foro']) }}

/*
  Modelo Silver: silver_losviajeros
  Resumen por hilo del foro LosViajeros.com.
  Columnas reales en bronze_losviajeros_temas: tema_id, titulo, url
  Columnas reales en bronze_losviajeros_mensajes: tema_id, tema_titulo, mensaje_id, url, contexto_pagina_raw, fetched_at
*/

WITH temas AS (
    SELECT
        tema_id,
        titulo AS titulo_tema,
        url
    FROM {{ source('bronze', 'bronze_losviajeros_temas') }}
    WHERE tema_id IS NOT NULL
),

mensajes AS (
    SELECT
        tema_id,
        mensaje_id,
        contexto_pagina_raw AS texto,
        fetched_at::date    AS fecha_mensaje,
        LENGTH(contexto_pagina_raw) AS longitud_texto
    FROM {{ source('bronze', 'bronze_losviajeros_mensajes') }}
    WHERE mensaje_id IS NOT NULL
      AND contexto_pagina_raw IS NOT NULL
      AND TRIM(contexto_pagina_raw) != ''
      AND fetched_at::date >= '2022-01-01'
)

SELECT
    t.tema_id,
    t.titulo_tema,
    t.url,
    COUNT(m.mensaje_id)                          AS mensajes_validos,
    ROUND(AVG(m.longitud_texto)::numeric, 1)     AS longitud_media_mensaje,
    MIN(m.fecha_mensaje)                          AS primera_respuesta,
    MAX(m.fecha_mensaje)                          AS ultima_respuesta
FROM temas t
LEFT JOIN mensajes m ON t.tema_id = m.tema_id
GROUP BY t.tema_id, t.titulo_tema, t.url
