# Limitación metodológica: orden por relevancia en el scraping profundo

**Fecha de decisión:** 20 de agosto de 2026
**Contexto:** `booking_scraper_deep.py` — segunda pasada para estudiar estacionalidad

## Decisión tomada

Para establecimientos con más de 50 reseñas totales en Booking, se amplía el límite de extracción de 30 a 200 reseñas, **sin modificar el orden por defecto** ("Más relevantes primero", el algoritmo propio de Booking).

## Por qué esto es una limitación, no una elección neutral

El orden "más relevantes" **no es cronológico** — combina factores no documentados públicamente por Booking (utilidad percibida, completitud de la reseña, probablemente algo de recencia). Esto significa que las 200 reseñas obtenidas:

- No están garantizadas a distribuirse de forma pareja a lo largo de todos los años de actividad del establecimiento
- Podrían seguir concentradas en períodos recientes, si el algoritmo de Booking pondera recencia como parte de la "relevancia"
- No permiten, por sí solas, un análisis de estacionalidad mes-a-mes completamente confiable y uniforme

## Por qué se decidió así de todas formas

- Cambiar el orden a "más antiguas primero" requiere localizar e interactuar con un dropdown adicional, aumentando la complejidad del scraper
- Aun ordenando por antigüedad, 200 reseñas de un establecimiento con miles de reseñas totales seguirían siendo una muestra parcial (probablemente solo los primeros 1-2 años de actividad), no necesariamente mejor para estacionalidad que el orden por relevancia
- Se prioriza obtener un volumen mayor de datos ahora, con la posibilidad de revisar la estrategia si el análisis exploratorio revela que la distribución temporal resultante no es útil

## Plan de contingencia

Una vez scrapeadas las 200 reseñas por establecimiento, correr la consulta de distribución por año/mes (ver ejemplo abajo) sobre los establecimientos con `total_reviews > 50`. Si la distribución resulta demasiado concentrada en 1-2 años, evaluar:
1. Implementar el cambio de orden a "más antiguas primero" como mejora futura
2. Combinar ambos órdenes (una pasada con cada uno) para los establecimientos más grandes, sumando cobertura

```sql
SELECT
    e.establishment_id,
    TO_CHAR(r.review_date, 'YYYY-MM') AS anio_mes,
    COUNT(*) AS cantidad
FROM silver.silver_booking_reviews r
JOIN silver.silver_booking_establishments e ON r.establishment_id = e.establishment_id
WHERE e.establishment_id IN (
    -- establecimientos que pasaron por el scraping profundo
    SELECT establishment_id FROM silver.silver_booking_establishments
    -- (filtrar según corresponda una vez identificados)
)
GROUP BY e.establishment_id, TO_CHAR(r.review_date, 'YYYY-MM')
ORDER BY e.establishment_id, anio_mes;
```
