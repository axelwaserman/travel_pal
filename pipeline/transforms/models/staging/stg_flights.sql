-- Staging: cast and clean raw OpenSky fields.
-- Reads via DuckDB iceberg_scan() so that Iceberg metadata (snapshots,
-- manifests, partition specs) is honoured rather than bypassed.
-- The table root is the Iceberg warehouse path managed by pyiceberg + Nessie;
-- allow_moved_paths = true handles any relocation of data files between
-- Iceberg snapshot writes.
SELECT
    icao24,
    TRIM(callsign)                                  AS callsign,
    to_timestamp(first_seen)                        AS departed_at,
    to_timestamp(last_seen)                         AS arrived_at,
    est_departure_airport                           AS origin_icao,
    est_arrival_airport                             AS destination_icao
FROM iceberg_scan(
    's3://{{ env_var("RAW_BUCKET", "raw-flights") }}/warehouse/flights/raw_flights',
    allow_moved_paths = true
)
WHERE icao24 IS NOT NULL
  AND NULLIF(TRIM(callsign), '') IS NOT NULL
  AND first_seen IS NOT NULL
  AND last_seen  IS NOT NULL
