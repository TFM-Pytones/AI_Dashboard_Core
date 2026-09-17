# scripts/condense_tfm_to_20_pages.py
"""
Script de edición y condensación de contenido para TFM_Memoria_Final_UCM.docx
Objetivo: Ajustar el cuerpo de la memoria (Resumen Ejecutivo, Capítulos 1 al 8 y Referencias Bibliográficas)
a un límite estricto de exactamente 20 páginas (con bibliografía incluida),
preservando la integridad técnica, los datos empíricos y la orientación a negocio.
"""

import os
import sys
import docx
from docx.shared import Pt, Inches, RGBColor
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls

TARGET_DOC = "TFM_Memoria_Final_UCM.docx"

def edit_and_condense_docx(file_path):
    print(f"Cargando {file_path}...")
    doc = docx.Document(file_path)
    
    # 1. Ajustar márgenes de sección (2.4 cm = 68 pt)
    for s in doc.sections:
        s.top_margin = Pt(66)
        s.bottom_margin = Pt(66)
        s.left_margin = Pt(68)
        s.right_margin = Pt(68)

    # 2. Reemplazo y condensación de bloques textuales redundantes
    # Localizar párrafos por contenido clave y reemplazarlos o compactarlos
    
    paras = doc.paragraphs
    
    # Condensación de Sección 2.6 (Derechos de uso, licencias y marco ético)
    # Buscamos P75 (encabezado 2.6) hasta P85
    idx_26 = None
    for i, p in enumerate(paras):
        if "2.6. Derechos de uso, licencias" in p.text:
            idx_26 = i
            break
            
    if idx_26 is not None:
        print(f"Condensando Sección 2.6 en índice {idx_26}...")
        # Localizar fin de 2.6 (antes de Capítulo 3)
        idx_cap3 = None
        for j in range(idx_26 + 1, len(paras)):
            if "3. Data Lakehouse y Topología Geoespacial" in paras[j].text:
                idx_cap3 = j
                break
                
        if idx_cap3 is not None:
            # Reemplazar el primer párrafo con texto sintetizado y vaciar los redundantes intermedios
            paras[idx_26 + 1].text = (
                "El tratamiento de datos se rigió por principios estrictos de diligencia debida legal y ética, diferenciando dos regímenes normativos:"
            )
            paras[idx_26 + 2].text = (
                "• Datos abiertos institucionales y teledetección: Las fuentes gubernamentales (ISTAC, IDECanarias, Cabildo, Agrocabildo y GTFS de TITSA) "
                "se explotan bajo la Directiva (UE) 2019/1024 y la Ley 37/2007 de reutilización del sector público (licencias CC-BY 4.0). "
                "Las imágenes satelitales Sentinel-2 (ESA) y VIIRS (NASA/NOAA) operan bajo sus políticas científicas de acceso libre y abierto."
            )
            paras[idx_26 + 3].text = (
                "• Extracción cualitativa, RGPD y transición comercial: Para Booking.com y TripAdvisor, la ingesta se restringió estrictamente al marco de investigación "
                "académica de la UCM, aplicando rate limiting conservador (2,5–5,0 s por petición), caché relacional en PostGIS y cabeceras identificadas sin sobrecarga de servidores. "
                "En cumplimiento estricto del RGPD, se aplicó anonimización irreversible (cero extracción de nombres, avatares o IPs; hash unidireccional y agregación espacial en H3). "
                "Para la explotación comercial en TUI Group, la arquitectura desacoplada del Lakehouse permite sustituir directamente los extractores por las APIs oficiales correspondientes "
                "(Booking Connectivity Partner, TripAdvisor Content y YouTube Enterprise)."
            )
            # Vaciar los párrafos restantes entre idx_26+4 e idx_cap3
            for k in range(idx_26 + 4, idx_cap3):
                paras[k].text = ""

    # Condensación de Sección 4.5 (MGWR, PTNA y Marco ESG)
    idx_45 = None
    for i, p in enumerate(paras):
        if "4.5. Regresión geográfica ponderada multiescala" in p.text:
            idx_45 = i
            break
            
    if idx_45 is not None:
        print(f"Condensando Sección 4.5 en índice {idx_45}...")
        idx_46 = None
        for j in range(idx_45 + 1, len(paras)):
            if "4.6. Segmentación territorial no supervisada" in paras[j].text:
                idx_46 = j
                break
                
        if idx_46 is not None:
            paras[idx_45 + 1].text = (
                "Los modelos de regresión lineal global (OLS) asumen erróneamente que las relaciones espaciales son estacionarias en toda la isla. "
                "La Regresión Geográfica Ponderada Multiescala (MGWR) resuelve la heterogeneidad territorial estimando anchos de banda locales independientes para cada variable explicativa. "
                "El modelo checkpoint v3 reveló escalas de operación genuinamente locales para el vigor vegetal (NDVI, bw=198) y la cota altimétrica (bw=138), "
                "mientras que 9 variables (distancia a costa o tiempos a aeropuertos) saturaron a escala regional (bw≈2.573). "
                "El ajuste MGWR eleva el R² global de 0,5444 (OLS) a 0,8272 y reduce la autocorrelación espacial residual (I de Moran de 0,3065 a 0,0355, p=0,0110)."
            )
            paras[idx_45 + 2].text = (
                "Índice de Potencial Turístico No Aprovechado (PTNA) y Salvaguarda ESG: El PTNA cuantifica la brecha entre la densidad alojativa estimada por el modelo "
                "y la observada en cada celda (ptna_score = predy_MGWR − Y_observado). Un ptna_score > 0 define áreas con condiciones biofísicas óptimas infrautilizadas. "
                "Como contrapeso ético para evitar sobrecargas, se integró un Índice ESG Territorial (0–100) estructurado en tres pilares: "
                "Medioambiental (E, 40 %: NDVI, polución lumínica VIIRS, sellado NDBI y ENP protegidos), "
                "Social (S, 40 %: densidad residencial, accesibilidad TITSA y ausencia de quejas acústicas) y "
                "Gobernanza (G, 20 %: formalización hotelera y patrimonio BIC). "
                "El cruce multicriterio (PTNA > 0 y ESG > 60) aísla exactamente 247 hexágonos de oportunidad ideal (9,6 % del territorio), "
                "liderados por Santa Cruz (34), La Laguna (29), La Orotava (22), Buenavista (20), El Tanque (19) y Los Realejos (18)."
            )
            # Vaciar los párrafos redundantes hasta idx_46
            for k in range(idx_45 + 3, idx_46):
                paras[k].text = ""

    # Condensación de Sección 6.3 (Guardrails anti-alucinación y asistente dual)
    idx_63 = None
    for i, p in enumerate(paras):
        if "6.3. Guardrails anti-alucinación" in p.text:
            idx_63 = i
            break
            
    if idx_63 is not None:
        print(f"Condensando Sección 6.3 en índice {idx_63}...")
        idx_64 = None
        for j in range(idx_63 + 1, len(paras)):
            if "6.4. Validación empírica del sistema RAG" in paras[j].text:
                idx_64 = j
                break
                
        if idx_64 is not None:
            paras[idx_63 + 1].text = (
                "Para garantizar respuestas fiables en comités directivos de TUI, rag_answer.py incorpora cuatro salvaguardas anti-alucinación estrictas: "
                "(1) Descomposición contextual de opiniones en título, aspectos positivos y aspectos negativos; "
                "(2) Citación obligatoria entre corchetes [1][2] vinculada a fragmentos reales del Lakehouse; "
                "(3) Fórmula determinista de abstención si la similitud semántica o densidad léxica no supera los umbrales mínimos; y "
                "(4) Prohibición explícita en el system prompt de extrapolar porcentajes globales a partir de muestras cualitativas locales."
            )
            paras[idx_63 + 2].text = (
                "El asistente conversacional articula un doble motor de respuesta: un Router de Intención (router.py con LLM a T=0,0) "
                "que bifurca las consultas entre analítica agregada (enrutadas al Agente Text-to-SQL con validación sintáctica AST sobre 7 tablas maestras Gold) "
                "y síntesis reputacional cualitativa (enrutadas al pipeline RAG híbrido)."
            )
            for k in range(idx_63 + 3, idx_64):
                paras[k].text = ""

    # Condensación de Sección 7 (Productivización)
    idx_71 = None
    for i, p in enumerate(paras):
        if "7.1. Arquitectura Frontend" in p.text:
            idx_71 = i
            break
            
    if idx_71 is not None:
        print(f"Condensando Sección 7 en índice {idx_71}...")
        idx_8 = None
        for j in range(idx_71 + 1, len(paras)):
            if "8. Conclusiones: Respuesta a las Preguntas" in paras[j].text:
                idx_8 = j
                break
                
        if idx_8 is not None:
            paras[idx_71 + 1].text = (
                "El cuadro de mando operacional se implementó con Streamlit (v1.40+) y PyDeck / Deck.gl, optimizado para la renderización "
                "interactiva y fluida de las 2.579 celdas H3 en 2D y 3D (extrusión por volumen y presión turística), "
                "con soporte de almacenamiento en caché en memoria (st.cache_data / st.cache_resource) y conexión pooling a Azure PostgreSQL."
            )
            # Buscar 7.2
            for k in range(idx_71 + 2, idx_8):
                if "7.2. Vistas especializadas" in paras[k].text:
                    paras[k + 1].text = (
                        "La plataforma articula 10 páginas modulares: (1) Resumen y Diagnóstico Macro (KPIs insulares de capacidad de carga y saturación); "
                        "(2) Visor Cartográfico Multicapa (conmutación micro H3 y macro municipal con capas de satélite, clima y accesibilidad); "
                        "(3) Matriz de Oportunidades y Arquetipos TUI (cuadrantes bidimensionales de potencial PTNA vs. saturación); y "
                        "(4) Monitores Sectoriales de microeconomía municipal y auditoría alojativa."
                    )
                elif "7.3. Simulador territorial" in paras[k].text:
                    paras[k + 1].text = (
                        "El Simulador de Decisiones (simulador.py) modela dinámicamente el desvío de flujos turísticos (10–20 %) "
                        "recalculando instantáneamente la presión costera, la inyección económica en medianías y el impacto en celdas de alta fragilidad ecológica mediante alertas en tiempo real."
                    )

    # 3. Eliminar físicamente los párrafos vaciados antes de Anexos
    # Para no desestructurar el documento, limpiamos los párrafos vacíos consecutivos
    print("Optimizando párrafos y eliminando vacíos...")
    p_to_remove = []
    for p in doc.paragraphs:
        if p.text.strip().lower() == "anexos":
            break
        # Si el párrafo está vacío y no es un salto intencionado
        if p.text.strip() == "":
            p_to_remove.append(p)
            
    for p in p_to_remove:
        # Remover del XML
        p._p.getparent().remove(p._p)

    # 4. Ajustar interlineado y espaciado de párrafos en el cuerpo
    for p in doc.paragraphs:
        if p.text.strip().lower() == "anexos":
            break
        style = p.style.name if p.style else ""
        if style.startswith("Heading 1") or style.startswith("Título 1"):
            p.paragraph_format.space_before = Pt(6)
            p.paragraph_format.space_after = Pt(3)
            p.paragraph_format.line_spacing = 1.05
        elif style.startswith("Heading 2") or style.startswith("Título 2"):
            p.paragraph_format.space_before = Pt(5)
            p.paragraph_format.space_after = Pt(2)
            p.paragraph_format.line_spacing = 1.05
        elif style.startswith("Heading 3") or style.startswith("Título 3"):
            p.paragraph_format.space_before = Pt(4)
            p.paragraph_format.space_after = Pt(1.5)
            p.paragraph_format.line_spacing = 1.05
        else:
            p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.space_after = Pt(2.0)
            p.paragraph_format.line_spacing = 1.08

    # 5. Ajustar fuentes y padding de tablas en el cuerpo (primeras 4 tablas)
    for t in doc.tables[:4]:
        t.autofit = True
        for row in t.rows:
            for cell in row.cells:
                # cell padding compacto
                tcPr = cell._tc.get_or_add_tcPr()
                tcMar = parse_xml(r'<w:tcMar %s><w:top w:w="30" w:type="dxa"/><w:bottom w:w="30" w:type="dxa"/><w:left w:w="50" w:type="dxa"/><w:right w:w="50" w:type="dxa"/></w:tcMar>' % nsdecls('w'))
                tcPr.append(tcMar)
                for cp in cell.paragraphs:
                    cp.paragraph_format.space_before = Pt(0)
                    cp.paragraph_format.space_after = Pt(1)
                    cp.paragraph_format.line_spacing = 1.0
                    for cr in cp.runs:
                        if cr.font.size and cr.font.size > Pt(8.5):
                            cr.font.size = Pt(8.5)

    print(f"Guardando cambios en {file_path}...")
    doc.save(file_path)

if __name__ == "__main__":
    edit_and_condense_docx(TARGET_DOC)
