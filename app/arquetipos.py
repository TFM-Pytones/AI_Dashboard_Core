import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

from app.color_scales import (
    ACCENT_OPORTUNIDADES,
    ARCHETYPE_COLOR_MAP_HEX,
    CLUSTER_COLOR_MAP_HEX,
)
from app.data import filter_by_municipio, list_municipios
from app.ui_helpers import add_chart_motion, format_metric


def render_arquetipos_tab(gdf: pd.DataFrame) -> None:
    st.markdown("<div style='margin-top: 1.5rem;'></div>", unsafe_allow_html=True)

    # ── 1. Resumen Ejecutivo y Métricas Clave ──
    n_total = len(gdf)
    n_saturado = int((gdf["tipo_zona"] == "Saturado/Overtourism").sum())
    n_transicion = int((gdf["tipo_zona"] == "Transición").sum())
    n_rural_infra = int((gdf["tipo_zona"] == "Rural Infrautilizada").sum())
    n_oportunidad_ideal = int(gdf.get("es_oportunidad_ideal", pd.Series(False, index=gdf.index)).sum())

    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    with kpi1.container(border=True):
        st.metric(
            "🔴 Clúster Saturado (Overtourism)",
            f"{n_saturado} hex.",
            f"{(n_saturado / n_total * 100):.1f}% del territorio",
            help="Hexágonos costeros con densidad hotelera extrema y máxima luz nocturna (HDBSCAN).",
        )
    with kpi2.container(border=True):
        st.metric(
            "🟡 Clúster Transición",
            f"{n_transicion} hex.",
            f"{(n_transicion / n_total * 100):.1f}% del territorio",
            help="Zonas con desarrollo turístico moderado o en crecimiento, óptimas para diversificación.",
        )
    with kpi3.container(border=True):
        st.metric(
            "🟢 Rural Infrautilizado",
            f"{n_rural_infra} hex.",
            f"{(n_rural_infra / n_total * 100):.1f}% del territorio",
            help="Zonas de alto valor paisajístico y natural (NDVI alto, PTNA positivo) sin explotación masiva.",
        )
    with kpi4.container(border=True):
        st.metric(
            "⭐ Oportunidades Ideales TUI",
            f"{n_oportunidad_ideal} hex.",
            "Alto PTNA + Alto ESG",
            help="Hexágonos identificados en Bloque 5 que combinan alto potencial de atracción y máxima sostenibilidad.",
        )

    st.divider()

    # ── 2. Matriz Estratégica Territorial 2D ──
    st.subheader("🧭 Matriz Estratégica: Eje 1 vs Eje 2")
    st.markdown(
        """
        Esta matriz proyecta la totalidad del territorio insular en dos dimensiones cuantitativas complementarias:
        - **Eje 1 (HDBSCAN, silhouette 0.808): Saturado $\\leftrightarrow$ Transición [continuo]**  
          Mide el gradiente continuo de presión y densidad turística (de 0,0 en núcleos sin presión hasta 1,0 en saturación extrema).
        - **Eje 2 (score compuesto): Rural Infrautilizado [0-1]**  
          Integra vegetación satelital (NDVI), potencial no explotado (PTNA), ausencia de masificación previa, baja artificialización y score ESG.
        """
    )

    col_ctrl1, col_ctrl2 = st.columns([2, 2])
    color_by = col_ctrl1.radio(
        "Colorear puntos por:",
        ["Tipología Territorial (Clústeres)", "Arquetipo TUI Óptimo"],
        horizontal=True,
    )
    filtro_muni = col_ctrl2.selectbox(
        "Filtrar por municipio en la matriz:",
        ["Todos"] + list_municipios(gdf),
        key="matriz_muni_filtro",
    )

    matriz_df = filter_by_municipio(gdf, filtro_muni).copy()

    # Mapeo de color para el scatter
    if color_by == "Tipología Territorial (Clústeres)":
        color_col = "tipo_zona"
        color_map = CLUSTER_COLOR_MAP_HEX
    else:
        color_col = "arquetipo_principal"
        color_map = ARCHETYPE_COLOR_MAP_HEX

    fig_scatter = px.scatter(
        matriz_df,
        x="eje_1_saturacion",
        y="eje_2_rural_infrautilizado",
        color=color_col,
        color_discrete_map=color_map,
        hover_name="municipio",
        hover_data={
            "h3_index": True,
            "tipo_zona": True,
            "arquetipo_principal": True,
            "n_plazas_registro": ":d",
            "eje_1_saturacion": ":.3f",
            "eje_2_rural_infrautilizado": ":.3f",
            "ptna_score": ":.2f",
            "esg_h3_score": ":.1f",
        },
        labels={
            "eje_1_saturacion": "Eje 1: Saturación Turística (HDBSCAN continuo)",
            "eje_2_rural_infrautilizado": "Eje 2: Rural Infrautilizado (Score compuesto 0-1)",
            color_col: "Categoría",
        },
        title="Posicionamiento Territorial en la Matriz Estratégica TUI",
        height=540,
    )

    # Líneas divisorias de cuadrantes estratégicos
    fig_scatter.add_vline(x=0.45, line_dash="dash", line_color="#94a3b8", opacity=0.6)
    fig_scatter.add_hline(y=0.55, line_dash="dash", line_color="#94a3b8", opacity=0.6)

    # Anotaciones de cuadrantes
    fig_scatter.add_annotation(
        x=0.85,
        y=0.15,
        text="<b>CUADRANTE I: SATURADO</b><br>Contención & Descompresión",
        showarrow=False,
        bgcolor="rgba(239, 68, 68, 0.12)",
        bordercolor="#ef4444",
        font=dict(size=11, color="#991b1b"),
    )
    fig_scatter.add_annotation(
        x=0.15,
        y=0.85,
        text="<b>CUADRANTE II: RURAL INFRAUTILIZADO</b><br>Ecoturismo & Alto Potencial",
        showarrow=False,
        bgcolor="rgba(16, 185, 129, 0.12)",
        bordercolor="#10b981",
        font=dict(size=11, color="#065f46"),
    )
    fig_scatter.add_annotation(
        x=0.50,
        y=0.45,
        text="<b>CUADRANTE III: TRANSICIÓN</b><br>Cultura, Pueblo & Bienestar",
        showarrow=False,
        bgcolor="rgba(245, 158, 11, 0.12)",
        bordercolor="#f59e0b",
        font=dict(size=11, color="#92400e"),
    )
    fig_scatter.add_annotation(
        x=0.15,
        y=0.15,
        text="<b>CUADRANTE IV: URBANO / RESIDENCIAL</b><br>Sin oferta turística directa",
        showarrow=False,
        bgcolor="rgba(100, 116, 139, 0.12)",
        bordercolor="#64748b",
        font=dict(size=11, color="#334155"),
    )

    fig_scatter.update_traces(marker=dict(size=7, opacity=0.8))
    fig_scatter.update_layout(
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis=dict(range=[-0.02, 1.05]),
        yaxis=dict(range=[-0.02, 1.05]),
    )
    add_chart_motion(fig_scatter)
    st.plotly_chart(fig_scatter, width="stretch")

    st.divider()

    # ── 3. Fichas de los 5 Arquetipos de Producto Turístico TUI ──
    st.subheader("🏷️ Catálogo de Arquetipos de Producto TUI")
    st.caption("Estrategias de desarrollo turístico y modelos operativos basados en los datos del dashboard.")

    tab_sol, tab_eco, tab_cult, tab_av, tab_bien = st.tabs(
        [
            "🏖️ Sol y Playa Premium",
            "🌿 Ecoturismo Rural",
            "🏛️ Cultural y Patrimonial",
            "🏔️ Aventura y Activo",
            "🧘 Bienestar y Salud",
        ]
    )

    with tab_sol:
        c1, c2 = st.columns([2, 1])
        with c1:
            st.markdown("### 🏖️ Sol y Playa Premium (Gestión de Capacidad)")
            st.markdown(
                """
                - **Ubicación clave:** Adeje, Arona (Los Cristianos, Playa de las Américas), Puerto de la Cruz litoral.
                - **Perfil territorial:** Eje 1 alto (> 0,55), proximidad a costa < 1 km, altitud media baja, alta densidad de plazas y luz nocturna VIIRS.
                - **Estrategia TUI:**
                  1. **Contención de nuevas plazas:** Priorizar renovación cualitativa sobre expansión cuantitativa.
                  2. **Certificación ESG & Eco-Hotels:** Acompañar a la planta hotelera con sellos de sostenibilidad insular.
                  3. **Descompresión activa:** Ofrecer a los huéspedes de sol y playa paquetes integrados de excursión hacia las medianías rurales y culturales.
                """
            )
        with c2.container(border=True):
            sub_df = gdf[gdf["arquetipo_principal"] == "🏖️ Sol y Playa"]
            st.metric("Hexágonos asignados", f"{len(sub_df)}")
            st.metric("Plazas registradas", format_metric(int(sub_df["n_plazas_registro"].sum()), "entero"))
            st.metric("Eje 1 medio", f"{sub_df['eje_1_saturacion'].mean():.2f}")
            st.metric("Distancia a costa media", f"{sub_df['dist_costa_km'].mean():.2f} km")

    with tab_eco:
        c1, c2 = st.columns([2, 1])
        with c1:
            st.markdown("### 🌿 Ecoturismo Rural (Dinamización en Rural Infrautilizado)")
            st.markdown(
                """
                - **Ubicación clave:** Medianías de La Orotava, Teno (Buenavista, El Tanque), Anaga (Santa Cruz/La Laguna norte), Vilaflor, Arico interior.
                - **Perfil territorial:** Eje 2 muy alto (> 0,65), NDVI > 0,40, PTNA positivo (+20 a +40), muy baja densidad de camas (< 20 por celda).
                - **Estrategia TUI:**
                  1. **Red TUI Nature Lodges:** Red de casas rurales y agroturismos de alta calidad con gestión descentralizada.
                  2. **Dinamización de la economía local:** Traspaso directo de gasto turístico al sector primario, gastronomía km 0 y artesanía.
                  3. **Turismo regenerativo:** Rutas de reforestación y conservación de la laurisilva y pinares.
                """
            )
        with c2.container(border=True):
            sub_df = gdf[gdf["arquetipo_principal"] == "🌿 Ecoturismo Rural"]
            st.metric("Hexágonos asignados", f"{len(sub_df)}")
            st.metric("Eje 2 medio (potencial rural)", f"{sub_df['eje_2_rural_infrautilizado'].mean():.2f}")
            st.metric("NDVI medio", f"{sub_df['ndvi_medio'].mean():.2f}")
            st.metric("PTNA Score medio", f"{sub_df['ptna_score'].mean():.1f}")

    with tab_cult:
        c1, c2 = st.columns([2, 1])
        with c1:
            st.markdown("### 🏛️ Cultural y Patrimonial (Identidad y Enoturismo)")
            st.markdown(
                """
                - **Ubicación clave:** San Cristóbal de La Laguna (Patrimonio UNESCO), La Orotava casco histórico, Garachico, Candelaria, Icod de los Vinos.
                - **Perfil territorial:** Alta concentración de POIs culturales y gastronómicos, transpirabilidad peatonal, conexión de guaguas (TITSA), sentimiento positivo.
                - **Estrategia TUI:**
                  1. **Rutas temáticas histórico-arquitectónicas:** Circuitos guiados por historiadores locales.
                  2. **Enoturismo y Rutas de Guachinches:** Visitas exclusivas a bodegas de las Denominaciones de Origen Tacoronte-Acentejo, Valle de La Orotava y Abona.
                  3. **Turismo urbano cultural no masificado:** Boutique hotels en edificios históricos protegidos.
                """
            )
        with c2.container(border=True):
            sub_df = gdf[gdf["arquetipo_principal"] == "🏛️ Cultural y Patrimonial"]
            st.metric("Hexágonos asignados", f"{len(sub_df)}")
            st.metric("POIs culturales totales", f"{int(sub_df['n_cultura'].sum())}")
            st.metric("Restaurantes registrados", f"{int(sub_df['n_restaurantes'].sum())}")
            st.metric("Sentimiento medio", f"{sub_df['sentimiento_medio'].mean():.2f} / 5")

    with tab_av:
        c1, c2 = st.columns([2, 1])
        with c1:
            st.markdown("### 🏔️ Aventura y Activo (Turismo Deportivo y Vulcanológico)")
            st.markdown(
                """
                - **Ubicación clave:** Anillo de la Corona Forestal, Parque Nacional del Teide, Macizo de Teno (Masca), barrancos del sur.
                - **Perfil territorial:** Pendiente elevada (> 15°), gran amplitud altitudinal (> 800 m), presencia de senderos PR/GR y miradores naturales.
                - **Estrategia TUI:**
                  1. **Trekking y trail running guiado:** Rutas de montaña seguras y respetuosas con los senderos oficiales del Cabildo.
                  2. **Astroturismo Reserva Starlight:** Excursiones nocturnas a cumbres con telescopios y astrofísica divulgativa.
                  3. **Cicloturismo de altura:** Entrenamiento de pretemporada y rutas gravel por pistas forestales autorizadas.
                """
            )
        with c2.container(border=True):
            sub_df = gdf[gdf["arquetipo_principal"] == "🏔️ Aventura y Activo"]
            st.metric("Hexágonos asignados", f"{len(sub_df)}")
            st.metric("Pendiente media", f"{sub_df['slope_mean'].mean():.1f}°")
            st.metric("Altitud media", f"{sub_df['altitud_media_m'].mean():.0f} m")
            st.metric("Score Aventura medio", f"{sub_df['score_aventura'].mean():.2f}")

    with tab_bien:
        c1, c2 = st.columns([2, 1])
        with c1:
            st.markdown("### 🧘 Bienestar y Salud (Desestacionalización Climática)")
            st.markdown(
                """
                - **Ubicación clave:** Medianías bajas del norte (Tacoronte, Sauzal) y valles protegidos del sur (Valle San Lorenzo, Guía de Isora interior).
                - **Perfil territorial:** Temperatura media anual templada (~20-22°C), baja oscilación térmica diaria, ambiente sereno sin contaminación acústica ni masificación.
                - **Estrategia TUI:**
                  1. **Estancias medias y largas de invierno (Silver Tourism):** Destino de salud para público sénior europeo que huye del frío continental.
                  2. **Retiros holísticos y spas de naturaleza:** Centros de yoga, relajación y talasoterapia sostenible.
                  3. **Nómadas digitales wellness:** Alojamientos preparados con alta conectividad y entorno saludable.
                """
            )
        with c2.container(border=True):
            sub_df = gdf[gdf["arquetipo_principal"] == "🧘 Bienestar y Salud"]
            st.metric("Hexágonos asignados", f"{len(sub_df)}")
            st.metric("Temperatura media anual", f"{sub_df['temp_media_anual'].mean():.1f} °C")
            st.metric("Score ESG medio", f"{sub_df['esg_h3_score'].mean():.1f} / 100")
            st.metric("Score Bienestar medio", f"{sub_df['score_bienestar'].mean():.2f}")

    st.divider()

    # ── 4. Explorador y Catálogo de Oportunidades por Arquetipo ──
    st.subheader("🔍 Catálogo Filtrable de Hexágonos y Oportunidades")

    col_f1, col_f2, col_f3 = st.columns(3)
    arq_opciones = ["Todos"] + sorted(gdf["arquetipo_principal"].dropna().unique().tolist())
    sel_arq = col_f1.selectbox("Filtrar por Arquetipo", arq_opciones)
    muni_opciones = ["Todos"] + list_municipios(gdf)
    sel_muni = col_f2.selectbox("Filtrar por Municipio", muni_opciones, key="catalogo_muni")
    solo_ideal = col_f3.checkbox("⭐ Solo Oportunidad Ideal (PTNA + ESG)", value=False)

    catalogo = gdf.copy()
    if sel_arq != "Todos":
        catalogo = catalogo[catalogo["arquetipo_principal"] == sel_arq]
    if sel_muni != "Todos":
        catalogo = catalogo[catalogo["municipio"] == sel_muni]
    if solo_ideal and "es_oportunidad_ideal" in catalogo.columns:
        catalogo = catalogo[catalogo["es_oportunidad_ideal"] == True]

    st.caption(f"Mostrando **{len(catalogo)}** hexágonos según los filtros seleccionados.")

    columnas_mostrar = [
        "h3_index",
        "municipio",
        "tipo_zona",
        "arquetipo_principal",
        "eje_1_saturacion",
        "eje_2_rural_infrautilizado",
        "n_plazas_registro",
        "ptna_score",
        "esg_h3_score",
        "ndvi_medio",
        "altitud_media_m",
    ]
    cols_existentes = [c for c in columnas_mostrar if c in catalogo.columns]
    tabla_display = catalogo[cols_existentes].sort_values(
        by="eje_2_rural_infrautilizado" if sel_arq == "🌿 Ecoturismo Rural" else "eje_1_saturacion",
        ascending=False,
    )

    column_config = {
        "h3_index": st.column_config.TextColumn("H3 ID"),
        "municipio": st.column_config.TextColumn("Municipio"),
        "tipo_zona": st.column_config.TextColumn("Clúster Territorial"),
        "arquetipo_principal": st.column_config.TextColumn("Arquetipo Óptimo"),
        "eje_1_saturacion": st.column_config.ProgressColumn(
            "Eje 1 (Saturación)", min_value=0.0, max_value=1.0, format="%.2f"
        ),
        "eje_2_rural_infrautilizado": st.column_config.ProgressColumn(
            "Eje 2 (Rural Infrautilizado)", min_value=0.0, max_value=1.0, format="%.2f"
        ),
        "n_plazas_registro": st.column_config.NumberColumn("Plazas", format="%d"),
        "ptna_score": st.column_config.NumberColumn("PTNA Score", format="%.1f"),
        "esg_h3_score": st.column_config.NumberColumn("Score ESG", format="%.1f"),
        "ndvi_medio": st.column_config.NumberColumn("NDVI", format="%.2f"),
        "altitud_media_m": st.column_config.NumberColumn("Altitud (m)", format="%.0f"),
    }

    st.dataframe(
        tabla_display,
        column_config=column_config,
        hide_index=True,
        width="stretch",
    )

    csv_data = tabla_display.to_csv(index=False).encode("utf-8")
    st.download_button(
        "📥 Descargar Catálogo de Oportunidades (CSV)",
        data=csv_data,
        file_name="catalogo_oportunidades_tui.csv",
        mime="text/csv",
    )
