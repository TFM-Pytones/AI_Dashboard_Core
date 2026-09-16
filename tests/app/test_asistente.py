import pandas as pd

from app.asistente import _construir_pregunta_con_contexto, resumen_contexto_hexagono


def test_resumen_contexto_hexagono_incluye_municipio_y_metricas_disponibles():
    row = pd.Series(
        {
            "municipio": "Adeje",
            "n_hoteles": 12,
            "n_establecimientos_registro": 45,
            "ndvi_medio": 0.42,
            "sentimiento_medio": None,
            "rating_booking_medio": 8.1,
            "rating_tripadvisor_medio": None,
            "pct_area_enp": 0,
            "pct_area_zona_turistica": 0.8,
            "aeropuerto_mas_cercano": "TFS",
            "tiempo_aeropuerto_min": 18,
            "dist_hospital_km": 3.2,
            "dist_costa_km": 0.5,
            "n_paradas_bus_500m": 4,
        }
    )
    resumen = resumen_contexto_hexagono(row)
    assert "Adeje" in resumen
    assert "8,1" in resumen
    assert "Zona turística oficial" in resumen


def test_resumen_contexto_hexagono_omite_metricas_sin_dato_no_pone_none_ni_nan():
    row = pd.Series({"municipio": "Vilaflor", "sentimiento_medio": None, "rating_booking_medio": None})
    resumen = resumen_contexto_hexagono(row)
    assert "None" not in resumen
    assert "nan" not in resumen.lower()


def test_resumen_contexto_hexagono_sin_restricciones_no_menciona_restriccion():
    row = pd.Series({"municipio": "Adeje", "pct_area_enp": 0, "pct_area_zona_turistica": 0})
    resumen = resumen_contexto_hexagono(row)
    assert "Restricciones" not in resumen


def test_construir_pregunta_con_contexto_devuelve_la_pregunta_igual_sin_contexto():
    assert _construir_pregunta_con_contexto("¿qué tal el clima?", None) == "¿qué tal el clima?"


def test_construir_pregunta_con_contexto_antepone_el_resumen_del_hexagono():
    resultado = _construir_pregunta_con_contexto("¿qué puedo hacer aquí?", "Hexágono en Adeje.")
    assert "Hexágono en Adeje." in resultado
    assert "¿qué puedo hacer aquí?" in resultado
