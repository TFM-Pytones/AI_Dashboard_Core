import numpy as np
import pandas as pd
import pytest

from app.simulador import (
    compute_dataset_normalization_bounds,
    create_radar_comparison_chart,
    create_strategic_matrix_simulation_chart,
    simulate_hexagon_intervention,
)


@pytest.fixture
def mock_gdf():
    data = {
        "h3_index": ["88344125d1fffff", "883441249bfffff", "88344122c7fffff"],
        "municipio": ["Adeje", "Arona", "Santiago del Teide"],
        "n_plazas_registro": [1500.0, 300.0, 50.0],
        "viirs_medio": [45.0, 20.0, 5.0],
        "dist_costa_km": [0.5, 1.2, 4.5],
        "n_establecimientos_registro": [20.0, 8.0, 2.0],
        "ndvi_medio": [0.15, 0.25, 0.65],
        "ndbi_medio": [0.35, 0.15, -0.05],
        "slope_mean": [5.0, 8.0, 22.0],
        "altitud_media_m": [50.0, 120.0, 650.0],
        "ptna_score": [850.0, -120.0, 350.0],
        "esg_h3_score": [58.0, 48.0, 72.0],
        "n_cultura": [5.0, 2.0, 1.0],
        "n_restaurantes": [40.0, 15.0, 3.0],
        "n_pois_total": [60.0, 22.0, 6.0],
        "n_naturaleza": [2.0, 3.0, 15.0],
        "rating_booking_medio": [8.4, 7.9, 8.8],
        "temp_media_anual": [22.5, 21.8, 18.5],
        "tiempo_aeropuerto_min": [18.0, 25.0, 55.0],
        "pct_area_enp": [0.0, 0.0, 0.85],
        "area_km2": [0.737, 0.737, 0.737],
        "eje_1_saturacion": [0.75, 0.45, 0.12],
        "eje_2_rural_infrautilizado": [0.25, 0.38, 0.82],
        "score_sol_playa": [0.82, 0.55, 0.15],
        "score_ecoturismo": [0.20, 0.30, 0.85],
        "score_cultural": [0.50, 0.35, 0.20],
        "score_aventura": [0.15, 0.25, 0.78],
        "score_bienestar": [0.45, 0.40, 0.65],
        "arquetipo_principal": ["🏖️ Sol y playa", "🏖️ Sol y playa", "🌿 Ecoturismo rural"],
        "es_oportunidad_ideal": [False, False, True],
        "restriction_category": ["Sin restricción", "Sin restricción", "Espacio Natural Protegido"],
    }
    return pd.DataFrame(data)


def test_normalization_bounds_computation(mock_gdf):
    bounds = compute_dataset_normalization_bounds(mock_gdf)
    assert "log_plazas" in bounds
    assert "ndvi_medio" in bounds
    assert "ptna_score" in bounds
    assert bounds["ndvi_medio"][0] <= bounds["ndvi_medio"][1]


def test_simulation_intervention_deltas(mock_gdf):
    bounds = compute_dataset_normalization_bounds(mock_gdf)
    row = mock_gdf.iloc[0]  # Adeje row

    # Simular +200 plazas, -10 min aeropuerto, +0.10 NDVI, +10 POIs, +5 ESG
    res = simulate_hexagon_intervention(
        hexagon_data=row,
        delta_plazas=200,
        delta_tiempo_aeropuerto=-10,
        delta_ndvi=0.10,
        delta_pois=10,
        delta_esg=5.0,
        bounds=bounds,
    )

    base = res["base"]
    sim = res["simulado"]
    deltas = res["deltas"]

    # Comprobación de deltas en variables de intervención
    assert sim["plazas"] == base["plazas"] + 200
    assert sim["tiempo_aeropuerto"] == base["tiempo_aeropuerto"] - 10
    assert pytest.approx(sim["ndvi"], 0.01) == base["ndvi"] + 0.10
    assert sim["pois"] == base["pois"] + 10
    assert sim["esg"] == base["esg"] + 5.0

    # Comprobación de que el impacto en plazas reduce el PTNA (absorbe oferta)
    # y mejorar tiempo incrementa el potencial de demanda
    assert "ptna" in sim
    assert "eje_1" in sim
    assert "eje_2" in sim
    assert "arquetipo" in sim


def test_simulation_physical_bounds_clipping(mock_gdf):
    bounds = compute_dataset_normalization_bounds(mock_gdf)
    row = mock_gdf.iloc[2]  # Santiago del Teide (50 plazas, tiempo 55)

    # Intentar restar más plazas de las que hay y reducir tiempo por debajo de 0
    res = simulate_hexagon_intervention(
        hexagon_data=row,
        delta_plazas=-500,
        delta_tiempo_aeropuerto=-100,
        delta_ndvi=-2.0,
        delta_pois=-100,
        delta_esg=-150.0,
        bounds=bounds,
    )

    sim = res["simulado"]
    assert sim["plazas"] == 0.0
    assert sim["tiempo_aeropuerto"] >= 5.0
    assert sim["ndvi"] == 0.0
    assert sim["pois"] == 0.0
    assert sim["esg"] == 0.0


def test_simulation_alerts(mock_gdf):
    bounds = compute_dataset_normalization_bounds(mock_gdf)

    # Caso 1: ENP conflicto (Santiago del Teide tiene pct_area_enp = 0.85)
    row_enp = mock_gdf.iloc[2]
    res_enp = simulate_hexagon_intervention(
        hexagon_data=row_enp,
        delta_plazas=100,  # Sumar plazas en ENP
        delta_tiempo_aeropuerto=0,
        delta_ndvi=0.0,
        delta_pois=0,
        delta_esg=0.0,
        bounds=bounds,
    )
    assert res_enp["alertas"]["is_enp_conflict"] is True

    # Caso 2: Riesgo de saturación crítica / overtourism
    row_adeje = mock_gdf.iloc[0]
    res_sat = simulate_hexagon_intervention(
        hexagon_data=row_adeje,
        delta_plazas=1000,
        delta_tiempo_aeropuerto=-10,
        delta_ndvi=-0.1,
        delta_pois=20,
        delta_esg=-10.0,
        bounds=bounds,
    )
    assert res_sat["alertas"]["is_overtourism_risk"] is True

    # Caso 3: Desbloqueo de oportunidad ideal (PTNA > 0 y ESG > 60)
    row_arona = mock_gdf.iloc[1]  # base PTNA < 0, ESG 48
    res_opp = simulate_hexagon_intervention(
        hexagon_data=row_arona,
        delta_plazas=-100,
        delta_tiempo_aeropuerto=-15,
        delta_ndvi=0.20,
        delta_pois=20,
        delta_esg=20.0,  # Sube ESG a 68 (> 60)
        bounds=bounds,
    )
    assert res_opp["simulado"]["esg"] > 60.0


def test_charts_creation(mock_gdf):
    bounds = compute_dataset_normalization_bounds(mock_gdf)
    row = mock_gdf.iloc[1]

    res = simulate_hexagon_intervention(
        hexagon_data=row,
        delta_plazas=50,
        delta_tiempo_aeropuerto=-5,
        delta_ndvi=0.05,
        delta_pois=5,
        delta_esg=5.0,
        bounds=bounds,
    )

    fig_radar = create_radar_comparison_chart(res["base"]["scores"], res["simulado"]["scores"])
    assert fig_radar is not None
    assert len(fig_radar.data) == 2  # Dos trazas: Situación actual y Escenario simulado

    fig_matrix = create_strategic_matrix_simulation_chart(
        full_gdf=mock_gdf,
        municipio_actual="Arona",
        base_eje1=res["base"]["eje_1"],
        base_eje2=res["base"]["eje_2"],
        sim_eje1=res["simulado"]["eje_1"],
        sim_eje2=res["simulado"]["eje_2"],
    )
    assert fig_matrix is not None
    assert len(fig_matrix.data) == 4  # Nube de fondo, vector, punto inicial, punto simulado
