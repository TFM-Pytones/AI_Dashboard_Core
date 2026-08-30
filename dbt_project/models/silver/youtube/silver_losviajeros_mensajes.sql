{{ config(materialized='table', tags=['silver', 'nlp', 'foro']) }}

/*
  Modelo Silver: silver_losviajeros_mensajes
  Contiene 1 fila por mensaje del foro. 
  Generado específicamente para alimentar el pipeline de NLP (BERTopic / PyABSA).
*/

WITH mensajes AS (
    SELECT
        id_mensaje,
        id_tema,
        fecha_mensaje::date  AS fecha_mensaje,
        autor,
        texto,
        LENGTH(texto)        AS longitud_texto,
        CASE 
            WHEN fecha_mensaje::date BETWEEN '2020-03-14' AND '2021-12-31' THEN TRUE 
            ELSE FALSE 
        END AS periodo_covid
    FROM {{ source('bronze', 'losviajeros_mensajes') }}
    WHERE id_mensaje IS NOT NULL
      AND texto IS NOT NULL
      AND TRIM(texto) != ''
)

SELECT * FROM mensajes
