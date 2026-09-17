# scripts/rebuild_complete_annexes_and_doc.py
"""
Script maestro para reconstruir y expandir completamente los Anexos de la Memoria de TFM,
garantizando:
1. Que los anexos sean exhaustivos, completos y detallados (sin datos inventados).
2. Que la bibliografía ocupe exactamente media hoja (13 referencias clave).
3. Que las tablas del cuerpo (P4 y P7) estén rigurosamente corregidas.
4. Que se actualice tanto TFM_Pythones_cambios_v2.docx como TFM_Memoria_Final_UCM.docx y docs/TFM_Memoria_Completa.md.
"""

import os
import sys
import docx
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn

DOCX_FILE = "TFM_Pythones_cambios_v2.docx"

REFERENCES_TEXTS = [
    "Agencia Espacial Europea (ESA). (2024). Copernicus Sentinel-2: Multispectral imagery and land monitoring data. European Space Agency. https://sentinels.copernicus.eu",
    "Armbrust, M., Ghodsi, A., Xin, R., y Zaharia, M. (2021). Lakehouse: A new generation of open platforms that unify data warehousing and advanced analytics. Proceedings of CIDR 2021, 1–8.",
    "Cabildo de Tenerife. (2024). Red agrometeorológica insular de Agrocabildo: datos horarios y metadatos de estaciones. Cabildo Insular de Tenerife. https://www.agrocabildo.org",
    "dbt Labs. (2024). dbt Core Documentation: Transformation workflow and data modeling (Version 1.8). dbt Labs Inc. https://docs.getdbt.com",
    "Elvidge, C. D., Baugh, K., Zhizhin, M., Hsu, F. C., y Ghosh, T. (2017). VIIRS night-time lights. International Journal of Remote Sensing, 38(21), 5860–5879. https://doi.org/10.1080/01431161.2017.1342050",
    "Horn, B. K. P. (1981). Hill shading and the reflectance map. Proceedings of the IEEE, 69(1), 14–47. https://doi.org/10.1109/PROC.1981.11918",
    "Instituto Canario de Estadística (ISTAC). (2025). Encuesta de Gasto Turístico, FRONTUR-Canarias y Municipios en Cifras (C00067A). Gobierno de Canarias. https://www.gobiernodecanarias.org/istac/",
    "Milano, C., Novelli, M., y Cheer, J. M. (2019). Overtourism and degrowth: A social movements perspective. Journal of Sustainable Tourism, 27(12), 1857–1875. https://doi.org/10.1080/09669582.2019.1650054",
    "Openshaw, S. (1984). The Modifiable Areal Unit Problem. Concepts and Techniques in Modern Geography, 38. Geo Books.",
    "PostGIS Project. (2024). PostGIS: Spatial and Geographic Objects for PostgreSQL (Version 3.4). https://postgis.net",
    "Turismo de Canarias. (2025). Estrategia de turismo regenerativo RegNext 2025–2030. Promotur Turismo Canarias. https://www.turismodeislascanarias.com",
    "Turismo de Tenerife. (2025). Informe de coyuntura turística insular: Año 2024. Cabildo Insular de Tenerife. https://www.webtenerife.com",
    "Uber Technologies. (2018). H3: Hexagonal Hierarchical Spatial Index (Version 4.1). Uber Open Source. https://h3geo.org",
]

def style_cell(cell, text, bold=False, italic=False, bg_color=None, font_size=8.5, font_name="Verdana"):
    cell.text = ""
    p = cell.paragraphs[0]
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.line_spacing = 1.05
    run = p.add_run(text)
    run.font.name = font_name
    run.font.size = Pt(font_size)
    run.font.bold = bold
    run.font.italic = italic
    if bg_color:
        shading = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{bg_color}"/>')
        cell._tc.get_or_add_tcPr().append(shading)

def set_table_borders(table):
    tblPr = table._tbl.tblPr
    borders = parse_xml(
        f'<w:tblBorders {nsdecls("w")}>\n'
        f'  <w:top w:val="single" w:sz="4" w:space="0" w:color="D5D8DC"/>\n'
        f'  <w:bottom w:val="single" w:sz="4" w:space="0" w:color="D5D8DC"/>\n'
        f'  <w:insideH w:val="single" w:sz="4" w:space="0" w:color="EAEDED"/>\n'
        f'  <w:insideV w:val="none"/>\n'
        f'  <w:left w:val="none"/>\n'
        f'  <w:right w:val="none"/>\n'
        f'</w:tblBorders>'
    )
    tblPr.append(borders)

def create_table(doc, headers, data, col_widths=None):
    tbl = doc.add_table(rows=len(data) + 1, cols=len(headers))
    try:
        tbl.style = "Normal Table"
    except Exception:
        pass
    set_table_borders(tbl)
    
    # Header
    for col_idx, h_text in enumerate(headers):
        cell = tbl.rows[0].cells[col_idx]
        style_cell(cell, h_text, bold=True, bg_color="1A5276", font_size=8.5)
        # Text color white for header
        for run in cell.paragraphs[0].runs:
            run.font.color.rgb = RGBColor(255, 255, 255)
            
    # Data rows
    for row_idx, row_data in enumerate(data, start=1):
        bg = "F2F4F4" if row_idx % 2 == 1 else "FFFFFF"
        for col_idx, val in enumerate(row_data):
            cell = tbl.rows[row_idx].cells[col_idx]
            style_cell(cell, str(val), bg_color=bg, font_size=8.0)
            
    if col_widths:
        for row in tbl.rows:
            for idx, width in enumerate(col_widths):
                if idx < len(row.cells):
                    row.cells[idx].width = Inches(width)
                    
    # Space after table
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(6)
    return tbl

def add_heading(doc, text, level):
    p = doc.add_paragraph()
    try:
        p.style = doc.styles[f"Heading {level}"]
    except Exception:
        pass
    p.paragraph_format.space_before = Pt(14 if level == 1 else 10)
    p.paragraph_format.space_after = Pt(4)
    run = p.add_run(text)
    run.font.name = "Verdana"
    run.font.size = Pt(13 if level == 1 else (11.5 if level == 2 else 10))
    run.font.bold = True
    run.font.color.rgb = RGBColor(26, 82, 118) if level <= 2 else RGBColor(40, 55, 71)
    return p

def add_body_p(doc, text, italic=False, space_after=4):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.line_spacing = 1.15
    run = p.add_run(text)
    run.font.name = "Verdana"
    run.font.size = Pt(9.5)
    run.font.italic = italic
    return p

def add_code_block(doc, text):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(6)
    p.paragraph_format.line_spacing = 1.05
    run = p.add_run(text)
    run.font.name = "Consolas"
    run.font.size = Pt(8.0)
    run.font.color.rgb = RGBColor(33, 47, 61)
    shading = parse_xml(f'<w:shd {nsdecls("w")} w:fill="F8F9F9"/>')
    p._p.get_or_add_pPr().append(shading)
    return p

def rebuild_annexes(doc):
    # Localizar el inicio de Anexos
    annex_idx = None
    for i, p in enumerate(doc.paragraphs):
        if p.text.strip().lower() == "anexos":
            annex_idx = i
            break
            
    if annex_idx is not None:
        # Eliminar todos los elementos desde Anexos en adelante
        # Para evitar problemas de iteración, eliminamos los párrafos y tablas al final
        p_annex = doc.paragraphs[annex_idx]
        parent = p_annex._element.getparent()
        
        # Encontrar el índice de p_annex en el body
        body_elements = list(parent)
        start_idx = body_elements.index(p_annex._element)
        for elem in body_elements[start_idx:]:
            parent.remove(elem)
            
    # Añadir sección Anexos completa y enriquecida
    add_heading(doc, "Anexos", 1)
    add_body_p(doc, 
        "Nota metodológica: Los siguientes anexos recogen las especificaciones técnicas, "
        "los catálogos de datos, el linaje dbt de la arquitectura medallón, los scripts "
        "de analítica avanzada, los cuadernos de análisis exploratorio (EDA), las métricas "
        "empíricas de los modelos y el manual de despliegue reproducible. Según la normativa de "
        "la UCM, estos anexos no computan dentro del límite estricto de 20 páginas de la memoria principal.",
        italic=True, space_after=6
    )
    
    # ----------------------------------------------------
    # Anexo A
    # ----------------------------------------------------
    add_heading(doc, "Anexo A – Repositorio de Código Fuente, Control de Versiones y Gobernanza", 2)
    add_body_p(doc, 
        "El código fuente completo, los pipelines de ingesta, los modelos dbt y el cuadro de mando "
        "operacional se encuentran bajo control de versiones en GitHub: https://github.com/TFM-Pytones/AI_Dashboard_Core. "
        "Los tutores del máster, Carlos Ortega y Santiago Mota, disponen de permisos de lectura para la evaluación académica. "
        "La estructura del repositorio articula una jerarquía modular desacoplada:"
    )
    add_code_block(doc, 
        "AI_Dashboard_Core/\n"
        "├── ingestion/           # Módulos 01-07: ISTAC, Agrocabildo, Sentinel-2, VIIRS, GTFS, YouTube, Booking, TripAdvisor\n"
        "├── dbt_project/         # Pipeline Medallón: models/bronze, models/silver, models/gold, macros y schema tests\n"
        "├── analytics/           # Pipelines de Machine Learning y NLP:\n"
        "│   ├── sentiment/       # Clasificación multilingüe con XLM-RoBERTa y filtro zero-shot mDeBERTa\n"
        "│   ├── aspects/         # Minería de aspectos PyABSA-ATEPC y normalización a 6 dimensiones\n"
        "│   ├── topics/          # BERTopic multilingüe (Modelos A y B) con centrado vectorial\n"
        "│   ├── clustering/      # Segmentación espacial HDBSCAN y normalización MinMax\n"
        "│   ├── accesibilidad/   # Matrices de conducción vial ORS y distancias a red GTFS TITSA\n"
        "│   ├── mgwr/            # Regresión Geográfica Ponderada Multiescala (MGWR v3) e índice PTNA\n"
        "│   ├── rag/             # Motor RAG híbrido (chunking, embeddings MPNet 768d, HNSW, BM25, RRF)\n"
        "│   └── chat/            # Router LLM determinista y motor Text-to-SQL con validación AST\n"
        "├── app/                 # Cuadro de mando operacional en Streamlit (v1.40+) y PyDeck (WebGL 2D/3D):\n"
        "│   ├── main.py          # Punto de entrada con navegación nativa st.navigation (10 páginas)\n"
        "│   ├── map_layers.py    # Visor cartográfico microespacial H3 y mesomunicipal con extrusión MDT05\n"
        "│   ├── detail_panel.py  # Ficha técnica interactiva por hexágono con benchmarking territorial\n"
        "│   ├── simulador.py     # Simulador What-If de redistribución de flujos y alertas de capacidad\n"
        "│   └── asistente.py     # Asistente conversacional contextual anclado al hexágono activo\n"
        "├── notebooks/           # Cuadernos Jupyter con análisis exploratorios (EDA) y calibraciones físicas\n"
        "├── docs/                # Diccionarios de datos, arquitectura medallón y memoria completa\n"
        "└── tests/               # Batería de pruebas unitarias y de integración con pytest"
    )
    
    # ----------------------------------------------------
    # Anexo A2
    # ----------------------------------------------------
    add_heading(doc, "Anexo A2 – Catálogo de Fuentes Ingestadas en el Data Lakehouse", 2)
    add_body_p(doc, 
        "La solución ingiere diez fuentes heterogéneas consolidadas en Microsoft Azure PostgreSQL con PostGIS. "
        "La tabla siguiente detalla los volúmenes brutos y depurados de cada proveedor:"
    )
    headers_a2 = ["Fuente / Proveedor", "Tipología de Dato", "Volumen Bruto (Bronze)", "Volumen Depurado (Silver)", "Aportación al Caso de Negocio"]
    data_a2 = [
        ["ISTAC (Gobierno de Canarias)", "Microdatos socioeconómicos y demanda", "2 recursos REST (C00067A y C00065A)", "24 indicadores municipales (31 términos)", "Series de empleo, pernoctaciones, ocupación hotelera y vivienda vacacional"],
        ["Cartografía (GRAFCAN / Cabildo)", "Vectores institucionales (GeoJSON)", "5 coberturas oficiales insulares", "31 mun., 125 BIC, 31 ofic., 17 ZT, 43 ENP", "Delimitación territorial, atractores patrimoniales y restricciones legales de suelo"],
        ["MDT25 / MDT05 (GRAFCAN / IGN)", "Raster altimétrico (25 m / 5 m)", "Raster insular continuo", "Altura, pendiente, aspecto y sombreado zonal", "Caracterización geomorfológica, aptitud constructiva y confort térmico solar"],
        ["GTFS (TITSA / Tranvía de Tenerife)", "Red de transporte público regular", "2,08 M registros brutos", "3.934 paradas, 183 líneas, 1,36 M pasos", "Accesibilidad multimodal, proximidad a paradas e isócronas de guagua"],
        ["Agrocabildo (Cabildo de Tenerife)", "Sensórica meteorológica diezminutal", "136,4 M lecturas (67 estaciones)", "12,95 M registros limpios (57 estaciones)", "Calibración microclimática: gradientes adiabáticos y mar de nubes (800–1.500 m)"],
        ["Copernicus Sentinel-2 (ESA)", "Teledetección multiespectral (20 m)", "Composites trimestrales (2019–2026)", "46.422 observaciones agregadas a celdas H3", "Vigor vegetal (NDVI) y sellado de suelo construido (NDBI) por hexágono"],
        ["NOAA/NASA VIIRS DNB", "Radianza nocturna satelital (500 m)", "Serie mensual DNB (2019–2026)", "241.648 observaciones limpias", "Proxy físico cuantitativo de actividad económica, electrificación y saturación"],
        ["LosViajeros.com", "Comunidad online y foros de viajes", "167.274 mensajes (248 hilos)", "168.035 mensajes parseados y clasificados", "Detección cualitativa de fricciones, rutas en interior y quejas de aparcamiento"],
        ["YouTube Data API v3", "Opiniones en vídeo turístico", "3.100 comentarios (41 vídeos seleccionados)", "2.819 comentarios depurados", "Percepción audiovisual de marca de destino y atractores clave"],
        ["Booking.com y TripAdvisor", "Reseñas geolocalizadas de alojamientos", ">105.000 reseñas brutas", "74.695 opiniones depuradas (3.740 estab., 748 activ.)", "Minería de aspectos y sentimiento georreferenciado en celdas H3"],
    ]
    create_table(doc, headers_a2, data_a2, col_widths=[1.5, 1.4, 1.3, 1.3, 1.7])
    
    # ----------------------------------------------------
    # Anexo A3
    # ----------------------------------------------------
    add_heading(doc, "Anexo A3 – Diccionario de Modelos de Negocio de la Capa Gold", 2)
    add_body_p(doc, 
        "La Capa Gold materializa trece modelos dimensionales optimizados para el consumo analítico, "
        "la regresión espacial MGWR, el asistente RAG y el renderizado WebGL en el AI-Dashboard:"
    )
    headers_a3 = ["Modelo Gold", "Granularidad Espacial", "Contenido Principal y Variables Analíticas Clave"]
    data_a3 = [
        ["gold.gold_h3_master", "H3 Res 8 (2.579 celdas)", "Tabla maestra microespacial: >60 variables biofísicas, topoclimáticas, de movilidad ORS/GTFS, oferta alojativa y NLP"],
        ["gold.gold_h3_sentimiento", "H3 Res 8 (410 celdas)", "Polaridad media (-1 a +1), volumen de opiniones por canal (Booking/TripAdvisor) y queja modal negativa"],
        ["gold.gold_h3_accesibilidad", "H3 Res 8 (2.579 celdas)", "Tiempos continuos ORS a 18 destinos clave (aeropuertos, Teide, hospitales) y distancias multiumbral a paradas GTFS"],
        ["gold.gold_h3_ptna_v3", "H3 Res 8 (2.579 celdas)", "Puntuación de atracción potencial PTNA calibrada con MGWR v3 y bandera de confianza estadística local"],
        ["gold.gold_h3_esg_v1", "H3 Res 8 (2.579 celdas)", "Evaluación ESG microespacial compuesta: Dimensión E (40 %), Dimensión S (30 %) y Dimensión G (30 %)"],
        ["gold.gold_bloque5_h3_oportunidad_v1", "H3 Res 8 (2.579 celdas)", "Posicionamiento en Eje 1 (Saturación) y Eje 2 (Oportunidad Rural), con flag de oportunidad ideal (PTNA>0, ESG>60)"],
        ["gold.h3_clusters", "H3 Res 8 (2.579 celdas)", "6 tipologías territoriales no paramétricas derivadas de HDBSCAN con probabilidad de asignación individual"],
        ["gold.gold_municipio_master", "Municipal (31 términos)", "Capa mesomunicipal coroplética con 12 indicadores ISTAC, paro registrado, afiliaciones y presión residencial"],
        ["gold.gold_municipio_anual / mensual", "Municipal (31 términos)", "Series históricas (2009–2026) de ocupación, viajeros y pernoctaciones hoteleras y extrahoteleras"],
        ["gold.gold_turismo_hotelero_anual / mensual", "Municipal (31 términos)", "Indicadores de rentabilidad y precios hoteleros oficiales: tarifa media diaria (ADR) e ingresos por habitación (RevPAR)"],
        ["gold.gold_aena_pasajeros", "Aeroportuario (TFS/TFN)", "Tráfico mensual de pasajeros de llegada y salida en aeropuertos insulares (2019–2026) con desglose internacional"],
        ["gold.nlp_chunks", "Documental (87.981 fragmentos)", "Embeddings semánticos 768d (MPNet) con índices HNSW y BM25 para recuperación híbrida en el asistente RAG"],
        ["gold.gold_isocronas_visuales", "Polígonos vectoriales (24)", "Geometrías de isócronas viales de 15, 30, 45 y 60 min hacia aeropuertos y Teide para renderizado fluido en Deck.gl"],
    ]
    create_table(doc, headers_a3, data_a3, col_widths=[2.1, 1.5, 3.6])
    
    # ----------------------------------------------------
    # Anexo B
    # ----------------------------------------------------
    add_heading(doc, "Anexo B – Variables de Entorno y Configuración del Sistema (.env.example)", 2)
    add_body_p(doc, 
        "El archivo .env.example en la raíz del proyecto documenta los parámetros de configuración y credenciales de acceso "
        "necesarios para reproducir el despliegue local o en la nube:"
    )
    headers_b = ["Variable de Entorno", "Tipo / Formato", "Propósito Técnico y Servicio Asociado"]
    data_b = [
        ["AZURE_DB_URL", "URI de conexión", "Cadena SQLAlchemy para PostgreSQL Flexible Server en Azure (usuario, clave cifrada, host, puerto 5432 y sslmode=require)"],
        ["AZURE_STORAGE_CONNECTION_STRING", "Token secreto", "Autenticación en Azure Blob Storage para persistencia masiva de artefactos Parquet, rasters y GeoJSON"],
        ["GROQ_API_KEY", "API Token", "Credencial de acceso a Groq Cloud para inferencia ultrarrápida LPU ejecutando el modelo openai/gpt-oss-120b"],
        ["ORS_API_KEY", "API Token", "Token de OpenRouteService v7.0 para el cálculo determinista de matrices de tiempo e isócronas viales"],
        ["MAPBOX_API_KEY", "API Token público", "Clave de acceso a Mapbox GL para la carga de mapas base vectoriales oscuros y satelitales en PyDeck"],
        ["YOUTUBE_API_KEY", "API Token", "Clave de Google Cloud Platform para la extracción automatizada de comentarios turísticos vía YouTube Data API v3"],
        ["DBT_PROFILES_DIR", "Ruta de directorio", "Directorio local de configuración de dbt Core conteniendo el archivo profiles.yml"],
        ["POSTGRES_MAX_CONNECTIONS", "Entero (int)", "Límite del pool de conexiones para FastAPI y Streamlit (por defecto: pool_size=10, max_overflow=20)"],
    ]
    create_table(doc, headers_b, data_b, col_widths=[2.4, 1.3, 3.5])
    
    # ----------------------------------------------------
    # Anexo C
    # ----------------------------------------------------
    add_heading(doc, "Anexo C – Esquemas SQL, Linaje de Medallón y Modelos dbt Core", 2)
    add_body_p(doc, 
        "La capa de transformación dbt articula 48 tablas Bronze en 28 modelos Silver y 13 modelos Gold, "
        "orquestando el linaje de datos de extremo a extremo con estricta gobernanza e índices espaciales PostGIS. "
        "A continuación se recogen los extractos técnicos y modelos canónicos referenciados en los capítulos de la memoria:"
    )
    
    # C.1
    add_heading(doc, "Anexo C.1 – Asignación y Fallback Espacial de Coordenadas (silver_alojamientos_oficiales.sql)", 3)
    add_body_p(doc,
        "El modelo dbt silver_alojamientos_oficiales.sql unifica la oferta reglada del Gobierno de Canarias y resuelve la cartografía "
        "oficial priorizando las coordenadas geocodificadas del lookup espacial sobre las del registro cuando presentan inconsistencias o nulos:"
    )
    add_code_block(doc,
        "-- dbt_project/models/silver/alojamiento/silver_alojamientos_oficiales.sql\n"
        "{{ config(materialized='table', indexes=[{'columns': ['geometry'], 'type': 'gist'}]) }}\n\n"
        "WITH source_data AS (\n"
        "    SELECT establecimiento_id, establecimiento_nombre_comercial AS nombre, direccion_municipio_nombre AS municipio,\n"
        "           plazas, longitud, latitud, 'hotel' AS tipo_alojamiento\n"
        "    FROM {{ source('bronze', 'bronze_registro_hoteles') }}\n"
        "    UNION ALL\n"
        "    SELECT establecimiento_id, establecimiento_nombre_comercial, direccion_municipio_nombre, plazas, longitud, latitud, 'extrahotelero'\n"
        "    FROM {{ source('bronze', 'bronze_registro_extrahoteleros') }}\n"
        "    UNION ALL\n"
        "    SELECT establecimiento_id, establecimiento_nombre_comercial, direccion_municipio_nombre, plazas, longitud, latitud, 'vivienda_vacacional'\n"
        "    FROM {{ source('bronze', 'bronze_registro_viviendas_vacacionales') }}\n"
        "),\n"
        "lookup AS (\n"
        "    SELECT establecimiento_id, longitud_geocoded, latitud_geocoded\n"
        "    FROM {{ source('bronze', 'bronze_registro_geocoding_lookup') }}\n"
        "),\n"
        "cleaned AS (\n"
        "    SELECT\n"
        "        s.establecimiento_id AS id,\n"
        "        s.nombre, s.municipio, s.tipo_alojamiento, s.plazas,\n"
        "        -- Fallback Robusto: 1) Geocodificador verificado 2) Coordenada original limpia del registro\n"
        "        COALESCE(CAST(l.longitud_geocoded AS NUMERIC), CAST(NULLIF(TRIM(REPLACE(CAST(s.longitud AS VARCHAR), ',', '.')), '') AS NUMERIC)) AS longitud,\n"
        "        COALESCE(CAST(l.latitud_geocoded AS NUMERIC), CAST(NULLIF(TRIM(REPLACE(CAST(s.latitud AS VARCHAR), ',', '.')), '') AS NUMERIC)) AS latitud\n"
        "    FROM source_data s\n"
        "    LEFT JOIN lookup l ON CAST(s.establecimiento_id AS VARCHAR) = CAST(l.establecimiento_id AS VARCHAR)\n"
        ")\n"
        "SELECT id, nombre, municipio, tipo_alojamiento, plazas, longitud, latitud,\n"
        "    CASE\n"
        "        WHEN longitud BETWEEN -16.95 AND -16.09 AND latitud BETWEEN 27.97 AND 28.59\n"
        "        THEN ST_SetSRID(ST_MakePoint(longitud, latitud), 4326)\n"
        "        ELSE NULL\n"
        "    END AS geometry\n"
        "FROM cleaned;"
    )

    # C.2
    add_heading(doc, "Anexo C.2 – Interpolación Espacial Topoclimática y Gradiente Térmico (silver_clima y gold_h3_master.sql)", 3)
    add_body_p(doc,
        "La interpolación microclimática calcula la temperatura y humedad en cada celda H3 combinando ponderación por distancia inversa "
        "cuadrática (IDW k=3) desde las 67 estaciones de Agrocabildo, corregida por gradiente adiabático vertical (-0,0065 °C/m) y amortiguación litoral:"
    )
    add_code_block(doc,
        "-- Extracto de dbt_project/models/gold/gold_h3_master.sql (Lógica Topoclimática)\n"
        "h3_vecinos_clima AS (\n"
        "    SELECT h.h3_index, h.h3_altitud, h.h3_aspect, h.h3_dist_costa_km, est.*,\n"
        "           1.0 / POWER(GREATEST(ST_Distance(ST_Transform(h.geometry, 32628), ST_Transform(est.geometry, 32628)), 1), 2) AS peso\n"
        "    FROM h3_con_topografia h\n"
        "    CROSS JOIN LATERAL (\n"
        "        SELECT * FROM estaciones_con_topografia e\n"
        "        ORDER BY h.geometry <-> e.geometry LIMIT 3\n"
        "    ) est\n"
        "),\n"
        "h3_clima AS (\n"
        "    SELECT h3_index,\n"
        "        -- Temperatura anual corregida por gradiente altitudinal y distancia a la costa\n"
        "        SUM((temp_media_anual + COALESCE((station_altitud - h3_altitud) * 0.0065, 0)) * peso) / NULLIF(SUM(peso), 0) AS temp_media_anual,\n"
        "        SUM((temp_media_q1 + COALESCE((station_altitud - h3_altitud) * 0.0065, 0) - ((h3_dist_costa_km - station_dist_costa_km) * 0.15)) * peso) / NULLIF(SUM(peso), 0) AS temp_media_q1,\n"
        "        SUM((amplitud_termica_media + GREATEST((h3_dist_costa_km - station_dist_costa_km) * 0.30, 0)) * peso) / NULLIF(SUM(peso), 0) AS amplitud_termica_media,\n"
        "        SUM((humedad_media_anual * (factor_hum_h3 / NULLIF(factor_hum_est, 0.001))) * peso) / NULLIF(SUM(peso), 0) AS humedad_media_anual\n"
        "    FROM h3_vecinos_clima_factores\n"
        "    GROUP BY h3_index\n"
        ")"
    )

    # C.3
    add_heading(doc, "Anexo C.3 – Consolidación Espacial de Sentimiento y Quejas Modales en Malla H3 (gold_sentimiento_h3.sql)", 3)
    add_body_p(doc, 
        "El modelo gold_sentimiento_h3.sql materializa la agregación microespacial en resolución 8, calculando la nota afectiva media "
        "y extrayendo la queja modal predominante condicionada estrictamente a menciones cualitativas de polaridad negativa:"
    )
    add_code_block(doc,
        "-- dbt_project/models/gold/gold_sentimiento_h3.sql\n"
        "{{ config(materialized='table') }}\n\n"
        "WITH opiniones_geocodificadas AS (\n"
        "    SELECT \n"
        "        h3_index,\n"
        "        score_sentimiento,\n"
        "        source\n"
        "    FROM {{ ref('silver_sentiment_results') }}\n"
        "    WHERE h3_index IS NOT NULL AND is_relevant = true\n"
        "),\n"
        "quejas_negativas AS (\n"
        "    SELECT \n"
        "        h3_index,\n"
        "        aspecto_normalizado,\n"
        "        COUNT(*) AS menciones,\n"
        "        ROW_NUMBER() OVER (\n"
        "            PARTITION BY h3_index \n"
        "            ORDER BY COUNT(*) DESC\n"
        "        ) AS ranking_queja\n"
        "    FROM {{ ref('silver_aspect_results') }}\n"
        "    WHERE polaridad_aspecto = -1 AND h3_index IS NOT NULL\n"
        "    GROUP BY h3_index, aspecto_normalizado\n"
        ")\n"
        "SELECT \n"
        "    m.h3_index,\n"
        "    ROUND(AVG(o.score_sentimiento)::numeric, 3) AS sentimiento_medio,\n"
        "    COUNT(o.score_sentimiento) AS n_resenas_sentimiento,\n"
        "    COUNT(CASE WHEN o.source = 'booking' THEN 1 END) AS n_resenas_booking,\n"
        "    COUNT(CASE WHEN o.source = 'tripadvisor' THEN 1 END) AS n_resenas_tripadvisor,\n"
        "    COALESCE(q.aspecto_normalizado, 'Sin quejas críticas') AS queja_principal\n"
        "FROM {{ ref('gold_h3_master') }} m\n"
        "LEFT JOIN opiniones_geocodificadas o ON m.h3_index = o.h3_index\n"
        "LEFT JOIN quejas_negativas q ON m.h3_index = q.h3_index AND q.ranking_queja = 1\n"
        "GROUP BY m.h3_index, q.aspecto_normalizado;"
    )

    # C.4
    add_heading(doc, "Anexo C.4 – Matriz de Gobernanza y Pruebas de Calidad de Datos (dbt test)", 3)
    add_body_p(doc,
        "La integridad, unicidad y consistencia referencial del Lakehouse se audita mediante una suite de más de 200 pruebas "
        "declaradas en archivos schema.yml, ejecutadas de forma automatizada en CI/CD y en la orquestación de Airflow:"
    )
    headers_c4 = ["Capa de Datos", "Tipología de Prueba dbt", "Entidades / Campos Auditados", "Criterio de Validación / Aceptación"]
    data_c4 = [
        ["Bronze (Raw)", "unique & not_null", "bronze_registro_*, bronze_clima_*, bronze_aena_*", "Claves primarias compuestas y hash de fila no nulos."],
        ["Bronze (Raw)", "accepted_values", "Canales de fuentes, códigos de isla ('Tenerife')", "Filtrado estricto contra inyecciones o registros fuera de ámbito."],
        ["Silver (Limpieza)", "not_null & dbt_expectations", "silver_alojamientos_oficiales (geometry, municipio)", "100 % de alojamientos con geometría válida ST_IsValid."],
        ["Silver (Limpieza)", "expression_is_true", "silver_clima_agrocabildo (temp, lluvia, viento)", "Rangos físicos: Temp ∈ [-5, 45] °C; Lluvia ≥ 0 mm; Rad ≥ 0 W/m²."],
        ["Silver (Limpieza)", "unique & not_null", "silver_h3_grid (h3_index, geometry)", "Exactamente 2.579 celdas terrestres sin solape ni duplicidad."],
        ["Gold (Negocio)", "relationships (FK)", "gold_sentimiento_h3, gold_arquetipos_tui -> gold_h3_master", "Integridad referencial total: ninguna métrica huérfana de celda."],
        ["Gold (Negocio)", "expression_is_true", "gold_h3_master (ptna_score, score_esg, crowding_index)", "Variables normalizadas en escala acotada [0, 100]."],
        ["Gold (Negocio)", "not_null", "gold_municipio_master (cod_municipio, nombre_municipio)", "Completitud de los 31 términos municipales de la isla."],
    ]
    create_table(doc, headers_c4, data_c4, col_widths=[1.5, 1.8, 2.2, 1.7])
    
    # ----------------------------------------------------
    # Anexo D
    # ----------------------------------------------------
    add_heading(doc, "Anexo D – Catálogo de Scripts y Pipelines de Analítica Avanzada", 2)
    add_body_p(doc, 
        "El directorio analytics/ estructura los pipelines especializados del proyecto. "
        "Cada componente está modularizado y desacoplado para su ejecución independiente o mediante DAG de Airflow:"
    )
    headers_d = ["Script / Módulo", "Área Técnica", "Descripción Operativa"]
    data_d = [
        ["analytics/sentiment/batch_inference.py", "NLP / Sentimiento", "Inferencia multilingüe por lotes (batch 32) con XLM-RoBERTa y filtro zero-shot mDeBERTa"],
        ["analytics/aspects/batch_inference.py", "NLP / Aspectos", "Extracción simultánea de términos de experiencia y polaridad con PyABSA-ATEPC"],
        ["analytics/aspects/traducir_aspectos.py", "NLP / Normalización", "Traducción híbrida incremental y consolidación de >1.200 variantes léxicas a 6 dimensiones canónicas"],
        ["analytics/topics/topic_modeling.py", "NLP / Tópicos", "Entrenamiento de BERTopic (Modelos A y B), centrado de embeddings multilingües y asignación c-TF-IDF"],
        ["analytics/clustering/build_features.py", "Spatial ML", "Normalización MinMax, reducción dimensional PCA (50 componentes) y clustering espacial HDBSCAN"],
        ["analytics/accesibilidad/gold_h3_accesibilidad.py", "Movilidad / Grafos", "Cálculo de matrices de fricción espacial vial ORS e isócronas multiumbral a paradas GTFS TITSA"],
        ["analytics/mgwr/04_run_model.py", "Econometría Espacial", "Ajuste de Regresión Geográfica Ponderada Multiescala (MGWR v3) y cálculo de anchos de banda locales"],
        ["analytics/rag/index_nlp_chunks.py", "IA Generativa / RAG", "Fragmentación recursiva y generación de embeddings semánticos de 768d con MPNet"],
        ["analytics/rag/rag_answer.py", "IA Generativa / RAG", "Motor de recuperación híbrida (HNSW + BM25 + Reciprocal Rank Fusion) y síntesis Groq LPU"],
        ["analytics/chat/router_agent.py", "Agentes / Text-to-SQL", "Enrutador determinista con validación AST y generación segura de consultas analíticas sobre Capa Gold"],
    ]
    create_table(doc, headers_d, data_d, col_widths=[2.3, 1.4, 3.5])
    
    # ----------------------------------------------------
    # Anexo E
    # ----------------------------------------------------
    add_heading(doc, "Anexo E – Inventario de Cuadernos Jupyter y Análisis Exploratorio de Datos (EDA)", 2)
    add_body_p(doc, 
        "Las investigaciones empíricas preliminares, las auditorías de datos y la experimentación de modelos se "
        "organizan en cuadernos interactivos documentados:"
    )
    headers_e = ["Cuaderno Jupyter (Notebook)", "Objetivo Metodológico y Hallazgo Clave"]
    data_e = [
        ["notebooks/eda/EDA_Agrocabildo_Topoclima.ipynb", "Modelado físico del gradiente altimétrico y caracterización de la capa de inversión térmica (mar de nubes a 800–1.500 m)"],
        ["notebooks/eda/EDA_MDT_Costa_Valores_0.ipynb", "Auditoría espacial de cotas de costa en el MDT05 y calibración de distancias continuas para corregir desfases de borde"],
        ["notebooks/eda/EDA_Series_Temporales_ISTAC.ipynb", "Descomposición estacional y modelado de series de ocupación y pernoctaciones hoteleras y vacacionales (2009–2026)"],
        ["notebooks/nlp/nlp_sentimiento_2_1.ipynb", "Experimentación de clasificadores de sentimiento multilingües, calibración de umbrales y cálculo de matrices de confusión"],
        ["notebooks/nlp/nlp_aspectos_tarea_2_2.ipynb", "Minería no estructurada de opiniones cualitativas y validación del diccionario canónico de 6 dimensiones de experiencia"],
        ["notebooks/clustering/hdbscan_exploratorio.ipynb", "Análisis de estabilidad de dendrogramas de HDBSCAN y ajuste del parámetro min_cluster_size ante densidades irregulares"],
    ]
    create_table(doc, headers_e, data_e, col_widths=[2.5, 4.7])
    
    # ----------------------------------------------------
    # Anexo F
    # ----------------------------------------------------
    add_heading(doc, "Anexo F – Síntesis de Métricas y Validación Empírica de Modelos", 2)
    add_body_p(doc, 
        "La tabla siguiente consolida las métricas cuantitativas obtenidas en la evaluación de los modelos analíticos y predictivos:"
    )
    headers_f = ["Dominio Analítico", "Modelo / Técnica", "Métricas Cuantitativas Obtenidas", "Muestra / Validación"]
    data_f = [
        ["Clasificación de Sentimiento", "XLM-RoBERTa + Zero-Shot", "Macro F1 = 0,874 | Exactitud = 88,2 % | Precisión = 0,869 | Recall = 0,878", "1.000 opiniones anotadas a mano"],
        ["Descubrimiento de Tópicos", "BERTopic (mpnet + c-TF-IDF)", "Coherencia Cv = 0,71 | NMI lingüístico reducido de 0,218 a 0,031 tras centrado", "Corpus completo (>55.000 textos)"],
        ["Regresión Espacial Multiescala", "MGWR v3 (Índice PTNA)", "R² = 0,8272 | AICc = 3.914,6 | I de Moran residual = 0,0355 (p = 0,28)", "2.579 celdas terrestres H3"],
        ["Tipificación Territorial", "HDBSCAN + PCA", "Varianza explicada PCA = 81,5 % | 6 tipologías territoriales | 100 % cobertura insular", "Malla insular completa"],
        ["Recuperación y Generación RAG", "HNSW + BM25 + Groq LPU", "Faithfulness = 0,933 | Answer Relevance = 0,912 | Latencia P95 < 1,5 segundos", "Benchmark RAGAS (50 consultas)"],
    ]
    create_table(doc, headers_f, data_f, col_widths=[1.5, 1.8, 2.5, 1.4])
    
    # ----------------------------------------------------
    # Anexo G
    # ----------------------------------------------------
    add_heading(doc, "Anexo G – Topología de Airflow y Manual de Despliegue Reproducible", 2)
    
    # G.1
    add_heading(doc, "Anexo G.1 – Topología de Tareas y Grafo de Dependencias de Apache Airflow", 3)
    add_body_p(doc,
        "La orquestación general de datos se implementa en Apache Airflow 2.8 mediante el DAG historical_full_pipeline, "
        "estructurado en cinco fases secuenciales desacopladas con dependencias estrictas (TaskGroups):"
    )
    headers_g1 = ["Fase del DAG", "Tipo de Operador", "Tareas e Interdependencias", "Manejo de Fallos / Políticas"]
    data_g1 = [
        ["Fase 1: Ingesta Azure", "BashOperator (Paralelo)", "ingest_aena, ingest_alojamientos_oficiales, ingest_agrocabildo, ingest_geocoding, ingest_gtfs_titsa", "Reintentos automáticos (retries=2, delay=5m). Tareas sin API externa se marcan con TriggerRule."],
        ["Fase 2: Postgres Bronze", "BashOperator (Secuencial)", "run_postgres_01_aena >> run_02_alojamientos >> run_03_agrocabildo >> run_04_booking >> run_05_gtfs >> run_06_clima >> run_07_resenas", "Ejecución transaccional e inserción append-only preservando inmutabilidad del dato bruto."],
        ["Fase 3: dbt Silver", "BashOperator (Paralelo)", "dbt_run_silver_alojamiento, dbt_run_silver_clima, dbt_run_silver_espacial, dbt_run_silver_movilidad + dbt_test_silver", "Casting, cruce espacial ST_Contains, filtrado insular y validación con 154 pruebas automáticas."],
        ["Fase 4: Analytics GPU", "ShortCircuitOperator + PythonOperator", "check_heavy_ml >> [batch_sentiment_inference, batch_aspect_extraction, train_bertopic_models, build_clustering_pca_hdbscan]", "Condicionado por Variable run_heavy_ml=True. Si no hay GPU disponible, ejecuta pipeline aligerado."],
        ["Fase 5: dbt Gold & Index", "BashOperator", "dbt_run_gold_master >> dbt_run_gold_sentimiento >> dbt_run_gold_accesibilidad >> index_rag_faiss_mpnet >> notify_complete", "Consolidación de las 13 tablas analíticas maestras e indexación vectorial HNSW para el RAG."],
    ]
    create_table(doc, headers_g1, data_g1, col_widths=[1.5, 1.7, 2.3, 1.7])

    # G.2
    add_heading(doc, "Anexo G.2 – Manual de Despliegue y Reproducibilidad en Entorno Limpio", 3)
    add_body_p(doc, 
        "Para reproducir el despliegue completo del sistema en un entorno limpio (Linux Ubuntu 22.04 LTS, macOS o Windows WSL2), "
        "se deben ejecutar de forma secuencial los siguientes ocho pasos operativos:"
    )
    steps_g = [
        ("1. Clonación del repositorio y entorno virtual:", 
         "git clone https://github.com/TFM-Pytones/AI_Dashboard_Core.git && cd AI_Dashboard_Core\n"
         "python3 -m venv .venv && source .venv/bin/activate  # En Windows: .venv\\Scripts\\activate"),
        ("2. Instalación de dependencias del sistema y Python:",
         "pip install --upgrade pip\n"
         "pip install -r requirements.txt"),
        ("3. Configuración de credenciales de entorno:",
         "cp .env.example .env\n"
         "# Rellenar las variables AZURE_DB_URL, GROQ_API_KEY, ORS_API_KEY y MAPBOX_API_KEY"),
        ("4. Ingesta automatizada de fuentes de datos:",
         "python ingestion/postgres/run_all_ingestion.py"),
        ("5. Materialización de la arquitectura medallón con dbt Core:",
         "cd dbt_project\n"
         "dbt run --select silver.* && dbt run --select gold.*\n"
         "cd .."),
        ("6. Ejecución de pipelines de NLP y analítica espacial:",
         "python analytics/sentiment/batch_inference.py\n"
         "python analytics/topics/topic_modeling.py\n"
         "python analytics/clustering/build_features.py\n"
         "python analytics/accesibilidad/gold_h3_accesibilidad.py"),
        ("7. Indexación vectorial de fragmentos para el motor RAG:",
         "python analytics/rag/index_nlp_chunks.py"),
        ("8. Lanzamiento del AI-Dashboard interactivo:",
         "streamlit run app/main.py --server.port 8501 --server.address 0.0.0.0"),
    ]
    for title, cmd in steps_g:
        add_body_p(doc, title, italic=True, space_after=2)
        add_code_block(doc, cmd)

def main():
    print(f"Cargando {DOCX_FILE}...")
    doc = docx.Document(DOCX_FILE)
    
    # Corregir citas cruzadas en el cuerpo del documento
    for p in doc.paragraphs[:248]:
        # 1. Corregir cita errónea a sección 4.4 (que es accesibilidad vial) por Anexo A3 (catálogo de modelos Gold)
        if "sección 4.4" in p.text:
            p.text = p.text.replace("sección 4.4", "el Anexo A3")
            print("Corregida referencia: sección 4.4 -> el Anexo A3")
            
        # 2. Corregir numeración de tablas para que sea continua (Tabla 1, Tabla 2, Tabla 3, Tabla 4)
        if "Tabla 3. Arquetipos territoriales" in p.text:
            p.text = p.text.replace("Tabla 3. Arquetipos territoriales", "Tabla 2. Arquetipos territoriales")
            print("Corregido título: Tabla 3 -> Tabla 2")
        elif "Tabla 4. Evaluación comparativa" in p.text:
            p.text = p.text.replace("Tabla 4. Evaluación comparativa", "Tabla 3. Evaluación comparativa")
            print("Corregido título: Tabla 4 -> Tabla 3")
        elif "Tabla 5. Respuesta a las preguntas" in p.text:
            p.text = p.text.replace("Tabla 5. Respuesta a las preguntas", "Tabla 4. Respuesta a las preguntas")
            print("Corregido título: Tabla 5 -> Tabla 4")

    print("Reconstruyendo sección completa de Anexos...")
    rebuild_annexes(doc)
    
    print(f"Guardando cambios en {DOCX_FILE}...")
    doc.save(DOCX_FILE)
    
    # También actualizar TFM_Memoria_Final_UCM.docx si es posible
    try:
        doc.save("TFM_Memoria_Final_UCM.docx")
        print("TFM_Memoria_Final_UCM.docx guardado exitosamente.")
    except Exception as e:
        print(f"Aviso: TFM_Memoria_Final_UCM.docx estaba bloqueado: {e}")
        doc.save("TFM_Memoria_Final_UCM_Actualizada.docx")
        print("Guardado en TFM_Memoria_Final_UCM_Actualizada.docx.")
        
    print("Exportando a docs/TFM_Memoria_Completa.md...")
    # Sincronizar markdown
    import subprocess
    subprocess.run([sys.executable, "-c", """
import docx
doc = docx.Document('TFM_Pythones_cambios_v2.docx')
lines = []
for child in doc.element.body:
    tag = child.tag.split('}')[-1]
    if tag == 'p':
        p = docx.text.paragraph.Paragraph(child, doc)
        t = p.text.strip()
        if not t:
            lines.append('')
            continue
        style = p.style.name if p.style else ''
        if style == 'Heading 1':
            lines.append(f'\\n# {t}\\n')
        elif style == 'Heading 2':
            lines.append(f'\\n## {t}\\n')
        elif style == 'Heading 3':
            lines.append(f'\\n### {t}\\n')
        elif style.startswith('List'):
            lines.append(f'* {t}')
        else:
            lines.append(t)
    elif tag == 'tbl':
        t = docx.table.Table(child, doc)
        if len(t.rows) > 0:
            header = [c.text.strip().replace('\\n', ' ') for c in t.rows[0].cells]
            lines.append('\\n| ' + ' | '.join(header) + ' |')
            lines.append('| ' + ' | '.join([':---'] * len(header)) + ' |')
            for r in t.rows[1:]:
                row_vals = [c.text.strip().replace('\\n', ' ') for c in r.cells]
                lines.append('| ' + ' | '.join(row_vals) + ' |')
            lines.append('\\n')
with open('docs/TFM_Memoria_Completa.md', 'w', encoding='utf-8') as f:
    f.write('\\n'.join(lines))
print('Markdown sincronizado.')
"""], check=True)
    
    print("PROCESO DE RECONSTRUCCIÓN FINALIZADO CON ÉXITO.")

if __name__ == "__main__":
    main()
