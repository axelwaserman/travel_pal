-- Staging: cast and clean raw OpenSky fields
SELECT
    icao24,
    TRIM(callsign)                                  AS callsign,
    CAST(first_seen AS TIMESTAMP)                   AS departed_at,
    CAST(last_seen  AS TIMESTAMP)                   AS arrived_at,
    est_departure_airport                           AS origin_icao,
    est_arrival_airport                             AS destination_icao
FROM {{ source('raw', 'raw_flights') }}
WHERE icao24 IS NOT NULL
  AND callsign IS NOT NULL
  AND first_seen IS NOT NULL
  AND last_seen  IS NOT NULL
