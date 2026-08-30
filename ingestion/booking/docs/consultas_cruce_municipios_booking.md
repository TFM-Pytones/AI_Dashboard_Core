
Consultas SQL — Análisis exploratorio de datos de Booking (geográfico y temporal)
**Fecha:** 23 de agosto de 2026
**Contexto:** Consultas de análisis exploratorio sobre los datos scrapeados de Booking.com en la capa Silver — distribución geográfica (cruce con municipios de Tenerife) y distribución temporal (año/mes) de las reseñas.

## Notas técnicas importantes

- `silver.silver_booking_establishments` guarda `latitude`/`longitude` en **WGS84 (EPSG:4326)** — el estándar GPS, resultado de la geocodificación con Nominatim.
- `limites_municipales.geometry` está en **UTM zona 28N (EPSG:32628)** — el estándar del proyecto para Canarias, confirmado con `ST_SRID(geometry)`.
- Por eso es necesario `ST_Transform()` antes de comparar ambas geometrías con `ST_Contains()` — sin la conversión, la comparación fallaría o no encontraría coincidencias, ya que ambos sistemas usan escalas de números distintas para representar la misma ubicación física.
- `limites_municipales` mezcla varios niveles geográficos en la misma tabla (columna `granularidad`) — se filtra explícitamente por `granularidad = 'MUNICIPIOS'` para evitar cruces contra otros niveles (isla, comarca, provincia).

---

## 1. Cruce individual: cada establecimiento con su municipio

Devuelve una fila por establecimiento, indicando en qué municipio cae según sus coordenadas.

```sql
SELECT
    e.establishment_id,
    e.name,
    m.etiqueta AS municipio
FROM silver.silver_booking_establishments e
JOIN limites_municipales m
    ON ST_Contains(
        m.geometry,
        ST_Transform(ST_SetSRID(ST_MakePoint(e.longitude, e.latitude), 4326), 32628)
    )
WHERE e.latitude IS NOT NULL
  AND m.granularidad = 'MUNICIPIOS';
```

---

## 2. Conteo agregado: cantidad de establecimientos por municipio

Agrupa el resultado anterior, mostrando primero los municipios con más oferta scrapeada.

```sql
SELECT
    m.etiqueta AS municipio,
    COUNT(e.establishment_id) AS cantidad_establecimientos
FROM silver.silver_booking_establishments e
JOIN limites_municipales m
    ON ST_Contains(
        m.geometry,
        ST_Transform(ST_SetSRID(ST_MakePoint(e.longitude, e.latitude), 4326), 32628)
    )
WHERE e.latitude IS NOT NULL
  AND m.granularidad = 'MUNICIPIOS'
GROUP BY m.etiqueta
ORDER BY cantidad_establecimientos DESC;
```

### Variante: incluir municipios con 0 establecimientos

Útil para identificar zonas sin oferta scrapeada visible en el dataset actual.

```sql
SELECT
    m.etiqueta AS municipio,
    COUNT(e.establishment_id) AS cantidad_establecimientos
FROM silver.limites_municipales m
LEFT JOIN silver.silver_booking_establishments e
    ON ST_Contains(
        m.geometry,
        ST_Transform(ST_SetSRID(ST_MakePoint(e.longitude, e.latitude), 4326), 32628)
    )
    AND e.latitude IS NOT NULL
WHERE m.granularidad = 'MUNICIPIOS'
GROUP BY m.etiqueta
ORDER BY cantidad_establecimientos DESC;
```

---

## 3. Distribución de reseñas por año

```sql
SELECT
    EXTRACT(YEAR FROM review_date) AS anio,
    COUNT(*) AS cantidad
FROM silver.silver_booking_reviews
WHERE review_date IS NOT NULL
GROUP BY EXTRACT(YEAR FROM review_date)
ORDER BY anio;
```

### Variante: incluyendo reseñas sin fecha parseada

```sql
SELECT
    COALESCE(EXTRACT(YEAR FROM review_date)::TEXT, 'SIN FECHA') AS anio,
    COUNT(*) AS cantidad
FROM silver.silver_booking_reviews
GROUP BY COALESCE(EXTRACT(YEAR FROM review_date)::TEXT, 'SIN FECHA')
ORDER BY anio;
```

---

## 4. Distribución de reseñas por año y mes

```sql
SELECT
    COALESCE(TO_CHAR(review_date, 'YYYY-MM'), 'SIN FECHA') AS anio_mes,
    COUNT(*) AS cantidad
FROM silver.silver_booking_reviews
GROUP BY COALESCE(TO_CHAR(review_date, 'YYYY-MM'), 'SIN FECHA')
ORDER BY anio_mes;
```

**Nota**: se usa `TO_CHAR(review_date, 'YYYY-MM')` en vez de columnas separadas de año y mes — esto ordena correctamente de forma cronológica al hacer `ORDER BY` (formato texto `"2026-07"` ordena bien como string), evitando el problema de que el mes como número de texto suelto (`"10"` antes que `"2"`) rompa el orden cronológico dentro de cada año.



Establecimientos con `latitude`/`longitude` nulos (geocodificación fallida — ver limitaciones documentadas del scraper) quedan excluidos de ambas consultas por el filtro `WHERE e.latitude IS NOT NULL`. No afecta el análisis de distribución relativa entre municipios, pero implica que el total de establecimientos "geolocalizados" es ligeramente menor al total absoluto en `silver_booking_establishments`.
