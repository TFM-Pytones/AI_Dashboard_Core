{{ config(materialized='table', tags=['silver', 'nlp', 'foro']) }}

/*
  Modelo Silver: silver_losviajeros_mensajes
  Contiene 1 fila por mensaje del foro.
  Columnas reales en bronze: tema_id, tema_titulo, mensaje_id, url, contexto_pagina_raw, fetched_at

  Limpieza de 'i'/'I' turcas (i sin punto / I con punto): caso aislado de
  mojibake detectado en 1 de 12.950 mensajes (byte guardado con la
  codificacion Windows-1254 en vez de Windows-1252).
*/

WITH mensajes AS (
    SELECT
        mensaje_id,
        tema_id,
        tema_titulo,
        fetched_at::date        AS fecha_mensaje,
        REPLACE(REPLACE(contexto_pagina_raw, 'ı', 'i'), 'İ', 'I') AS texto,
        LENGTH(contexto_pagina_raw) AS longitud_texto,
        CASE
            WHEN fetched_at::date BETWEEN '2020-03-14' AND '2021-12-31' THEN TRUE
            ELSE FALSE
        END AS periodo_covid
    FROM {{ source('bronze', 'bronze_losviajeros_mensajes') }}
    WHERE mensaje_id IS NOT NULL
      AND contexto_pagina_raw IS NOT NULL
      AND TRIM(contexto_pagina_raw) != ''
      AND fetched_at::date >= '2022-01-01'
)

SELECT * FROM mensajes
