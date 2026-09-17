import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.enum.section import WD_SECTION_START, WD_ORIENTATION
from docx.oxml import parse_xml

doc = docx.Document()

# Page Setup: A4 Landscape for wide annex table
section = doc.sections[0]
section.orientation = WD_ORIENTATION.LANDSCAPE
section.page_width = Inches(11.69)
section.page_height = Inches(8.27)
section.top_margin = Inches(0.7)
section.bottom_margin = Inches(0.7)
section.left_margin = Inches(0.7)
section.right_margin = Inches(0.7)

p_title = doc.add_paragraph()
p_title.paragraph_format.space_before = Pt(4)
p_title.paragraph_format.space_after = Pt(4)
run_title = p_title.add_run('Tabla Anexo. Inventario, métodos de ingesta y volumetría de fuentes integradas en el Data Lakehouse')
run_title.font.name = 'Verdana'
run_title.font.size = Pt(11)
run_title.font.bold = True
run_title.font.color.rgb = RGBColor(16, 44, 87)

table_data = [
    ['Fuente / Proveedor', 'Tipología de Dato', 'Método de Ingesta (Bronze / Origen)', 'Volumen Bruto (Bronze)', 'Volumen Depurado (Silver)', 'Aportación al Caso de Negocio (TUI)'],
    [
        'ISTAC (Gobierno de Canarias)',
        'Microdatos socioeconómicos y demanda',
        'API REST / SDMX oficial (recursos C00067A y C00065A_000061) con paginación JSON → Azure Blob (bronce-raw) → PostgreSQL',
        '2 recursos REST (15+9 series)',
        '24 indicadores municipales (31 municipios)',
        'Series de empleo, pernoctaciones, ocupación hotelera y vivienda vacacional'
    ],
    [
        'Cartografía (GRAFCAN / Cabildo)',
        'Vectores institucionales (GeoJSON)',
        'Descarga programática API CKAN (datos.tenerife.es) y servicios WFS de IDECanarias → GeoParquet → PostGIS (EPSG:4326/32628)',
        '5 coberturas oficiales insulares',
        '31 municipios, 125 BIC, 31 oficinas, 17 ZT, 43 ENP',
        'Delimitación territorial, atractores patrimoniales y restricciones legales'
    ],
    [
        'MDT25 (GRAFCAN)',
        'Raster altimétrico (25 m)',
        'Descarga WCS / GeoTIFF de GRAFCAN → Álgebra de mapas en Python (Horn, 1981) → Estadísticas zonales por celda H3 en PostgreSQL',
        'Raster insular continuo (2.034 km²)',
        'Estadísticas de pendiente, aspecto y sombreado zonal',
        'Caracterización orográfica y aptitud de desarrollo ecoturístico'
    ],
    [
        'GTFS (TITSA / Tranvía)',
        'Red de transporte público regular',
        'Extracción de paquetes ZIP GTFS oficiales de portales de datos abiertos → Azure Blob → Ingesta relacional de 7 tablas en PostgreSQL',
        '2,08 M registros brutos (pasos horarios)',
        '3.934 paradas, 183 líneas, 1,36 M registros de paso',
        'Accesibilidad multimodal e isócronas de conectividad hacia el interior'
    ],
    [
        'Agrocabildo (Cabildo de Tenerife)',
        'Sensórica meteorológica decaminutal',
        'API REST v2.0.0 Agrocabildo con control de flujo (10 req/min) y partición Hive (año=YYYY/mes=MM/) → Azure Blob → PostgreSQL',
        '136,4 M lecturas (68 estaciones automáticas)',
        '12,95 M registros (57 estaciones maduras > 2022)',
        'Calibración microclimática (gradiente térmico y mar de nubes)'
    ],
    [
        'Copernicus Sentinel-2',
        'Teledetección multiespectral (20 m)',
        'Procesamiento en Google Earth Engine (GEE) con filtrado SCL y calima (AOT/B02) → GeoTIFF trimestral → Azure Blob → PostgreSQL',
        'Composites trimestrales 2019–2026 (30 trimestres)',
        '46.422 registros por celda H3 (NDVI y NDBI)',
        'Vigor vegetal y huella de suelo construido por celda H3'
    ],
    [
        'NOAA/NASA VIIRS',
        'Radianza nocturna satelital (500 m)',
        'Extracción GEE de la colección mensual calibrada VNP46A2/VCMSLCFG → GeoTIFF → Azure Blob → Estadísticas zonales en PostgreSQL',
        '90 composites mensuales (2019–2026)',
        '241.648 observaciones limpias (2022–2026)',
        'Proxy objetivo de presión antrópica y actividad económica'
    ],
    [
        'LosViajeros.com',
        'Comunidad y foros de viajes',
        'Web scraping ético en Python (BeautifulSoup) con cortesía de 1,5 s y parseo de hilos HTML → Azure Blob → PostgreSQL',
        '167.274 mensajes brutos (248 hilos temáticos)',
        '168.035 mensajes parseados y normalizados',
        'Detección cualitativa de fricciones (tráfico) y rutas en interior'
    ],
    [
        'YouTube Data API v3',
        'Comentarios en vídeo turístico',
        'Extracción automatizada vía YouTube Data API v3 (Google Cloud Platform) con filtrado REST por vídeo → Azure Blob → PostgreSQL',
        '3.100 comentarios (41 vídeos seleccionados)',
        '2.819 comentarios contemporáneos depurados',
        'Percepción de marca de destino y atractores clave'
    ],
    [
        'Booking.com y TripAdvisor',
        'Reseñas geolocalizadas de alojamientos',
        'Web scraping ético distribuido (Booking: sitemaps XML y rotación UA; TripAdvisor: endpoints con validación perimetral PostGIS) → Azure Blob → PostgreSQL',
        '>105.000 reseñas brutas recopiladas',
        '74.695 reseñas limpias (3.740 estab., 748 activ.)',
        'Minería de aspectos y sentimiento georreferenciado en malla H3'
    ]
]

table = doc.add_table(rows=len(table_data), cols=6)
table.alignment = WD_TABLE_ALIGNMENT.CENTER
col_widths = [Inches(1.5), Inches(1.3), Inches(2.5), Inches(1.3), Inches(1.4), Inches(2.2)]

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
            run.font.size = Pt(8.0)
            run.font.color.rgb = RGBColor(40, 40, 40)
            if r_idx % 2 == 1:
                shd = parse_xml('<w:shd xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" w:fill="F4F6F9"/>')
                tcPr.append(shd)

doc.save('docs/tabla_2_inventario_fuentes_word.docx')
print('Successfully saved docs/tabla_2_inventario_fuentes_word.docx')
