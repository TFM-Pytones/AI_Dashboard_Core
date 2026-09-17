# AI-Dashboard Territorial de Tenerife — `app/`
Plataforma analítica geoespacial y de inteligencia turística para la isla de Tenerife. Desarrollada con **Streamlit**, **Pydeck (Deck.gl)** y **Plotly**, conectada al almacén de datos dimensionales en **Azure PostgreSQL** (capas Gold H3 y municipal).
---

## Vistas y Módulos de la Aplicación (`app/main.py`)
La aplicación implementa navegación nativa multipágina (`st.navigation`) organizada en las siguientes áreas de análisis:
1. **Resumen Insular (`page_resumen` / `app/summary.py`):**
   - Radiografía global de Tenerife a escala micro-territorial (2.579 hexágonos H3 de resolución 8, ~0,73 km²).
   - KPIs insulares de capacidad alojativa, satisfacción turística y sentimiento.
   - Distribución de arquetipos estratégicos y régimen de protección de suelo (ENP).
2. **Visor de Mapa (`page_mapa` / `app/map_layers.py`):**
   - **Malla H3 Interactiva (2D y 3D con Modelo Digital del Terreno):** Saturación turística, potencial rural, potencial turístico (PTNA con escala calibrada P1–P99 anti-outliers), índice ESG (0–100), densidad hotelera, sentimiento, vegetación (NDVI), luz nocturna (VIIRS), accesibilidad e infraestructuras.
   - **Capa Municipal Coroplética:** 12 métricas meso-territoriales (presión residencial, densidad turística, evolución de vivienda vacacional, empleo, población, ingresos).
   - **Infraestructuras y Patrimonio:** Isócronas de tiempo de conducción (15 a 60 min), red insular de guaguas (GTFS TITSA), Bienes de Interés Cultural (BIC) y estaciones meteorológicas (Agrocabildo).
   - **Ficha de Detalle Territorial (`app/detail_panel.py`):** Panel dinámico al pulsar cualquier celda H3 con comparativa frente a la media municipal e insular.
3. **Tabla Detallada (`page_tabla` / `app/table_view.py`):**
   - Explorador de datos tabulares a nivel de celda H3 con filtros combinados por municipio y régimen de protección, y descarga directa en CSV.
4. **Rankings Territoriales (`page_rankings` / `app/rankings.py`):**
   - Tablas de clasificación insular (top hexágonos con mayor presión, potencial de regeneración, satisfacción, vegetación y capacidad).
5. **Arquetipos TUI (`page_arquetipos` / `app/arquetipos.py`):**
   - Segmentación de la isla en 5 arquetipos de producto turístico (*Sol y playa*, *Ecoturismo rural*, *Cultural y patrimonial*, *Turismo activo y aventura*, *Bienestar y salud*).
   - Diagnóstico DAFO, matriz de posicionamiento y distribución geográfica.
6. **Simulador Territorial What-If (`page_simulador` / `app/simulador.py`):**
   - Motor de proyección de políticas e intervenciones a 4 escalas: hexágono individual, municipio completo, arquetipo o clúster HDBSCAN.
   - Parámetros de intervención: plazas regladas, conectividad aeroportuaria, vegetación, equipamientos (POIs) e índice ESG.
   - Recálculo en tiempo real de los ejes estratégicos, gráficos radar y matriz de posicionamiento territorial.
   - Indicador de nivel de confianza predictiva (media / baja) asociado al modelo PTNA (MGWR).
7. **Clima (`page_clima` / `app/clima.py`):**
   - Monitorización agroclimática insular mediante la red de estaciones de Agrocabildo (temperatura, humedad, viento y precipitaciones).
8. **Municipios (`page_municipios` / `app/municipios.py`):**
   - Radiografía socioeconómica de los 31 municipios: evolución de empleo (afiliados), paro registrado, dependencia de la hostelería y evolución temporal.
9. **Alojamiento y Oferta (`page_alojamiento_temas` / `app/alojamiento.py`, `app/temas.py`):**
   - Distribución de hoteles y viviendas vacacionales, ratings de reputación online (Booking) y análisis de tópicos NLP de reseñas traducidos al castellano.
10. **Turismo (`page_turismo` / `app/turismo.py`):**
    - Series temporales de coyuntura hotelera y extrahotelera del ISTAC por polo turístico (viajeros, pernoctaciones, estancia media e ingresos VV).
11. **Asistente IA (`page_asistente` / `app/asistente.py`):**
    - Agente conversacional inteligente con enrutador analítico, Text-to-SQL y fundamentación (*grounding*) territorial con el hexágono seleccionado.
---

## Arquitectura de Soporte (`app/`)
| Módulo | Responsabilidad principal |
|---|---|
| [`data.py`](file:///c:/Users/ROBERTO/Proyectos_Python/TFM_TUI_Tenerife/AI_Dashboard_Core/app/data.py) | Conexión con PostgreSQL, consultas SQL optimizadas de capas Gold y almacenamiento en caché (`@st.cache_data`). |
| [`map_layers.py`](file:///c:/Users/ROBERTO/Proyectos_Python/TFM_TUI_Tenerife/AI_Dashboard_Core/app/map_layers.py) | Construcción de capas Pydeck (`GeoJsonLayer`, `H3HexagonLayer`, `ScatterplotLayer`), 3D, leyendas HTML y caps percentiles P1–P99. |
| [`color_scales.py`](file:///c:/Users/ROBERTO/Proyectos_Python/TFM_TUI_Tenerife/AI_Dashboard_Core/app/color_scales.py) | Paletas cromáticas continuas, divergentes y categóricas calibradas para modo oscuro. |
| [`ui_helpers.py`](file:///c:/Users/ROBERTO/Proyectos_Python/TFM_TUI_Tenerife/AI_Dashboard_Core/app/ui_helpers.py) | Formateadores de métricas (porcentajes, euros, enteros), badges y banners de cabecera. |
| [`topic_labels_es.py`](file:///c:/Users/ROBERTO/Proyectos_Python/TFM_TUI_Tenerife/AI_Dashboard_Core/app/topic_labels_es.py) | Mapeo y traducción de tópicos BERTopic de opiniones turísticas al español. |
---

## Ejecución y Validación
### Entorno local
```bash
# 1. Asegurarse de disponer del archivo .env con las credenciales de Azure
# 2. Activar el entorno virtual e iniciar el dashboard
streamlit run app/main.py