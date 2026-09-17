"""
simulador.py
------------
Módulo de la vista 'Simulador de escenarios' (Subtarea 8.5 de plan_final_mejorado.md).
Permite modelar intervenciones territoriales a nivel de hexágono individual, municipio completo,
arquetipo turístico TUI o clúster territorial, proyectando instantáneamente el nuevo PTNA,
los Ejes Estratégicos 1 y 2, los arquetipos TUI y las alertas de capacidad de carga.
"""

from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app.color_scales import (
    ARCHETYPE_COLOR_MAP_HEX,
    CLUSTER_COLOR_MAP_HEX,
)
from app.data import list_municipios
from app.ui_helpers import add_chart_motion


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


def aggregate_hexagon_group(group_df: pd.DataFrame, label: str, group_type: str) -> pd.Series:
    """
    Sintetiza un conjunto de hexágonos (por municipio, arquetipo o clúster) en una fila
    representativa para alimentar el motor de simulación.
    """
    n_hex = max(1, len(group_df))
    total_area = float(group_df["area_km2"].sum() if "area_km2" in group_df.columns else n_hex * 0.737)
    total_plazas = float(group_df["n_plazas_registro"].sum() if "n_plazas_registro" in group_df.columns else 0.0)

    # Arquetipo dominante en el grupo (moda)
    if "arquetipo_principal" in group_df.columns and not group_df["arquetipo_principal"].empty:
        mode_arch = group_df["arquetipo_principal"].mode()
        arch_dom = mode_arch.iloc[0] if not mode_arch.empty else "🌿 Ecoturismo rural"
    else:
        arch_dom = "🌿 Ecoturismo rural"

    # Categoría de restricción mayoritaria
    if "restriction_category" in group_df.columns and not group_df["restriction_category"].empty:
        mode_rest = group_df["restriction_category"].mode()
        rest_dom = mode_rest.iloc[0] if not mode_rest.empty else "Sin restricción"
    else:
        rest_dom = "Sin restricción"

    # Municipio
    if group_type == "municipio":
        mun_name = label
    else:
        mun_mode = group_df["municipio"].mode() if "municipio" in group_df.columns else pd.Series()
        mun_name = mun_mode.iloc[0] if not mun_mode.empty else "Insular"

    synth_dict = {
        "h3_index": f"{label} ({n_hex} hex.)",
        "municipio": mun_name,
        "n_hex": n_hex,
        "area_km2": total_area,
        "n_plazas_registro": total_plazas,
        "tiempo_aeropuerto_min": float(group_df["tiempo_aeropuerto_min"].mean() if "tiempo_aeropuerto_min" in group_df.columns else 40.0),
        "ndvi_medio": float(group_df["ndvi_medio"].mean() if "ndvi_medio" in group_df.columns else 0.35),
        "viirs_medio": float(group_df["viirs_medio"].mean() if "viirs_medio" in group_df.columns else 10.0),
        "ndbi_medio": float(group_df["ndbi_medio"].mean() if "ndbi_medio" in group_df.columns else 0.0),
        "dist_costa_km": float(group_df["dist_costa_km"].mean() if "dist_costa_km" in group_df.columns else 5.0),
        "n_establecimientos_registro": float(group_df["n_establecimientos_registro"].sum() if "n_establecimientos_registro" in group_df.columns else 5.0),
        "slope_mean": float(group_df["slope_mean"].mean() if "slope_mean" in group_df.columns else 10.0),
        "altitud_media_m": float(group_df["altitud_media_m"].mean() if "altitud_media_m" in group_df.columns else 300.0),
        "ptna_score": float(group_df["ptna_score"].mean() if "ptna_score" in group_df.columns else 0.0),
        "esg_h3_score": float(group_df["esg_h3_score"].mean() if "esg_h3_score" in group_df.columns else 52.0),
        "n_cultura": float(group_df["n_cultura"].sum() if "n_cultura" in group_df.columns else 2.0),
        "n_restaurantes": float(group_df["n_restaurantes"].sum() if "n_restaurantes" in group_df.columns else 10.0),
        "n_pois_total": float(group_df["n_pois_total"].sum() if "n_pois_total" in group_df.columns else 20.0),
        "n_naturaleza": float(group_df["n_naturaleza"].sum() if "n_naturaleza" in group_df.columns else 5.0),
        "rating_booking_medio": float(group_df["rating_booking_medio"].mean() if "rating_booking_medio" in group_df.columns else 8.1),
        "temp_media_anual": float(group_df["temp_media_anual"].mean() if "temp_media_anual" in group_df.columns else 21.0),
        "pct_area_enp": float(group_df["pct_area_enp"].mean() if "pct_area_enp" in group_df.columns else 0.0),
        "eje_1_saturacion": float(group_df["eje_1_saturacion"].mean() if "eje_1_saturacion" in group_df.columns else 0.25),
        "eje_2_rural_infrautilizado": float(group_df["eje_2_rural_infrautilizado"].mean() if "eje_2_rural_infrautilizado" in group_df.columns else 0.45),
        "score_sol_playa": float(group_df["score_sol_playa"].mean() if "score_sol_playa" in group_df.columns else 0.2),
        "score_ecoturismo": float(group_df["score_ecoturismo"].mean() if "score_ecoturismo" in group_df.columns else 0.5),
        "score_cultural": float(group_df["score_cultural"].mean() if "score_cultural" in group_df.columns else 0.3),
        "score_aventura": float(group_df["score_aventura"].mean() if "score_aventura" in group_df.columns else 0.3),
        "score_bienestar": float(group_df["score_bienestar"].mean() if "score_bienestar" in group_df.columns else 0.4),
        "arquetipo_principal": arch_dom,
        "es_oportunidad_ideal": bool(group_df["es_oportunidad_ideal"].any() if "es_oportunidad_ideal" in group_df.columns else False),
        "restriction_category": rest_dom,
    }
    return pd.Series(synth_dict)


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
    Soporta tanto hexágonos individuales como agregaciones macro (municipales o clústeres).
    """
    n_hex = int(hexagon_data.get("n_hex", 1) or 1)
    total_area_km2 = float(hexagon_data.get("area_km2", 0.737 * n_hex) or (0.737 * n_hex))
    if total_area_km2 <= 0.05:
        total_area_km2 = 0.737 * n_hex

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

    # 2. Nuevos valores absolutos simulados
    sim_plazas = max(0.0, base_plazas + delta_plazas)
    sim_tiempo = max(5.0, base_tiempo + delta_tiempo_aeropuerto)
    sim_ndvi = float(np.clip(base_ndvi + delta_ndvi, 0.0, 1.0))
    sim_pois = max(0.0, base_pois + delta_pois)
    sim_esg = float(np.clip(base_esg + delta_esg, 0.0, 100.0))

    # Estimación de componentes de POIs
    base_rest = float(hexagon_data.get("n_restaurantes", 2.0) or 2.0)
    base_cult = float(hexagon_data.get("n_cultura", 1.0) or 1.0)
    base_nat = float(hexagon_data.get("n_naturaleza", 1.0) or 1.0)
    sim_rest = max(0.0, base_rest + (delta_pois * 0.5))
    sim_cult = max(0.0, base_cult + (delta_pois * 0.3))
    sim_nat = max(0.0, base_nat + (delta_pois * 0.2))

    # 3. Proyección del PTNA simulado (Ecuación de sensibilidad MGWR)
    # Si es grupo macro, el impacto se amortigua proporcionalmente sobre el área total
    impacto_plazas_ptna = - (delta_plazas / total_area_km2)
    impacto_tiempo_ptna = SENSITIVITY_BETA_TIEMPO * delta_tiempo_aeropuerto
    impacto_ndvi_ptna = SENSITIVITY_BETA_NDVI * delta_ndvi
    impacto_pois_ptna = SENSITIVITY_BETA_POIS * (delta_pois / max(1.0, n_hex * 0.5))

    sim_ptna = base_ptna + impacto_plazas_ptna + impacto_tiempo_ptna + impacto_ndvi_ptna + impacto_pois_ptna

    # 4. Proyección de componentes normalizadas
    # Se evalúa en escala per cápita de celda para ser invariante a agregación
    sim_plazas_cell = sim_plazas / n_hex
    p_norm = _norm_val(np.log1p(sim_plazas_cell), bounds["log_plazas"][0], bounds["log_plazas"][1])
    v_norm = _norm_val(np.log1p(float(hexagon_data.get("viirs_medio", 0.0) or 0.0)), bounds["log_viirs"][0], bounds["log_viirs"][1])
    dist_costa = float(hexagon_data.get("dist_costa_km", 5.0) or 5.0)
    costa_prox = float(np.clip(1.0 - (dist_costa / 10.0), 0.0, 1.0))

    base_establ_cell = (float(hexagon_data.get("n_establecimientos_registro", 1.0) or 1.0)) / n_hex
    sim_establ_cell = max(0.0, base_establ_cell + ((delta_plazas / n_hex) / 25.0))
    establ_norm = _norm_val(np.log1p(sim_establ_cell), bounds["log_establ"][0], bounds["log_establ"][1])

    ndvi_norm = _norm_val(sim_ndvi, bounds["ndvi_medio"][0], bounds["ndvi_medio"][1])
    base_ndbi = float(hexagon_data.get("ndbi_medio", 0.0) or 0.0)
    ndbi_norm = _norm_val(base_ndbi, bounds["ndbi_medio"][0], bounds["ndbi_medio"][1])
    ndbi_inv = float(np.clip(1.0 - ndbi_norm, 0.0, 1.0))

    slope_norm = _norm_val(float(hexagon_data.get("slope_mean", 10.0) or 10.0), bounds["slope_mean"][0], bounds["slope_mean"][1])
    alt_norm = _norm_val(float(hexagon_data.get("altitud_media_m", 200.0) or 200.0), bounds["altitud_media_m"][0], bounds["altitud_media_m"][1])

    ptna_norm = _norm_val(sim_ptna, bounds["ptna_score"][0], bounds["ptna_score"][1])
    esg_norm = float(np.clip(sim_esg / 100.0, 0.0, 1.0))

    cult_cell = sim_cult / n_hex
    rest_cell = sim_rest / n_hex
    pois_cell = sim_pois / n_hex
    nat_cell = sim_nat / n_hex

    cult_norm = _norm_val(np.log1p(cult_cell), bounds["log_cultura"][0], bounds["log_cultura"][1])
    rest_norm = _norm_val(np.log1p(rest_cell), bounds["log_rest"][0], bounds["log_rest"][1])
    pois_norm = _norm_val(np.log1p(pois_cell), bounds["log_pois"][0], bounds["log_pois"][1])
    nat_norm = _norm_val(np.log1p(nat_cell), bounds["log_nat"][0], bounds["log_nat"][1])

    rating_val = float(hexagon_data.get("rating_booking_medio", 8.0) or 8.0)
    rating_norm = _norm_val(rating_val, bounds["rating_booking_medio"][0], bounds["rating_booking_medio"][1])

    temp_val = float(hexagon_data.get("temp_media_anual", 21.0) or 21.0)
    temp_opt = float(np.clip(1.0 - (abs(temp_val - 21.0) / 10.0), 0.0, 1.0))

    # 5. Proyección de Ejes Estratégicos
    sim_eje_1_raw = 0.45 * p_norm + 0.25 * v_norm + 0.15 * costa_prox + 0.15 * establ_norm
    sim_eje_1 = float(np.clip(sim_eje_1_raw, 0.0, 1.0))

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
    Genera un radar chart comparativo de gran formato con etiquetas legibles en 2 líneas.
    """
    # Etiquetas en 2 líneas para evitar recortes en pantallas y paneles
    categories = [
        "Sol y<br>playa",
        "Ecoturismo<br>rural",
        "Cultural y<br>patrimonial",
        "Aventura y<br>activo",
        "Bienestar y<br>salud",
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
            line=dict(color="#2980B9", width=2.5),
            fillcolor="rgba(41, 128, 185, 0.20)",
        )
    )

    # Traza escenario simulado
    fig.add_trace(
        go.Scatterpolar(
            r=r_sim,
            theta=theta,
            fill="toself",
            name="Escenario simulado",
            line=dict(color="#E67E22", width=3.5, dash="solid"),
            fillcolor="rgba(230, 126, 34, 0.35)",
        )
    )

    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 1.05],
                tickfont=dict(size=11, color="#777"),
                gridcolor="rgba(180, 180, 180, 0.25)",
            ),
            angularaxis=dict(
                tickfont=dict(size=13, color="var(--text-color, #222)"),
                gridcolor="rgba(180, 180, 180, 0.25)",
            ),
        ),
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.16,
            xanchor="center",
            x=0.5,
            font=dict(size=12),
        ),
        margin=dict(l=75, r=75, t=35, b=60),
        height=470,
    )

    return add_chart_motion(fig)


def create_strategic_matrix_simulation_chart(
    full_gdf: pd.DataFrame,
    base_eje1: float,
    base_eje2: float,
    sim_eje1: float,
    sim_eje2: float,
) -> go.Figure:
    """
    Representa la posición en la Matriz Estratégica Insular con leyenda externa no solapada.
    """
    df_sample = full_gdf.sample(min(len(full_gdf), 900), random_state=42).copy()

    fig = go.Figure()

    # Nube de fondo
    fig.add_trace(
        go.Scatter(
            x=df_sample["eje_1_saturacion"],
            y=df_sample["eje_2_rural_infrautilizado"],
            mode="markers",
            name="Resto de hexágonos insulares",
            marker=dict(
                size=4.5,
                color="rgba(150, 160, 175, 0.30)",
                symbol="circle",
            ),
            hoverinfo="skip",
        )
    )

    # Vector de transición
    fig.add_trace(
        go.Scatter(
            x=[base_eje1, sim_eje1],
            y=[base_eje2, sim_eje2],
            mode="lines",
            name="Vector de desplazamiento",
            line=dict(color="#C0392B", width=3.5, dash="dot"),
            hoverinfo="none",
        )
    )

    # Punto inicial
    fig.add_trace(
        go.Scatter(
            x=[base_eje1],
            y=[base_eje2],
            mode="markers+text",
            name="Punto inicial",
            text=["Inicial"],
            textposition="bottom center",
            textfont=dict(size=12, color="#2980B9"),
            marker=dict(size=14, color="#2980B9", symbol="circle", line=dict(color="#ffffff", width=2)),
            hovertemplate="<b>Situación actual</b><br>Eje 1: %{x:.3f}<br>Eje 2: %{y:.3f}<extra></extra>",
        )
    )

    # Punto final simulado
    fig.add_trace(
        go.Scatter(
            x=[sim_eje1],
            y=[sim_eje2],
            mode="markers+text",
            name="Punto simulado",
            text=["Simulado"],
            textposition="top center",
            textfont=dict(size=12, color="#D35400"),
            marker=dict(size=17, color="#E67E22", symbol="diamond", line=dict(color="#ffffff", width=2)),
            hovertemplate="<b>Escenario simulado</b><br>Eje 1: %{x:.3f}<br>Eje 2: %{y:.3f}<extra></extra>",
        )
    )

    # Cuadrantes estratégicos
    fig.add_vline(x=0.5, line_width=1, line_dash="dash", line_color="rgba(150, 150, 150, 0.4)")
    fig.add_hline(y=0.5, line_width=1, line_dash="dash", line_color="rgba(150, 150, 150, 0.4)")

    fig.update_layout(
        xaxis=dict(title="Eje 1: Saturación turística [0-1]", range=[-0.05, 1.05], gridcolor="rgba(200,200,200,0.15)"),
        yaxis=dict(title="Eje 2: Potencial rural y sostenible [0-1]", range=[-0.05, 1.05], gridcolor="rgba(200,200,200,0.15)"),
        margin=dict(l=55, r=30, t=55, b=50),
        height=490,
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.03,
            xanchor="right",
            x=1.0,
            font=dict(size=11),
        ),
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

    # ── 1. Nivel de Análisis y Ámbito Territorial ──
    col_modo, col_filtro = st.columns([1, 2])

    modo_analisis = col_modo.radio(
        "Nivel de análisis del escenario:",
        [
            "Hexágono individual (H3)",
            "Municipio completo",
            "Por arquetipo turístico TUI",
            "Por clúster territorial",
        ],
        index=0,
        help="Permite simular intervenciones a escala micro (hexágono) o macro (municipio, arquetipo o clúster completo).",
    )

    todos_municipios = list_municipios(full_gdf)

    if modo_analisis == "Hexágono individual (H3)":
        # Selector de municipio + buscador de hexágonos
        sub_c1, sub_c2 = col_filtro.columns(2)
        mun_filtro = sub_c1.selectbox("Filtrar por municipio:", ["Todos"] + todos_municipios, index=0)

        if mun_filtro != "Todos":
            hex_pool = full_gdf[full_gdf["municipio"] == mun_filtro].copy()
        else:
            hex_pool = full_gdf.copy()

        # Atajo rápido desplegable (con descripciones completas)
        caso_estudio = st.selectbox(
            "Casos representativos de Tenerife (atajos rápidos):",
            [
                "Personalizado (seleccionar de la lista inferior)",
                "🏝️ Adeje costa (núcleo de alta densidad y masificación en el sur)",
                "🌿 Guía de Isora rural (medianías con alto potencial PTNA no aprovechado)",
                "🏛️ Puerto de la Cruz casco (turismo consolidado y patrimonio histórico)",
                "🌲 Anaga reserva (espacio natural de máxima protección ambiental)",
                "🌋 Vilaflor cumbre (alta cota y turismo activo de montaña)",
            ],
            index=0,
            help="Carga automáticamente las coordenadas y atributos de un caso emblemático de la isla.",
        )

        selected_h3_override = None
        if "Adeje" in caso_estudio:
            adeje_hex = full_gdf[full_gdf["municipio"] == "Adeje"].sort_values("n_plazas_registro", ascending=False)
            selected_h3_override = adeje_hex.iloc[0]["h3_index"] if not adeje_hex.empty else None
        elif "Isora" in caso_estudio:
            isora_hex = full_gdf[(full_gdf["municipio"] == "Guia de Isora") & (full_gdf["ptna_score"] > 500)]
            selected_h3_override = isora_hex.iloc[0]["h3_index"] if not isora_hex.empty else None
        elif "Puerto de la Cruz" in caso_estudio:
            puerto_hex = full_gdf[full_gdf["municipio"] == "Puerto de la Cruz"].sort_values("n_plazas_registro", ascending=False)
            selected_h3_override = puerto_hex.iloc[0]["h3_index"] if not puerto_hex.empty else None
        elif "Anaga" in caso_estudio:
            anaga_hex = full_gdf[(full_gdf["municipio"] == "Santa Cruz de Tenerife") & (full_gdf["pct_area_enp"] > 0.5)]
            selected_h3_override = anaga_hex.iloc[0]["h3_index"] if not anaga_hex.empty else None
        elif "Vilaflor" in caso_estudio:
            vilaflor_hex = full_gdf[full_gdf["municipio"] == "Vilaflor"].sort_values("altitud_media_m", ascending=False)
            selected_h3_override = vilaflor_hex.iloc[0]["h3_index"] if not vilaflor_hex.empty else None

        hex_pool["display_label"] = (
            hex_pool["h3_index"].astype(str).str.slice(0, 11) + "… | " +
            hex_pool["municipio"].astype(str) + " | " +
            hex_pool["arquetipo_principal"].astype(str) + " (" +
            hex_pool["n_plazas_registro"].fillna(0).astype(int).astype(str) + " plazas)"
        )

        all_hex_indices = hex_pool["h3_index"].tolist()
        default_idx = 0
        if selected_h3_override and selected_h3_override in all_hex_indices:
            default_idx = all_hex_indices.index(selected_h3_override)

        selected_target_id = sub_c2.selectbox(
            "Hexágono H3 analizado:",
            all_hex_indices,
            index=default_idx,
            format_func=lambda h3: hex_pool.loc[hex_pool["h3_index"] == h3, "display_label"].values[0] if h3 in hex_pool["h3_index"].values else h3,
            help="Selecciona el hexágono sobre el que proyectar la intervención.",
        )

        if not selected_target_id or selected_target_id not in full_gdf["h3_index"].values:
            st.warning("No se ha seleccionado ningún hexágono válido.")
            return

        row = full_gdf.loc[full_gdf["h3_index"] == selected_target_id].iloc[0].copy()
        row["n_hex"] = 1
        ambito_titulo = f"Hexágono: `{selected_target_id[:13]}…` ({row.get('municipio')})"

    elif modo_analisis == "Municipio completo":
        mun_sel = col_filtro.selectbox("Seleccionar municipio a simular:", todos_municipios, index=0)
        group_df = full_gdf[full_gdf["municipio"] == mun_sel].copy()
        if group_df.empty:
            st.warning(f"No hay datos para el municipio {mun_sel}.")
            return
        row = aggregate_hexagon_group(group_df, label=mun_sel, group_type="municipio")
        ambito_titulo = f"Municipio: **{mun_sel}**"

    elif modo_analisis == "Por arquetipo turístico TUI":
        arquetipos_disponibles = sorted(full_gdf["arquetipo_principal"].dropna().unique().tolist())
        sub_c1, sub_c2 = col_filtro.columns(2)
        mun_filtro = sub_c1.selectbox("Ámbito geográfico:", ["Toda la isla"] + todos_municipios, index=0)
        arch_sel = sub_c2.selectbox("Seleccionar arquetipo TUI:", arquetipos_disponibles, index=0)

        group_df = full_gdf[full_gdf["arquetipo_principal"] == arch_sel].copy()
        if mun_filtro != "Toda la isla":
            group_df = group_df[group_df["municipio"] == mun_filtro].copy()

        if group_df.empty:
            st.warning(f"No hay hexágonos con arquetipo '{arch_sel}' en {mun_filtro}.")
            return
        label = f"{arch_sel} ({mun_filtro})"
        row = aggregate_hexagon_group(group_df, label=label, group_type="arquetipo")
        ambito_titulo = f"Arquetipo TUI: **{arch_sel}** ({mun_filtro})"

    else:  # Por clúster territorial
        clusters_disponibles = sorted(full_gdf["tipo_zona"].dropna().unique().tolist())
        sub_c1, sub_c2 = col_filtro.columns(2)
        mun_filtro = sub_c1.selectbox("Ámbito geográfico:", ["Toda la isla"] + todos_municipios, index=0)
        cluster_sel = sub_c2.selectbox("Seleccionar clúster territorial:", clusters_disponibles, index=0)

        group_df = full_gdf[full_gdf["tipo_zona"] == cluster_sel].copy()
        if mun_filtro != "Toda la isla":
            group_df = group_df[group_df["municipio"] == mun_filtro].copy()

        if group_df.empty:
            st.warning(f"No hay hexágonos del clúster '{cluster_sel}' en {mun_filtro}.")
            return
        label = f"{cluster_sel} ({mun_filtro})"
        row = aggregate_hexagon_group(group_df, label=label, group_type="cluster")
        ambito_titulo = f"Clúster territorial: **{cluster_sel}** ({mun_filtro})"

    # ── 2. Ficha Base de Información (Dividida en 2 Filas Espaciosas) ──
    st.markdown("##### Información territorial base")
    n_hex = int(row.get("n_hex", 1) or 1)
    total_area = float(row.get("area_km2", 0.737 * n_hex) or (0.737 * n_hex))
    plazas_tot = float(row.get("n_plazas_registro", 0.0) or 0.0)
    dens_plazas = plazas_tot / max(0.1, total_area)
    ptna_base = float(row.get("ptna_score", 0.0) or 0.0)
    esg_base = float(row.get("esg_h3_score", 50.0) or 50.0)
    eje1_base = float(row.get("eje_1_saturacion", 0.2) or 0.2)
    eje2_base = float(row.get("eje_2_rural_infrautilizado", 0.4) or 0.4)
    arch_base = str(row.get("arquetipo_principal", "Ecoturismo rural"))
    rest_cat = str(row.get("restriction_category", "Sin restricción"))
    pct_enp = float(row.get("pct_area_enp", 0.0) or 0.0)

    # Fila 1 de tarjetas
    r1_c1, r1_c2, r1_c3, r1_c4 = st.columns(4)
    with r1_c1.container(border=True):
        st.metric("Ámbito territorial", str(row.get("municipio", "Tenerife")), f"{n_hex:,} hexágono(s)")
    with r1_c2.container(border=True):
        st.metric("Superficie analizada", f"{total_area:,.1f} km²", f"~{total_area/n_hex:.2f} km²/celda")
    with r1_c3.container(border=True):
        st.metric("Plazas regladas actuales", f"{int(plazas_tot):,} plazas", f"{dens_plazas:.1f} pl/km²")
    with r1_c4.container(border=True):
        st.metric("Arquetipo dominante actual", arch_base)

    # Fila 2 de tarjetas
    r2_c1, r2_c2, r2_c3, r2_c4, r2_c5 = st.columns(5)
    with r2_c1.container(border=True):
        st.metric(
            "Índice PTNA base",
            f"{ptna_base:+.1f}",
            "Oportunidad" if ptna_base > 0 else "Saturación",
            help="Positivo = potencial no aprovechado; Negativo = sobreexplotado.",
        )
    with r2_c2.container(border=True):
        st.metric("Score ESG base", f"{esg_base:.1f} / 100", help="Índice sintético de sostenibilidad territorial.")
    with r2_c3.container(border=True):
        st.metric("Eje 1: Saturación", f"{eje1_base:.3f}", help="Presión en el gradiente de masificación (0 a 1).")
    with r2_c4.container(border=True):
        st.metric("Eje 2: Potencial rural", f"{eje2_base:.3f}", help="Potencial ambiental no masificado (0 a 1).")
    with r2_c5.container(border=True):
        enp_sub = f"Solape ENP: {pct_enp*100:.1f}%" if pct_enp > 0 else "Urbano / turístico"
        st.metric("Protección legal", rest_cat, enp_sub)

    st.divider()

    # ── 3. Panel de Configuración del Escenario (Presets en Desplegable + Sliders) ──
    st.subheader("⚙️ Configuración del escenario simulado")

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

    col_pre_sel, col_pre_reset = st.columns([3, 1])

    preset_opciones = [
        "— Selecciona un preset preconfigurado —",
        "🏨 Expansión hotelera / resort (+400 plazas, -10 min aeropuerto, +15 POIs, -5 ESG)",
        "🌿 Ecoturismo y regeneración (+35 plazas rurales, +0.15 NDVI, +5 POIs, +12 ESG)",
        "🏛️ Hub cultural y dinamización (+60 plazas boutique, +25 POIs, -5 min aeropuerto, +6 ESG)",
        "🛑 Moratoria y descompresión (-150 plazas, +0.10 NDVI, +15 ESG)",
    ]

    preset_elegido = col_pre_sel.selectbox(
        "Cargar preset de intervención rápida:",
        preset_opciones,
        index=0,
        help="Aplica automáticamente valores calibrados para una hipótesis de planificación típica.",
    )

    if preset_elegido == preset_opciones[1]:
        st.session_state.sim_delta_plazas = 400
        st.session_state.sim_delta_tiempo = -10
        st.session_state.sim_delta_ndvi = -0.06
        st.session_state.sim_delta_pois = 15
        st.session_state.sim_delta_esg = -5.0
    elif preset_elegido == preset_opciones[2]:
        st.session_state.sim_delta_plazas = 35
        st.session_state.sim_delta_tiempo = 0
        st.session_state.sim_delta_ndvi = 0.15
        st.session_state.sim_delta_pois = 5
        st.session_state.sim_delta_esg = 12.0
    elif preset_elegido == preset_opciones[3]:
        st.session_state.sim_delta_plazas = 60
        st.session_state.sim_delta_tiempo = -5
        st.session_state.sim_delta_ndvi = 0.02
        st.session_state.sim_delta_pois = 25
        st.session_state.sim_delta_esg = 6.0
    elif preset_elegido == preset_opciones[4]:
        st.session_state.sim_delta_plazas = -150
        st.session_state.sim_delta_tiempo = 0
        st.session_state.sim_delta_ndvi = 0.10
        st.session_state.sim_delta_pois = 0
        st.session_state.sim_delta_esg = 15.0

    if col_pre_reset.button("🔄 Restablecer valores", use_container_width=True, help="Devuelve todos los controles a cero"):
        st.session_state.sim_delta_plazas = 0
        st.session_state.sim_delta_tiempo = 0
        st.session_state.sim_delta_ndvi = 0.0
        st.session_state.sim_delta_pois = 0
        st.session_state.sim_delta_esg = 0.0
        st.rerun()

    # Deslizadores de control interactivo en 2 columnas
    s_col1, s_col2 = st.columns(2)

    # Escalado de rango de plazas según escala analizada
    max_plazas_slider = 1500 if n_hex == 1 else min(5000, max(1500, int(n_hex * 350)))
    min_plazas_slider = -min(1000, max(250, int(plazas_tot * 0.75)))

    with s_col1:
        delta_plazas = st.slider(
            "Plazas de alojamiento regladas (Δ):",
            min_value=min_plazas_slider,
            max_value=max_plazas_slider,
            value=int(st.session_state.sim_delta_plazas),
            step=25 if n_hex <= 2 else 50,
            help="Modifica el número de plazas hoteleras o de alojamiento reglado en el ámbito territorial.",
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
            min_value=-20 if n_hex <= 2 else -50,
            max_value=50 if n_hex <= 2 else 150,
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

    # ── 4. Ejecución de la Simulación ──
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
            f"🛡️ **Restricción ambiental:** El ámbito analizado presenta un {alertas['pct_enp']*100:.1f}% de solape con "
            f"**Espacio Natural Protegido**. La adición de {int(deltas['plazas']):+} plazas está "
            f"sujeta a régimen especial de protección ambiental o moratoria turística en Canarias."
        )

    if alertas["is_overtourism_risk"]:
        st.error(
            f"⚠️ **Riesgo de saturación crítica / overtourism:** El escenario eleva el Eje 1 a **{sim['eje_1']:.3f}** "
            f"o sitúa el PTNA en **{sim['ptna']:.1f}**, señalando riesgo de sobreexplotación de la capacidad de carga."
        )

    if alertas["is_ideal_opportunity"] and not base["es_oportunidad_ideal"]:
        st.success(
            "🌟 **Oportunidad ideal desbloqueada:** Con la intervención propuesta, el ámbito cumple simultáneamente "
            "los criterios estratégicos de TUI: **PTNA > 0** (potencial atractivo) y **ESG > 60** (sostenibilidad certificada)."
        )

    st.divider()

    # ── 7. Visualizaciones Gráficas Espaciosas en 2 Filas ──
    # Gráfico 1: Radar Chart Comparativo (fila completa)
    st.markdown("##### Comparativa de arquetipos TUI")
    fig_radar = create_radar_comparison_chart(base["scores"], sim["scores"])
    st.plotly_chart(fig_radar, use_container_width=True)

    # Gráfico 2: Desplazamiento en la Matriz Estratégica (fila completa)
    st.markdown("##### Desplazamiento en la matriz estratégica")
    fig_matrix = create_strategic_matrix_simulation_chart(
        full_gdf=full_gdf,
        base_eje1=base["eje_1"],
        base_eje2=base["eje_2"],
        sim_eje1=sim["eje_1"],
        sim_eje2=sim["eje_2"],
    )
    st.plotly_chart(fig_matrix, use_container_width=True)

    st.divider()

    # ── 8. Diagnóstico Narrativo Ejecutivo Automatizado ──
    st.markdown("##### Diagnóstico estratégico del escenario")

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
        La simulación planteada para **{ambito_titulo}** contempla un {texto_plazas},
        una variación en accesibilidad de **{int(deltas['tiempo_aeropuerto']):+} min**, un ajuste en vegetación (NDVI) de **{deltas['ndvi']:+.2f}**,
        y un balance ESG de **{deltas['esg']:+.1f} puntos**.
        
        Como resultado, el índice PTNA evoluciona de **{base['ptna']:+.1f}** a **{sim['ptna']:+.1f}**, mientras que el Eje 1 de saturación
        alcanza **{sim['eje_1']:.3f}** y el Eje 2 de potencial rural se sitúa en **{sim['eje_2']:.3f}**.
        
        *Recomendación estratégica:* Al evaluar el balance {tipo_balance}, {texto_conclusiones}.
        """
    )
