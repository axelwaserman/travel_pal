-- Staging: cast and clean raw OpenSky fields.
-- Reads via the Nessie REST catalog (ATTACHed in macros/setup_iceberg.sql) so
-- the table location is resolved by the catalog at query time.  This avoids
-- hardcoding the UUID-suffixed Iceberg table directory, which Nessie always
-- appends and which the catalog is the only authority on.
SELECT
    icao24,
    TRIM(callsign)                                  AS callsign,
    to_timestamp(first_seen)                        AS departed_at,
    to_timestamp(last_seen)                         AS arrived_at,
    est_departure_airport                           AS origin_icao,
    est_arrival_airport                             AS destination_icao
FROM nessie.flights.raw_flights
WHERE icao24 IS NOT NULL
  AND NULLIF(TRIM(callsign), '') IS NOT NULL
  AND first_seen IS NOT NULL
  AND last_seen  IS NOT NULL
