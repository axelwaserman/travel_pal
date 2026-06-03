-- Staging: cast and clean raw OpenSky fields.
-- Reads parquet data files written by the raw_flights Iceberg asset directly
-- from S3 so that dbt is not dependent on an unpopulated DuckDB table.
SELECT
    icao24,
    TRIM(callsign)                                  AS callsign,
    CAST(first_seen AS TIMESTAMP)                   AS departed_at,
    CAST(last_seen  AS TIMESTAMP)                   AS arrived_at,
    est_departure_airport                           AS origin_icao,
    est_arrival_airport                             AS destination_icao
FROM read_parquet('s3://{{ env_var("RAW_BUCKET", "raw-flights") }}/warehouse/flights/raw_flights/data/*.parquet')
WHERE icao24 IS NOT NULL
  AND callsign IS NOT NULL
  AND first_seen IS NOT NULL
  AND last_seen  IS NOT NULL
