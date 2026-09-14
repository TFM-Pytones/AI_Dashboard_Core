# Hallazgo metodológico: proporción de establecimientos sin reseñas en Booking.com

**Fecha de detección:** 15 de agosto de 2026
**Fuente:** Corrida de scraping de Booking.com (issue #12), capa Silver

## Contexto

Durante el desarrollo del scraper se detectó que una proporción no despreciable de los establecimientos turísticos de Tenerife listados en Booking.com **no tienen ninguna reseña de huéspedes todavía**. Inicialmente esto se manifestaba como un error técnico (timeout del scraper al intentar localizar el botón "Leer todos los comentarios", inexistente en estas fichas), lo cual provocaba que el establecimiento se perdiera por completo sin quedar registrado.

Tras corregir el scraper para detectar explícitamente el banner `[data-testid="no-reviews-banner"]` que Booking muestra en estos casos, los establecimientos sin reseñas pasaron a guardarse correctamente (con 0 reseñas asociadas), permitiendo cuantificar el fenómeno por primera vez.

## Datos observados

En una corrida de 96 establecimientos nuevos incorporados el 15 de agosto de 2026 —la primera corrida realizada **después** de corregir el bug de timeout descrito arriba—:

| Categoría | Cantidad | Porcentaje |
|---|---|---|
| Establecimientos con al menos 1 reseña | 28 | ~29% |
| Establecimientos sin ninguna reseña | 68 | ~71% |
| **Total** | **96** | **100%** |

Entre los establecimientos que sí tienen reseñas, el promedio observado fue de **~8.7 reseñas por establecimiento** — cifra consistente con lo observado en corridas anteriores del proyecto, lo que descarta que se trate de un problema de extracción y confirma que el fenómeno es real y propio de los datos de origen.

## Sesgo de selección detectado al contrastar con el dataset acumulado completo

Al calcular la misma proporción sobre el dataset **acumulado completo** (407 establecimientos, sumando todas las corridas desde el inicio del proyecto), el resultado fue notablemente distinto:

| Categoría | Cantidad (acumulado, N=407) | Porcentaje |
|---|---|---|
| Establecimientos con al menos 1 reseña | 339 | ~83% |
| Establecimientos sin ninguna reseña | 68 | ~17% |

**Nota crítica:** el número absoluto de establecimientos "sin reseña" es idéntico (68) en ambas mediciones — es decir, **la totalidad de los establecimientos sin reseñas del dataset provienen exclusivamente de la corrida posterior al arreglo del bug**. Ninguna de las corridas anteriores (que en conjunto representan 311 de los 407 establecimientos) contiene un solo caso de "sin reseñas".

Esto no es casualidad, sino la consecuencia directa del bug ya descrito: antes de su corrección, un establecimiento sin reseñas nunca llegaba a guardarse (el scraper terminaba en timeout y el establecimiento se perdía por completo, sin dejar registro en Bronce). Por lo tanto:

- El **17% acumulado** subestima sistemáticamente la proporción real de alojamientos sin reseñas en Tenerife, porque la mayor parte del dataset (311 de 407 establecimientos) proviene de un período en el que esta categoría era **estructuralmente invisible** para el scraper — no es que hubiera pocos casos, es que ninguno podía registrarse.
- El **~71% observado en la corrida del 15 de agosto** es la estimación más confiable disponible hasta el momento, al ser la primera (y hasta ahora única) corrida que capturó la totalidad de los establecimientos candidatos, sin exclusión sistemática de ningún subgrupo.

Se recomienda, antes de reportar una cifra definitiva en el TFM, recalcular esta proporción exclusivamente sobre corridas posteriores al 15 de agosto de 2026 (fecha de corrección del bug), excluyendo el dataset anterior de la muestra usada para esta estimación específica — aunque ese dataset anterior sigue siendo válido para el resto de los análisis (reseñas, sentimiento, geolocalización) donde este sesgo no aplica.

## Interpretación

Esta alta proporción de establecimientos sin reseñas es consistente con las características típicas de los listados que Booking va incorporando progresivamente a su plataforma:

- Alojamientos particulares (apartamentos, casas) publicados recientemente
- Alojamientos de rotación baja o estacional, con pocos huéspedes hasta la fecha
- Posible sesgo del propio método de descubrimiento del proyecto: a medida que se agotan los candidatos más "evidentes" (grandes hoteles con nombre reconocible en el slug de la URL), el caché de descubrimiento tiende a incorporar progresivamente alojamientos más pequeños y con menor trayectoria en la plataforma — hipótesis pendiente de contrastar con un análisis más detallado por tipo de establecimiento.

## Implicancias para el análisis del proyecto

1. **Segmentación de la oferta turística**: este hallazgo permite distinguir entre "oferta consolidada" (con historial de reseñas, apta para análisis de sentimiento/opinión) y "oferta emergente" (sin reseñas todavía, pero geolocalizable y caracterizable por tipo/ubicación) — una dimensión adicional de interés para el dashboard del proyecto, más allá del análisis de sentimiento propiamente dicho.
2. **Sesgo en el análisis de sentimiento**: cualquier análisis de opiniones/reseñas sobre la oferta turística de Tenerife excluye, por diseño, a este ~71% de establecimientos — debe declararse explícitamente como limitación metodológica en la sección correspondiente del TFM.
3. **Los establecimientos sin reseñas siguen aportando valor**: cuentan con datos completos de nombre, dirección, coordenadas y tipo de establecimiento, útiles para el componente de geolocalización y mapeo de la oferta, aunque no para el componente de sentimiento.

## Nota metodológica

Este hallazgo se detectó y cuantificó de forma incidental, como parte de la depuración de un error técnico del scraper — no fue resultado de un diseño experimental específico para medirlo. El contraste entre la medición de la corrida individual (~71%) y la medición sobre el dataset acumulado completo (~17%) reveló además un **sesgo de selección retrospectivo**: las corridas previas a la corrección del bug excluyeron sistemáticamente, sin dejar rastro, a todos los establecimientos sin reseñas. Cualquier análisis futuro que combine datos de corridas anteriores y posteriores al 15 de agosto de 2026 debe tener en cuenta esta discontinuidad metodológica, particularmente para cualquier estimación relacionada con la proporción de oferta "sin reseñas" en el territorio. Se recomienda una consulta dedicada sobre corridas exclusivamente posteriores a esa fecha, a mayor escala, para confirmar si el ~71% se mantiene estable.
