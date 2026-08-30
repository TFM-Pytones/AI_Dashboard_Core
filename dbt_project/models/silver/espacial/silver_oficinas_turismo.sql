{{ config(
    materialized='table',
    tags=['silver', 'espacial', 'turismo'],
    indexes=[
      {'columns': ['geometry'], 'type': 'gist'}
    ]
) }}

SELECT
    NULL AS id,
    oficina_nombre AS nombre,
    'oficina_turismo' AS tipo,
    municipio_nombre AS municipio,
    oficina_horario AS horario,
    oficina_descripcion AS descripcion,
    oficina_telefono AS telefono,
    oficina_estado AS estado,
    geometry
FROM {{ source('bronze', 'oficinas_turismo') }}
WHERE geometry IS NOT NULL
  -- Limpiamos las que están marcadas como cerradas temporalmente
  AND (oficina_estado IS NULL OR LOWER(oficina_estado) NOT LIKE '%cerrado temporal%')
