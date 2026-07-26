# Diagnóstico de Validación y Justificación Meteorológica

Este documento reúne el diagnóstico físico y metodológico de los resultados obtenidos tras ejecutar la evaluación completa en los dos niveles (L1 ERA5 Reanálisis vs L2 GFS Forecast Operacional).

---

## 📌 Principio de Validación Genérica

> **Importante:** El código de validación (`run_validation.py`) se mantiene **100% genérico, objetivo e independiente de parches o ajustes ad-hoc por estación**.
> 
> No se aplican correcciones personalizadas (*hacks* de código para estaciones específicas) porque el objetivo del framework es evaluar objetivamente la calidad bruta de los modelos NWP operacionales en cualquier ubicación futura. Las discrepancias observadas se justifican científica y físicamente en la memoria del TFM.

---

## 🔍 Análisis Diagnóstico de Resultados

### 1. Barrera Topográfica del Teide (Viento - WSP/WDR)
Se observa un incremento del error ($\Delta$ MAE) en la velocidad y dirección del viento entre ERA5 (L1) y GFS Forecast (L2), especialmente en zonas con marcada orografía como La Orotava y Tejina.
- **Explicación Física:** La malla del modelo global GFS (~25 km) no logra resolver la canalización microclimática de los vientos alisios que provoca el relieve volcánico. El modelo suaviza los picos de viento localizados y desvía la dirección predominante.

### 2. Capa de Inversión y "Mar de Nubes" (Humedad - HUM)
Los errores en humedad oscilan entre el 10% y el 17%.
- **Explicación Física:** La inversión térmica que genera el mar de nubes en la fachada norte de Tenerife es un fenómeno estratificado a altitudes medias (800-1500 m). El modelo de pronóstico global tiene dificultades para predecir con exactitud la cota exacta de la base y tope de la capa de nubes, produciendo desviaciones bruscas en las estaciones situadas a esa altitud.

### 3. Naturaleza Intermitente y Asimétrica (Lluvia - RAIN)
El coeficiente $R^2$ para la precipitación es frecuentemente muy bajo o negativo.
- **Explicación Matemática:** $R^2$ asume comportamientos continuos lineales. En Canarias la precipitación ocurre en episodios breves, intensos o intermitentes. Pequeños desfases temporales (p. ej. predecir lluvia 1 hora antes o después) penalizan severamente $R^2$ y RMSE a pesar de que el modelo haya previsto correctamente la ocurrencia del evento.

### 4. Sesgo Altitudinal por Suavizado de Topografía (Vilaflor - TEMP)
La estación de Vilaflor (1258 m) presenta un sesgo (bias) apreciable en temperatura.
- **Explicación Física:** Los modelos globales asumen una cota topográfica promediada para cada celda de la rejilla. Al promediar zonas de valle y cumbre, la rejilla del modelo sitúa la cota virtual por debajo de los 1258 m reales de Vilaflor. Debido al gradiente térmico vertical ($\approx -0.65 \, ^\circ\text{C} / 100\,\text{m}$), el modelo estima la temperatura a una altitud más baja (más cálida de lo real).

---

## 📊 Conclusiones para la Defensa del TFM

1. **Validez de los Resultados:** Los resultados son meteorológicamente consistentes y demuestran la limitación inherente de utilizar modelos globales (GFS/ERA5) en microclimas insulares complejos.
2. **Justificación sin Manipulación:** Demostrar ante un tribunal de TFM que el modelo falla en variables microclimáticas (viento/humedad en laderas) refuerza la solidez metodológica de la investigación, ya que no se alteran artificialmente los datos de validación.
