# Extracción y Normalización de Aspectos (PyABSA + Traducción Híbrida)

Este módulo gestiona el análisis de sentimiento basado en aspectos (**ABSA - Aspect-Based Sentiment Analysis**) y la normalización lingüística multilingüe de opiniones turísticas en Tenerife.

---

## Estructura del Módulo

```
analytics/aspects/
├── batch_inference.py       # Inferencia por lotes con PyABSA ATEPC (multilingüe)
├── traducir_aspectos.py     # Traducción incremental híbrida a español (Google + MyMemory)
└── setup_test.py            # Verificación de dependencias (PyABSA, torch, CUDA)
```

---

## 1. Inferencia de Aspectos (`batch_inference.py`)

Aísla las menciones concretas de aspectos de interés (limpieza, servicio, ubicación, comida, etc.) y su sentimiento asociado (positivo, neutro, negativo).

### Parámetros de ejecución:
```bash
# Procesar todas las fuentes (Booking, TripAdvisor, YouTube)
python analytics/aspects/batch_inference.py --source todas

# Procesar fuentes específicas
python analytics/aspects/batch_inference.py --source booking
python analytics/aspects/batch_inference.py --source tripadvisor
python analytics/aspects/batch_inference.py --source youtube
```

* **Modelo**: Checkpoint multilingüe de PyABSA ATEPC.
* **Destino**: `gold.nlp_aspectos_resenas` (para reseñas) y `silver.aspect_results` (para comentarios de YouTube).

---

## 2. Traducción y Normalización de Aspectos (`traducir_aspectos.py`)

Dado que las reseñas de turistas provienen de múltiples nacionalidades (inglés, alemán, francés, italiano, español), los aspectos extraídos por PyABSA quedan en el idioma original del texto (ej. `"location"`, `"posizione"`, `"lage"`, `"ubicación"`).

Este script traduce y normaliza de forma incremental los aspectos a español canónico y los almacena en `gold.aspecto_traducciones`.

### Características:
- **Estrategia Híbrida**: Intenta primero Google Translate (`deep-translator`), con fallback a MyMemory Translator con detección automática de idioma (`langdetect`).
- **Incremental**: Consulta únicamente los términos de `gold.nlp_aspectos_resenas` que aún no existen en `gold.aspecto_traducciones`.
- **Priorización por frecuencia**: Procesa primero los aspectos con mayor volumen de menciones.
- **Tolerancia a fallos**: Inserciones seguras (`ON CONFLICT DO UPDATE`) en lotes (`batch-size 20`).

### Uso:
```bash
# Traducción incremental de todos los términos pendientes
python analytics/aspects/traducir_aspectos.py

# Limitar a los N términos más frecuentes
python analytics/aspects/traducir_aspectos.py --limit 500

# Simulación en memoria (dry-run)
python analytics/aspects/traducir_aspectos.py --limit 50 --dry-run
```

---

## 3. Integración con la Malla H3 y dbt

La tabla `gold.aspecto_traducciones` es consumida por el modelo dbt:
- **`gold.gold_sentimiento_h3`**: Calcula la `queja_principal` (moda de los aspectos normalizados) en cada celda hexagonal H3 (`silver.silver_h3_grid`).

---

## 4. Histórico y Proporción Académica

Los cuadernos de investigación y desarrollo exploratorio originales se encuentran archivados en:
- `notebooks/tarea2/nlp_aspectos_tarea_2_2.ipynb`
- `notebooks/tarea2/traducir_aspectos.ipynb`
- `notebooks/tarea2/traducir_aspectos_hibrido.ipynb`
