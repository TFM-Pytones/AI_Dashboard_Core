# Modelización Microclimática Espacial en Tenerife (Hexágonos H3)

## 1. Introducción y Contexto Geográfico
Tenerife se caracteriza por su extrema complejidad orográfica. El relieve, dominado por el Teide (3.718m) y la Cordillera Dorsal, actúa como una barrera natural frente a los vientos dominantes (los **Alisios** del Noreste). Esto genera una enorme disparidad climática entre la vertiente Norte (Barlovento) y la vertiente Sur (Sotavento).

En sistemas de predicción espacial o gemelos digitales territoriales, interpolar datos meteorológicos utilizando únicamente la distancia lineal entre estaciones (método IDW tradicional) arroja resultados erróneos. Por ejemplo, interpolar lluvia entre el Norte y el Sur ignorando que la montaña frena las nubes. 

Para solucionar esto, en la capa **Gold (`gold_h3_master`)** hemos diseñado un modelo microclimático que ajusta las variables base interpoladas introduciendo **Deltas Topográficos y Modificadores Espaciales** basados en cuatro grandes factores:
1. Gradiente Térmico (Altitud)
2. Termorregulación Oceánica (Distancia a la Costa)
3. Mar de Nubes y Sombra de Lluvia (Orientación de ladera - Aspect)
4. Exposición y Aceleración del Viento (Orientación)

---

## 2. Marco Teórico y Fórmulas Matemáticas

### 2.1. Gradiente Térmico Altitudinal
La temperatura desciende a medida que aumenta la altitud. En condiciones estándar, este descenso (Gradiente Térmico Seco / Húmedo) oscila alrededor de **-0.0065°C por metro** de ascenso.
*   **Fórmula Base:** `Temp_H3 = Temp_Estacion + (Altitud_Estacion - Altitud_H3) * 0.0065`

### 2.2. Termorregulación Oceánica (Índice de Continentalidad/Oceanidad)
El Océano Atlántico actúa como un gigantesco acumulador térmico. Las zonas costeras (distancia a la costa < 1km) gozan de inviernos más cálidos y veranos más frescos. Tierra adentro, la amplitud térmica (diferencia entre máximas y mínimas) aumenta drásticamente.
Para corregir este efecto en H3, se calcula el `Delta de Distancia a la Costa` en kilómetros entre la celda H3 y la estación de la cual interpola el dato:
`Delta_Dist_Km = (H3_Dist_Costa_m - Estacion_Dist_Costa_m) / 1000`

Se aplican los siguientes factores de penalización a la Temperatura (si el Delta es positivo, significa que el H3 está más lejos del mar que la estación):
*   **Verano (Q3):** Aumenta el calor extremo: `+ (Delta_Dist_Km * 0.15°C)`.
*   **Invierno (Q1):** Aumenta el frío: `- (Delta_Dist_Km * 0.15°C)`.
*   **Estaciones de Transición (Q2, Q4):** Efecto suave: `+/- (Delta_Dist_Km * 0.05°C)`.
*   **Amplitud Térmica Media:** Se dispara un `+0.30°C` por cada kilómetro interior.

### 2.3. Efecto "Mar de Nubes" y Humedad Costera
La humedad en Tenerife no obedece a un gradiente lineal, sino a la capa de inversión térmica provocada por los Alisios. En el Norte, el aire húmedo queda atrapado entre los 800 y los 1.500 msnm. Por encima de la inversión (Las Cañadas del Teide), la humedad se desploma. A su vez, vivir en primera línea de mar aporta humedad adicional.

**Factor Humedad:**
Se calcula un `Factor` para la Estación y otro para el Hexágono H3 basado en el modelo digital del terreno (`aspect_mean` y `elevation_mean`).
*   **Vertiente Norte (Barlovento / Alisios) [Aspect 300° a 90°]:**
    *   Zona Mar de Nubes (800m - 1500m): **Factor 1.25** (+25%)
    *   Alta Montaña (> 1500m): **Factor 0.70** (-30%)
    *   Costa Norte (< 800m): **Factor 1.05** (+5%)
*   **Vertiente Sur (Sotavento) [Aspect 90° a 300°]:**
    *   **Factor 0.85** (-15%)
*   **Bono Costero Extra:** Si la celda está a `< 1500m` de la costa, se añade `+0.15` al factor.

El cálculo matemático para la imputación final en H3 es:
`Humedad_Final = Humedad_Estacion * (Factor_Humedad_H3 / Factor_Humedad_Estacion)`

### 2.4. Sombra de Lluvia y Efecto Föhn (Precipitación)
El relieve bloquea los frentes lluviosos procedentes del NE, concentrando las precipitaciones en la vertiente Norte y generando un "desierto" orográfico en el Sur (Sombra de Lluvia).

**Factor Lluvia:**
*   Norte/Noreste con Altitud < 1500m (Exposición máxima a frentes): **Factor 1.30**
*   Sur/Oeste (Sombra pluviométrica): **Factor 0.40**
*   Alta Montaña / Otras zonas: **Factor 1.00**

*Fórmula:* `Lluvia_Final = Lluvia_Estacion * (Factor_Lluvia_H3 / Factor_Lluvia_Estacion)`

*(Nota: Al usar la división de factores, si se extrapola la lluvia de una estación ubicada en la seca vertiente Sur a un hexágono situado en el húmedo Norte, el modelo automáticamente multiplica la precipitación registrada en la estación por ~3.25, equilibrando las deficiencias del interpolador IDW).*

### 2.5. Efecto Escudo y Canalización (Velocidad del Viento)
La orografía no solo bloquea el viento, sino que lo acelera en ciertas laderas o valles por el *efecto Venturi*. El modelo se ajusta estimando el Topographic Position Index (TPI) y la exposición directa a los vientos alisios del Noreste.

**Factor Viento:**
*   Exposición Directa (Aspect 0° a 90°): **Factor 1.20**
*   Sotavento Protegido (Aspect 180° a 270°): **Factor 0.60**
*   Alta Montaña (> 2000m): **Factor 1.40** (vientos libres de rozamiento).

*Fórmula:* `Viento_Final = Viento_Estacion * (Factor_Viento_H3 / Factor_Viento_Estacion)`

---

## 3. Implementación Arquitectónica (dbt)

Esta matemática se inyecta mediante las CTEs (*Common Table Expressions*) en el modelo analítico `gold_h3_master.sql`. 
En lugar de cargar pesados modelos geoespaciales raster en Python, dbt aprovecha la potencia de PostGIS (Azure Database for PostgreSQL Flexible Server) para ejecutar estas condicionales (`CASE WHEN`) a nivel de fila durante la materialización de la tabla.

Los inputs espaciales (`aspect_mean`, `slope_mean`, `elevation_mean`) requeridos para las fórmulas proceden de la capa `silver_mdt_stats`, generada a partir del Modelo Digital del Terreno de 5m del IGN.
