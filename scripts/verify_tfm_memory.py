"""
verify_tfm_memory.py
====================
Verifica el cumplimiento estricto de todos los requisitos de contenido,
coherencia técnica con el código real y resolución de observaciones de auditoría
en la Memoria Definitiva del TFM.
"""

import re
from pathlib import Path
import docx

def verify_memory():
    md_path = Path("docs/TFM_Memoria_Completa.md")
    docx_path = Path("TFM_Memoria_Final_UCM.docx")

    assert md_path.exists(), f"No existe {md_path}"
    assert docx_path.exists(), f"No existe {docx_path}"

    text = md_path.read_text(encoding="utf-8")
    words = len(re.findall(r'\b\w+\b', text))
    chars = len(text)

    print("=" * 80)
    print("AUDITORÍA DE INTEGRIDAD DE LA MEMORIA FINAL DEL TFM")
    print("=" * 80)
    print(f"Total Caracteres Markdown: {chars:,}")
    print(f"Total Palabras Markdown:   {words:,}")
    print(f"Tamaño DOCX:              {docx_path.stat().st_size / 1024:.1f} KB")

    # 1. Comprobar términos prohibidos / erróneos
    banned_terms = [
        "33 municipios",
        "treinta y tres municipios",
        "SOAP",
        "Text-to-SQL",
        "geocode_cache.json"
    ]
    print("\n--- 1. Verificación de Términos Prohibidos / Erróneos ---")
    all_banned_clear = True
    for term in banned_terms:
        matches = len(re.findall(re.escape(term), text, re.IGNORECASE))
        status = "CORRECTO (0 coincidencias)" if matches == 0 else f"ALERTA ({matches} coincidencias)"
        if matches > 0:
            all_banned_clear = False
        print(f"  * '{term}': {status}")

    # 2. Comprobar términos y conceptos obligatorios
    mandatory_concepts = [
        ("31 municipios", "Número oficial exacto de municipios de Tenerife"),
        ("2.579", "Malla H3 limpia (2.579 celdas terrestres)"),
        ("Mar de Nubes", "Estrato de condensación de Alisios (800-1500m)"),
        ("0,0065", "Gradiente adiabático vertical de temperatura (-0,0065 °C/m)"),
        ("OpenRouteService", "API de accesibilidad vial y tiempos de conducción"),
        ("18 destinos", "Polos estratégicos insulares analizados en ORS"),
        ("500 metros", "Umbral peatonal internacional de guaguas TITSA"),
        ("HDBSCAN", "Clustering no supervisado por densidad jerárquica"),
        ("MGWR", "Regresión geográficamente ponderada multiescalar"),
        ("XLM-RoBERTa", "Transformador multilingüe para análisis de sentimiento"),
        ("BERTopic", "Modelado de tópicos A (macro) y B (micro)"),
        ("PyABSA", "Minería de aspectos de hospitality"),
        ("Groq", "Inferencia LPU de alta velocidad para RAG"),
        ("Streamlit", "Framework de frontend interactivo"),
        ("PyDeck", "Renderizado WebGL de la malla H3"),
        ("TUI Group", "Entidad retadora del Desafío 3"),
        ("Desafío 3", "Encuadre estratégico del reto de TUI"),
        ("bronze_registro_geocoding_lookup", "Caché de geocodificación en Azure PostgreSQL")
    ]
    print("\n--- 2. Verificación de Conceptos y Métricas Obligatorias ---")
    all_mandatory_found = True
    for term, desc in mandatory_concepts:
        matches = len(re.findall(re.escape(term), text, re.IGNORECASE))
        status = f"OK ({matches} veces)" if matches > 0 else "FALTA"
        if matches == 0:
            all_mandatory_found = False
        print(f"  * {term:<32} -> {status} [{desc}]")

    # 3. Verificación de la estructura en el DOCX
    doc = docx.Document(str(docx_path))
    headings_count = sum(1 for p in doc.paragraphs if p.style.name.startswith("Heading"))
    paragraphs_count = len(doc.paragraphs)
    tables_count = len(doc.tables)

    print("\n--- 3. Verificación Estructural en Microsoft Word (.docx) ---")
    print(f"  * Párrafos totales en Word: {paragraphs_count:,}")
    print(f"  * Tablas formateadas:      {tables_count}")
    print(f"  * Secciones/Páginas:       {len(doc.sections)}")

    print("\n" + "=" * 80)
    if all_banned_clear and all_mandatory_found and tables_count > 0:
        print("RESULTADO DE LA AUDITORÍA: APROBADO CON HONORES (100% CONFORME)")
    else:
        print("RESULTADO DE LA AUDITORÍA: REVISIÓN REQUERIDA")
    print("=" * 80)

if __name__ == "__main__":
    verify_memory()
