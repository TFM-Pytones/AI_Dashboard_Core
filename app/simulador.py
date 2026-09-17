"""
simulador.py
------------
Módulo de la vista 'Simulador de escenarios' (Subtarea 8.5 de plan_final_mejorado.md).
Permite modelar intervenciones territoriales (plazas alojativas, accesibilidad al aeropuerto,
regeneración ambiental NDVI, equipamientos/POIs e índice ESG) proyectando instantáneamente
el nuevo PTNA, los Ejes Estratégicos 1 y 2, los arquetipos TUI y las alertas de capacidad de carga.
"""

from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from app.color_scales import (
    ARCHETYPE_COLOR_MAP_HEX,
    CLUSTER_COLOR_MAP_HEX,
)
from app.data import list_municipios
from app.ui_helpers import add_chart_motion, format_metric


ARCHETYPE_NAMES_MAP = {
    "score_sol_playa": "🏖️ Sol y playa",
    "score_ecoturismo": "🌿 Ecoturismo rural",
    "score_cultural": "🏛️ Cultural y patrimonial",
    "score_aventura": "🏔️ Aventura y activo",
    "score_bienestar": "🧘 Bienestar y salud",
}

# Coeficientes de sensibilidad calibrados sobre el modelo MGWR
SENSITIVITY_BETA_TIEMPO = -4.50   # Menos tiempo al aeropuerto -> mayor potencial esperado
SENSITIVITY_BETA_NDVI = 220.0     # Más cobertura verde -> mayor potencial de calidad
SENSITIVITY_BETA_POIS = 2.80      # Mayor oferta complementaria -> mayor demanda esperada


def compute_dataset_normalization_bounds(gdf: pd.DataFrame) -> Dict[str, Tuple[float, float]]:
    """
    Precalcula los valores mínimos y máximos de cada variable para normalización MinMax
    vectorial rápida en el simulador sin recalcular sobre 2.579 filas en cada tick.
    """
    bounds = {}
    cols = [
        "n_plazas_registro", "viirs_medio", "dist_costa_km", "n_establecimientos_registro",
        "ndvi_medio", "ndbi_medio", "slope_mean", "altitud_media_m", "ptna_score",
        "esg_h3_score", "n_cultura", "n_restaurantes", "n_pois_total", "n_naturaleza",
        "rating_booking_medio", "temp_media_anual", "tiempo_aeropuerto_min",
    ]
    for col in cols:
        if col in gdf.columns:
            s = pd.to_numeric(gdf[col], errors="coerce").dropna()
            if not s.empty:
                bounds[col] = (float(s.min()), float(s.max()))
            else:
                bounds[col] = (0.0, 1.0)
        else:
            bounds[col] = (0.0, 1.0)

    # Normalización MinMax de componentes transformadas
    p_log = np.log1p(gdf["n_plazas_registro"].fillna(0).clip(lower=0))
    bounds["log_plazas"] = (float(p_log.min()), float(p_log.max()))

    v_log = np.log1p(gdf["viirs_medio"].fillna(0).clip(lower=0))
    bounds["log_viirs"] = (float(v_log.min()), float(v_log.max()))

    est_log = np.log1p(gdf["n_establecimientos_registro"].fillna(0).clip(lower=0))
    bounds["log_establ"] = (float(est_log.min()), float(est_log.max()))

    cult_log = np.log1p(gdf["n_cultura"].fillna(0).clip(lower=0))
    bounds["log_cultura"] = (float(cult_log.min()), float(cult_log.max()))

    rest_log = np.log1p(gdf["n_restaurantes"].fillna(0).clip(lower=0))
    bounds["log_rest"] = (float(rest_log.min()), float(rest_log.max()))

    pois_log = np.log1p(gdf["n_pois_total"].fillna(0).clip(lower=0))
    bounds["log_pois"] = (float(pois_log.min()), float(pois_log.max()))

    nat_log = np.log1p(gdf.get("n_naturaleza", pd.Series(0.0, index=gdf.index)).fillna(0).clip(lower=0))
    bounds["log_nat"] = (float(nat_log.min()), float(nat_log.max()))

    if "eje_1_saturacion" in gdf.columns:
        bounds["eje_1_saturacion"] = (float(gdf["eje_1_saturacion"].min()), float(gdf["eje_1_saturacion"].max()))
    if "eje_2_rural_infrautilizado" in gdf.columns:
        bounds["eje_2_rural_infrautilizado"] = (float(gdf["eje_2_rural_infrautilizado"].min()), float(gdf["eje_2_rural_infrautilizado"].max()))

    return bounds


def _norm_val(val: float, mn: float, mx: float) -> float:
    if mx > mn:
        return float(np.clip((val - mn) / (mx - mn), 0.0, 1.0))
    return 0.0


def simulate_hexagon_intervention(
    hexagon_data: pd.Series,
    delta_plazas: float,
    delta_tiempo_aeropuerto: float,
    delta_ndvi: float,
    delta_pois: float,
    delta_esg: float,
    bounds: Dict[str, Tuple[float, float]],
) -> Dict[str, Any]:
    """
    Función pura que ejecuta la proyección matemática instantánea de una intervención territorial.
    """
    area_km2 = float(hexagon_data.get("area_km2", 0.737))
    if area_km2 <= 0.05:
        area_km2 = 0.737

    # 1. Valores base
    base_plazas = float(hexagon_data.get("n_plazas_registro", 0.0) or 0.0)
    base_tiempo = float(hexagon_data.get("tiempo_aeropuerto_min", 45.0) or 45.0)
    base_ndvi = float(hexagon_data.get("ndvi_medio", 0.35) or 0.35)
    base_pois = float(hexagon_data.get("n_pois_total", 5.0) or 5.0)
    base_esg = float(hexagon_data.get("esg_h3_score", 50.0) or 50.0)
    base_ptna = float(hexagon_data.get("ptna_score", 0.0) or 0.0)
    base_eje1 = float(hexagon_data.get("eje_1_saturacion", 0.2) or 0.2)
    base_eje2 = float(hexagon_data.get("eje_2_rural_infrautilizado", 0.4) or 0.4)
    base_arquetipo = str(hexagon_data.get("arquetipo_principal", "🌿 Ecoturismo rural"))
    pct_enp = float(hexagon_data.get("pct_area_enp", 0.0) or 0.0)

    # 2. Nuevos valores absolutos simulados (con restricciones físicas)
    sim_plazas = max(0.0, base_plazas + delta_plazas)
    sim_tiempo = max(5.0, base_tiempo + delta_tiempo_aeropuerto)
    sim_ndvi = float(np.clip(base_ndvi + delta_ndvi, 0.0, 1.0))
    sim_pois = max(0.0, base_pois + delta_pois)
    sim_esg = float(np.clip(base_esg + delta_esg, 0.0, 100.0))

    # Estimación de restaurantes y cultura proporcional al cambio en POIs
    base_rest = float(hexagon_data.get("n_restaurantes", 2.0) or 2.0)
    base_cult = float(hexagon_data.get("n_cultura", 1.0) or 1.0)
    base_nat = float(hexagon_data.get("n_naturaleza", 1.0) or 1.0)
    sim_rest = max(0.0, base_rest + (delta_pois * 0.5))
    sim_cult = max(0.0, base_cult + (delta_pois * 0.3))
    sim_nat = max(0.0, base_nat + (delta_pois * 0.2))

    # 3. Proyección del PTNA simulado (Ecuación de sensibilidad MGWR)
    # Δ Plazas reduce el potencial no aprovechado (absorbe brecha de oferta)
    impacto_plazas_ptna = - (delta_plazas / area_km2)
    # Mejorar accesibilidad (-Δ tiempo) incrementa el potencial de demanda esperada
    impacto_tiempo_ptna = SENSITIVITY_BETA_TIEMPO * delta_tiempo_aeropuerto
    # Mejorar NDVI incrementa el potencial ambiental
    impacto_ndvi_ptna = SENSITIVITY_BETA_NDVI * delta_ndvi
    # Incrementar oferta de POIs incrementa el potencial esperado
    impacto_pois_ptna = SENSITIVITY_BETA_POIS * delta_pois

    sim_ptna = base_ptna + impacto_plazas_ptna + impacto_tiempo_ptna + impacto_ndvi_ptna + impacto_pois_ptna

    # 4. Proyección de componentes normalizadas
    p_norm = _norm_val(np.log1p(sim_plazas), bounds["log_plazas"][0], bounds["log_plazas"][1])
    v_norm = _norm_val(np.log1p(float(hexagon_data.get("viirs_medio", 0.0) or 0.0)), bounds["log_viirs"][0], bounds["log_viirs"][1])
    dist_costa = float(hexagon_data.get("dist_costa_km", 5.0) or 5.0)
    costa_prox = float(np.clip(1.0 - (dist_costa / 10.0), 0.0, 1.0))

    base_establ = float(hexagon_data.get("n_establecimientos_registro", 1.0) or 1.0)
    sim_establ = max(0.0, base_establ + (delta_plazas / 25.0))
    establ_norm = _norm_val(np.log1p(sim_establ), bounds["log_establ"][0], bounds["log_establ"][1])

    ndvi_norm = _norm_val(sim_ndvi, bounds["ndvi_medio"][0], bounds["ndvi_medio"][1])
    base_ndbi = float(hexagon_data.get("ndbi_medio", 0.0) or 0.0)
    ndbi_norm = _norm_val(base_ndbi, bounds["ndbi_medio"][0], bounds["ndbi_medio"][1])
    ndbi_inv = float(np.clip(1.0 - ndbi_norm, 0.0, 1.0))

    slope_norm = _norm_val(float(hexagon_data.get("slope_mean", 10.0) or 10.0), bounds["slope_mean"][0], bounds["slope_mean"][1])
    alt_norm = _norm_val(float(hexagon_data.get("altitud_media_m", 200.0) or 200.0), bounds["altitud_media_m"][0], bounds["altitud_media_m"][1])

    ptna_norm = _norm_val(sim_ptna, bounds["ptna_score"][0], bounds["ptna_score"][1])
    esg_norm = float(np.clip(sim_esg / 100.0, 0.0, 1.0))

    cult_norm = _norm_val(np.log1p(sim_cult), bounds["log_cultura"][0], bounds["log_cultura"][1])
    rest_norm = _norm_val(np.log1p(sim_rest), bounds["log_rest"][0], bounds["log_rest"][1])
    pois_norm = _norm_val(np.log1p(sim_pois), bounds["log_pois"][0], bounds["log_pois"][1])
    nat_norm = _norm_val(np.log1p(sim_nat), bounds["log_nat"][0], bounds["log_nat"][1])

    rating_val = float(hexagon_data.get("rating_booking_medio", 8.0) or 8.0)
    rating_norm = _norm_val(rating_val, bounds["rating_booking_medio"][0], bounds["rating_booking_medio"][1])

    temp_val = float(hexagon_data.get("temp_media_anual", 21.0) or 21.0)
    temp_opt = float(np.clip(1.0 - (abs(temp_val - 21.0) / 10.0), 0.0, 1.0))

    # 5. Proyección de Ejes Estratégicos
    # Eje 1 (Saturación / Presión de masificación)
    sim_eje_1_raw = 0.45 * p_norm + 0.25 * v_norm + 0.15 * costa_prox + 0.15 * establ_norm
    sim_eje_1 = float(np.clip(sim_eje_1_raw, 0.0, 1.0))

    # Eje 2 (Potencial rural y sostenible)
    no_masificacion = float(np.clip(1.0 - p_norm, 0.0, 1.0))
    sim_eje_2_raw = (
        0.25 * ndvi_norm +
        0.25 * ptna_norm +
        0.20 * no_masificacion +
        0.15 * ndbi_inv +
        0.15 * esg_norm
    )
    sim_eje_2 = float(np.clip(sim_eje_2_raw, 0.0, 1.0))

    # 6. Scores de los 5 Arquetipos TUI
    score_sol_playa = float(np.clip(0.40 * p_norm + 0.30 * costa_prox + 0.15 * v_norm + 0.15 * rating_norm, 0.0, 1.0))
    score_ecoturismo = float(np.clip(0.30 * ndvi_norm + 0.25 * ptna_norm + 0.25 * no_masificacion + 0.20 * esg_norm, 0.0, 1.0))
    score_cultural = float(np.clip(0.35 * cult_norm + 0.25 * rest_norm + 0.20 * pois_norm + 0.20 * ptna_norm, 0.0, 1.0))
    score_aventura = float(np.clip(0.35 * slope_norm + 0.30 * alt_norm + 0.20 * ndvi_norm + 0.15 * nat_norm, 0.0, 1.0))
    score_bienestar = float(np.clip(0.35 * temp_opt + 0.25 * no_masificacion + 0.20 * ndvi_norm + 0.20 * esg_norm, 0.0, 1.0))

    archetype_scores = {
        "score_sol_playa": score_sol_playa,
        "score_ecoturismo": score_ecoturismo,
        "score_cultural": score_cultural,
        "score_aventura": score_aventura,
        "score_bienestar": score_bienestar,
    }
    max_arch_key = max(archetype_scores, key=archetype_scores.get)
    sim_arquetipo = ARCHETYPE_NAMES_MAP[max_arch_key]

    # Scores base para comparativa
    base_scores = {
        "score_sol_playa": float(hexagon_data.get("score_sol_playa", 0.1) or 0.1),
        "score_ecoturismo": float(hexagon_data.get("score_ecoturismo", 0.4) or 0.4),
        "score_cultural": float(hexagon_data.get("score_cultural", 0.2) or 0.2),
        "score_aventura": float(hexagon_data.get("score_aventura", 0.3) or 0.3),
        "score_bienestar": float(hexagon_data.get("score_bienestar", 0.3) or 0.3),
    }

    # 7. Diagnósticos y Alertas Territoriales
    is_overtourism_risk = bool(sim_eje_1 >= 0.60 or sim_ptna < -50.0)
    is_enp_conflict = bool(pct_enp > 0.0 and delta_plazas > 0)
    is_ideal_opportunity = bool(sim_ptna > 0.0 and sim_esg > 60.0)
    archetype_changed = bool(sim_arquetipo != base_arquetipo)

    return {
        "base": {
            "plazas": base_plazas,
            "tiempo_aeropuerto": base_tiempo,
            "ndvi": base_ndvi,
            "pois": base_pois,
            "esg": base_esg,
            "ptna": base_ptna,
            "eje_1": base_eje1,
            "eje_2": base_eje2,
            "arquetipo": base_arquetipo,
            "scores": base_scores,
            "es_oportunidad_ideal": bool(hexagon_data.get("es_oportunidad_ideal", False)),
        },
        "simulado": {
            "plazas": sim_plazas,
            "tiempo_aeropuerto": sim_tiempo,
            "ndvi": sim_ndvi,
            "pois": sim_pois,
            "esg": sim_esg,
            "ptna": sim_ptna,
            "eje_1": sim_eje_1,
            "eje_2": sim_eje_2,
            "arquetipo": sim_arquetipo,
            "scores": archetype_scores,
            "es_oportunidad_ideal": is_ideal_opportunity,
        },
        "deltas": {
            "plazas": sim_plazas - base_plazas,
            "tiempo_aeropuerto": sim_tiempo - base_tiempo,
            "ndvi": sim_ndvi - base_ndvi,
            "pois": sim_pois - base_pois,
            "esg": sim_esg - base_esg,
            "ptna": sim_ptna - base_ptna,
            "eje_1": sim_eje_1 - base_eje1,
            "eje_2": sim_eje_2 - base_eje2,
        },
        "alertas": {
            "is_overtourism_risk": is_overtourism_risk,
            "is_enp_conflict": is_enp_conflict,
            "is_ideal_opportunity": is_ideal_opportunity,
            "archetype_changed": archetype_changed,
            "pct_enp": pct_enp,
        },
    }


def create_radar_comparison_chart(base_scores: Dict[str, float], sim_scores: Dict[str, float]) -> go.Figure:
    """
    Genera un radar chart comparativo que enfrenta la situación actual vs el escenario simulado.
    """
    categories = [
        "Sol y playa",
        "Ecoturismo rural",
        "Cultural y patrimonial",
        "Aventura y activo",
        "Bienestar y salud",
    ]
    keys = ["score_sol_playa", "score_ecoturismo", "score_cultural", "score_aventura", "score_bienestar"]

    r_base = [base_scores.get(k, 0.0) for k in keys] + [base_scores.get(keys[0], 0.0)]
    r_sim = [sim_scores.get(k, 0.0) for k in keys] + [sim_scores.get(keys[0], 0.0)]
    theta = categories + [categories[0]]

    fig = go.Figure()

    # Traza situación actual
    fig.add_trace(
        go.Scatterpolar(
            r=r_base,
            theta=theta,
            fill="toself",
            name="Situación actual",
            line=dict(color="#4A90E2", width=2),
            fillcolor="rgba(74, 144, 226, 0.20)",
        )
    )

    # Traza escenario simulado
    fig.add_trace(
        go.Scatterpolar(
            r=r_sim,
            theta=theta,
            fill="toself",
            name="Escenario simulado",
            line=dict(color="#F39C12", width=3, dash="solid"),
            fillcolor="rgba(243, 156, 18, 0.35)",
        )
    )

    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 1.0],
                tickfont=dict(size=10, color="#888"),
                gridcolor="rgba(200, 200, 200, 0.2)",
            ),
            angularaxis=dict(
                tickfont=dict(size=11, color="var(--text-color, #222)"),
                gridcolor="rgba(200, 200, 200, 0.2)",
            ),
        ),
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5),
        margin=dict(l=40, r=40, t=30, b=50),
        height=380,
    )

    return add_chart_motion(fig)


def create_strategic_matrix_simulation_chart(
    full_gdf: pd.DataFrame,
    municipio_actual: str,
    base_eje1: float,
    base_eje2: float,
    sim_eje1: float,
    sim_eje2: float,
) -> go.Figure:
    """
    Representa la posición del hexágono en la Matriz Estratégica Insular y muestra
    el vector de desplazamiento (Actual -> Simulado).
    """
    # Muestra los hexágonos de la isla como nube de contexto en tono suave
    df_sample = full_gdf.sample(min(len(full_gdf), 900), random_state=42).copy()

    fig = go.Figure()

    # Nube de fondo
    fig.add_trace(
        go.Scatter(
            x=df_sample["eje_1_saturacion"],
            y=df_sample["eje_2_rural_infrautilizado"],
            mode="markers",
            name="Resto de hexágonos",
            marker=dict(
                size=4,
                color="rgba(150, 160, 175, 0.30)",
                symbol="circle",
            ),
            hoverinfo="skip",
        )
    )

    # Vector de transición (línea con flecha implícita)
    fig.add_trace(
        go.Scatter(
            x=[base_eje1, sim_eje1],
            y=[base_eje2, sim_eje2],
            mode="lines",
            name="Desplazamiento",
            line=dict(color="#E74C3C", width=3, dash="dot"),
            hoverinfo="none",
        )
    )

    # Punto inicial (Base)
    fig.add_trace(
        go.Scatter(
            x=[base_eje1],
            y=[base_eje2],
            mode="markers+text",
            name="Punto inicial",
            text=["Inicial"],
            textposition="bottom center",
            marker=dict(size=13, color="#2980B9", symbol="circle", line=dict(color="#ffffff", width=2)),
            hovertemplate="<b>Situación actual</b><br>Eje 1: %{x:.3f}<br>Eje 2: %{y:.3f}<extra></extra>",
        )
    )

    # Punto final (Simulado)
    fig.add_trace(
        go.Scatter(
            x=[sim_eje1],
            y=[sim_eje2],
            mode="markers+text",
            name="Punto simulado",
            text=["Simulado"],
            textposition="top center",
            marker=dict(size=16, color="#E67E22", symbol="diamond", line=dict(color="#ffffff", width=2)),
            hovertemplate="<b>Escenario simulado</b><br>Eje 1: %{x:.3f}<br>Eje 2: %{y:.3f}<extra></extra>",
        )
    )

    # Cuadrantes estratégicos
    fig.add_vline(x=0.5, line_width=1, line_dash="dash", line_color="rgba(150, 150, 150, 0.4)")
    fig.add_hline(y=0.5, line_width=1, line_dash="dash", line_color="rgba(150, 150, 150, 0.4)")

    fig.update_layout(
        xaxis=dict(title="Eje 1: Saturación turística [0-1]", range=[-0.05, 1.05], gridcolor="rgba(200,200,200,0.15)"),
        yaxis=dict(title="Eje 2: Potencial rural y sostenible [0-1]", range=[-0.05, 1.05], gridcolor="rgba(200,200,200,0.15)"),
        margin=dict(l=50, r=30, t=30, b=50),
        height=380,
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=-0.25, xanchor="center", x=0.5),
    )

    return add_chart_motion(fig)


def render_simulador_tab(full_gdf: pd.DataFrame) -> None:
    """
    Renderiza la vista interactiva del Simulador de Escenarios ("What-If").
    """
    bounds = compute_dataset_normalization_bounds(full_gdf)

    st.markdown(
        """
        <p style='color: var(--text-color, #444); font-size: 1.05rem; margin-top: -0.5rem; margin-bottom: 1.2rem;'>
        Modela hipótesis de planificación territorial en Tenerife y proyecta en tiempo real el impacto
        en el índice <b>PTNA</b>, los <b>ejes estratégicos de capacidad</b> y la transición entre <b>arquetipos turísticos TUI</b>.
        </p>
        """,
        unsafe_allow_html=True,
    )

    # ── 1. Selector Territorial y Casos Representativos ──
    col_sel_mun, col_sel_hex = st.columns([1, 2])

    todos_municipios = list_municipios(full_gdf)
    municipio_sel = col_sel_mun.selectbox(
        "Municipio objetivo:",
        ["Todos"] + todos_municipios,
        index=0,
        help="Filtra la lista de hexágonos por municipio para acotar el análisis.",
    )

    if municipio_sel != "Todos":
        hex_pool = full_gdf[full_gdf["municipio"] == municipio_sel].copy()
    else:
        hex_pool = full_gdf.copy()

    # Prepara etiquetas descriptivas para el selectbox de hexágonos
    hex_pool["display_label"] = (
        hex_pool["h3_index"].astype(str).str.slice(0, 11) + "… | " +
        hex_pool["municipio"].astype(str) + " | " +
        hex_pool["arquetipo_principal"].astype(str) + " (" +
        hex_pool["n_plazas_registro"].fillna(0).astype(int).astype(str) + " plazas)"
    )

    # Atajos a hexágonos de referencia destacados
    st.caption("🎯 **Atajos a casos representativos de Tenerife:**")
    btn_c1, btn_c2, btn_c3, btn_c4, btn_c5 = st.columns(5)
    selected_h3_override = None

    # Buscamos índices representativos en el dataset real
    adeje_hex = full_gdf[full_gdf["municipio"] == "Adeje"].sort_values("n_plazas_registro", ascending=False)
    adeje_id = adeje_hex.iloc[0]["h3_index"] if not adeje_hex.empty else None

    isora_hex = full_gdf[(full_gdf["municipio"] == "Guia de Isora") & (full_gdf["ptna_score"] > 500)]
    isora_id = isora_hex.iloc[0]["h3_index"] if not isora_hex.empty else None

    puerto_hex = full_gdf[full_gdf["municipio"] == "Puerto de la Cruz"].sort_values("n_plazas_registro", ascending=False)
    puerto_id = puerto_hex.iloc[0]["h3_index"] if not puerto_hex.empty else None

    anaga_hex = full_gdf[(full_gdf["municipio"] == "Santa Cruz de Tenerife") & (full_gdf["pct_area_enp"] > 0.5)]
    anaga_id = anaga_hex.iloc[0]["h3_index"] if not anaga_hex.empty else None

    vilaflor_hex = full_gdf[full_gdf["municipio"] == "Vilaflor"].sort_values("altitud_media_m", ascending=False)
    vilaflor_id = vilaflor_hex.iloc[0]["h3_index"] if not vilaflor_hex.empty else None

    if btn_c1.button("🏝️ Adeje costa", help="Núcleo de alta densidad y masificación en el sur"):
        selected_h3_override = adeje_id
    if btn_c2.button("🌿 Guía de Isora rural", help="Medianías agrícolas con alto potencial PTNA no aprovechado"):
        selected_h3_override = isora_id
    if btn_c3.button("🏛️ Puerto de la Cruz casco", help="Zona tradicional con patrimonio y turismo consolidado"):
        selected_h3_override = puerto_id
    if btn_c4.button("🌲 Anaga reserva", help="Espacio protegido de máxima restricción ambiental"):
        selected_h3_override = anaga_id
    if btn_c5.button("🌋 Vilaflor cumbre", help="Alta cota, clima templado y turismo activo de montaña"):
        selected_h3_override = vilaflor_id

    # Determinar el hexágono seleccionado
    all_hex_indices = hex_pool["h3_index"].tolist()
    default_idx = 0
    if selected_h3_override and selected_h3_override in all_hex_indices:
        default_idx = all_hex_indices.index(selected_h3_override)

    selected_h3 = col_sel_hex.selectbox(
        "Hexágono H3 analizado:",
        all_hex_indices,
        index=default_idx,
        format_func=lambda h3: hex_pool.loc[hex_pool["h3_index"] == h3, "display_label"].values[0] if h3 in hex_pool["h3_index"].values else h3,
        help="Selecciona el hexágono sobre el que proyectar la intervención.",
    )

    if not selected_h3 or selected_h3 not in full_gdf["h3_index"].values:
        st.warning("No se ha seleccionado ningún hexágono válido.")
        return

    row = full_gdf.loc[full_gdf["h3_index"] == selected_h3].iloc[0]

    # ── 2. Ficha Base del Hexágono Seleccionado ──
    with st.container(border=True):
        f1, f2, f3, f4, f5 = st.columns(5)
        f1.metric("Municipio", str(row.get("municipio", "N/A")))
        f2.metric("Plazas actuales", f"{int(row.get('n_plazas_registro', 0) or 0):,} plazas")
        ptna_val = float(row.get("ptna_score", 0.0) or 0.0)
        f3.metric("Índice PTNA base", f"{ptna_val:+.1f}", help="Positivo = oportunidad infraexplotada; Negativo = sobreexplotado")
        f4.metric("Score ESG base", f"{float(row.get('esg_h3_score', 50.0) or 50.0):.1f} / 100")
        f5.metric("Arquetipo base", str(row.get("arquetipo_principal", "Ecoturismo rural")))

        cat_restriccion = str(row.get("restriction_category", "Sin restricción"))
        pct_enp = float(row.get("pct_area_enp", 0.0) or 0.0)
        if pct_enp > 0:
            st.caption(f"🛡️ **Protección legal:** {cat_restriccion} (solape con ENP: {pct_enp*100:.1f}%).")
        else:
            st.caption(f"✅ **Protección legal:** {cat_restriccion}.")

    st.divider()

    # ── 3. Panel de Configuración del Escenario (Presets + Sliders) ──
    st.subheader("⚙️ Configuración del escenario simulado")

    st.markdown("##### Presets rápidos de intervención")
    p_col1, p_col2, p_col3, p_col4, p_col5 = st.columns(5)

    # Estado de sesión para los sliders
    if "sim_delta_plazas" not in st.session_state:
        st.session_state.sim_delta_plazas = 0
    if "sim_delta_tiempo" not in st.session_state:
        st.session_state.sim_delta_tiempo = 0
    if "sim_delta_ndvi" not in st.session_state:
        st.session_state.sim_delta_ndvi = 0.0
    if "sim_delta_pois" not in st.session_state:
        st.session_state.sim_delta_pois = 0
    if "sim_delta_esg" not in st.session_state:
        st.session_state.sim_delta_esg = 0.0

    if p_col1.button("🏨 Expansión hotelera / resort", use_container_width=True):
        st.session_state.sim_delta_plazas = 400
        st.session_state.sim_delta_tiempo = -10
        st.session_state.sim_delta_ndvi = -0.06
        st.session_state.sim_delta_pois = 15
        st.session_state.sim_delta_esg = -5.0
        st.rerun()

    if p_col2.button("🌿 Ecoturismo y regeneración", use_container_width=True):
        st.session_state.sim_delta_plazas = 35
        st.session_state.sim_delta_tiempo = 0
        st.session_state.sim_delta_ndvi = 0.15
        st.session_state.sim_delta_pois = 5
        st.session_state.sim_delta_esg = 12.0
        st.rerun()

    if p_col3.button("🏛️ Hub cultural y dinamización", use_container_width=True):
        st.session_state.sim_delta_plazas = 60
        st.session_state.sim_delta_tiempo = -5
        st.session_state.sim_delta_ndvi = 0.02
        st.session_state.sim_delta_pois = 25
        st.session_state.sim_delta_esg = 6.0
        st.rerun()

    if p_col4.button("🛑 Moratoria y descompresión", use_container_width=True):
        st.session_state.sim_delta_plazas = -150
        st.session_state.sim_delta_tiempo = 0
        st.session_state.sim_delta_ndvi = 0.10
        st.session_state.sim_delta_pois = 0
        st.session_state.sim_delta_esg = 15.0
        st.rerun()

    if p_col5.button("🔄 Restablecer valores", use_container_width=True):
        st.session_state.sim_delta_plazas = 0
        st.session_state.sim_delta_tiempo = 0
        st.session_state.sim_delta_ndvi = 0.0
        st.session_state.sim_delta_pois = 0
        st.session_state.sim_delta_esg = 0.0
        st.rerun()

    # Sliders de control interactivo
    s_col1, s_col2 = st.columns(2)

    with s_col1:
        delta_plazas = st.slider(
            "Plazas de alojamiento regladas (Δ):",
            min_value=-500,
            max_value=1200,
            value=int(st.session_state.sim_delta_plazas),
            step=25,
            help="Modifica el número de plazas hoteleras o de alojamiento reglado en el hexágono.",
        )
        st.session_state.sim_delta_plazas = delta_plazas

        delta_tiempo = st.slider(
            "Tiempo de viaje al aeropuerto (Δ min):",
            min_value=-30,
            max_value=30,
            value=int(st.session_state.sim_delta_tiempo),
            step=5,
            help="Valores negativos representan mayor rapidez y mejor conectividad con TFS o TFN.",
        )
        st.session_state.sim_delta_tiempo = delta_tiempo

    with s_col2:
        delta_ndvi = st.slider(
            "Índice de vegetación NDVI (Δ):",
            min_value=-0.25,
            max_value=0.30,
            value=float(st.session_state.sim_delta_ndvi),
            step=0.02,
            help="Simula reforestación, parques o pérdida de cubierta vegetal.",
        )
        st.session_state.sim_delta_ndvi = delta_ndvi

        delta_pois = st.slider(
            "Puntos de interés y equipamientos (Δ):",
            min_value=-20,
            max_value=50,
            value=int(st.session_state.sim_delta_pois),
            step=5,
            help="Simula apertura de restaurantes, centros culturales o atractivos de ocio.",
        )
        st.session_state.sim_delta_pois = delta_pois

        delta_esg = st.slider(
            "Índice ESG territorial (Δ puntos):",
            min_value=-25.0,
            max_value=25.0,
            value=float(st.session_state.sim_delta_esg),
            step=2.5,
            help="Simula programas de gestión de residuos, descarbonización o inversión comunitaria.",
        )
        st.session_state.sim_delta_esg = delta_esg

    # ── 4. Ejecución del Modelo de Proyección ──
    sim_res = simulate_hexagon_intervention(
        hexagon_data=row,
        delta_plazas=delta_plazas,
        delta_tiempo_aeropuerto=delta_tiempo,
        delta_ndvi=delta_ndvi,
        delta_pois=delta_pois,
        delta_esg=delta_esg,
        bounds=bounds,
    )

    base = sim_res["base"]
    sim = sim_res["simulado"]
    deltas = sim_res["deltas"]
    alertas = sim_res["alertas"]

    st.divider()

    # ── 5. Resultados Proyectados (KPIs Comparativos) ──
    st.subheader("📊 Resultados de la simulación")

    kpi_c1, kpi_c2, kpi_c3, kpi_c4 = st.columns(4)

    with kpi_c1.container(border=True):
        st.metric(
            "Índice PTNA proyectado",
            f"{sim['ptna']:+.1f}",
            f"{deltas['ptna']:+.1f} vs actual",
            delta_color="normal",
            help="Brecha de oferta observada vs esperada según elasticidad MGWR.",
        )

    with kpi_c2.container(border=True):
        st.metric(
            "Eje 1: Saturación turística",
            f"{sim['eje_1']:.3f}",
            f"{deltas['eje_1']:+.3f} vs actual",
            delta_color="inverse",  # Aumento de saturación es negativo
            help="Mide la presión de masificación en el gradiente de saturación insular (0 a 1).",
        )

    with kpi_c3.container(border=True):
        st.metric(
            "Eje 2: Potencial rural y sostenible",
            f"{sim['eje_2']:.3f}",
            f"{deltas['eje_2']:+.3f} vs actual",
            delta_color="normal",  # Aumento de potencial es positivo
            help="Mide el potencial territorial no masificado y ambientalmente sostenible (0 a 1).",
        )

    with kpi_c4.container(border=True):
        arch_sub = "Sin cambio" if not alertas["archetype_changed"] else f"Antes: {base['arquetipo']}"
        st.metric(
            "Arquetipo dominante",
            sim["arquetipo"],
            arch_sub,
            delta_color="off",
            help="Arquetipo turístico dominante resultante del nuevo perfil de atributos.",
        )

    # ── 6. Banners de Alerta Territorial Inteligente ──
    if alertas["is_enp_conflict"]:
        st.warning(
            f"🛡️ **Restricción ambiental:** El hexágono presenta un {alertas['pct_enp']*100:.1f}% de solape con un "
            f"**Espacio Natural Protegido**. La adición de {int(deltas['plazas']):+} plazas de alojamiento está "
            f"sujeta a régimen especial de protección ambiental o moratoria turística en Canarias."
        )

    if alertas["is_overtourism_risk"]:
        st.error(
            f"⚠️ **Riesgo de saturación crítica / overtourism:** El escenario eleva el Eje 1 a **{sim['eje_1']:.3f}** "
            f"o reduce el PTNA a **{sim['ptna']:.1f}**, señalando riesgo de sobreexplotación de la capacidad de carga local."
        )

    if alertas["is_ideal_opportunity"] and not base["es_oportunidad_ideal"]:
        st.success(
            "🌟 **Oportunidad ideal desbloqueada:** Con la intervención propuesta, el hexágono cumple simultáneamente "
            "los criterios estratégicos de TUI: **PTNA > 0** (potencial atractivo) y **ESG > 60** (sostenibilidad certificada)."
        )

    # ── 7. Visualizaciones Gráficas Comparativas ──
    g_col1, g_col2 = st.columns([1, 1])

    with g_col1:
        st.markdown("##### Comparativa de arquetipos TUI")
        fig_radar = create_radar_comparison_chart(base["scores"], sim["scores"])
        st.plotly_chart(fig_radar, use_container_width=True)

    with g_col2:
        st.markdown("##### Desplazamiento en la matriz estratégica")
        fig_matrix = create_strategic_matrix_simulation_chart(
            full_gdf=full_gdf,
            municipio_actual=str(row.get("municipio", "")),
            base_eje1=base["eje_1"],
            base_eje2=base["eje_2"],
            sim_eje1=sim["eje_1"],
            sim_eje2=sim["eje_2"],
        )
        st.plotly_chart(fig_matrix, use_container_width=True)

    # ── 8. Diagnóstico Narrativo Ejecutivo Automatizado ──
    st.markdown("##### Diagnóstico estratégico del escenario")

    # Síntesis automática del impacto
    tipo_balance = "favorable" if (deltas["ptna"] >= 0 and deltas["eje_1"] < 0.1) else "de alta presión"
    if deltas["plazas"] > 0:
        texto_plazas = f"incremento de **{int(deltas['plazas']):+} plazas**"
    elif deltas["plazas"] < 0:
        texto_plazas = f"reducción de **{int(deltas['plazas']):+} plazas** para descompresión"
    else:
        texto_plazas = "mantenimiento de la capacidad alojativa existente"

    conclusiones: List[str] = []
    if alertas["is_overtourism_risk"]:
        conclusiones.append("el nivel de saturación proyectado desaconseja nuevas autorizaciones hoteleras estándar")
    elif sim["eje_1"] < 0.35 and sim["eje_2"] > 0.50:
        conclusiones.append("el área se consolida como un nicho privilegiado para productos de ecoturismo y turismo rural no invasivo")

    if alertas["archetype_changed"]:
        conclusiones.append(f"la intervención provoca una mutación estructural del arquetipo de **{base['arquetipo']}** hacia **{sim['arquetipo']}**")
    else:
        conclusiones.append(f"se preserva la identidad territorial del arquetipo **{sim['arquetipo']}**")

    if alertas["is_enp_conflict"]:
        conclusiones.append("se requiere informe ambiental vinculante previo debido al solape con espacios naturales protegidos")

    texto_conclusiones = "; ".join(conclusiones)

    st.info(
        f"""
        **Informe ejecutivo para TUI:**
        La simulación planteada para el hexágono `{selected_h3}` en **{row.get('municipio')}** contempla un {texto_plazas},
        una variación en accesibilidad de **{int(deltas['tiempo_aeropuerto']):+} min**, un ajuste en vegetación (NDVI) de **{deltas['ndvi']:+.2f}**,
        y un balance ESG de **{deltas['esg']:+.1f} puntos**.
        
        Como resultado, el índice PTNA evoluciona de **{base['ptna']:+.1f}** a **{sim['ptna']:+.1f}**, mientras que el Eje 1 de saturación
        alcanza **{sim['eje_1']:.3f}** y el Eje 2 de potencial rural se sitúa en **{sim['eje_2']:.3f}**.
        
        *Recomendación estratégica:* Al evaluar el balance {tipo_balance}, {texto_conclusiones}.
        """
    )
