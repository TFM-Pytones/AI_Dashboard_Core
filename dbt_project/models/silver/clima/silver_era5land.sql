{{ config(materialized='table', tags=['silver', 'clima', 'reanalisis']) }}

/*
  Modelo Silver: silver_era5land
  Limpieza y normalización de unidades ERA5-Land (reanálisis atmosférico).
  Conversiones:
    - Temperatura: Kelvin → Celsius
    - Precipitación: m → mm
    - Viento u/v: componentes → velocidad escalar (m/s)
    - Radiación: J/m² → W/m² (dividir entre 3600)
*/

WITH source AS (
    SELECT * FROM {{ source('bronze', 'era5land_consolidado') }}
)

SELECT
    "timestamp",
    municipio,
    latitud,
    longitud,
    -- Temperatura (Kelvin → Celsius)
    ROUND(CAST(temperatura_2m - 273.15 AS NUMERIC), 2)          AS temperatura_2m_c,
    ROUND(CAST(temperatura_suelo - 273.15 AS NUMERIC), 2)       AS temperatura_suelo_c,
    -- Precipitación (m → mm)
    ROUND(CAST(precipitacion * 1000 AS NUMERIC), 2)             AS precipitacion_mm,
    -- Velocidad del viento a partir de componentes u/v
    ROUND(CAST(SQRT(viento_u^2 + viento_v^2) AS NUMERIC), 2)   AS velocidad_viento_ms,
    -- Humedad relativa directa
    ROUND(CAST(humedad_relativa AS NUMERIC), 1)                  AS humedad_relativa,
    -- Radiación (J/m² → W/m²)
    ROUND(CAST(radiacion_solar / 3600.0 AS NUMERIC), 2)         AS radiacion_solar_wm2
FROM source
WHERE "timestamp" IS NOT NULL
  AND municipio IS NOT NULL
