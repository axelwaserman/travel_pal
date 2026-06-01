-- Aggregate: per-route timeliness metrics
-- on_time_ratio uses ≤15-minute variance from route median block time
WITH route_medians AS (
    SELECT
        origin_icao,
        destination_icao,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY block_minutes) AS median_block_minutes
    FROM {{ ref('fct_flight_performance') }}
    GROUP BY origin_icao, destination_icao
),
with_delay AS (
    SELECT
        f.*,
        f.block_minutes - m.median_block_minutes AS delay_minutes
    FROM {{ ref('fct_flight_performance') }} f
    JOIN route_medians m
        ON f.origin_icao = m.origin_icao
       AND f.destination_icao = m.destination_icao
)
SELECT
    origin_icao,
    destination_icao,
    COUNT(*)                                                    AS total_flights,
    ROUND(AVG(delay_minutes), 1)                                AS avg_delay_minutes,
    ROUND(STDDEV(delay_minutes), 1)                             AS delay_volatility,
    ROUND(
        SUM(CASE WHEN delay_minutes <= 15 THEN 1 ELSE 0 END) * 1.0 / COUNT(*),
        3
    )                                                           AS on_time_ratio
FROM with_delay
GROUP BY origin_icao, destination_icao
