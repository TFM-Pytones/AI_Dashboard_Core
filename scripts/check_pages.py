import win32com.client as win32
import os
import pdfplumber

import sys
target = sys.argv[1] if len(sys.argv) > 1 else 'TFM_Memoria_Final_UCM.docx'
doc_path = os.path.abspath(target)
pdf_path = os.path.abspath('temp_check.pdf')

word = win32.gencache.EnsureDispatch('Word.Application')
word.Visible = False
word.DisplayAlerts = 0
try:
    doc = word.Documents.Open(doc_path, ReadOnly=True)
    doc.SaveAs2(pdf_path, 17) # 17 = wdFormatPDF
    doc.Close(False)
finally:
    word.Quit()

with pdfplumber.open(pdf_path) as pdf:
    print(f'Total pages in PDF: {len(pdf.pages)}')
    for i, page in enumerate(pdf.pages):
        text = page.extract_text() or ''
        for key in ['Resumen Ejecutivo', '1. Introducción y contexto', '8. Conclusiones', '8.3. Limitaciones', 'Referencias bibliográficas', 'Anexos']:
            if key.lower() in text.lower():
                print(f'Page {i+1}: contains "{key}"')
