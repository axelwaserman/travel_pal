{{ config(
    location="s3://" ~ env_var('RAW_BUCKET', 'raw-flights') ~ "/warehouse/marts/" ~ this.name ~ ".parquet"
) }}
SELECT
    origin_icao,
    destination_icao,
    COUNT(*)                                                       AS total_scheduled,
    SUM(CASE WHEN cancelled THEN 1 ELSE 0 END)                     AS cancelled,
    ROUND(
        SUM(CASE WHEN cancelled THEN 1 ELSE 0 END) * 1.0
            / NULLIF(COUNT(*), 0),
        4
    )                                                              AS cancellation_rate,
    MIN(flight_date)                                               AS period_start,
    MAX(flight_date)                                               AS period_end
FROM {{ ref('stg_bts_on_time') }}
GROUP BY origin_icao, destination_icao
