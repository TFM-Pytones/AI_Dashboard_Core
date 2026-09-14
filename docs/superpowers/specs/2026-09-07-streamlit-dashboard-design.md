# Dashboard v1 — Mapa H3 interactivo con KPIs (Streamlit)

## Contexto

El TFM "AI-Dashboard para la Gestión de la oferta turística georreferenciada
de Tenerife" define en `plan_final_mejorado.md` (Bloque 8) un dashboard
Streamlit completo: mapa H3, chatbot IA (Text-to-SQL), y simulador
"what-if" basado en coeficientes MGWR.

A día de hoy solo existen dos modelos gold en `dbt_project/models/gold/`:

- `gold_h3_master`: una fila por hexágono H3 (res. 8) con alojamiento,
  plataformas (Booking/TripAdvisor), POIs, transporte, topografía (MDT),
  satélite (NDVI/NDBI/VIIRS), clima estacional y distancia a costa.
- `gold_sentimiento_h3`: sentimiento medio (BERT multilingüe) y aspecto/queja
  principal (PyABSA) por hexágono, agregando reseñas de Booking + TripAdvisor.

No existen todavía: la tabla de scores PTNA/ESG, el clustering HDBSCAN
(`tipo_zona`), las isócronas de accesibilidad, los coeficientes MGWR, ni el
agente LangChain Text-to-SQL. Por tanto el Bloque 8 completo no es
construible hoy — este spec cubre únicamente la porción que sí lo es:
mapa interactivo + panel de detalle por hexágono. El chatbot y el
simulador what-if quedan como fases futuras, cada una con su propio
spec cuando sus dependencias (Bloque 5 y Bloque 7) existan.

## Objetivo

Una app Streamlit que permita a un usuario:

1. Ver Tenerife como una malla de hexágonos H3 coloreados por una métrica
   seleccionable (densidad hotelera, sentimiento, NDVI).
2. Filtrar el mapa por municipio.
3. Hacer clic en un hexágono y ver sus KPIs y sus aspectos/quejas NLP más
   frecuentes.

## Arquitectura

```
Azure PostgreSQL (esquema gold: gold_h3_master, gold_sentimiento_h3)
        │
        ▼  geopandas.read_postgis (cacheado con st.cache_data)
app/data.py
        │
        ├──▶ app/map_layers.py  ──▶ PyDeck H3HexagonLayer (3 capas toggleables)
        │
        └──▶ app/detail_panel.py ──▶ KPI cards (st.metric) + barra Plotly (aspectos)
        
app/main.py orquesta layout, sidebar (filtro municipio + toggle de capa) y
el estado de selección del hexágono clicado.
```

No hay una capa de servicio/API intermedia: Streamlit consulta Postgres
directamente, como ya hacía el resto del plan (`Subtarea 8.1`).

### Ficheros

- `app/main.py` — entrypoint (`streamlit run app/main.py`). Layout de
  página, sidebar (selector de capa + filtro de municipio), monta el mapa
  y el panel de detalle, y guarda el hexágono seleccionado en
  `st.session_state`.
- `app/data.py` — `get_engine()` (`st.cache_resource`, lee `AZURE_DB_URL`
  de `.env` vía `python-dotenv`), `load_h3_master()` y
  `load_sentimiento()` (`st.cache_data`, `geopandas.read_postgis` /
  `pandas.read_sql`), y un `join` de ambas por `h3_index` para exponer un
  único GeoDataFrame a la app.
- `app/map_layers.py` — construye las tres `pydeck.Layer` tipo
  `H3HexagonLayer` (una por métrica) y las funciones de escala de color
  correspondientes (secuencial para densidad/NDVI, divergente para
  sentimiento — paleta según skill `dataviz`). Devuelve el `pydeck.Deck`
  completo, listo para `st.pydeck_chart`.
- `app/detail_panel.py` — dado un `h3_index`, renderiza `st.metric` para
  KPIs (n_hoteles, ndvi_medio, sentimiento_medio, rating medio) y un
  `plotly.express.bar` con el conteo de aspectos/quejas del hexágono. Si
  no hay hexágono seleccionado, muestra un placeholder ("Haz clic en un
  hexágono del mapa").

## Interacción de selección

Se usa la selección nativa de Streamlit para PyDeck:
`st.pydeck_chart(deck, on_select="rerun", selection_mode="single-object")`
con las capas marcadas `pickable=True` e `id="h3_index"`. El hexágono
clicado llega en `st.session_state["<key>"]["selection"]["objects"]` y se
pasa a `detail_panel.py`. No se usan componentes de terceros
(`streamlit-keplergl`, etc.).

El filtro de municipio (sidebar `st.selectbox`, valores de
`gold_h3_master.municipio`) filtra el GeoDataFrame antes de construir las
capas — es un filtro adicional, no sustituye al clic.

## Capas del mapa (togglable vía `st.radio`/`st.multiselect` en sidebar)

| Capa | Columna | Tipo de escala |
|---|---|---|
| Densidad hotelera | `n_plazas_registro` (fallback `n_establecimientos_registro` si plazas es 0/NULL) | Secuencial |
| Sentimiento | `sentimiento_medio` (de `gold_sentimiento_h3`) | Divergente (centrado en el neutro de la escala de sentimiento) |
| Naturaleza (NDVI) | `ndvi_medio` | Secuencial |

Hexágonos con la métrica activa a `NULL` se pintan en gris ("sin datos")
en vez de excluirse del mapa, para no dar la falsa impresión de que la
zona no existe.

## Panel de detalle

Al seleccionar un hexágono:

- KPI cards: `n_hoteles`, `n_establecimientos_registro`, `ndvi_medio`,
  `sentimiento_medio`, `rating_booking_medio`, `rating_tripadvisor_medio`.
  Un valor `NULL` se muestra como "—", no como 0.
- Gráfico de barras Plotly con la frecuencia de `queja_principal` — dado
  que `gold_sentimiento_h3` solo trae el aspecto más frecuente (una fila
  por hexágono, no el desglose completo), la barra compara el hexágono
  seleccionado frente a la media del municipio al que pertenece (mismo
  patrón que ya sugiere el propio modelo dbt: "agrupar hexágonos por
  municipio en el dashboard").

## Manejo de errores

Ninguno artificial. Si la conexión a Postgres falla, se deja que
Streamlit muestre el traceback (es un fallo de configuración/red que hay
que ver, no enmascarar). Los `NULL` en columnas métricas se gestionan
mostrando "sin datos" en vez de fallar o convertir a 0 silenciosamente.

## Dependencias nuevas

Añadir a `requirements.txt` (no instaladas hoy): `streamlit`, `pydeck`,
`plotly`. Se mantiene `geopandas`, `sqlalchemy`, `psycopg2-binary`,
`python-dotenv`, ya presentes.

## Testing

No hay suite automatizada razonable para una app visual de Streamlit. La
verificación es manual: `streamlit run app/main.py` contra la BD Azure
real, comprobando que:

1. Las 3 capas pintan y cambian correctamente al togglear.
2. El filtro de municipio reduce el mapa a los hexágonos correctos.
3. El clic en un hexágono actualiza el panel de detalle con sus datos.
4. Un hexágono sin reseñas (sentimiento `NULL`) no rompe ni el mapa ni el
   panel.

## Fuera de alcance (fases futuras, specs propios)

- Chatbot Text-to-SQL (Bloque 7 del plan) — requiere el agente LangChain,
  que no existe todavía.
- Simulador what-if (Subtarea 8.5) — requiere los coeficientes MGWR
  (Bloque 5), que no existen todavía.
- Capas de Potencial PTNA, Clustering Overtourism/Rural e Isócronas —
  requieren tablas gold que no existen todavía.
- Informe narrativo automático y bandeja de alertas (Bloques 9-10).
