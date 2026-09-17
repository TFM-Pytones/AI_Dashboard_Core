import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import parse_xml

doc = docx.Document()

# Page Setup: A4, 2.5 cm margins
for section in doc.sections:
    section.top_margin = Inches(1)
    section.bottom_margin = Inches(1)
    section.left_margin = Inches(1)
    section.right_margin = Inches(1)

normal_style = doc.styles['Normal']
normal_style.font.name = 'Verdana'
normal_style.font.size = Pt(10)
normal_style.font.color.rgb = RGBColor(40, 40, 40)
normal_style.paragraph_format.line_spacing = 1.15
normal_style.paragraph_format.space_after = Pt(6)

def add_h1(text):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(16)
    p.paragraph_format.space_after = Pt(6)
    p.paragraph_format.keep_with_next = True
    run = p.add_run(text)
    run.font.name = 'Verdana'
    run.font.size = Pt(13)
    run.font.bold = True
    run.font.color.rgb = RGBColor(16, 44, 87)
    return p

def add_h2(text):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(12)
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.keep_with_next = True
    run = p.add_run(text)
    run.font.name = 'Verdana'
    run.font.size = Pt(11)
    run.font.bold = True
    run.font.color.rgb = RGBColor(16, 44, 87)
    return p

def add_body(text):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(6)
    p.paragraph_format.line_spacing = 1.15
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    run = p.add_run(text)
    run.font.name = 'Verdana'
    run.font.size = Pt(10)
    run.font.color.rgb = RGBColor(40, 40, 40)
    return p

def add_bullet(bold_prefix, text):
    p = doc.add_paragraph(style='List Bullet')
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.line_spacing = 1.15
    run_b = p.add_run(bold_prefix)
    run_b.font.name = 'Verdana'
    run_b.font.size = Pt(10)
    run_b.font.bold = True
    run_b.font.color.rgb = RGBColor(30, 30, 30)
    run_t = p.add_run(text)
    run_t.font.name = 'Verdana'
    run_t.font.size = Pt(10)
    run_t.font.color.rgb = RGBColor(50, 50, 50)
    return p

# Chapter 4
add_h1('4. Inteligencia Territorial, Modelado Espacio-Temporal y Machine Learning')

add_h2('4.1. Doble escala analítica: Malla H3 maestra y modelos agregados municipales')
add_body('Para articular una toma de decisiones informada en TUI Group, el sistema combina simultáneamente dos niveles complementarios de agregación espacial:')
add_bullet('Escala micro-territorial (Malla H3 Resolución 8): ', 'Articulada sobre gold_h3_master, unifica en las 2.579 celdas terrestres limpias (~0,85 km² y 461 m de apotema) más de sesenta covariables biofísicas, microclimáticas, de conectividad vial, oferta reglada y reputación online. Esta resolución micro permite evaluar la viabilidad de producto en un barranco o núcleo rural específico sin arrastrar los sesgos del promedio comarcal.')
add_bullet('Escala macro-estratégica (Ámbito municipal): ', 'La suite liderada por gold_municipio_master (junto a sus modelos anuales, mensuales y de empleo) agrega los indicadores socioeconómicos del ISTAC y el tráfico aéreo de AENA para los 31 términos municipales. Esta perspectiva macro facilita el seguimiento de KPIs corporativos, la correlación de pernoctaciones con el PIB comarcal y el diálogo con las administraciones públicas.')

add_h2('4.2. Análisis de sentimiento multilingüe e inferencia por lotes')
add_body('El corpus cualitativo recopilado presentaba un doble desafío: un elevado volumen de comentarios irrelevantes (conversaciones personales, autopromoción o mensajes vacíos) y una diversidad lingüística acusada (español, inglés, alemán, francés e italiano). Para resolverlo con rigor metodológico y eficiencia operativa, se implementó un pipeline en dos etapas:')
add_bullet('Filtro de relevancia zero-shot: ', 'El modelo transformador multilingüe MoritzLaurer/mDeBERTa-v3-base-mnli-xnli evalúa la semántica de cada texto frente a hipótesis contextualizadas sobre viajes, alojamiento y sostenibilidad en Canarias. Solo los documentos con un margen de confianza favorable superior a 0,25 acceden a la fase de inferencia.')
add_bullet('Clasificación de polaridad con XLM-RoBERTa: ', 'Los textos filtrados se procesan mediante el checkpoint cardiffnlp/twitter-xlm-roberta-base-sentiment, optimizado para lenguaje informal y jerga de redes. El modelo genera una distribución de probabilidades (positivo, neutro, negativo) que se sintetiza en una puntuación continua de polaridad. La inferencia se ejecuta de forma incremental por lotes de 32 documentos en GPU, alcanzando un Macro F1 de 0,874 y una exactitud global del 88,2 % sobre muestras de validación (Anexo F).')

add_h2('4.3. Descubrimiento no supervisado de tópicos y minería de aspectos')
add_body('Para desentrañar los factores latentes de satisfacción e insatisfacción sin imponer categorías predefinidas, el proyecto combinó dos enfoques complementarios:')
add_bullet('Modelado de tópicos con BERTopic: ', 'Mediante embeddings multilingües de 768 dimensiones (paraphrase-multilingual-mpnet-base-v2), reducción UMAP y clustering jerárquico c-TF-IDF, se articularon dos variantes: el Modelo A (visión macro insular sobre YouTube y foros, aislando debates clave sobre atascos en la TF-1/TF-5, masificación costera y gastronomía en guachinches) y el Modelo B (micro-geolocalizado sobre Booking y TripAdvisor, vinculando temáticas a hexágonos concretos).')
add_bullet('Extracción de aspectos y polaridad con PyABSA: ', 'El modelo multilingüe ATEPC detecta simultáneamente términos de experiencia (limpieza, servicio, relación calidad-precio, ubicación, ruido e instalaciones) y su sentimiento asociado. Mediante la tabla de mapeo gold.aspecto_traducciones se armonizan más de 1.200 expresiones en seis dimensiones canónicas, permitiendo que gold_sentimiento_h3 calcule la queja principal de cada celda filtrando estrictamente menciones negativas (Anexo C.3).')

add_h2('4.4. Caracterización físico-territorial, teledetección y modelado microclimático')
add_body('Para asegurar que las propuestas de redistribución respondan a la realidad biofísica del territorio, el sistema articula tres componentes analíticos:')
add_bullet('Teledetección satelital de vigor y huella antrópica: ', 'A partir de 30 composites trimestrales de Copernicus Sentinel-2 L2A (20 m) procesados en Google Earth Engine con triple filtro anti-calima y nubes, se derivaron las series de NDVI (vigor fotosintético, de 0,08 en malpaíses a 0,82 en Anaga) y NDBI (suelo construido). La serie se complementó con la radianza nocturna calibrada de NOAA/NASA VIIRS DNB (500 m) como indicador de presión turística nocturna.')
add_bullet('Modelado topoclimático físico insular: ', 'Integrando las 67 estaciones automáticas de Agrocabildo mediante interpolación IDW cuadrática (k=3), se incorporaron correcciones físicas reales: (1) gradiente adiabático vertical de temperatura (-0,0065 °C/m); (2) factor de humedad por inversión térmica del Mar de Nubes entre 800 y 1.500 m (+25 % humedad en barlovento); y (3) efecto Föhn y sombra de lluvia en sotavento (-15 % humedad, -60 % precipitación), ajustando la climatología a la orografía insular (Anexo C.2).')

add_h2('4.5. Segmentación espacial no supervisada: Arquetipos con HDBSCAN')
add_body('La tipificación territorial se formuló con HDBSCAN (Hierarchical Density-Based Spatial Clustering of Applications with Noise), antecedido por un análisis de componentes principales (PCA) que condensa el 81 % de la varianza en tres dimensiones no redundantes (n_plazas_log, viirs_log, ndvi, ndbi, altitud, pendiente, distancia a costa y porcentaje de espacio natural protegido). Los parámetros óptimos (min_cluster_size = 30, min_samples = 10) permiten segmentar el territorio aislando celdas de ruido geográfico.')

# Table 3
p_t3 = doc.add_paragraph()
p_t3.paragraph_format.space_before = Pt(8)
p_t3.paragraph_format.space_after = Pt(4)
p_t3.paragraph_format.keep_with_next = True
r_t3 = p_t3.add_run('Tabla 3. Arquetipos territoriales identificados con HDBSCAN y directrices para TUI Group')
r_t3.font.name = 'Verdana'
r_t3.font.size = Pt(9.5)
r_t3.font.bold = True
r_t3.font.color.rgb = RGBColor(16, 44, 87)

t3_data = [
    ['Arquetipo Territorial', 'Perfil Físico y Turístico', 'Municipios Representativos', 'Directriz Estratégica para TUI'],
    ['Polos Maduros Concentrados', 'Máxima densidad alojativa (>1.850 pl/km²), alta radianza VIIRS (>50 nW), queja dominante de ruido y masificación.', 'Adeje, Arona, Playa de las Américas', 'Contener nueva contratación alojativa; priorizar descongestión de accesos y certificar hoteles en sostenibilidad.'],
    ['Presión Urbana Intermedia', 'Densidad media-alta, excelente dotación de servicios y transporte, función mixta residencial-turística.', 'Puerto de la Cruz, Santa Cruz, La Laguna', 'Desarrollar producto cultural, rutas gastronómicas urbanas y desestacionalizar la planta hotelera tradicional.'],
    ['Oportunidad Rural / Activa', 'Elevado NDVI (>0,60), clima templado (18–22 °C), alta valoración cualitativa y bajísima densidad actual (<15 pl/km²).', 'Icod, Buenavista, Vilaflor, Garachico, Arico', 'Foco prioritario de inversión: contratación de casas rurales, trekking botánico y ecoturismo de alto margen.'],
    ['Protección y Exclusión', 'Pendientes abruptas (>25°), alta cota (>1.500 m), régimen estricto de protección ambiental (ENP / Red Natura).', 'Parque Nacional del Teide, Corona Forestal, Anaga, Teno', 'Exclusión absoluta de nueva oferta alojativa; comercializar únicamente excursiones guiadas de bajo impacto.']
]

table3 = doc.add_table(rows=len(t3_data), cols=4)
table3.alignment = WD_TABLE_ALIGNMENT.CENTER
t3_widths = [Inches(1.5), Inches(2.2), Inches(1.5), Inches(2.2)]

for r_idx, row in enumerate(table3.rows):
    for c_idx, cell in enumerate(row.cells):
        cell.width = t3_widths[c_idx]
        cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        tcPr = cell._tc.get_or_add_tcPr()
        p = cell.paragraphs[0]
        p.paragraph_format.space_before = Pt(2)
        p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.line_spacing = 1.05
        run = p.add_run(t3_data[r_idx][c_idx])
        run.font.name = 'Verdana'
        if r_idx == 0:
            shd = parse_xml('<w:shd xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" w:fill="102C57"/>')
            tcPr.append(shd)
            run.font.bold = True
            run.font.size = Pt(8.5)
            run.font.color.rgb = RGBColor(255, 255, 255)
        else:
            run.font.size = Pt(8.0)
            run.font.color.rgb = RGBColor(40, 40, 40)
            if r_idx % 2 == 1:
                shd = parse_xml('<w:shd xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" w:fill="F4F6F9"/>')
                tcPr.append(shd)

add_h2('4.6. Modelado de accesibilidad territorial: Isócronas y fricción de red')
add_body('La viabilidad operativa de descongestionar la costa reside en la accesibilidad real. En una isla dominada por barrancos y calzadas sinuosas, las distancias euclídeas resultan engañosas; por ello, el sistema computó matrices de viaje por carretera mediante el motor OpenRouteService (ORS) desde cada celda H3 hacia 18 destinos estratégicos (aeropuertos TFS/TFN, Teide, polos costeros y cabeceras de comarca). Esto se integró con la red de transporte público GTFS (conteo de paradas a 200 m, 500 m y 1.000 m) y la proximidad al centro hospitalario comarcal más cercano en PostGIS, generando isócronas de 15, 30, 45 y 60 minutos consolidadas en gold_h3_accesibilidad.')

add_h2('4.7. Regresión geográfica ponderada multiescala (MGWR) e Índice PTNA')
add_body('Los modelos lineales globales (OLS) asumen erróneamente que las relaciones territoriales son homogéneas en toda la isla. Sin embargo, lo que condiciona la satisfacción o demanda en un resort costero de Adeje difiere radicalmente de los atractores de una estancia rural en Vilaflor. La Regresión Geográfica Ponderada Multiescala (MGWR) resuelve esta no-estacionariedad estimando anchos de banda locales específicos por variable: hiperlocales para la distancia a costa (bw=85 celdas), intermedios para la vegetación (bw=240) y de escala comarcal para la accesibilidad al aeropuerto (bw=820).')
add_body('El ajuste de MGWR elevó el R² de 0,418 (OLS) a 0,782 y eliminó la autocorrelación espacial residual (I de Moran = 0,041, p = 0,28). A partir de estos coeficientes locales se formuló el Índice PTNA (Potential Tourism Niche Attraction, escala 0–100), que cuantifica el diferencial entre las condiciones objetivas de una celda (atractivo ambiental, confort térmico y accesibilidad <45 min) y su oferta actual: puntuaciones superiores a 70 identifican las micro-zonas prioritarias de inversión para TUI en medianías del norte y valles del sureste.')

add_h2('4.8. Evaluación técnica comparativa frente a metodologías alternativas')
add_body('En coherencia con los criterios de evaluación de la Universidad Complutense, la arquitectura algorítmica se seleccionó tras contrastar su rendimiento frente a enfoques tradicionales:')

# Table 4
p_t4 = doc.add_paragraph()
p_t4.paragraph_format.space_before = Pt(8)
p_t4.paragraph_format.space_after = Pt(4)
p_t4.paragraph_format.keep_with_next = True
r_t4 = p_t4.add_run('Tabla 4. Evaluación comparativa de técnicas de modelización frente a alternativas descartadas')
r_t4.font.name = 'Verdana'
r_t4.font.size = Pt(9.5)
r_t4.font.bold = True
r_t4.font.color.rgb = RGBColor(16, 44, 87)

t4_data = [
    ['Técnica Seleccionada', 'Tarea / Dominio', 'Métricas Clave Obtenidas', 'Ventaja Diferencial de Negocio', 'Riesgo Técnico / Mitigación', 'Alternativa Descartada y Justificación'],
    [
        'XLM-RoBERTa + mDeBERTa Zero-Shot',
        'Filtro de relevancia y polaridad de reseñas',
        'Macro F1 = 0,874; Exactitud = 88,2 %',
        'Inferencia multilingüe real (ES/EN/DE) sensible a sintaxis de redes sociales.',
        'Coste computacional en GPU mitigado por procesamiento por lotes de 32 textos.',
        'VADER / TextBlob: descartados por depender de diccionarios estáticos sin contexto ni soporte multilingüe.'
    ],
    [
        'BERTopic (UMAP + c-TF-IDF)',
        'Descubrimiento no supervisado de tópicos',
        'Coherencia semántica = 0,71 (14 tópicos insulares)',
        'Extracción dinámica de quejas y atractores sin fijar listas cerradas previas.',
        'Sensibilidad a textos breves mitigada agrupando por hilo y filtrando por longitud.',
        'LDA (Latent Dirichlet Allocation): descartado por pobre rendimiento ante textos coloquiales cortos.'
    ],
    [
        'HDBSCAN (con PCA)',
        'Tipificación territorial de 2.579 celdas H3',
        'Silhouette = 0,582; Varianza PCA = 81,4 %',
        'Detecta morfologías arbitrarias y aísla ruido geográfico sin imponer clústeres artificiales.',
        'Calibración de min_cluster_size optimizada mediante análisis de estabilidad de dendrograma.',
        'K-Means: descartado por forzar clústeres esféricos de igual tamaño, distorsionando la geografía insular.'
    ],
    [
        'MGWR Multiescala',
        'Determinantes espaciales y cálculo del PTNA',
        'R² = 0,782; AICc = 3.914,6; Moran I = 0,041',
        'Asigna anchos de banda locales independientes por variable, capturando microclimas y economías.',
        'Riesgo de colinealidad local controlado mediante filtrado estricto de VIF < 5.',
        'OLS Global (R² = 0,418, Moran I = 0,472): descartado por sesgo espacial severo e hipótesis homogénea falsa.'
    ]
]

table4 = doc.add_table(rows=len(t4_data), cols=6)
table4.alignment = WD_TABLE_ALIGNMENT.CENTER
t4_widths = [Inches(1.3), Inches(1.1), Inches(1.3), Inches(1.5), Inches(1.3), Inches(1.5)]

for r_idx, row in enumerate(table4.rows):
    for c_idx, cell in enumerate(row.cells):
        cell.width = t4_widths[c_idx]
        cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        tcPr = cell._tc.get_or_add_tcPr()
        p = cell.paragraphs[0]
        p.paragraph_format.space_before = Pt(2)
        p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.line_spacing = 1.05
        run = p.add_run(t4_data[r_idx][c_idx])
        run.font.name = 'Verdana'
        if r_idx == 0:
            shd = parse_xml('<w:shd xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" w:fill="102C57"/>')
            tcPr.append(shd)
            run.font.bold = True
            run.font.size = Pt(8.5)
            run.font.color.rgb = RGBColor(255, 255, 255)
        else:
            run.font.size = Pt(8.0)
            run.font.color.rgb = RGBColor(40, 40, 40)
            if r_idx % 2 == 1:
                shd = parse_xml('<w:shd xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" w:fill="F4F6F9"/>')
                tcPr.append(shd)

doc.save('docs/capitulo_4_modelos_word.docx')
print('Successfully saved docs/capitulo_4_modelos_word.docx')
