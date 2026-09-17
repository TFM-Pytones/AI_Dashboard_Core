# Módulo de Inferencia LLM (`analytics/llm`)

Este módulo implementa la capa de conexión y generación con Modelos de Lenguaje de Gran Escala (**LLM**) para el ecosistema analítico de TUI en Tenerife. Proporciona el cliente base de inferencia acelerada por hardware y el generador automatizado de informes ejecutivos a partir del modelado de tópicos.

---

## 1. Arquitectura y Elección Tecnológica (`llm_client.py`)

Para la generación narrativa y el razonamiento del asistente conversacional, se descartó el aprovisionamiento de GPUs dedicadas en Azure (cuyo coste operativo superaba los 900 USD/mes para uso intermitente) y la ejecución local en Ollama (dependiente del encendido permanente de la máquina virtual del proyecto).

En su lugar, se seleccionó la **API Cloud de Groq**, sustentada en procesadores **LPU (Language Processing Unit)**:
* **Rendimiento de Inferencia:** Velocidad de generación superior a **250 tokens/segundo**, reduciendo la latencia de respuesta de decenas de segundos a menos de 1,5 segundos.
* **Modelo Principal:** `openai/gpt-oss-120b` (sustituye al modelo original `llama-3.1-70b-versatile` tras su depreciación en el catálogo de Groq, validado empíricamente contra `client.models.list()`). Modelo de respaldo (*fallback*): `llama-3.3-70b-versatile`.
* **Manejo de Tokens de Razonamiento:** Dado que `openai/gpt-oss-120b` emplea presupuesto interno para cadenas de pensamiento (*thinking tokens*) antes de emitir la salida visible, los límites de `max_tokens` están calibrados estrictamente en cada tarea (`max_tokens=150` para clasificación booleana/enrutamiento en router, `max_tokens=1000` para Text-to-SQL, y `max_tokens=1200` para redacción ejecutiva), evitando respuestas truncadas.
* **Temperatura Operativa:** Fijada en $T = 0,4$ para redacción ejecutiva (balance entre riqueza léxica y consistencia factual) y $T = 0,0$ para enrutamiento y generación de consultas SQL (determinismo absoluto).

---

## 2. Generador de Informes Ejecutivos (`report_generator.py`)

Convierte las distribuciones de tópicos derivadas de **BERTopic** en síntesis ejecutivas estructuradas de **tres párrafos**, almacenándolas con trazabilidad completa en la base de datos PostgreSQL.

### 2.1. Ámbitos de Análisis (`--ambito`)

El generador unifica la extracción de informes en dos perspectivas analíticas complementarias:

1. **Ámbito General (`--ambito general`):**
   * **Modelo Base:** Modelo A de BERTopic ($k=20$).
   * **Corpus:** Comentarios de YouTube (filtrados con `published_at >= '2022-01-01'` mediante `LEFT JOIN` a `bronze.bronze_youtube_comments`) combinados con mensajes del foro LosViajeros sin geolocalización detectada.
   * **Foco:** Percepción insular de marca, impacto de la masificación, colapso de carreteras insulares (TF-5 y TF-1) y accesibilidad a espacios protegidos (Teide, Anaga, Masca).

2. **Ámbito Alojamiento (`--ambito alojamiento`):**
   * **Modelo Base:** Modelo B de BERTopic ($k=50$).
   * **Corpus:** >38.000 reseñas georreferenciadas de Booking.com, TripAdvisor y foros comunitarios.
   * **Foco:** Calidad de servicio hotelero y extrahotelero, confort acústico, climatización, instalaciones y discrepancias precio-calidad.

### 2.2. Estructura Narrativa del Informe

El prompt exige al LLM actuar bajo el rol de *Analista Senior de Turismo Sostenible de TUI* y estructurar el informe en tres bloques clave:
1. **Percepción General:** Diagnóstico global del destino o de la planta alojativa.
2. **Fricciones y Puntos Críticos:** Identificación de problemas recurrentes reportados por los viajeros.
3. **Oportunidades Estratégicas para TUI:** Recomendaciones accionables de mitigación, redistribución de flujos y diferenciación de producto.

### 2.3. Persistencia en Capa Gold (`gold.nlp_informe_global`)

Cada informe ejecutado se persiste en la tabla analítica con el siguiente esquema:
* `id`: Identificador autoincremental único.
* `model_name`: Identificador del modelo BERTopic utilizado.
* `ambito`: Ámbito analizado (`general` o `alojamiento`).
* `prompt_utilizado`: Texto exacto del prompt inyectado.
* `informe_texto`: Contenido textual del informe generado por el LLM.
* `parametros`: Diccionario JSON con los parámetros de ejecución (fecha mínima, número de tópicos, volumen analizado).
* `fecha_generacion`: Timestamp UTC de generación.

---

## 3. Guía de Ejecución

```bash
# Generar informe de percepción general de marca y destino (Modelo A, post-2022)
python analytics/llm/report_generator.py --ambito general

# Generar informe de experiencia y calidad alojativa (Modelo B, >38k reseñas)
python analytics/llm/report_generator.py --ambito alojamiento
```
