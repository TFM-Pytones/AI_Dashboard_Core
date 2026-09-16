from analytics.clustering.build_features import QUERY_FEATURES_RAW


def test_query_usa_columnas_reales_de_gold_h3_master():
    # Bug real (punto 15 de la revision de codigo del companero): la consulta
    # usaba m.es_enp y m.elevation_mean, columnas que no existen en
    # gold_h3_master -- el esquema real usa pct_area_enp y altitud_media_m
    # (confirmado por auditoria directa de las 121 columnas de la tabla).
    assert "m.es_enp" not in QUERY_FEATURES_RAW
    assert "m.elevation_mean" not in QUERY_FEATURES_RAW
    assert "m.pct_area_enp" in QUERY_FEATURES_RAW
    assert "m.altitud_media_m" in QUERY_FEATURES_RAW


def test_query_lee_la_tabla_real_de_sentimiento():
    # gold.gold_sentimiento_h3 es el modelo dbt que nunca se materializo (ver
    # app/data.py) -- la tabla real es gold.gold_h3_sentimiento.
    assert "gold.gold_sentimiento_h3" not in QUERY_FEATURES_RAW
    assert "gold.gold_h3_sentimiento" in QUERY_FEATURES_RAW
