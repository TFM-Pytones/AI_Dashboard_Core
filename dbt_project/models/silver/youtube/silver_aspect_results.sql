{{ config(
    materialized='incremental',
    unique_key=['source', 'source_id', 'aspect'],
    enabled=false
) }}

WITH raw_aspects AS (
    SELECT
        source,
        source_id,
        text,
        aspect,
        aspect_sentiment,
        confidence,
        model_name,
        processed_at
    FROM {{ source('bronze', 'bronze_ml_aspect_results') }}
)

SELECT
    source,
    source_id,
    TRIM(text) AS text,
    TRIM(aspect) AS aspect,
    aspect_sentiment,
    CAST(confidence AS FLOAT) AS confidence,
    model_name,
    processed_at
FROM raw_aspects

{% if is_incremental() %}
  WHERE processed_at > (SELECT coalesce(MAX(processed_at), '1900-01-01') FROM {{ this }})
{% endif %}
