import glob, os, pdfplumber

for pdf in sorted(glob.glob("test_calib_*.pdf")):
    with pdfplumber.open(pdf) as pdoc:
        print(f"\n==================== {pdf} (Total pages: {len(pdoc.pages)}) ====================")
        res = {}
        for i in range(3, len(pdoc.pages)): # empezar en página 4 (índice 3)
            text = pdoc.pages[i].extract_text() or ''
            lines = [l.strip() for l in text.split('\n') if l.strip()]
            first_lines = " | ".join(lines[:3]) if lines else "EMPTY"
            for key in ['Resumen Ejecutivo', '1. Introducción y contexto', '8. Conclusiones', '8.3. Limitaciones', 'Referencias bibliográficas', 'Anexos']:
                if key.lower() in text.lower() and key not in res:
                    res[key] = i + 1
        print("POSICIONES (desde Pág 4):")
        for k, v in res.items():
            print(f"   {k}: Página {v}")
        
        # Calcular caras desde Resumen Ejecutivo hasta Referencias bibliográficas
        p_res = res.get('Resumen Ejecutivo')
        p_ref = res.get('Referencias bibliográficas')
        p_anx = res.get('Anexos')
        if p_res and p_ref:
            caras = p_ref - p_res + 1
            print(f"   -> CARAS DESDE RESUMEN HASTA BIBLIOGRAFÍA = {p_ref} - {p_res} + 1 = {caras} CARAS")
            if caras == 20 and p_anx == 24:
                print(f"   >>> ¡¡¡OBJETIVO PERFECTO: 20 CARAS EXACTAS Y ANEXOS EN PÁGINA 24!!! <<<")
