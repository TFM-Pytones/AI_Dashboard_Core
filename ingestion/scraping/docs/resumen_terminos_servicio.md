
**Fecha de revisión:** 18 de julio de 2026

## Contexto

Como continuación al análisis de los archivos `robots.txt` de ambas plataformas, se revisaron sus Términos de Servicio vigentes con el fin de completar la evaluación de riesgos legales y éticos asociados al desarrollo del scraper de reseñas turísticas.

---

## TripAdvisor — Términos de Uso

**Fuente:** Términos de Uso de TripAdvisor (sección "Prohibited Activities")

Los Términos de Uso de TripAdvisor prohíben explícitamente:

- Acceder, monitorear, reproducir o copiar cualquier contenido del sitio mediante robots, spiders, scrapers u otros medios automatizados sin permiso expreso por escrito de la plataforma.
- Violar las restricciones declaradas en los "robot exclusion headers" (es decir, el archivo `robots.txt`) o eludir otras medidas empleadas para prevenir o limitar el acceso al sitio.
- Imponer una carga irrazonable o desproporcionadamente grande sobre la infraestructura del sitio.

**Observación relevante:** los términos vinculan explícitamente el cumplimiento del `robots.txt` con las obligaciones contractuales del usuario, reforzando la importancia de las decisiones metodológicas ya documentadas en el análisis previo de dicho archivo.

---

## Booking.com — Términos de Servicio (Sección A14, Intellectual Property Rights)

**Fuente:** Customer Terms of Service de Booking.com, sección A14

Los términos vigentes de Booking.com establecen:

- No está permitido monitorear, copiar, hacer scraping/crawling, descargar, reproducir o usar de cualquier otra forma contenido de la plataforma **con fines comerciales**, sin permiso escrito de Booking.com o sus licenciantes.
- Booking.com declara vigilar activamente cada visita a su plataforma y bloquear a cualquier persona o sistema automatizado que sospeche esté realizando un volumen irrazonable de búsquedas, utilizando software para recopilar precios u otra información, o generando una carga indebida sobre la infraestructura del sitio.

**Observación relevante:** a diferencia de TripAdvisor, la redacción de Booking.com condiciona la restricción principal a un uso "con fines comerciales". Dado que el presente proyecto tiene finalidad exclusivamente académica y de investigación (TFM), sin fines de lucro ni republicación del contenido extraído, esto representa un matiz relevante a considerar—si bien no constituye una autorización expresa para scrapear la plataforma.

---

## Consideraciones legales generales

- El incumplimiento de un Términos de Servicio se interpreta generalmente como un asunto de naturaleza civil (incumplimiento contractual), no penal, si bien esto varía según la jurisdicción aplicable.
- La extracción de datos públicamente accesibles (sin necesidad de autenticación) tiende a considerarse lícita en diversas jurisdicciones, de forma independiente a la validez contractual del Términos de Servicio.
- El incumplimiento del Términos de Servicio, con independencia de su calificación legal, habilita a la plataforma a bloquear direcciones IP, revocar accesos o iniciar acciones legales de naturaleza civil.

## Decisiones metodológicas derivadas

1. El scraping se limitará estrictamente a **fines de investigación académica interna** (análisis de sentimiento, generación de insights agregados para el dashboard), sin republicación del contenido original de las reseñas.
2. **No se recopilará información personal identificable** de los autores de las reseñas (nombres de usuario, fotos de perfil, ubicación exacta del perfil), limitando la extracción a texto de reseña, puntuación, fecha y establecimiento asociado, en cumplimiento con el RGPD dado el probable origen europeo de una parte de los datos.
3. Se mantendrá un ritmo de extracción conservador (rate limiting) para evitar imponer una carga indebida sobre la infraestructura de ambas plataformas, en línea con lo exigido explícitamente en sus términos.
4. Se documenta el presente análisis, junto con el de los archivos `robots.txt`, como evidencia de la diligencia debida aplicada por el equipo antes del desarrollo técnico del scraper, reconociendo las limitaciones y riesgos identificados como parte de la metodología del TFM.

## Nota metodológica

El presente análisis no constituye asesoramiento legal. Se recomienda que estas consideraciones sean puestas en conocimiento del tutor académico del TFM como parte de la validación de la metodología del proyecto.