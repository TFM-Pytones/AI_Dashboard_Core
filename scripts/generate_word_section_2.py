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

def add_heading_2(text):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(14)
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.keep_with_next = True
    run = p.add_run(text)
    run.font.name = 'Verdana'
    run.font.size = Pt(11.5)
    run.font.bold = True
    run.font.color.rgb = RGBColor(16, 44, 87) # Navy blue
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

# 2.2
add_heading_2('2.2. Extracción de microdatos oficiales tabulares y espaciales')
add_body('La base territorial y socioeconómica se consolidó a partir de fuentes institucionales abiertas:')
add_bullet('Instituto Canario de Estadística (ISTAC): ', 'Mediante integración directa con dos recursos REST de su API oficial (Municipios en Cifras C00067A y el recurso estadístico de Vivienda Vacacional C00065A_000061), se ingirieron veinticuatro indicadores socioeconómicos y de demanda alojativa para los 31 municipios de Tenerife (códigos INE 38001 a 38052). Este corpus abarca la demografía censal, el desempleo registrado mensual, la matriz de pernoctaciones y ocupación hotelera (EOH), la suite trimestral de afiliaciones a la Seguridad Social (desglosada por regímenes general/autónomo y seis sectores de actividad económica), la Población Turística Equivalente (PTE) y las series completas de vivienda vacacional (plazas, ocupación, estancia media e ingresos brutos), garantizando la caracterización socioeconómica continua tanto de los polos tradicionales como de los municipios de interior.')
add_bullet('Cartografía Vectorial Oficial: ', 'Desde el portal insular de datos abiertos (datos.tenerife.es) y GRAFCAN/IDECanarias, se integraron los límites municipales (31), Bienes de Interés Cultural (125 BIC), oficinas de turismo (31), Zonas Turísticas (17) y Espacios Naturales Protegidos (43 ENP), estandarizados en GeoParquet y PostGIS (EPSG:4326 y EPSG:32628).')
add_bullet('Modelo Digital del Terreno (MDT25): ', 'Con celda de 25 m y mediante el operador de gradiente de Horn (1981), se extrajeron altitud, pendiente, orientación y sombreado (hillshade a 315° NW y 45° de elevación), integrando sus estadísticas zonales en la malla insular.')

# 2.3
add_heading_2('2.3. Integración de la red de transporte público insular (GTFS)')
add_body('La movilidad colectiva se modeló a partir de los datos GTFS de TITSA (guaguas) y Metropolitano de Tenerife (tranvía). Se estructuró en siete tablas maestras: 3.934 paradas físicas georreferenciadas, 873 trazados de rutas (183 líneas comerciales), 48.655 viajes planificados y un histórico operativo de 1,36 millones de registros de paso horarios (derivados de los 2,08 millones del volcado bruto). Esta topología permite calcular isócronas de accesibilidad turística y evaluar la conectividad de las zonas de interior frente a los núcleos costeros.')

# 2.4
add_heading_2('2.4. Ingesta meteorológica de alta resolución y teledetección satelital')
add_body('Para caracterizar los marcados microclimas insulares derivados del relieve y los vientos alisios, se integró la red de Agrocabildo (Cabildo de Tenerife):')
add_bullet('Series Meteorológicas: ', 'Recoge el inventario de 68 estaciones automáticas (378 sensores físicos) y 136,4 millones de lecturas brutas (2019–2026). En la capa Silver se depuraron 12,95 millones de registros correspondientes a las 57 estaciones maduras (instaladas antes de 2022), garantizando series históricas continuas y sin sesgos de muestreo.')
add_bullet('Teledetección Satelital: ', 'Se procesaron compuestos trimestrales de reflectancia sin nubosidad de Copernicus Sentinel-2 (20 m) para computar los índices de vegetación (NDVI) y edificación (NDBI) sobre la malla insular (46.422 registros en Silver), junto con la serie mensual de luz nocturna del sensor NOAA/NASA VIIRS (241.648 observaciones) como proxy de actividad antropogénica.')

# 2.5
add_heading_2('2.5. Extracción de datos cualitativos sociales y reputacionales')
add_body('Para capturar la percepción de la demanda y el sentimiento del visitante, se combinaron tres canales complementarios:')
add_bullet('Comunidades de Viajeros (LosViajeros.com): ', 'Mediante web scraping ético con BeautifulSoup se recopiló el debate cualitativo completo sobre Tenerife entre 2004 y 2026, abarcando 248 hilos temáticos y 167.274 mensajes brutos (168.035 procesados en Silver tras limpieza de entidades y etiquetas).')
add_bullet('Contenido Audiovisual (YouTube Data API v3): ', 'Se monitorizaron 41 vídeos de alta difusión turística, extrayendo 3.100 comentarios brutos depurados a 2.819 opiniones contemporáneas (2022–2026).')
add_bullet('Plataformas de Alojamiento (Booking.com y TripAdvisor): ', 'Constituyen el núcleo geolocalizado del análisis reputacional, acumulando más de 105.000 reseñas brutas y consolidando en Silver 74.695 reseñas limpias y georreferenciadas (73.888 de Booking y 807 de TripAdvisor) asociadas a 3.740 establecimientos hoteleros y 748 actividades turísticas, lo que posibilita su indexación directa en los hexágonos H3.')

# Table summary (Tabla 2)
p_tab_title = doc.add_paragraph()
p_tab_title.paragraph_format.space_before = Pt(12)
p_tab_title.paragraph_format.space_after = Pt(4)
p_tab_title.paragraph_format.keep_with_next = True
run_tt = p_tab_title.add_run('Tabla 2. Inventario y volumetría de fuentes de datos integradas en el Data Lakehouse')
run_tt.font.name = 'Verdana'
run_tt.font.size = Pt(9.5)
run_tt.font.bold = True
run_tt.font.color.rgb = RGBColor(16, 44, 87)

table_data = [
    ['Fuente / Proveedor', 'Tipología de Dato', 'Volumen Bruto (Bronze)', 'Volumen Depurado (Silver)', 'Aportación al Caso de Negocio'],
    ['ISTAC (Gob. Canarias)', 'Microdatos socioeconómicos y demanda', '2 recursos REST (C00067A y C00065A)', '24 indicadores municipales (31 municipios)', 'Series de empleo, pernoctaciones, ocupación y vivienda vacacional'],
    ['Cartografía (GRAFCAN / Cabildo)', 'Vectores institucionales (GeoJSON)', '5 coberturas oficiales insulares', '31 mun., 125 BIC, 31 ofic., 17 ZT, 43 ENP', 'Delimitación territorial, atractores patrimoniales y restricciones'],
    ['MDT25 (GRAFCAN)', 'Raster altimétrico (25 m)', 'Raster insular continuo', 'Pendiente, aspecto y sombreado zonal', 'Caracterización orográfica y aptitud de desarrollo'],
    ['GTFS (TITSA / Tranvía)', 'Red de transporte público regular', '2,08 M registros brutos', '3.934 paradas, 183 líneas, 1,36 M pasos', 'Accesibilidad multimodal e isócronas de transporte'],
    ['Agrocabildo (Cabildo TF)', 'Sensórica meteorológica horaria', '136,4 M lecturas (68 estaciones)', '12,95 M registros (57 estaciones maduras)', 'Calibración microclimática (temperatura y mar de nubes)'],
    ['Copernicus Sentinel-2', 'Teledetección multiespectral (20 m)', 'Composites trimestrales (2019-2026)', '46.422 registros (NDVI y NDBI)', 'Vigor vegetal y huella construida por celda'],
    ['NOAA/NASA VIIRS', 'Radianza nocturna satelital (500 m)', 'Serie mensual DNB (2019-2026)', '241.648 observaciones limpias', 'Proxy objetivo de actividad económica y saturación'],
    ['LosViajeros.com', 'Comunidad y foros de viajes', '167.274 mensajes (248 hilos)', '168.035 mensajes parseados', 'Detección cualitativa de fricciones y rutas en interior'],
    ['YouTube Data API v3', 'Opiniones en vídeo turístico', '3.100 comentarios (41 vídeos)', '2.819 comentarios depurados', 'Percepción de marca de destino y atractores clave'],
    ['Booking y TripAdvisor', 'Reseñas geolocalizadas de alojamientos', '>105.000 reseñas brutas', '74.695 reseñas (3.740 estab., 748 activ.)', 'Minería de aspectos y sentimiento georreferenciado H3']
]

table = doc.add_table(rows=len(table_data), cols=5)
table.alignment = WD_TABLE_ALIGNMENT.CENTER
col_widths = [Inches(1.2), Inches(1.2), Inches(1.3), Inches(1.3), Inches(1.8)]

for r_idx, row in enumerate(table.rows):
    for c_idx, cell in enumerate(row.cells):
        cell.width = col_widths[c_idx]
        cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        tcPr = cell._tc.get_or_add_tcPr()
        
        p = cell.paragraphs[0]
        p.paragraph_format.space_before = Pt(2)
        p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.line_spacing = 1.05
        
        run = p.add_run(table_data[r_idx][c_idx])
        run.font.name = 'Verdana'
        
        if r_idx == 0:
            shd = parse_xml('<w:shd xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" w:fill="102C57"/>')
            tcPr.append(shd)
            run.font.bold = True
            run.font.size = Pt(8.5)
            run.font.color.rgb = RGBColor(255, 255, 255)
        else:
            run.font.size = Pt(8.5)
            run.font.color.rgb = RGBColor(40, 40, 40)
            if r_idx % 2 == 1:
                shd = parse_xml('<w:shd xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" w:fill="F4F6F9"/>')
                tcPr.append(shd)

doc.save('docs/seccion_2_datos_para_word.docx')
print('Word document saved successfully at docs/seccion_2_datos_para_word.docx')
