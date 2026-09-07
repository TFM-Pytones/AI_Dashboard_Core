{{ config(
    materialized='incremental',
    unique_key=['source', 'source_id'],
    enabled=false
) }}

WITH raw_sentiment AS (
    SELECT
        source,
        source_id,
        text,
        label,
        score,
        model_name,
        processed_at,
        is_relevant,
        relevance_score
    FROM {{ source('bronze', 'bronze_ml_sentiment_results') }}
)

SELECT
    source,
    source_id,
    TRIM(text) AS text,
    label,
    CAST(score AS FLOAT) AS score,
    model_name,
    processed_at,
    is_relevant,
    CAST(relevance_score AS FLOAT) AS relevance_score
FROM raw_sentiment

{% if is_incremental() %}
  -- this filter will only be applied on an incremental run
  WHERE processed_at > (SELECT coalesce(MAX(processed_at), '1900-01-01') FROM {{ this }})
{% endif %}
