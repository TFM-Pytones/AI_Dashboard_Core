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
    run.font.size = Pt(12.5)
    run.font.bold = True
    run.font.color.rgb = RGBColor(16, 44, 87)
    return p

def add_h2(text):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(11)
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.keep_with_next = True
    run = p.add_run(text)
    run.font.name = 'Verdana'
    run.font.size = Pt(10.5)
    run.font.bold = True
    run.font.color.rgb = RGBColor(16, 44, 87)
    return p

def add_h3(text):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(8)
    p.paragraph_format.space_after = Pt(3)
    p.paragraph_format.keep_with_next = True
    run = p.add_run(text)
    run.font.name = 'Verdana'
    run.font.size = Pt(10)
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

# ==========================================
# CAPÍTULO 4
# ==========================================
add_h1('4. Inteligencia Territorial, Modelado Microclimático y Machine Learning Espacial')

add_h2('4.1. Doble escala analítica: Malla canónica H3 y agregación municipal')
add_body('Para articular una toma de decisiones informada en TUI Group, el sistema combina simultáneamente dos niveles complementarios de agregación espacial:')
add_bullet('Escala micro-territorial (Malla H3 Resolución 8): ', 'Articulada sobre gold_h3_master, unifica en las 2.579 celdas terrestres limpias (~0,85 km² y 461 m de apotema) más de sesenta covariables biofísicas, microclimáticas, de conectividad vial, oferta reglada y reputación online. Esta resolución micro permite evaluar la viabilidad de producto en un barranco o núcleo rural específico sin arrastrar los sesgos del promedio comarcal.')
add_bullet('Escala macro-estratégica (Ámbito municipal): ', 'La suite liderada por gold_municipio_master agrega los indicadores socioeconómicos del ISTAC y el tráfico aéreo de AENA para los 31 términos municipales. Esta perspectiva macro facilita el seguimiento de KPIs corporativos, la correlación de pernoctaciones con el PIB comarcal y el diálogo con las administraciones públicas.')

add_h2('4.2. Caracterización biofísica y teledetección satelital')
add_body('La capacidad de carga y el atractivo ambiental del territorio se parametrizaron mediante teledetección multiespectral y radianza nocturna procesadas en Google Earth Engine (GEE):')
add_bullet('Composites trimestrales Copernicus Sentinel-2 (20 m): ', 'Para superar el bloqueo visual de la «panza de burro» y los episodios de polvo sahariano, se generaron 30 compuestos trimestrales mediante un triple filtro a nivel de píxel (clasificación de escena SCL, aerosol AOT < 0,3 y banda azul B02). De ellos se derivaron el NDVI (vigor vegetal, de 0,08 en lavas áridas a 0,82 en Anaga) y el NDBI (huella de suelo construido), consolidando 46.422 registros limpios en Silver.')
add_bullet('Radianza nocturna NOAA/NASA VIIRS DNB (500 m): ', 'A partir de 90 compuestos mensuales calibrados, se obtuvo un proxy objetivo de presión antrópica y actividad económica nocturna: los polos turísticos saturados del sur superan los 65 nW/(cm²·sr), mientras que las medianías rurales caen por debajo de 4 nW/(cm²·sr).')

add_h2('4.3. Climatología analítica y modelado topoclimático microinsular')
add_body('El clima de Tenerife está gobernado por cuatro forzadores físicos: vientos alisios del noreste, inversión térmica de subsidencia (800–1.500 m), efecto Föhn en sotavento y advecciones de calima sahariana. Para modelar con fidelidad estos microclimas, se articuló en dbt una cadena de inferencia topoclimática sobre las 67 estaciones automáticas de la red de Agrocabildo:')
add_bullet('Interpolación espacial y gradiente térmico: ', 'Se aplicó ponderación por distancia inversa cuadrática (IDW k=3) corregida por gradiente adiabático vertical (-0,0065 °C/m según la cota de la celda respecto a la estación) y amortiguación litoral (Anexo C.2).')
add_bullet('Modelado físico de humedad y precipitación: ', 'Se incorporó un factor de condensación orográfica que eleva la humedad relativa en un +25 % en la franja del Mar de Nubes (800–1.500 m en barlovento) y la reduce en un 30 % en la cumbre seca subsidente (>1.500 m). En sotavento sur se modeló el efecto paraguas orográfico (-15 % humedad, -60 % lluvia), ajustando la climatología interpolada a las singularidades microinsulares de la isla.')

add_h2('4.4. Fricción de red y accesibilidad multimodal')
add_body('La viabilidad de descongestionar el sur depende de la conectividad real por carretera. En una isla de relieve escarpado, las distancias euclídeas resultan engañosas; por ello, el sistema computó matrices de viaje vial mediante OpenRouteService (ORS) desde cada celda H3 hacia 18 destinos estratégicos (aeropuertos TFS/TFN, Teide, núcleos costeros y cabeceras comarcales). Esto se complementó con la cobertura de transporte público regular GTFS (conteo escalonado de paradas TITSA a 200 m, 500 m y 1.000 m) y la distancia al hospital comarcal más cercano, generando isócronas continuas de 15, 30, 45 y 60 minutos en gold_h3_accesibilidad.')

add_h2('4.5. Regresión geográfica ponderada multiescala (MGWR) e Índice PTNA')
add_body('Los modelos de regresión lineal global (OLS) asumen erróneamente que las relaciones territoriales son constantes en toda la isla. Sin embargo, lo que condiciona la satisfacción del turista en un resort de Adeje difiere sustancialmente de lo que busca quien se hospeda en Vilaflor. La Regresión Geográfica Ponderada Multiescala (MGWR) resuelve la no-estacionariedad estimando anchos de banda locales independientes para cada variable explicativa:')
add_bullet('Escalas de operación empíricas: ', 'el modelo final (checkpoint v3, 2579 hexágonos) estimó anchos de banda genuinamente locales para variables como NDVI (bw=198) o altitud (bw=138), mientras que 9 de las 14 variables —entre ellas la distancia a la costa y el tiempo al aeropuerto— saturaron en bw≈2573, un ancho casi insular que el propio modelo señala como pérdida de variación local genuina, no como hallazgo positivo de escala; estos 259 hexágonos (10,0% del total) quedan marcados con confianza_ptna=\'baja\'.')
add_bullet('Bondad de ajuste y diagnóstico espacial: ', 'el MGWR eleva el R² global (no ajustado por grados de libertad efectivos) de 0,5444 (OLS, mismas 14 variables) a 0,8272, y reduce la I de Moran de los residuos de 0,3065 (OLS) a 0,0355, ambas con autocorrelación espacial estadísticamente significativa (p=0,0010 y p=0,0110 respectivamente, permutación con 999 iteraciones) — el MGWR mitiga sustancialmente, pero no elimina por completo, la dependencia espacial residual.')
add_bullet('Índice de Potencial Turístico No Aprovechado (PTNA): ', 'a partir del modelo MGWR ajustado, el PTNA se define como la diferencia entre la densidad de plazas esperada por el modelo y la densidad observada en cada hexágono (ptna_score = predy_MGWR − Y observado). Un valor ptna_score > 0 indica un hexágono con condiciones territoriales objetivamente superiores a su ocupación turística actual (oportunidad de inversión); un ptna_score < 0 señala zonas sobreexplotadas respecto a su vocación territorial (riesgo de overtourism). Los pesos implícitos de cada dimensión territorial no son arbitrarios: son los anchos de banda y coeficientes locales que el propio algoritmo MGWR estimó empíricamente a través de 14 variables explicativas. El filtro combinado PTNA×ESG identifica 247 hexágonos (9,6% del total), de los cuales 22 (8,9%) mantienen confianza_ptna=\'baja\', concentrados en Santa Cruz de Tenerife (34), La Laguna (29), La Orotava (22), Buenavista del Norte (20), El Tanque (19) y Los Realejos (18).')

add_h3('Marco Multidimensional ESG (Environmental, Social, Governance) Territorial y Municipal')
add_body('Para garantizar que la descompresión turística no comprometa la capacidad de carga insular, se diseñó un índice compuesto de sostenibilidad (Score_ESG = 0,40·E + 0,40·S + 0,20·G ∈ [0, 100]) formulado sobre datos públicos abiertos a dos escalas complementarias:')
add_bullet('Dimensión Medioambiental [E] (40 %): ', 'A escala microespacial H3 (gold.gold_h3_esg_v1), pondera vigor vegetal (NDVI y delta 2022-2026), polución lumínica (VIIRS frente a la protección de avifauna), sellado NDBI, protección ambiental (pct_area_enp, distancia a costa) y estrés térmico. A escala mesomunicipal (gold.gold_bloque5_municipio_esg_v1), consolida estos forzadores junto a la superficie protegida municipal.')
add_bullet('Dimensión Social [S] (40 %): ', 'A nivel H3, evalúa la presión alojativa (plazas/km² winsorizada al p95), accesibilidad a servicios esenciales (hospitales, paradas TITSA) y quejas vecinales por ruido o saturación extraídas por NLP. A nivel municipal, mide la vulnerabilidad por dependencia hostelera, desempleo, plazas por 1.000 habitantes y dependencia demográfica (ISTAC 2025).')
add_bullet('Dimensión de Gobernanza [G] (20 %): ', 'A nivel H3, premia la oferta hotelera reglada frente al alquiler vacacional desregulado (hoteles / (hoteles + VV)) y el patrimonio BIC. A nivel municipal, mide la formalización productiva mediante la tasa de afiliación de autónomos (gold.gold_municipio_empleo).')
add_body('El cruce del potencial económico con la solvencia ambiental (ptna_score > 0 y esg_h3_score > 60, umbral empírico adaptado) consolida la tabla gold.gold_bloque5_h3_oportunidad_v1. Este filtro aísla exactamente 247 hexágonos de Oportunidad Ideal (9,6 % de la isla), garantizando para TUI una expansión equilibrada con la cohesión social y ecológica de Tenerife.')


add_h2('4.6. Segmentación territorial no supervisada: Tipologías insulares con HDBSCAN y matriz estratégica')

add_body('Conociendo los forzadores territoriales y el potencial PTNA, se articuló el pipeline oficial de clustering espacial en Python (analytics/clustering/run_hdbscan_clustering.py). La acusada orografía insular y la extrema polarización turística invalidan algoritmos basados en particiones esféricas homogéneas (K-Means) o sin control legal de protección (que en modelos preliminares clasificaban erróneamente el Teide como urbano). El modelo definitivo opera sobre 8 covariables canónicas: plazas alojativas y radianza nocturna VIIRS (estabilizadas con transformación logarítmica log1p para atenuar colas pesadas), NDVI (vigor vegetal), NDBI (huella construida), altitud media, pendiente, distancia a la costa y el porcentaje de superficie en Espacio Natural Protegido (pct_area_enp, variable crítica). Tras estandarización con StandardScaler, un análisis PCA condensa el 81,5 % de la varianza en tres dimensiones no redundantes. La calibración óptima de HDBSCAN (min_cluster_size = 30, min_samples = 10, selección EOM) identificó de forma no supervisada 4 macro-clústeres de densidad (57,3 % del territorio). El 42,7 % restante de celdas de transición y ruido se reasignó mediante reglas de experto territorial: celdas con ≥ 500 plazas pasaron a «Saturado / Overtourism»; celdas con VIIRS ≥ 20 nW/(cm²·sr) y ENP < 20 % se tipificaron como «Urbano Residencial»; y el ruido remanente se absorbió proyectándolo al centroide euclídeo más próximo en el espacio PCA. El resultado consolida seis tipologías territoriales exhaustivas con el 100 % de cobertura insular:')

# Table 3
p_t3 = doc.add_paragraph()
p_t3.paragraph_format.space_before = Pt(8)
p_t3.paragraph_format.space_after = Pt(4)
p_t3.paragraph_format.keep_with_next = True
r_t3 = p_t3.add_run('Tabla 3. Tipologías territoriales identificadas con HDBSCAN, reglas de experto y directrices para TUI Group')
r_t3.font.name = 'Verdana'
r_t3.font.size = Pt(9.5)
r_t3.font.bold = True
r_t3.font.color.rgb = RGBColor(16, 44, 87)

t3_data = [
    ['Tipología Territorial', 'Cobertura y Peso (n / %)', 'Perfil Físico, Biofísico y Turístico', 'Comarcas y Municipios Representativos', 'Directriz Estratégica para TUI Group'],
    [
        'Espacio Natural / Teide y Cumbre',
        '716 celdas\n(27,8 %)',
        'Altitud media ~1.768 m, máxima protección (93 % ENP), radianza VIIRS nula (~0 nW), sustrato volcánico de alta cota.',
        'Parque Nacional del Teide, cumbre central y Corona Forestal alta.',
        'Preservación absoluta y exclusión hotelera; comercialización exclusiva de astroturismo y senderismo diurno de bajo impacto con guías certificados.'
    ],
    [
        'Espacios Rurales Protegidos (Anaga/Teno)',
        '456 celdas\n(17,7 %)',
        'Altitud media ~714 m, relieve muy abrupto (pendiente media ~30°), 87 % ENP, elevado vigor vegetal (NDVI alto), nula planta hotelera masiva.',
        'Macizo de Anaga (Santa Cruz, La Laguna), Parque Rural de Teno (Buenavista, Santiago del Teide).',
        'Ecoturismo botánico y senderismo regulado de residuo cero; valorización del patrimonio etnográfico sin nuevas edificaciones.'
    ],
    [
        'Transición Costera y Medianías',
        '895 celdas\n(34,7 %)',
        'Altitud media ~328 m, baja protección (8 % ENP), radianza VIIRS moderada (4,9 nW), posición bisagra entre el litoral y la cumbre.',
        'Corredores periurbanos y medianías bajas de Granadilla, San Miguel, Güímar, Fasnia y Candelaria.',
        'Vector de descompresión territorial; desarrollo de productos híbridos de media montaña, enoturismo y desvío de flujos excursionistas.'
    ],
    [
        'Rural Agrícola / Medianías Norte',
        '412 celdas\n(16,0 %)',
        'Altitud media ~490 m, alto verdor y humedad (elevado NDVI), baja edificación (NDBI bajo), VIIRS bajo (4,8 nW), clima templado con influencia atlántica.',
        'Medianías de Icod de los Vinos, La Orotava, Los Realejos, Garachico, Buenavista del Norte, Tacoronte.',
        'Foco prioritario de inversión y diversificación de TUI: micro-hoteles boutique rurales, agroturismo, rutas gastronómicas de guachinches y estancias de desconexión.'
    ],
    [
        'Saturado / Overtourism\n(Regla experto ≥500 pl.)',
        '61 celdas\n(2,4 %)',
        'Cota litoral (~71 m), hiperdensidad de camas (>500 pl/celda, >1.850 pl/km²), alta radianza VIIRS (~28 nW), queja dominante de masificación y ruido en NLP.',
        'Playa de las Américas, Los Cristianos, Costa Adeje (Adeje, Arona) y frente litoral maduro de Puerto de la Cruz.',
        'Moratoria y contención estricta de camas; reconversión de planta existente hacia estándares sostenibles (Travelife), elevación de ADR y redistribución de clientes.'
    ],
    [
        'Urbano Residencial\n(Regla experto VIIRS≥20)',
        '39 celdas\n(1,5 %)',
        'Máxima radianza económica (>41 nW promedio), 0 % ENP, elevada huella de suelo construido (NDBI), funciones residenciales y de servicios metropolitanos.',
        'Casco urbano consolidado de Santa Cruz de Tenerife y San Cristóbal de La Laguna.',
        'Turismo cultural urbano, patrimonio UNESCO, rutas gastronómicas metropolitanas y eventos corporativos MICE, protegiendo el parque residencial.'
    ]
]

table3 = doc.add_table(rows=len(t3_data), cols=5)
table3.alignment = WD_TABLE_ALIGNMENT.CENTER
t3_widths = [Inches(1.4), Inches(1.0), Inches(1.8), Inches(1.4), Inches(1.9)]

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
            run.font.size = Pt(8.0)
            run.font.color.rgb = RGBColor(255, 255, 255)
        else:
            run.font.size = Pt(7.5)
            run.font.color.rgb = RGBColor(40, 40, 40)
            if r_idx % 2 == 1:
                shd = parse_xml('<w:shd xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" w:fill="F4F6F9"/>')
                tcPr.append(shd)

add_body('Para transformar este diagnóstico territorial discreto en prescripciones accionables de negocio para TUI Group, los 2.579 hexágonos se proyectan en una matriz continua bidimensional: el Eje 1 (Saturación Turística [0–1], calibrado según plazas, VIIRS, proximidad litoral y densidad hotelera) frente al Eje 2 (Potencial Rural y Sostenible [0–1], que integra el índice PTNA derivado de MGWR, NDVI vegetal, ausencia de suelo sellado y gobernanza climática ESG). Este cruce analítico permite prescribir a cada microzona insular uno de los 5 Arquetipos de Producto Turístico de TUI (Sol y Playa Premium, Ecoturismo Rural y Medianías, Cultural y Patrimonial, Aventura y Turismo Activo, y Bienestar/Wellness), los cuales se explotan interactivamente en la vista de «Oportunidades TUI» del AI-Dashboard.')

# ==========================================
# CAPÍTULO 5
# ==========================================
add_h1('5. Procesamiento del Lenguaje Natural (NLP) y Percepción de Marca Destino')

add_h2('5.1. Inferencia multilingüe de polaridad afectiva por lotes')
add_body('El análisis cualitativo procesó un corpus de más de 55.000 opiniones procedentes de cuatro fuentes complementarias (Booking, TripAdvisor, YouTube y LosViajeros) en cinco idiomas principales (español, inglés, alemán, francés e italiano). Para maximizar la fidelidad analítica y optimizar el rendimiento computacional, el pipeline oficial (analytics/sentiment/batch_inference.py) articula un flujo desacoplado según la naturaleza estructurada o abierta de la fuente:')
add_bullet('Filtro de relevancia zero-shot para redes sociales: ', 'Aplicado específicamente sobre los comentarios de YouTube mediante el transformador MoritzLaurer/mDeBERTa-v3-base-mnli-xnli. Evalúa cada texto frente a cuatro hipótesis contextuales (una sobre turismo y tres de ruido: video/canal, charla personal y spam). Se descartan automáticamente aquellas aportaciones que no superen al ruido por un margen de confianza favorable mayor a 0,25. Las reseñas regladas de Booking y TripAdvisor, al constituir valoraciones verificadas de estancias, no requieren este filtro y pasan directamente a inferencia.')
add_bullet('Inferencia de polaridad y calificación continua: ', 'Los comentarios depurados de YouTube son clasificados mediante cardiffnlp/twitter-xlm-roberta-base-sentiment en 3 clases discretas (positivo, neutro y negativo) por lotes de 32 documentos, alcanzando en validación manual frente a 1.000 reseñas un Macro F1 de 0,874 y una exactitud global del 88,2 % (Anexo F). Paralelamente, las reseñas de alojamiento de Booking y TripAdvisor se procesan con nlptown/bert-base-multilingual-uncased-sentiment, infiriendo una calificación continua en escala de 1 a 5 estrellas que se persiste en gold.nlp_sentimiento_resenas y permite la posterior agregación espacial en la capa Gold.')

add_h2('5.2. Descubrimiento no supervisado de tópicos insulares (BERTopic)')
add_body('Para identificar las temáticas latentes sin imponer diccionarios predeterminados, se implementó el marco de BERTopic mediante embeddings semánticos multilingües de 768 dimensiones (paraphrase-multilingual-mpnet-base-v2). Para neutralizar el sesgo de idioma y evitar que el algoritmo agrupe por lengua en lugar de por semántica, se aplicó un centrado vectorial por idioma que redujo la dependencia mutua (NMI de 0,218 a 0,031). En producción (analytics/topics/entrenar_topicos.py), para evitar que HDBSCAN descartase como ruido el 76,8 % de los documentos breves, el agrupamiento se optimizó mediante PCA a 50 dimensiones y K-Means, generando palabras clave con c-TF-IDF multilingüe y asignando nombres en español asistidos por LLM (Llama-3 / Groq):')
add_bullet('Modelo A (Visión macro insular): ', 'Entrenado sobre YouTube y mensajes no geolocalizados de LosViajeros (k=20, coherencia 0,71), captura debates estratégicos generales: congestión vehicular en las autopistas TF-1 y TF-5 (polaridad media -0,62), saturación de playas del sur (-0,48) y valoraciones excelentes de la gastronomía y guachinches (+0,86).')
add_bullet('Modelo B (Micro geolocalizado): ', 'Entrenado sobre 51.252 reseñas geocodificadas de Booking, TripAdvisor y mensajes con toponimia validada en gold.geo_mentions (k=50). Asigna temáticas a hexágonos H3 específicos, contraponiendo quejas de masificación, ruidos nocturnos y fatiga de instalaciones en el litoral sur frente a sosiego, naturaleza y confort en las medianías del norte.')

add_h2('5.3. Minería de aspectos específicos y extracción de quejas principales (PyABSA)')
add_body('Mediante el modelo multilingüe PyABSA-ATEPC (Aspect-Term Extraction and Polarity Classification; analytics/aspects/batch_inference.py), el sistema extrae simultáneamente los términos de experiencia y su polaridad afectiva en una única pasada de inferencia por lotes de 32 textos. Dado el carácter políglota de los turistas, el script oficial analytics/aspects/traducir_aspectos.py aplica una traducción híbrida e incremental (Google Translate con respaldo en MyMemory y detección langdetect), persistiendo el mapeo en gold.aspecto_traducciones. Más de 1.200 términos normalizados se estructuran en seis dimensiones canónicas: Limpieza, Servicio, Relación Calidad-Precio, Ubicación, Confort/Ruido y Saturación/Instalaciones.')

add_h2('5.4. Integración espacial del sentimiento en la malla H3')
add_body('El modelo analítico gold_sentimiento_h3 (materializado en gold.gold_h3_sentimiento vía analytics/mgwr/scripts/00_create_sentimiento_table.py) consolida los indicadores cualitativos a escala hexagonal. La queja principal de cada celda se obtiene computando la moda del aspecto más frecuente condicionada estrictamente a menciones con sentimiento negativo: MODE() WITHIN GROUP (ORDER BY aspecto) WHERE sentimiento = \'Negative\'. Esta restricción matemática es crítica para evitar que el indicador quede falseado por aspectos mayoritariamente positivos (como ubicación o desayuno). El modelo consolida resultados sobre 410 de los 2.579 hexágonos (15,9 % del territorio), coincidiendo de forma exacta con las celdas insulares que albergan oferta alojativa con reseñas geolocalizadas.')

add_h2('5.5. Evaluación técnica comparativa de modelos frente a alternativas')
add_body('En cumplimiento de los estándares de evaluación de la UCM, la selección metodológica de técnicas analíticas y de aprendizaje automático se fundamenta en su contraste explícito frente a alternativas descartadas:')

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
        'Filtro de relevancia y polaridad de opiniones',
        'Macro F1 = 0,874; Exactitud = 88,2 %',
        'Inferencia multilingüe real (ES/EN/DE/FR/IT) sensible al contexto y libre de sesgo léxico estático.',
        'Coste computacional mitigado con filtro previo en YouTube y lotes de 32 textos.',
        'VADER / TextBlob: descartados por depender de diccionarios estáticos sin contexto ni soporte multilingüe.'
    ],
    [
        'BERTopic (mpnet-base-v2 + c-TF-IDF)',
        'Descubrimiento no supervisado de tópicos',
        'Coherencia semántica = 0,71 (14 temas macro, 50 micro)',
        'Extracción no supervisada de temáticas emergentes sin imponer taxonomías previas.',
        'Ruido de HDBSCAN mitigado mediante PCA(50) + K-Means y etiquetado asistido por LLM (Llama-3).',
        'LDA clásico: descartado por pobre rendimiento ante textos coloquiales cortos y pérdida de contexto semántico.'
    ],
    [
        'MGWR Multiescala',
        'Determinantes espaciales y cálculo del PTNA',
        'R² = 0,8272 (vs OLS 0,5444); Moran I = 0,0355 (p = 0,0110)',
        'Asigna anchos de banda locales independientes por variable, capturando microclimas y economías locales.',
        'Saturación de bandwidth en 9 covariables (bw≈2.573) señalizada con confianza_ptna=\'baja\' (10,0 %).',
        'OLS Global (R² = 0,5444, Moran I = 0,3065, p = 0,0010): descartado por sesgo espacial severo y menor ajuste.'
    ],
    [
        'HDBSCAN (con PCA)',
        'Tipificación territorial de 2.579 celdas H3',
        'Varianza PCA = 81,5 %; 6 tipologías (cobertura 100 %)',
        'Detecta morfologías arbitrarias y aísla ruido geográfico reasignado con reglas territoriales.',
        'Calibración de min_cluster_size optimizada mediante análisis de estabilidad de dendrograma.',
        'K-Means: descartado por forzar clústeres esféricos de igual tamaño, distorsionando la geografía insular.'
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

out_files = [
    'docs/capitulos_4_y_5_memoria_word.docx',
    'docs/capitulos_4_y_5_memoria_word_actualizado.docx',
    'docs/capitulos_4_y_5_memoria_word_definitivo.docx'
]

for out_file in out_files:
    try:
        doc.save(out_file)
        print(f'Successfully saved {out_file}')
    except Exception as e:
        print(f'Could not save {out_file}: {e}')

