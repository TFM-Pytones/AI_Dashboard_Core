{{ config(severity = 'warn') }}

-- Test: review_text no debe quedar vacío (ni solo espacios en blanco).
-- Devuelve las filas que SÍ tienen texto vacío — el test avisa (warn) si hay alguna.
--
-- Bajado a severity=warn: se confirmó que estos casos son legítimos (reseñas
-- donde el viajero dejó una puntuación sin escribir comentario, algo que
-- Booking permite) — no son un error del scraper, ver skill
-- booking-tenerife-scraper.

SELECT
    review_id,
    establishment_id
FROM {{ ref('silver_booking_reviews') }}
WHERE TRIM(review_text) = '' OR review_text IS NULL
