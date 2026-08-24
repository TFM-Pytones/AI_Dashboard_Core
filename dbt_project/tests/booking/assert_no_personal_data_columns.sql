-- Test de privacidad: confirma que NO existan columnas de nombre de usuario
-- o autor en la tabla de reseñas (regla del proyecto, ver README de scraping).
-- Consulta el catálogo de Postgres directamente, no los datos en sí.

SELECT column_name
FROM information_schema.columns
WHERE table_schema = 'silver'
  AND table_name = 'silver_booking_reviews'
  AND (
      column_name ILIKE '%username%'
      OR column_name ILIKE '%author%'
      OR column_name ILIKE '%reviewer_name%'
      OR column_name ILIKE '%user_name%'
  )
