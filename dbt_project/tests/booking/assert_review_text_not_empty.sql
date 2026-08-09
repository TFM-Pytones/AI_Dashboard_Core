-- Test: review_text no debe quedar vacío (ni solo espacios en blanco).
-- Devuelve las filas que SÍ tienen texto vacío — el test pasa si no hay ninguna.

SELECT
    review_id,
    establishment_id
FROM {{ ref('silver_booking_reviews') }}
WHERE TRIM(review_text) = '' OR review_text IS NULL
