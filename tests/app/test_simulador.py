import numpy as np
import pandas as pd
import pytest

from app.simulador import (
    aggregate_hexagon_group,
    compute_dataset_normalization_bounds,
    create_radar_comparison_chart,
    create_strategic_matrix_simulation_chart,
    simulate_hexagon_intervention,
)


@pytest.fixture
def mock_gdf():
    data = {
        "h3_index": ["88344125d1fffff", "883441249bfffff", "88344122c7fffff"],
        "municipio": ["Adeje", "Arona", "Adeje"],
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
        "arquetipo_principal": ["Sol y playa", "Sol y playa", "Ecoturismo rural"],
        "es_oportunidad_ideal": [False, False, True],
        "restriction_category": ["Sin restricción", "Sin restricción", "Espacio Natural Protegido"],
        "tipo_zona": ["Saturado / Overtourism", "Transición costera", "Rurales y medianías"],
    }
    return pd.DataFrame(data)


def test_simulation_zero_delta_guarantees_no_change(mock_gdf):
    """
    Verifica que con deltas en cero no exista ningún desplazamiento ficticio:
    simulado coincide exactamente con base, todos los deltas son 0.0 y no hay cambio de arquetipo.
    """
    bounds = compute_dataset_normalization_bounds(mock_gdf)
    row = mock_gdf.iloc[0]

    res = simulate_hexagon_intervention(
        hexagon_data=row,
        delta_plazas=0,
        delta_tiempo_aeropuerto=0,
        delta_ndvi=0.0,
        delta_pois=0,
        delta_esg=0.0,
        bounds=bounds,
    )

    base = res["base"]
    sim = res["simulado"]
    deltas = res["deltas"]
    alertas = res["alertas"]

    assert sim["plazas"] == base["plazas"]
    assert sim["tiempo_aeropuerto"] == base["tiempo_aeropuerto"]
    assert sim["ndvi"] == base["ndvi"]
    assert sim["pois"] == base["pois"]
    assert sim["esg"] == base["esg"]
    assert sim["ptna"] == base["ptna"]
    assert sim["eje_1"] == base["eje_1"]
    assert sim["eje_2"] == base["eje_2"]
    assert sim["arquetipo"] == base["arquetipo"]
    assert sim["scores"] == base["scores"]

    for k, v in deltas.items():
        assert v == 0.0, f"Delta for {k} was not zero: {v}"

    assert alertas["archetype_changed"] is False


def test_normalization_bounds_computation(mock_gdf):
    bounds = compute_dataset_normalization_bounds(mock_gdf)
    assert "log_plazas" in bounds
    assert "ndvi_medio" in bounds
    assert "ptna_score" in bounds
    assert bounds["ndvi_medio"][0] <= bounds["ndvi_medio"][1]


def test_simulation_intervention_deltas(mock_gdf):
    bounds = compute_dataset_normalization_bounds(mock_gdf)
    row = mock_gdf.iloc[0]  # Adeje row

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

    assert sim["plazas"] == base["plazas"] + 200
    assert sim["tiempo_aeropuerto"] == base["tiempo_aeropuerto"] - 10
    assert pytest.approx(sim["ndvi"], 0.01) == base["ndvi"] + 0.10
    assert sim["pois"] == base["pois"] + 10
    assert sim["esg"] == base["esg"] + 5.0
    assert "ptna" in sim
    assert "eje_1" in sim
    assert "eje_2" in sim
    assert "arquetipo" in sim


def test_simulation_physical_bounds_clipping(mock_gdf):
    bounds = compute_dataset_normalization_bounds(mock_gdf)
    row = mock_gdf.iloc[2]

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

    # Caso 1: ENP conflicto
    row_enp = mock_gdf.iloc[2]
    res_enp = simulate_hexagon_intervention(
        hexagon_data=row_enp,
        delta_plazas=100,
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

    # Caso 3: Desbloqueo de oportunidad ideal
    row_arona = mock_gdf.iloc[1]
    res_opp = simulate_hexagon_intervention(
        hexagon_data=row_arona,
        delta_plazas=-100,
        delta_tiempo_aeropuerto=-15,
        delta_ndvi=0.20,
        delta_pois=20,
        delta_esg=20.0,
        bounds=bounds,
    )
    assert res_opp["simulado"]["esg"] > 60.0


def test_aggregate_hexagon_group(mock_gdf):
    adeje_group = mock_gdf[mock_gdf["municipio"] == "Adeje"]
    synth_row = aggregate_hexagon_group(adeje_group, label="Adeje", group_type="municipio")

    assert synth_row["n_hex"] == 2
    assert synth_row["n_plazas_registro"] == 1550.0  # 1500 + 50
    assert synth_row["municipio"] == "Adeje"
    assert "area_km2" in synth_row

    bounds = compute_dataset_normalization_bounds(mock_gdf)
    res_group = simulate_hexagon_intervention(
        hexagon_data=synth_row,
        delta_plazas=500,
        delta_tiempo_aeropuerto=-5,
        delta_ndvi=0.05,
        delta_pois=10,
        delta_esg=5.0,
        bounds=bounds,
    )
    assert res_group["simulado"]["plazas"] == 2050.0
    assert "ptna" in res_group["simulado"]
    assert "eje_1" in res_group["simulado"]


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
    assert len(fig_radar.data) == 2

    fig_matrix = create_strategic_matrix_simulation_chart(
        full_gdf=mock_gdf,
        base_eje1=res["base"]["eje_1"],
        base_eje2=res["base"]["eje_2"],
        sim_eje1=res["simulado"]["eje_1"],
        sim_eje2=res["simulado"]["eje_2"],
    )
    assert fig_matrix is not None
    assert len(fig_matrix.data) == 4
    # Verificar que la leyenda está situada encima para no solaparse
    assert fig_matrix.layout.legend.y >= 1.0


def test_simulation_nan_robustness(mock_gdf):
    """
    Verifica que la presencia de valores NaN en columnas como tiempo_aeropuerto_min,
    rating_booking_medio, etc. no provoque excepciones (p.ej. cannot convert float NaN to integer).
    """
    bounds = compute_dataset_normalization_bounds(mock_gdf)

    nan_row = pd.Series({
        "h3_index": "8839446ca3fffff",
        "municipio": "Buenavista del Norte",
        "n_hex": 1,
        "tiempo_aeropuerto_min": np.nan,
        "rating_booking_medio": np.nan,
        "area_km2": np.nan,
        "ptna_score": np.nan,
        "n_plazas_registro": np.nan,
        "ndvi_medio": np.nan,
        "esg_h3_score": np.nan,
    })

    res = simulate_hexagon_intervention(
        hexagon_data=nan_row,
        delta_plazas=50,
        delta_tiempo_aeropuerto=-10,
        delta_ndvi=0.05,
        delta_pois=5,
        delta_esg=5.0,
        bounds=bounds,
    )

    deltas = res["deltas"]
    # Los deltas nunca deben ser NaN
    assert not np.isnan(deltas["tiempo_aeropuerto"])
    assert not np.isnan(deltas["plazas"])
    assert not np.isnan(deltas["ptna"])

    # Conversión a entero segura (el punto que causó la excepción anterior)
    int_delta_tiempo = int(deltas["tiempo_aeropuerto"])
    assert int_delta_tiempo == -10


def test_aggregate_hexagon_group_includes_confianza_ptna(mock_gdf):
    df = mock_gdf.copy()
    df["confianza_ptna"] = ["baja", "normal", "baja"]
    row = aggregate_hexagon_group(df, label="TestGroup", group_type="cluster")
    assert "confianza_ptna" in row
    assert row["confianza_ptna"] == "baja"


