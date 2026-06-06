-- Non-blocking signal that >1% of BTS rows are dropping out of stg_bts_on_time
-- because of a missing IATA→ICAO mapping. dbt singular test: returns rows for
-- failures. Severity warn so it does not block dbt build.
{{ config(severity='warn') }}

WITH raw AS (
    SELECT COUNT(*) AS n FROM nessie.flights.bts_on_time
),
stg AS (
    SELECT COUNT(*) AS n FROM {{ ref('stg_bts_on_time') }}
)
SELECT raw.n AS raw_rows, stg.n AS stg_rows
FROM raw, stg
WHERE stg.n * 1.0 / NULLIF(raw.n, 0) < 0.99
