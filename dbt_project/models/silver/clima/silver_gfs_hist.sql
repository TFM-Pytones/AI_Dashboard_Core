{{ config(materialized='table', tags=['silver', 'clima', 'forecast']) }}

/*
  Modelo Silver: silver_gfs_hist
  Limpieza del histórico de forecast GFS seamless (Open-Meteo).
  Conversiones idénticas a ERA5 para coherencia entre fuentes.
*/

SELECT
    "timestamp",
    municipio,
    latitud,
    longitud,
    leadtime_horas,
    ROUND(CAST(temperatura_2m - 273.15 AS NUMERIC), 2)          AS temperatura_2m_c,
    ROUND(CAST(precipitacion * 1000 AS NUMERIC), 2)             AS precipitacion_mm,
    ROUND(CAST(SQRT(viento_u^2 + viento_v^2) AS NUMERIC), 2)   AS velocidad_viento_ms,
    humedad_relativa,
    cobertura_nubosa
FROM {{ source('bronze', 'open_meteo_forecast') }}
WHERE "timestamp" IS NOT NULL
