{{ config(
    materialized='external',
    location="s3://" ~ env_var('RAW_BUCKET', 'raw-flights') ~ "/warehouse/marts/" ~ this.name ~ ".parquet"
) }}
WITH base AS (
    SELECT
        origin_icao,
        destination_icao,
        CASE
            WHEN cancellation_code = 'A' THEN 'Air Carrier'
            WHEN cancellation_code = 'B' THEN 'Weather'
            WHEN cancellation_code = 'C' THEN 'National Air System'
            WHEN cancellation_code = 'D' THEN 'Security'
            ELSE 'Other / Unknown'
        END AS reason
    FROM {{ ref('stg_bts_on_time') }}
    WHERE cancelled = TRUE
      AND NULLIF(cancellation_code, '') IS NOT NULL
)
SELECT
    origin_icao,
    destination_icao,
    reason,
    COUNT(*)                                                    AS cancelled_count,
    ROUND(
        COUNT(*) * 1.0
            / NULLIF(SUM(COUNT(*)) OVER (PARTITION BY origin_icao, destination_icao), 0),
        4
    )                                                           AS reason_share
FROM base
GROUP BY origin_icao, destination_icao, reason
