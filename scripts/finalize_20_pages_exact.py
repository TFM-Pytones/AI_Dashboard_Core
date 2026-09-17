# scripts/finalize_20_pages_exact.py
"""
Script maestro para ajustar la Memoria Oficial del TFM (TFM_Memoria_Final_UCM.docx)
para que el cuerpo (Resumen Ejecutivo, Capítulos 1 al 8 y Referencias Bibliográficas)
tenga exactamente 20 páginas con bibliografía incluida (Páginas 4 a 23).
Los Anexos comienzan en la página 24 con salto de página.
"""

import os
import sys
import shutil
import docx
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls

TARGET_DOC = "TFM_Memoria_Final_UCM.docx"

def condense_and_fit_to_20_pages(file_path):
    print(f"Abriendo {file_path}...")
    doc = docx.Document(file_path)
    
    # 1. Márgenes estándar (2.4 cm = 68 pt) en todas las secciones
    for s in doc.sections:
        s.top_margin = Pt(65)
        s.bottom_margin = Pt(65)
        s.left_margin = Pt(68)
        s.right_margin = Pt(68)
        
    paras = doc.paragraphs
    
    # ----------------------------------------------------
    # A. Condensar Resumen Ejecutivo (P32 a P34)
    # ----------------------------------------------------
    for i, p in enumerate(paras):
        if p.text.strip() == "Resumen Ejecutivo":
            idx_res = i
            paras[idx_res + 1].text = (
                "Tenerife recibe anualmente más de 7,2 millones de turistas internacionales bajo una distribución polarizada: "
                "la franja costera meridional concentra más del 80 % del parque alojativo y de la presión sobre infraestructuras y vivienda, "
                "mientras las comarcas del norte y medianías —de excepcional valor agroambiental y cultural— permanecen desaprovechadas. "
                "Esta hiperconcentración genera colapso vial en la TF-1 y TF-5, tensión hídrica y creciente rechazo social."
            )
            paras[idx_res + 2].text = (
                "El presente TFM responde al Desafío 3 de TUI Group desarrollando un sistema integral de inteligencia territorial y toma de decisiones. "
                "La solución articula un Data Lakehouse en Microsoft Azure con arquitectura Medallón (Bronze, Silver, Gold) sobre la malla hexagonal "
                "Uber H3 Resolución 8 (2.579 celdas insulares de ~0,85 km²), resolviendo el sesgo MAUP de las divisiones municipales. "
                "El pipeline integra microdatos oficiales (AENA, Registro Turístico, ISTAC), movilidad GTFS (TITSA y tranvía), "
                "teledetección Sentinel-2 (NDVI) y VIIRS (radiancia nocturna), modelado topoclimático corregido por gradiente adiabático (67 estaciones de Agrocabildo) "
                "y minería multilingüe NLP sobre >55.000 reseñas de Booking, TripAdvisor, YouTube y LosViajeros."
            )
            paras[idx_res + 3].text = (
                "La analítica avanzada despliega regresión espacial MGWR (R²=0,8272) para formular el Índice de Potencial Turístico No Aprovechado (PTNA), "
                "segmentación no supervisada HDBSCAN (6 arquetipos insulares), tópicos BERTopic, clasificación afectiva XLM-RoBERTa (F1=0,874), "
                "asistente conversacional RAG híbrido y un simulador interactivo de políticas en Streamlit/PyDeck. "
                "Los resultados demuestran que derivar un 10 % de la demanda alivia un 14 % la congestión costera e inyecta más de 45 M€ anuales en comarcas de oportunidad."
            )
            break

    # ----------------------------------------------------
    # B. Condensar Sección 2.6 (Derechos de uso y marco ético)
    # ----------------------------------------------------
    for i, p in enumerate(paras):
        if "2.6. Derechos de uso, licencias" in p.text:
            idx_26 = i
            paras[idx_26 + 1].text = (
                "El tratamiento de datos se rigió por principios estrictos de diligencia debida legal y ética, diferenciando dos regímenes normativos:"
            )
            paras[idx_26 + 2].text = (
                "• Datos abiertos institucionales y teledetección: Las fuentes gubernamentales (ISTAC, IDECanarias, Cabildo de Tenerife, Agrocabildo y la red GTFS de TITSA) "
                "se explotan bajo la Directiva (UE) 2019/1024 y la Ley 37/2007 de reutilización del sector público (licencias CC-BY 4.0). "
                "Las imágenes satelitales Sentinel-2 (ESA) y VIIRS (NASA/NOAA) se rigen por sus respectivas políticas científicas de acceso libre y abierto."
            )
            paras[idx_26 + 3].text = (
                "• Extracción cualitativa, RGPD y transición comercial: Para Booking.com y TripAdvisor, la ingesta se restringió estrictamente al marco de investigación "
                "académica de la UCM, implementando rate limiting conservador (2,5–5,0 s por petición), caché relacional en PostGIS y cabeceras identificadas sin sobrecarga de servidores. "
                "En cumplimiento estricto del RGPD, se aplicó anonimización irreversible (cero almacenamiento de nombres, perfiles o IPs; disociación mediante hash SHA-256 y agregación espacial H3). "
                "Para la explotación comercial en TUI Group, el desacoplamiento de la arquitectura medallón permite sustituir directamente los extractores experimentales por las APIs oficiales correspondientes "
                "(Booking Connectivity Partner, TripAdvisor Content y YouTube Enterprise)."
            )
            # Marcar párrafos redundantes
            for k in range(idx_26 + 4, idx_26 + 12):
                if k < len(paras) and not paras[k].text.startswith("3."):
                    paras[k].text = ""
            break

    # ----------------------------------------------------
    # C. Condensar Sección 4.5 (MGWR, PTNA y Marco ESG)
    # ----------------------------------------------------
    for i, p in enumerate(paras):
        if "4.5. Regresión geográfica ponderada multiescala" in p.text:
            idx_45 = i
            paras[idx_45 + 1].text = (
                "Los modelos lineales globales (OLS) asumen erróneamente homogeneidad espacial insular. La Regresión Geográfica Ponderada Multiescala (MGWR) "
                "resuelve esta no-estacionariedad estimando anchos de banda locales independientes para cada variable explicativa. "
                "El modelo checkpoint v3 reveló escalas locales para el vigor vegetal (NDVI, bw=198) y la cota altimétrica (bw=138), "
                "mientras que 9 variables (distancias costeras y tiempos al aeropuerto) saturaron a escala insular (bw≈2.573). "
                "El MGWR eleva el R² global de 0,5444 (OLS) a 0,8272 y reduce sustancialmente la autocorrelación espacial residual (I de Moran de 0,3065 a 0,0355, p=0,0110)."
            )
            paras[idx_45 + 2].text = (
                "Índice de Potencial Turístico No Aprovechado (PTNA) y Salvaguarda ESG: El PTNA cuantifica la brecha entre la densidad alojativa estimada por el modelo "
                "y la observada (ptna_score = predy_MGWR − Y_observado), identificando celdas con condiciones objetivas superiores a su explotación actual. "
                "Para garantizar una descompresión sostenible, se integró un Índice ESG Territorial (0–100) en tres pilares: "
                "Medioambiental (E, 40 %: NDVI, polución lumínica VIIRS, sellado NDBI y ENP protegidos), "
                "Social (S, 40 %: densidad residencial, transporte TITSA y ausencia de quejas) y "
                "Gobernanza (G, 20 %: formalización hotelera y patrimonio BIC). "
                "El filtro combinado (PTNA > 0 y ESG > 60) aísla exactamente 247 hexágonos de oportunidad ideal (9,6 % de la isla), "
                "liderados por Santa Cruz (34), La Laguna (29), La Orotava (22), Buenavista del Norte (20), El Tanque (19) y Los Realejos (18)."
            )
            for k in range(idx_45 + 3, idx_45 + 10):
                if k < len(paras) and not paras[k].text.startswith("4.6."):
                    paras[k].text = ""
            break

    # ----------------------------------------------------
    # D. Condensar Sección 6.3 (Guardrails anti-alucinación y asistente dual)
    # ----------------------------------------------------
    for i, p in enumerate(paras):
        if "6.3. Guardrails anti-alucinación" in p.text:
            idx_63 = i
            paras[idx_63 + 1].text = (
                "Para garantizar respuestas fiables ante comités directivos de TUI, rag_answer.py incorpora cuatro salvaguardas anti-alucinación estrictas: "
                "(1) Descomposición contextual de opiniones en título, aspectos positivos y aspectos negativos; "
                "(2) Citación obligatoria entre corchetes [1][2] vinculada a fragmentos reales del Lakehouse; "
                "(3) Fórmula determinista de abstención si la similitud semántica no supera los umbrales mínimos; y "
                "(4) Prohibición explícita de extrapolar porcentajes globales a partir de muestras cualitativas locales."
            )
            paras[idx_63 + 2].text = (
                "El asistente conversacional articula un doble motor de respuesta: un Router de Intención (router.py con LLM a T=0,0) "
                "que bifurca las consultas entre analítica cuantitativa (enrutadas al Agente Text-to-SQL con validación sintáctica AST sobre 7 tablas maestras Gold) "
                "y síntesis reputacional cualitativa (enrutadas al pipeline RAG híbrido)."
            )
            for k in range(idx_63 + 3, idx_63 + 10):
                if k < len(paras) and not paras[k].text.startswith("6.4."):
                    paras[k].text = ""
            break

    # ----------------------------------------------------
    # E. Condensar Sección 7 (Productivización)
    # ----------------------------------------------------
    for i, p in enumerate(paras):
        if "7.1. Arquitectura Frontend" in p.text:
            idx_71 = i
            paras[idx_71 + 1].text = (
                "El cuadro de mando operacional se implementó con Streamlit (v1.40+) y PyDeck / Deck.gl, optimizado para la renderización "
                "interactiva y fluida de las 2.579 celdas H3 en 2D y 3D (extrusión por volumen y presión turística), "
                "con soporte de almacenamiento en caché en memoria (st.cache_data / st.cache_resource) y conexión pooling a Azure PostgreSQL."
            )
            break
            
    for i, p in enumerate(paras):
        if "7.2. Vistas especializadas" in p.text:
            idx_72 = i
            paras[idx_72 + 1].text = (
                "La plataforma articula 10 páginas modulares: (1) Resumen y Diagnóstico Macro (KPIs insulares de capacidad de carga y saturación); "
                "(2) Visor Cartográfico Multicapa (conmutación micro H3 y macro municipal con capas de satélite, clima y accesibilidad); "
                "(3) Matriz de Oportunidades y Arquetipos TUI (cuadrantes bidimensionales de potencial PTNA vs. saturación); y "
                "(4) Monitores Sectoriales de microeconomía municipal y auditoría alojativa."
            )
            break

    for i, p in enumerate(paras):
        if "7.3. Simulador territorial" in p.text:
            idx_73 = i
            paras[idx_73 + 1].text = (
                "El Simulador de Decisiones (simulador.py) modela dinámicamente el desvío de flujos turísticos (10–20 %) "
                "recalculando instantáneamente la presión costera, la inyección económica en medianías y el impacto en celdas de alta fragilidad ecológica mediante alertas en tiempo real."
            )
            for k in range(idx_73 + 2, idx_73 + 7):
                if k < len(paras) and not paras[k].text.startswith("7.4.") and not paras[k].text.startswith("8."):
                    paras[k].text = ""
            break

    # ----------------------------------------------------
    # F. Condensar Sección 8.3 (Limitaciones del Estudio)
    # ----------------------------------------------------
    for i, p in enumerate(paras):
        if "8.3. Limitaciones del Estudio" in p.text:
            idx_83 = i
            paras[idx_83 + 1].text = (
                "El estudio presenta cuatro limitaciones operativas: (1) Falta de microdatos de telefonía móvil por secreto estadístico, suplida con proxies satelitales VIIRS y transporte GTFS; "
                "(2) Sesgo de muestreo en plataformas OTAs (sobrerrepresentación del turista anglosajón y germano), mitigado mediante ponderación c-TF-IDF multilingüe; "
                "(3) Fricción de accesibilidad calculada en flujo libre por restricciones de API histórica de tráfico; y "
                "(4) Desfase trimestral en series socioeconómicas del ISTAC frente a la inmediatez de sensores meteorológicos."
            )
            paras[idx_83 + 2].text = (
                "Como líneas futuras prioritarias se propone: integrar trazas GPS anonimizadas de flotas de alquiler, "
                "desplegar gemelos digitales hidrológicos sobre consumo de agua por cama turística y conectar el asistente RAG con el motor transaccional de reservas de TUI."
            )
            for k in range(idx_83 + 3, idx_83 + 7):
                if k < len(paras) and not paras[k].text.startswith("Referencias"):
                    paras[k].text = ""
            break

    # ----------------------------------------------------
    # G. Limpieza de párrafos vaciados entre P37 y Anexos
    # ----------------------------------------------------
    p_to_remove = []
    in_body = False
    for p in doc.paragraphs:
        if p.text.strip() == "1. Introducción y contexto de negocio":
            in_body = True
        if p.text.strip() == "Anexos":
            in_body = False
            break
        if in_body and p.text.strip() == "":
            p_to_remove.append(p)
            
    for p in p_to_remove:
        try:
            p._p.getparent().remove(p._p)
        except:
            pass

    # ----------------------------------------------------
    # H. Ajustar formato de párrafos en el cuerpo (P31 a Referencias)
    # ----------------------------------------------------
    for p in doc.paragraphs:
        if p.text.strip() == "Anexos":
            break
        st = p.style.name if p.style else ""
        txt = p.text.strip()
        if not txt:
            continue
            
        # No tocar la portada (P0 a P26)
        if any(k in txt for k in ["UNIVERSIDAD COMPLUTENSE", "Máster en Data Science", "TRABAJO DE FIN DE MÁSTER", "AI-Dashboard para la gestión", "Desafío 3 – Caso TUI Group", "Autores:", "Curso Académico"]):
            continue
            
        if st.startswith("Heading 1") or st.startswith("Título 1"):
            p.paragraph_format.space_before = Pt(5)
            p.paragraph_format.space_after = Pt(2)
            p.paragraph_format.line_spacing = 1.05
        elif st.startswith("Heading 2") or st.startswith("Título 2"):
            p.paragraph_format.space_before = Pt(4)
            p.paragraph_format.space_after = Pt(1.5)
            p.paragraph_format.line_spacing = 1.05
        elif st.startswith("Heading 3") or st.startswith("Título 3"):
            p.paragraph_format.space_before = Pt(3)
            p.paragraph_format.space_after = Pt(1)
            p.paragraph_format.line_spacing = 1.05
        else:
            p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.space_after = Pt(1.8)
            p.paragraph_format.line_spacing = 1.06

    # ----------------------------------------------------
    # I. Tablas compactas en el cuerpo (primeras 4 tablas)
    # ----------------------------------------------------
    for t in doc.tables[:4]:
        t.autofit = True
        for row in t.rows:
            for cell in row.cells:
                tcPr = cell._tc.get_or_add_tcPr()
                tcMar = parse_xml(r'<w:tcMar %s><w:top w:w="25" w:type="dxa"/><w:bottom w:w="25" w:type="dxa"/><w:left w:w="45" w:type="dxa"/><w:right w:w="45" w:type="dxa"/></w:tcMar>' % nsdecls('w'))
                tcPr.append(tcMar)
                for cp in cell.paragraphs:
                    cp.paragraph_format.space_before = Pt(0)
                    cp.paragraph_format.space_after = Pt(0.8)
                    cp.paragraph_format.line_spacing = 1.0
                    for cr in cp.runs:
                        if cr.font.size and cr.font.size > Pt(8.0):
                            cr.font.size = Pt(8.0)

    print(f"Guardando cambios en {file_path}...")
    doc.save(file_path)
    print("Documento guardado con éxito.")

if __name__ == "__main__":
    condense_and_fit_to_20_pages(TARGET_DOC)
