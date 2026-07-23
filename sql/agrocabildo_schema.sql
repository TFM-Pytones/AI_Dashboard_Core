-- Esquema SQL ultra-optimizado en el schema 'raw_data' para Azure PostgreSQL
-- Diseñado para el TFM (Desafío 3 TUI Challenges Masters - Índice TFM)

CREATE SCHEMA IF NOT EXISTS raw_data;

CREATE TABLE IF NOT EXISTS raw_data.estaciones_agrocabildo (
    id_estacion INT PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    municipio VARCHAR(100),
    latitud REAL,
    longitud REAL,
    altitud REAL,
    fecha_instalacion TIMESTAMPTZ,
    actualizado_en TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS raw_data.clima_horario_agrocabildo (
    id_estacion INT NOT NULL,
    id_sensor INT NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    valor_observado REAL,
    valor_validado REAL,
    es_validado BOOLEAN DEFAULT TRUE,
    PRIMARY KEY (id_estacion, id_sensor, timestamp),
    CONSTRAINT fk_estacion FOREIGN KEY (id_estacion) REFERENCES raw_data.estaciones_agrocabildo(id_estacion) ON DELETE CASCADE
);

-- Índices B-Tree optimizados para analítica y transformaciones dbt / Airflow
CREATE INDEX IF NOT EXISTS idx_clima_horario_ts ON raw_data.clima_horario_agrocabildo (timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_clima_horario_est_ts ON raw_data.clima_horario_agrocabildo (id_estacion, timestamp DESC);
