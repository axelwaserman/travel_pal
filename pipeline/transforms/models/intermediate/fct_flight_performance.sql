-- Fact: one row per flight with computed delay metrics
-- NOTE: OpenSky does not provide scheduled times; last_seen - first_seen = block time.
-- Delay is approximated as block_minutes vs. route median (computed in agg models).
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
    )                                               AS block_minutes,
    CASE
        WHEN arrived_at IS NULL THEN TRUE
        ELSE FALSE
    END                                             AS is_cancelled
FROM {{ ref('stg_flights') }}
