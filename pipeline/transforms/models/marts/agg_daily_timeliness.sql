-- Aggregate: per-day timeliness for the dashboard
WITH daily AS (
    SELECT
        CAST(departed_at AS DATE)   AS flight_date,
        origin_icao,
        block_minutes,
        is_cancelled
    FROM {{ ref('fct_flight_performance') }}
),
daily_medians AS (
    SELECT
        flight_date,
        origin_icao,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY block_minutes) AS median_block
    FROM daily
    WHERE is_cancelled = FALSE
    GROUP BY flight_date, origin_icao
)
SELECT
    d.flight_date,
    d.origin_icao,
    COUNT(*)                                                        AS total_flights,
    ROUND(AVG(d.block_minutes - m.median_block), 1)                AS avg_delay_minutes,
    ROUND(STDDEV(d.block_minutes - m.median_block), 1)             AS delay_volatility,
    ROUND(
        SUM(CASE WHEN (d.block_minutes - m.median_block) <= 15 THEN 1 ELSE 0 END)
            * 1.0 / NULLIF(SUM(CASE WHEN NOT d.is_cancelled THEN 1 ELSE 0 END), 0),
        3
    )                                                               AS on_time_ratio,
    ROUND(
        SUM(CASE WHEN d.is_cancelled THEN 1 ELSE 0 END) * 1.0 / COUNT(*),
        3
    )                                                               AS cancellation_rate
FROM daily d
LEFT JOIN daily_medians m
    ON d.flight_date = m.flight_date
   AND d.origin_icao = m.origin_icao
WHERE NOT d.is_cancelled
GROUP BY d.flight_date, d.origin_icao
ORDER BY d.flight_date
