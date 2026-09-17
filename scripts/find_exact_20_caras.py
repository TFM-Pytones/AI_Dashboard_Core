import docx
from docx.shared import Pt
import win32com.client as win32
import os
import pdfplumber
import sys

def run_calibration():
    src = "TFM_Memoria_Final_UCM.docx"
    
    # Iniciar Word una sola vez
    word = win32.gencache.EnsureDispatch('Word.Application')
    word.Visible = False
    word.DisplayAlerts = 0
    
    test_params = [
        (1.10, 2.2),
        (1.12, 2.6),
        (1.14, 3.0),
        (1.15, 3.2),
        (1.16, 3.4),
        (1.18, 3.6),
    ]
    
    try:
        for line_sp, sp_after in test_params:
            dst = f"test_calib_{line_sp}_{sp_after}.docx"
            pdf = f"test_calib_{line_sp}_{sp_after}.pdf"
            
            doc = docx.Document(src)
            for p in doc.paragraphs:
                txt = p.text.strip()
                if not txt:
                    continue
                if txt == "Anexos":
                    p.paragraph_format.page_break_before = True
                    break
                    
                if any(k in txt for k in ["UNIVERSIDAD COMPLUTENSE", "Máster en Data Science", "TRABAJO DE FIN DE MÁSTER", "AI-Dashboard para la gestión", "Desafío 3 – Caso TUI Group", "Autores:", "Curso Académico"]):
                    continue
                    
                st = p.style.name if p.style else ""
                if st.startswith("Heading 1") or st.startswith("Título 1"):
                    p.paragraph_format.space_before = Pt(6)
                    p.paragraph_format.space_after = Pt(3)
                    p.paragraph_format.line_spacing = 1.08
                elif st.startswith("Heading 2") or st.startswith("Título 2"):
                    p.paragraph_format.space_before = Pt(4)
                    p.paragraph_format.space_after = Pt(2)
                    p.paragraph_format.line_spacing = 1.08
                elif st.startswith("Heading 3") or st.startswith("Título 3"):
                    p.paragraph_format.space_before = Pt(3)
                    p.paragraph_format.space_after = Pt(1.5)
                    p.paragraph_format.line_spacing = 1.08
                elif txt == "Referencias bibliográficas":
                    p.paragraph_format.page_break_before = True
                    p.paragraph_format.space_before = Pt(12)
                    p.paragraph_format.space_after = Pt(6)
                    p.paragraph_format.line_spacing = 1.08
                elif p.text.startswith("Agencia Espacial") or p.text.startswith("Armbrust") or p.text.startswith("Cabildo") or p.text.startswith("Devlin") or p.text.startswith("Fotheringham") or p.text.startswith("Grootendorst") or p.text.startswith("Instituto Canario") or p.text.startswith("Lewis") or p.text.startswith("McInnes") or p.text.startswith("Promotur") or p.text.startswith("Turismo de") or p.text.startswith("Uber") or p.text.startswith("Reimers"):
                    p.paragraph_format.space_before = Pt(0)
                    p.paragraph_format.space_after = Pt(2.5)
                    p.paragraph_format.line_spacing = 1.05
                else:
                    p.paragraph_format.space_before = Pt(0)
                    p.paragraph_format.space_after = Pt(sp_after)
                    p.paragraph_format.line_spacing = line_sp
                    
            doc.save(dst)
            
            wdoc = word.Documents.Open(os.path.abspath(dst), ReadOnly=True)
            wdoc.SaveAs2(os.path.abspath(pdf), 17)
            wdoc.Close(False)
            
            with pdfplumber.open(pdf) as pdoc:
                res = {}
                for i, page in enumerate(pdoc.pages):
                    text = page.extract_text() or ''
                    for key in ['Resumen Ejecutivo', '1. Introducción y contexto', '8. Conclusiones', '8.3. Limitaciones', 'Referencias bibliográficas', 'Anexos']:
                        if key.lower() in text.lower() and key not in res:
                            res[key] = i + 1
                
                print(f"CALIB (line_sp={line_sp}, sp_after={sp_after}pt): Resumen={res.get('Resumen Ejecutivo')}, Cap1={res.get('1. Introducción y contexto')}, Cap8={res.get('8. Conclusiones')}, Limit={res.get('8.3. Limitaciones')}, RefBib={res.get('Referencias bibliográficas')}, Anexos={res.get('Anexos')}", flush=True)
                
                # Criterio: Resumen Ejecutivo en Pág 4, Referencias en Pág 23, Anexos en Pág 24
                if res.get('Resumen Ejecutivo') == 4 and res.get('Referencias bibliográficas') == 23 and res.get('Anexos') == 24:
                    print(f"\n=======================================================", flush=True)
                    print(f"¡ÉXITO TOTAL! line_spacing={line_sp}, space_after={sp_after}pt", flush=True)
                    print(f"Resumen Ejecutivo: Página 4 (Cara 1)", flush=True)
                    print(f"Referencias bibliográficas: Página 23 (Cara 20)", flush=True)
                    print(f"Total caras de memoria evaluada = 23 - 4 + 1 = 20 CARAS EXACTAS", flush=True)
                    print(f"Anexos: Página 24", flush=True)
                    print(f"=======================================================\n", flush=True)
                    break
    finally:
        word.Quit()

if __name__ == "__main__":
    run_calibration()
