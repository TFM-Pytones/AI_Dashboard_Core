{{ config(
    materialized='table',
    tags=['silver', 'booking']
) }}

-- Deduplica reseñas por review_id (hash determinístico del texto — ver
-- booking_scraper.py, _parse_review_card) y descarta cualquier reseña cuyo
-- establishment_id no exista en la capa Silver de establecimientos ya
-- deduplicada (integridad referencial, mismo criterio que valida
-- validate_booking_data.py sobre los datos crudos).
--
-- También parsea review_date (texto libre en español, ej. "21 de julio de
-- 2026") a un DATE real de Postgres — mismo patrón CASE/ILIKE que usa el
-- equipo en silver_istac_municipios_cifras_tenerife.sql, para consistencia
-- de estilo. Si el texto no matchea el patrón esperado, review_date_parsed
-- queda en NULL en vez de fallar toda la consulta.

WITH source_data AS (
    SELECT *
    FROM {{ source('bronze', 'booking_reviews') }}
),

deduplicated AS (
    SELECT DISTINCT ON (review_id) *
    FROM source_data
    ORDER BY review_id
),

valid_establishments AS (
    SELECT establishment_id
    FROM {{ ref('silver_booking_establishments') }}
),

joined AS (
    SELECT r.*
    FROM deduplicated r
    INNER JOIN valid_establishments e
        ON r.establishment_id = e.establishment_id
),

date_parts AS (
    SELECT
        *,
        (regexp_match(review_date, '(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})'))[1] AS day_str,
        (regexp_match(review_date, '(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})'))[2] AS month_str,
        (regexp_match(review_date, '(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})'))[3] AS year_str
    FROM joined
),

date_parsed AS (
    SELECT
        *,
        CASE
            WHEN month_str ILIKE 'enero' THEN 1
            WHEN month_str ILIKE 'febrero' THEN 2
            WHEN month_str ILIKE 'marzo' THEN 3
            WHEN month_str ILIKE 'abril' THEN 4
            WHEN month_str ILIKE 'mayo' THEN 5
            WHEN month_str ILIKE 'junio' THEN 6
            WHEN month_str ILIKE 'julio' THEN 7
            WHEN month_str ILIKE 'agosto' THEN 8
            WHEN month_str ILIKE 'septiembre' THEN 9
            WHEN month_str ILIKE 'octubre' THEN 10
            WHEN month_str ILIKE 'noviembre' THEN 11
            WHEN month_str ILIKE 'diciembre' THEN 12
            ELSE NULL
        END AS month_num
    FROM date_parts
)

SELECT
    review_id,
    establishment_id,
    rating,
    review_text,
    review_date AS review_date_original,
    CASE
        WHEN day_str IS NOT NULL AND month_num IS NOT NULL AND year_str IS NOT NULL
        THEN MAKE_DATE(year_str::INTEGER, month_num, day_str::INTEGER)
        ELSE NULL
    END AS review_date,
    reviewer_country
FROM date_parsed
