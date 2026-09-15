# AI-Dashboard — app/

Dashboard v1: mapa H3 interactivo (densidad hotelera / sentimiento / NDVI)
+ panel de detalle por hexágono. Ver el diseño completo en
`docs/superpowers/specs/2026-09-07-streamlit-dashboard-design.md`.

## Ejecutar en local

1. Asegúrate de que `.env` tiene `AZURE_DB_URL` relleno (ver `.env.example`).
2. Instala dependencias: `.venv/bin/python -m pip install -r requirements.txt`
3. Arranca la app: `.venv/bin/python -m streamlit run app/main.py`

## Fuera de alcance de esta v1

Chatbot Text-to-SQL, simulador what-if, capas de PTNA/Clustering/Isócronas,
informe narrativo y bandeja de alertas — ver la sección "Fuera de alcance"
del spec.
