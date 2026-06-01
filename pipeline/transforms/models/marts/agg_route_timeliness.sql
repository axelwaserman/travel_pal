SELECT
    origin_icao,
    destination_icao,
    COUNT(*)                                                    AS total_flights,
    ROUND(AVG(delay_minutes), 1)                                AS avg_delay_minutes,
    ROUND(STDDEV(delay_minutes), 1)                             AS delay_volatility,
    ROUND(
        SUM(CASE WHEN is_on_time THEN 1 ELSE 0 END) * 1.0 / NULLIF(COUNT(*), 0),
        3
    )                                                           AS on_time_ratio
FROM {{ ref('fct_flight_performance') }}
GROUP BY origin_icao, destination_icao
