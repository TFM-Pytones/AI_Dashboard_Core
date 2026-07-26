# Módulo de Validación Meteorológica: Satélite (Open-Meteo) vs. Estación (Agrocabildo)

Este directorio contiene el módulo desarrollado para validar la precisión de los datos meteorológicos por satélite y modelos numéricos de predicción de **Open-Meteo** en comparación con los registros reales de las estaciones en tierra de **Agrocabildo** (Cabildo de Tenerife). 

Esta validación es un paso metodológico crítico para el **TFM**, ya que justifica científicamente si es viable (y con qué margen de error) utilizar predicciones futuras de satélite/modelos para alimentar el AI Dashboard de TUI.

---

## 1. Justificación Metodológica: ¿Qué analizamos y por qué?

### A. Selección de las 4 Estaciones de Validación
Tenerife posee una topografía extremadamente compleja con multitud de microclimas debido al gradiente altitudinal (efecto del Teide) y a la influencia de los vientos alisios (norte húmedo vs. sur seco). Para que la validación sea representativa de toda la isla, seleccionamos **4 estaciones estratégicas**:

1. **GALLETAS (ID 2 - 95m, Litoral Sur)**: Representa el clima costero árido del sur. Poca nubosidad y relieve suave. Es la zona donde los modelos de satélite suelen tener menor error.
2. **TEJINA01 (ID 11 - 69m, Litoral Nordeste)**: Representa el clima de la costa norte expuesta directamente a la influencia marítima y el inicio del flujo del alisio.
3. **OROTAV01 (ID 7 - 214m, Valle Norte)**: Representa los valles agrícolas del norte, caracterizados por una alta humedad relativa, nubosidad frecuente ("mar de nubes") e inversión térmica.
4. **VILAFLOR (ID 13 - 1258m, Alta Montaña)**: Estación de gran altitud. Aquí el relieve real difiere enormemente del relieve suavizado que asume el satélite en su cuadrícula (píxel). Es el punto crítico para analizar errores sistemáticos debido a la altitud (efecto *lapse rate*).

### B. El Período Elegido: 2022–2024 (3 Años Completos)
* **¿Por qué 3 años?** Un análisis de menos de un año no capturaría la estacionalidad (comportamiento en inviernos lluviosos vs. veranos secos). Tres años es el estándar estadístico recomendado.
* **¿Por qué este periodo reciente?** Minimiza el riesgo de lagunas de datos debido a problemas históricos de mantenimiento y asegura que comparamos con datos que ya han pasado por los controles automáticos y manuales de validación de calidad de Agrocabildo (`valor_validado`).

### C. Las 6 Variables Clave
Se seleccionaron variables críticas para la agricultura y el turismo que cuentan con sensores homólogos en ambos sistemas:
* **Temperatura (`TEMP`)** en °C.
* **Humedad Relativa (`HUM`)** en %.
* **Precipitación (`RAIN`)** en mm/h.
* **Velocidad del viento (`WSP`)** en m/s.
* **Dirección del viento (`WDR`)** en grados (0-360°).
* **Radiación solar (`RAD`)** en W/m².

---

## 2. Estructura de Validación en Dos Niveles

Una de las aportaciones metodológicas más sólidas es separar la validación en **dos niveles conceptuales**, solucionando el problema de usar datos del pasado frente a predicciones futuras:

```
[Datos Reales Agrocabildo]
       │
       ├─► [Nivel 1: ERA5 Reanálisis]  (Valida sesgo físico y de terreno / cota de error optimista)
       │
       └─► [Nivel 2: Historical Forecast GFS] (Valida la calidad real de predicción operacional)
                 │
                 └─► [Análisis de Degradación (Lead-Time)] (D+1, D+3, D+7)
```

### 1️⃣ Nivel 1: Validación de Sesgo Físico y de Terreno (ERA5 Reanálisis)
* **Qué es**: El reanálisis global **ERA5** de ECMWF (~25km de resolución) toma modelos físicos y los corrige asimilando observaciones reales históricas del pasado.
* **Por qué se usa**: Sirve para comprobar cómo se comporta la física del modelo en la geografía de Tenerife para las 6 variables meteorológicas completas (TEMP, HUM, RAIN, WSP, WDR, RAD). Representa la **cota inferior del error** (el escenario más optimista). Si el modelo falla aquí, es por limitaciones físicas o de resolución espacial del terreno.

### 2️⃣ Nivel 2: Validación de la Capacidad Predictiva Real (Historical Forecast GFS)
* **Qué es**: El archivo histórico de predicciones operacionales del modelo global **GFS** de NOAA (`gfs_seamless`) provisto por Open-Meteo.
* **Por qué es clave**: A diferencia del modelo `best_match` (que en zonas insulares como Canarias recurre al propio reanálisis ERA5 para completar su historial del pasado), el modelo GFS conserva su serie de predicción operacional real e independiente para el periodo 2022-2024.
* **Justificación metodológica**: Valida con total fidelidad el rendimiento real de un sistema de predicción operacional frente a las observaciones de tierra, arrojando diferencias estadísticas reales y significativas frente al reanálisis.

### 3️⃣ Curva de Degradación (Lead-Time Analysis GFS)
* Obtiene las predicciones operacionales de GFS generadas a **24h (D+1), 72h (D+3) y 168h (D+7)** de antelación para el periodo completo.
* Esto te permite graficar cómo va aumentando el error a medida que nos alejamos del día actual, justificando hasta qué día de predicción es seguro confiar en el Dashboard.

---

## 3. ¿Qué hace cada código creado?

### 📁 `prepare_station_data.py`
Extrae y limpia las observaciones reales desde tu archivo masivo `clima_horario_agrocabildo.parquet` (28 millones de filas, ~235 MB).
* **Eficiencia (PyArrow Pushdown)**: En lugar de cargar todo el DataFrame en memoria (lo que causaría un desbordamiento de RAM/`ArrowMemoryError`), utiliza filtros optimizados a bajo nivel en PyArrow para leer exclusivamente las 4 estaciones, los sensores mapeados y el rango de fechas 2022-2024.
* **Tratamiento de Dirección de Viento (`WDR`)**: Al promediar horas sub-horarias, utiliza **aritmética circular** (promedio trigonométrico mediante componentes Seno y Coseno) para evitar el error de promediar, por ejemplo, 350° y 10° (cuyo promedio aritmético daría 180° -sur-, cuando físicamente el flujo medio es 0°/360° -norte-).
* **Tratamiento de Lluvia (`RAIN`)**: Resamplea los datos a paso horario sumando los registros acumulados.

### 📁 `open_meteo_client.py`
Funciona como el conector unificado de APIs para Open-Meteo.
* Proporciona conexión a tres endpoints diferentes:
  1. `archive-api` (para el reanálisis ERA5).
  2. `historical-forecast-api` (para las predicciones históricas operacionales de GFS).
  3. `previous-runs-api` (para extraer las series completas de predicción de GFS según el lead-time en días).
  4. `api.open-meteo.com` (para la predicción futura en tiempo real).
* **Caché persistente y reintentos**: Implementa `requests-cache` con base de datos SQLite local para no volver a descargar datos históricos ya consultados y respeta los límites de tasa de petición (rate limiting) para evitar bloqueos de IP.

### 📁 `run_validation.py`
Es el orquestador del pipeline.
1. Llama a los dos scripts anteriores para generar/cargar los parquets procesados.
2. Realiza un `inner join` temporal estricto basado en la zona horaria UTC.
3. Calcula métricas estadísticas clave por variable y estación:
   * **MAE (Error Medio Absoluto)**: Magnitud media del error.
   * **RMSE (Error Cuadrático Medio)**: Penaliza más los errores grandes (útil para detectar picos inesperados).
   * **Bias (Sesgo)**: Indica si el satélite sobreestima (Bias > 0) o subestima (Bias < 0) de forma sistemática.
   * **R² (Coeficiente de determinación)**: Mide el grado de correlación y la tendencia.
   * **MAE y RMSE Circulares**: Programados específicamente para la dirección del viento.
4. Compara los resultados con los **umbrales de aceptación del TFM** y genera un semáforo de calidad. Exporta los resultados a archivos `.csv`.

### 📁 `validation_analysis.ipynb`
El notebook interactivo diseñado para generar los análisis visuales y las conclusiones redactadas para tu memoria de TFM:
* **Sección 1**: Series temporales interactivas para visualizar el acoplamiento día/noche.
* **Sección 2 & 3**: Matriz de Scatter Plots (diagramas de dispersión) con rectas de regresión frente a la recta identidad $y = x$ y gráficos de barras de penalización de predicción ($\Delta$ MAE).
* **Sección 4 & 7**: Heatmaps visuales de RMSE/R² y el Semáforo de Calidad final.
* **Sección 5 (Crítica)**: Gráfica de la **Curva de Degradación del Error** contra los límites de aceptación del TFM, mostrando la evolución del MAE a D+1, D+3 y D+7.
* **Sección 6**: Boxplots de error mensual para analizar la pérdida de precisión durante los meses de invierno (mayor nubosidad y paso de frentes).
* **Sección 8**: Redacción automatizada de la justificación metodológica y las conclusiones adaptadas a los resultados reales para exportar directamente a tu TFM.

---

## 4. Instrucciones para ejecutar el pipeline

Una vez dentro de la terminal de tu entorno virtual `.venv` activado:

```bash
# 1. Asegúrate de instalar las nuevas dependencias añadidas a requirements.txt
pip install -r requirements.txt

# 2. Sitúate en la carpeta del módulo
cd validation

# 3. Ejecuta el pipeline completo de cálculo (esto descargará los datos y generará las métricas)
python run_validation.py
```

Una vez termine de ejecutarse, abre el notebook `validation_analysis.ipynb` en VS Code o Jupyter Lab, ejecuta todas las celdas y podrás visualizar y guardar todos los gráficos generados en `validation/results/plots/`.
