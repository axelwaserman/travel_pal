WITH all_flights AS (
    SELECT
        icao24,
        callsign,
        origin_icao,
        destination_icao,
        departed_at,
        arrived_at,
        CAST(
            (EXTRACT(EPOCH FROM arrived_at) - EXTRACT(EPOCH FROM departed_at)) / 60
            AS INTEGER
        ) AS block_minutes
    FROM {{ ref('stg_flights') }}
),
route_medians AS (
    SELECT
        origin_icao,
        destination_icao,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY block_minutes) AS median_block_minutes
    FROM all_flights
    GROUP BY origin_icao, destination_icao
)
SELECT
    f.icao24,
    f.callsign,
    f.origin_icao,
    f.destination_icao,
    f.departed_at,
    f.arrived_at,
    f.block_minutes,
    CASE
        WHEN f.block_minutes - m.median_block_minutes <= 15 THEN TRUE
        ELSE FALSE
    END AS is_on_time
FROM all_flights f
LEFT JOIN route_medians m
    ON f.origin_icao = m.origin_icao
   AND f.destination_icao = m.destination_icao
