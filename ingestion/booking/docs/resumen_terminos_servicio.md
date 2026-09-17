# Evaluación Ética y Legal: Términos de Servicio de Booking.com

**Fecha de revisión:** 18 de julio de 2026

---

## Contexto

Como continuación al análisis del archivo `robots.txt` de Booking.com, se revisaron sus Términos de Servicio vigentes con el fin de completar la evaluación de riesgos legales y éticos asociados al desarrollo del pipeline de extracción de reseñas de alojamientos para el proyecto de investigación (TFM).

---

## Booking.com — Términos de Servicio (Sección A14, Intellectual Property Rights)

**Fuente:** Customer Terms of Service de Booking.com, sección A14.

Los términos vigentes de Booking.com establecen:

- No está permitido monitorear, copiar, hacer scraping/crawling, descargar, reproducir o usar de cualquier otra forma contenido de la plataforma **con fines comerciales**, sin permiso escrito de Booking.com o sus licenciantes.
- Booking.com declara vigilar activamente cada visita a su plataforma y bloquear a cualquier persona o sistema automatizado que sospeche esté realizando un volumen irrazonable de búsquedas, utilizando software para recopilar precios u otra información, o generando una carga indebida sobre la infraestructura del sitio.

> **Observación relevante:** la redacción de Booking.com condiciona la restricción principal a un uso **"con fines comerciales"**. Dado que el presente proyecto tiene finalidad exclusivamente académica y de investigación (TFM), sin fines de lucro ni republicación del contenido extraído, esto representa un matiz relevante—si bien no constituye una autorización expresa para scrapear la plataforma.

---

## Consideraciones Legales Generales

- El incumplimiento de unos Términos de Servicio se interpreta generalmente como un asunto de naturaleza civil (incumplimiento contractual), no penal, sujeto a la jurisdicción aplicable.
- La extracción de datos públicamente accesibles (sin necesidad de autenticación) tiende a considerarse lícita en diversas jurisdicciones para propósitos de análisis estadístico e investigación.
- El incumplimiento del Términos de Servicio, con independencia de su calificación legal, habilita a la plataforma a bloquear direcciones IP o revocar accesos.

---

## Decisiones Metodológicas Derivadas

1. **Finalidad Académica Estricta**: El scraping se limitará estrictamente a fines de investigación académica interna (análisis de sentimiento, modelado temático y métricas para el dashboard de TFM), sin explotación ni republicación comercial del contenido.
2. **Protección de Datos Personales (Zero PII)**: En cumplimiento estricto con el RGPD, no se recopila información personal identificable de los autores de las reseñas (nombres de usuario, fotos de perfil, identificadores personales), extrayendo únicamente el texto de la reseña, puntuación numérica, fecha y establecimiento asociado.
3. **Carga Respetuosa y Rate Limiting**: Se mantuvieron pausas y retardos aleatorios entre peticiones para evitar cualquier sobrecarga de los servidores de la plataforma.
4. **Almacenamiento Seguro**: Los datos crudos se consolidan en Azure PostgreSQL (`bronze.bronze_booking_establishments` y `bronze.bronze_booking_reviews`) y Azure Blob Storage (`bronce-raw/booking/`), garantizando trazabilidad y seguridad.

---

## Nota Metodológica

El presente análisis no constituye asesoramiento legal formal. Se documenta como evidencia de la diligencia debida aplicada por el equipo de investigación previa al desarrollo de los pipelines de ingesta.