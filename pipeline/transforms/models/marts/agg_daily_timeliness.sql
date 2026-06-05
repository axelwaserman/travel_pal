{{ config(
    location="s3://" ~ env_var('RAW_BUCKET', 'raw-flights') ~ "/warehouse/marts/" ~ this.name ~ ".parquet"
) }}
SELECT
    CAST(departed_at AS DATE)                                       AS flight_date,
    origin_icao,
    COUNT(*)                                                        AS total_flights,
    ROUND(AVG(delay_minutes), 1)                                    AS avg_delay_minutes,
    ROUND(STDDEV(delay_minutes), 1)                                 AS delay_volatility,
    ROUND(
        COUNT(CASE WHEN is_on_time = TRUE THEN 1 END) * 1.0
            / NULLIF(COUNT(CASE WHEN is_on_time IS NOT NULL THEN 1 END), 0),
        3
    )                                                               AS on_time_ratio
FROM {{ ref('fct_flight_performance') }}
GROUP BY CAST(departed_at AS DATE), origin_icao
ORDER BY flight_date
