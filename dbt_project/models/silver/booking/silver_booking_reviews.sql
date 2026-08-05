{{ config(
    materialized='table',
    tags=['silver', 'booking']
) }}

-- Deduplica reseñas por review_id (hash determinístico del texto — ver
-- booking_scraper.py, _parse_review_card) y descarta cualquier reseña cuyo
-- establishment_id no exista en la capa Silver de establecimientos ya
-- deduplicada (integridad referencial, mismo criterio que valida
-- validate_booking_data.py sobre los datos crudos).

WITH source_data AS (
    SELECT *
    FROM {{ source('bronze', 'booking_reviews') }}
),

deduplicated AS (
    SELECT DISTINCT ON (review_id) *
    FROM source_data
    ORDER BY review_id, ctid
),

valid_establishments AS (
    SELECT establishment_id
    FROM {{ ref('silver_booking_establishments') }}
)

SELECT
    r.review_id,
    r.establishment_id,
    r.rating,
    r.review_text,
    r.review_date,
    r.reviewer_country
FROM deduplicated r
INNER JOIN valid_establishments e
    ON r.establishment_id = e.establishment_id
