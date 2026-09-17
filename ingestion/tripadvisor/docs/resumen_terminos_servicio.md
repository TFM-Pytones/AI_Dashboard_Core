# Evaluación Ética y Legal: Términos de Uso de TripAdvisor

**Fecha de revisión:** 18 de julio de 2026

---

## Contexto

Como continuación al análisis del archivo `robots.txt`, se revisaron los Términos de Servicio vigentes de TripAdvisor con el fin de completar la evaluación de riesgos legales y éticos asociados a la integración y captura de reseñas y valoraciones turísticas para el proyecto de investigación (TFM).

---

## TripAdvisor — Términos de Uso

**Fuente:** Términos de Uso de TripAdvisor (sección *"Prohibited Activities"*).

Los Términos de Uso de TripAdvisor establecen restricciones sobre:
- Acceder, monitorear, reproducir o copiar cualquier contenido del sitio mediante robots, spiders, scrapers u otros medios automatizados sin permiso expreso por escrito de la plataforma.
- Violar las restricciones declaradas en los encabezados de exclusión de robots (es decir, el archivo `robots.txt`) o eludir otras medidas empleadas para prevenir o limitar el acceso al sitio.
- Imponer una carga irrazonable o desproporcionadamente grande sobre la infraestructura del sitio.

> **Observación relevante:** TripAdvisor vincula explícitamente el cumplimiento del `robots.txt` con las condiciones de acceso. En este proyecto, la adquisición principal se canalizó a través de la **API oficial / Terra API**, complementada con prefiltrado espacial estricto (`ST_Contains` en PostGIS) para limitar el volumen a establecimientos verificados de Tenerife sin saturar el servicio.

---

## Consideraciones Legales Generales

- El incumplimiento de unos Términos de Servicio se interpreta generalmente como una cuestión de naturaleza contractual/civil, no penal, sujeta a la jurisdicción aplicable.
- La consulta y agregación de datos públicamente accesibles (sin autenticación de usuarios) para fines estadísticos e investigadores goza de reconocimiento en el ámbito académico.
- En cualquier caso, el uso responsable exige no generar sobrecarga en servidores ni redistribuir contenido comercialmente.

---

## Decisiones Metodológicas Derivadas

1. **Uso de API Oficial y Cuotas Controladas**: La extracción de datos de TripAdvisor se diseñó con un techo máximo conservador (900 llamadas/día) respetando el `Retry-After` de la API.
2. **Filtrado Geoespacial Previo**: Antes de solicitar detalles u opiniones de un establecimiento, se valida en PostGIS que sus coordenadas caigan dentro de la delimitación insular de Tenerife, evitando peticiones innecesarias.
3. **Fines Exclusivamente Académicos (TFM)**: Los datos se emplean únicamente para modelado de tópicos (BERTopic) y análisis de sentimiento agregado, sin republicación comercial.
4. **Protección de Datos Personales (Zero PII)**: No se almacenan identificadores ni perfiles personales de los autores de opiniones.

---

## Nota Metodológica

El presente análisis no constituye asesoramiento legal formal. Estas consideraciones forman parte de la memoria técnica de diligencia debida del TFM para justificar las buenas prácticas de ingeniería de datos.
