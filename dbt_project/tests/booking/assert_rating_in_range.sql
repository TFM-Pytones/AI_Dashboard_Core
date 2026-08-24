-- Test: el rating debe estar dentro del rango válido de Booking (1-10).
-- Convención dbt: este archivo debe devolver CERO filas para que el test pase.
-- Si devuelve filas, esas son las que están MAL (fuera de rango).

SELECT
    review_id,
    establishment_id,
    rating
FROM {{ ref('silver_booking_reviews') }}
WHERE rating < 1 OR rating > 10
