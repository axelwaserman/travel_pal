SELECT
    b.flight_date,
    a_origin.icao   AS origin_icao,
    a_dest.icao     AS destination_icao,
    c.icao          AS carrier_icao,
    c.name          AS carrier_name,
    b.carrier_iata,
    b.flight_number,
    b.tail_number,
    b.cancelled,
    b.cancellation_code,
    b.diverted,
    b.year_month
FROM nessie.flights.bts_on_time AS b
INNER JOIN {{ ref('dim_airport') }} AS a_origin
    ON a_origin.iata = b.origin_iata
INNER JOIN {{ ref('dim_airport') }} AS a_dest
    ON a_dest.iata = b.destination_iata
INNER JOIN {{ ref('dim_carrier') }} AS c
    ON c.iata = b.carrier_iata
WHERE NULLIF(b.origin_iata, '') IS NOT NULL
  AND NULLIF(b.destination_iata, '') IS NOT NULL
  AND NULLIF(b.carrier_iata, '') IS NOT NULL
