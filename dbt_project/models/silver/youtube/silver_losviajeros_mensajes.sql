{{ config(materialized='table', tags=['silver', 'nlp', 'foro']) }}

/*
  Modelo Silver: silver_losviajeros_mensajes
  Contiene 1 fila por mensaje del foro.
  Columnas reales en bronze: tema_id, tema_titulo, mensaje_id, url, contexto_pagina_raw, fetched_at
*/

WITH mensajes AS (
    SELECT
        mensaje_id,
        tema_id,
        tema_titulo,
        fetched_at::date        AS fecha_mensaje,
        contexto_pagina_raw     AS texto,
        LENGTH(contexto_pagina_raw) AS longitud_texto,
        CASE
            WHEN fetched_at::date BETWEEN '2020-03-14' AND '2021-12-31' THEN TRUE
            ELSE FALSE
        END AS periodo_covid
    FROM {{ source('bronze', 'bronze_losviajeros_mensajes') }}
    WHERE mensaje_id IS NOT NULL
      AND contexto_pagina_raw IS NOT NULL
      AND TRIM(contexto_pagina_raw) != ''
)

SELECT * FROM mensajes
