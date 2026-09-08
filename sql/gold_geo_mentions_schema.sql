-- Georreferenciacion por gazetteer (nombre de municipio/zona mencionado en el
-- texto) para fuentes sin ubicacion estructurada (LosViajeros, YouTube).
-- Booking y TripAdvisor NO necesitan esto: ya tienen lat/lon reales por
-- establecimiento (silver.silver_booking_establishments / tripadvisor_ubicaciones).

CREATE SCHEMA IF NOT EXISTS gold;

CREATE TABLE IF NOT EXISTS gold.geo_mentions (
    id             SERIAL PRIMARY KEY,
    source         TEXT NOT NULL,
    source_id      TEXT NOT NULL,
    place_type     TEXT NOT NULL,   -- 'municipio' | 'zona' (zona = hito conocido que no es municipio: Teide, Anaga, Masca...)
    place_name     TEXT NOT NULL,
    method         TEXT NOT NULL,   -- 'directo' (mencionado en el propio texto) | 'heredado_hilo' (del titulo del hilo/video)
    processed_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source, source_id)
);

CREATE INDEX IF NOT EXISTS idx_gold_geo_mentions_source ON gold.geo_mentions(source);
CREATE INDEX IF NOT EXISTS idx_gold_geo_mentions_place ON gold.geo_mentions(place_name);
